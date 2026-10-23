import re
from collections import Counter
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell

from app.core.config import settings


class WorkbookInspectionError(
    ValueError
):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ):
        super().__init__(message)

        self.message = message
        self.guardrail_name = (
            guardrail_name
        )


def normalize_name(
    value: Any,
) -> str:
    """
    Convert a sheet or column name into a
    deterministic normalized identifier.
    """

    if value is None:
        return ""

    text = str(value).strip().lower()

    normalized = re.sub(
        r"[^a-z0-9]+",
        "_",
        text,
    )

    return normalized.strip("_")


def make_unique_headers(
    headers: list[str],
) -> list[str]:
    """
    Make normalized headers unique while keeping
    their original order.

    Example:
    amount, amount, unnamed
    becomes:
    amount, amount_2, unnamed_column_3
    """

    counts: Counter[str] = Counter()
    unique_headers: list[str] = []

    for position, header in enumerate(
        headers,
        start=1,
    ):
        base_name = (
            header
            if header
            else f"unnamed_column_{position}"
        )

        counts[base_name] += 1

        if counts[base_name] == 1:
            unique_name = base_name
        else:
            unique_name = (
                f"{base_name}_"
                f"{counts[base_name]}"
            )

        unique_headers.append(unique_name)

    return unique_headers


def classify_value(
    value: Any,
) -> str:
    """
    Return a deterministic, JSON-friendly type label.
    """

    if value is None:
        return "null"

    if isinstance(value, bool):
        return "boolean"

    if isinstance(value, datetime):
        return "datetime"

    if isinstance(value, date):
        return "date"

    if isinstance(value, int):
        return "integer"

    if isinstance(
        value,
        (
            float,
            Decimal,
        ),
    ):
        return "decimal"

    if isinstance(value, str):
        return "string"

    return "other"


def choose_header_row(
    worksheet,
) -> tuple[int, list[Any]]:
    """
    Select the first non-empty row within the
    configured header scan window.

    This is deterministic and does not call an LLM.
    """

    maximum_scan_row = min(
        worksheet.max_row,
        settings.maximum_header_scan_rows,
    )

    for row_number in range(
        1,
        maximum_scan_row + 1,
    ):
        values = [
            worksheet.cell(
                row=row_number,
                column=column_number,
            ).value
            for column_number in range(
                1,
                worksheet.max_column + 1,
            )
        ]

        non_empty_values = [
            value
            for value in values
            if value is not None
            and str(value).strip() != ""
        ]

        if non_empty_values:
            return row_number, values

    raise WorkbookInspectionError(
        message=(
            f"No non-empty header row was found "
            f"in worksheet '{worksheet.title}'."
        ),
        guardrail_name=(
            "HEADER_ROW_REQUIRED"
        ),
    )


def inspect_formulas(
    worksheet,
) -> dict[str, Any]:
    """
    Count formulas and retain a bounded list
    of formula cell locations.

    Formula expressions are not exposed.
    """

    formula_count = 0
    formula_cells: list[str] = []

    for row in worksheet.iter_rows():
        for cell in row:
            if not isinstance(cell, Cell):
                continue

            if cell.data_type == "f":
                formula_count += 1

                if (
                    len(formula_cells)
                    < settings
                    .maximum_formula_samples_per_sheet
                ):
                    formula_cells.append(
                        cell.coordinate
                    )

    return {
        "formula_count": formula_count,
        "formula_cells": formula_cells,
        "formula_locations_truncated": (
            formula_count
            > len(formula_cells)
        ),
    }


def infer_column_types(
    worksheet,
    *,
    header_row_number: int,
    normalized_headers: list[str],
) -> list[dict[str, Any]]:
    """
    Sample a bounded number of rows after the header
    and infer the observed type distribution for
    each column.
    """

    first_data_row = (
        header_row_number + 1
    )

    last_sample_row = min(
        worksheet.max_row,
        header_row_number
        + settings.maximum_type_sample_rows,
    )

    column_results: list[dict[str, Any]] = []

    for column_number, column_name in enumerate(
        normalized_headers,
        start=1,
    ):
        type_counts: Counter[str] = Counter()
        non_null_count = 0
        null_count = 0

        for row_number in range(
            first_data_row,
            last_sample_row + 1,
        ):
            value = worksheet.cell(
                row=row_number,
                column=column_number,
            ).value

            value_type = classify_value(value)
            type_counts[value_type] += 1

            if value is None:
                null_count += 1
            else:
                non_null_count += 1

        non_null_type_counts = {
            key: count
            for key, count in type_counts.items()
            if key != "null"
        }

        if non_null_type_counts:
            inferred_type = max(
                non_null_type_counts,
                key=non_null_type_counts.get,
            )
        else:
            inferred_type = "unknown"

        column_results.append(
            {
                "position": column_number,
                "normalized_name": (
                    column_name
                ),
                "inferred_type": (
                    inferred_type
                ),
                "observed_type_counts": dict(
                    sorted(
                        type_counts.items()
                    )
                ),
                "sampled_non_null_count": (
                    non_null_count
                ),
                "sampled_null_count": (
                    null_count
                ),
            }
        )

    return column_results


def inspect_single_sheet(
    worksheet,
    sheet_position: int,
) -> dict[str, Any]:
    """
    Inspect one worksheet using deterministic rules.
    """

    if (
        worksheet.max_row
        > settings.max_rows_per_sheet
    ):
        raise WorkbookInspectionError(
            message=(
                f"Worksheet '{worksheet.title}' "
                f"contains {worksheet.max_row} rows, "
           f"exceeding the configured limit of "
                f"{settings.max_rows_per_sheet}."
            ),
            guardrail_name=(
                "MAXIMUM_ROWS_PER_SHEET"
            ),
        )

    if (
        worksheet.max_column
        > settings.max_columns_per_sheet
    ):
        raise WorkbookInspectionError(
            message=(
                f"Worksheet '{worksheet.title}' "
                f"contains "
                f"{worksheet.max_column} columns, "
                f"exceeding the configured limit of "
                f"{settings.max_columns_per_sheet}."
            ),
            guardrail_name=(
                "MAXIMUM_COLUMNS_PER_SHEET"
            ),
        )

    header_row_number, raw_headers = (
        choose_header_row(worksheet)
    )

    normalized_headers = [
        normalize_name(value)
        for value in raw_headers
    ]

    normalized_headers = (
        make_unique_headers(
            normalized_headers
        )
    )

    merged_ranges = [
        str(cell_range)
        for cell_range
        in list(
            worksheet.merged_cells.ranges
        )[
            :settings
            .maximum_merged_ranges_per_sheet
        ]
    ]

    merged_range_count = len(
        worksheet.merged_cells.ranges
    )

    formula_information = (
        inspect_formulas(worksheet)
    )

    column_profiles = infer_column_types(
        worksheet,
        header_row_number=(
            header_row_number
        ),
        normalized_headers=(
            normalized_headers
        ),
    )

    return {
        "position": sheet_position,
        "name": worksheet.title,
        "normalized_name": normalize_name(
            worksheet.title
        ),
        "visibility": worksheet.sheet_state,
        "is_hidden": (
            worksheet.sheet_state != "visible"
        ),
        "max_row": worksheet.max_row,
        "max_column": worksheet.max_column,
        "header_row": header_row_number,
        "raw_headers": [
            (
                None
                if value is None
                else str(value)
            )
            for value in raw_headers
        ],
        "normalized_headers": (
            normalized_headers
        ),
        "column_profiles": (
            column_profiles
        ),
        "merged_range_count": (
            merged_range_count
        ),
        "merged_ranges": merged_ranges,
        "merged_ranges_truncated": (
            merged_range_count
            > len(merged_ranges)
        ),
        **formula_information,
    }


def inspect_workbook_file(
    stored_path: str,
) -> dict[str, Any]:
    """
    Inspect an XLSX workbook structurally.

    No approved parser is executed.
    No LLM is called.
    No workbook formula is evaluated.
    """

    file_path = Path(stored_path)

    if not file_path.exists():
        raise WorkbookInspectionError(
            message=(
                "The stored workbook could "
                "not be found."
            ),
            guardrail_name=(
                "STORED_FILE_REQUIRED"
            ),
        )

    if not file_path.is_file():
        raise WorkbookInspectionError(
            message=(
                "The stored workbook path "
                "is not a regular file."
            ),
            guardrail_name=(
                "REGULAR_FILE_REQUIRED"
            ),
        )

    try:
        workbook = load_workbook(
            filename=file_path,
            read_only=False,
            data_only=False,
            keep_links=False,
        )

    except Exception as exception:
        raise WorkbookInspectionError(
            message=(
                "The workbook could not be opened "
                "for safe structural inspection."
            ),
            guardrail_name=(
                "WORKBOOK_OPEN_VALIDATION"
            ),
        ) from exception

    try:
        sheet_count = len(
            workbook.worksheets
        )

        if sheet_count == 0:
            raise WorkbookInspectionError(
                message=(
                    "The workbook does not "
                    "contain any worksheets."
                ),
                guardrail_name=(
                    "WORKSHEET_REQUIRED"
                ),
            )

        if sheet_count > settings.max_sheets:
            raise WorkbookInspectionError(
                message=(
                    f"The workbook contains "
                    f"{sheet_count} worksheets, "
                    f"exceeding the configured "
                    f"limit of "
                    f"{settings.max_sheets}."
                ),
                guardrail_name=(
                    "MAXIMUM_WORKSHEET_COUNT"
                ),
            )

        sheets = [
            inspect_single_sheet(
                worksheet=worksheet,
                sheet_position=position,
            )
            for position, worksheet
            in enumerate(
                workbook.worksheets,
                start=1,
            )
        ]

        hidden_sheet_count = sum(
            1
            for sheet in sheets
            if sheet["is_hidden"]
        )

        total_formula_count = sum(
            sheet["formula_count"]
            for sheet in sheets
        )

        total_merged_range_count = sum(
            sheet["merged_range_count"]
            for sheet in sheets
        )

        return {
            "inspection_version": "1.0",
            "sheet_count": sheet_count,
            "hidden_sheet_count": (
                hidden_sheet_count
            ),
            "total_formula_count": (
                total_formula_count
            ),
            "total_merged_range_count": (
                total_merged_range_count
            ),
            "sheets": sheets,
            "guardrails": [
                {
                    "name": (
                        "STORED_FILE_REQUIRED"
                    ),
                    "status": "PASSED",
                },
                {
                    "name": (
                        "WORKBOOK_OPEN_VALIDATION"
                    ),
                    "status": "PASSED",
                },
                {
                    "name": (
                        "MAXIMUM_WORKSHEET_COUNT"
                    ),
                    "status": "PASSED",
                },
                {
                    "name": (
                        "MAXIMUM_ROWS_PER_SHEET"
                    ),
                    "status": "PASSED",
                },
                {
                    "name": (
                        "MAXIMUM_COLUMNS_PER_SHEET"
                    ),
                    "status": "PASSED",
                },
                {
                    "name": (
                        "HEADER_ROW_REQUIRED"
                    ),
                    "status": "PASSED",
                },
            ],
        }

    finally:
        workbook.close()

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.parser_runtime import (
    ParserExecutionError,
    execute_declarative_parser,
)


def create_test_workbook(
    path: Path,
) -> None:
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Trade Data"

    sheet.append([
        "Trade ID",
        "Trade Date",
        "Currency",
        "Amount",
        "Status",
    ])

    sheet.append([
        " TRD-1001 ",
        "2026-10-19",
        "usd",
        "125,000.50",
        "booked",
    ])

    sheet.append([
        "TRD-1002",
        "20/10/2026",
        "eur",
        98000,
        "pending",
    ])

    workbook.save(path)


def parser_spec() -> dict:
    return {
        "source_sheet": "Trade Data",
        "header_row": 1,
        "mappings": [
            {
                "source": "trade_id",
                "target": "trade_id",
                "transform": "trim",
                "required": True,
            },
            {
                "source": "trade_date",
                "target": "trade_date",
                "transform": "parse_date",
                "required": True,
            },
            {
                "source": "currency",
                "target": "currency",
                "transform": "upper",
                "required": True,
            },
            {
                "source": "amount",
                "target": "amount",
                "transform": "parse_decimal",
                "required": True,
            },
            {
                "source": "status",
                "target": "status",
                "transform": "upper",
                "required": True,
            },
        ],
    }


def test_approved_parser_executes(
    tmp_path,
):
    workbook_path = (
        tmp_path / "approved.xlsx"
    )

    create_test_workbook(
        workbook_path
    )

    result = execute_declarative_parser(
        stored_path=str(workbook_path),
        parser_spec=parser_spec(),
        parser_execution_authorized=True,
        parser_match_found=True,
        matched_parser_approval_status=(
            "APPROVED"
        ),
        matched_parser_status="ACTIVE",
    )

    assert result[
        "parsed_row_count"
    ] == 2

    assert result[
        "rejected_row_count"
    ] == 0

    assert result[
        "parsed_records"
    ][0] == {
        "trade_id": "TRD-1001",
        "trade_date": "2026-10-19",
        "currency": "USD",
        "amount": "125000.50",
        "status": "BOOKED",
    }

    assert result[
        "parsed_records"
    ][1]["trade_date"] == (
        "2026-10-20"
    )


def test_unauthorized_parser_is_blocked(
    tmp_path,
):
    workbook_path = (
        tmp_path / "blocked.xlsx"
    )

    create_test_workbook(
        workbook_path
    )

    with pytest.raises(
        ParserExecutionError
    ) as exception:
        execute_declarative_parser(
            stored_path=str(
                workbook_path
            ),
            parser_spec=parser_spec(),
            parser_execution_authorized=False,
            parser_match_found=True,
            matched_parser_approval_status=(
                "APPROVED"
            ),
            matched_parser_status="ACTIVE",
        )

    assert (
        exception.value.guardrail_name
        == (
            "PARSER_EXECUTION_"
            "AUTHORIZATION_REQUIRED"
        )
    )


def test_unapproved_parser_is_blocked(
    tmp_path,
):
    workbook_path = (
        tmp_path / "unapproved.xlsx"
    )

    create_test_workbook(
        workbook_path
    )

    with pytest.raises(
        ParserExecutionError
    ) as exception:
        execute_declarative_parser(
            stored_path=str(
                workbook_path
            ),
            parser_spec=parser_spec(),
            parser_execution_authorized=True,
            parser_match_found=True,
            matched_parser_approval_status=(
                "PENDING"
            ),
            matched_parser_status="ACTIVE",
        )

    assert (
        exception.value.guardrail_name
        == "APPROVED_PARSER_REQUIRED"
    )


def test_missing_source_column_is_blocked(
    tmp_path,
):
    workbook_path = (
        tmp_path / "missing.xlsx"
    )

    create_test_workbook(
        workbook_path
    )

    invalid_spec = parser_spec()

    invalid_spec["mappings"].append(
        {
            "source": "counterparty",
            "target": "counterparty",
            "transform": "identity",
            "required": True,
        }
    )

    with pytest.raises(
        ParserExecutionError
    ) as exception:
        execute_declarative_parser(
            stored_path=str(
                workbook_path
            ),
            parser_spec=invalid_spec,
            parser_execution_authorized=True,
            parser_match_found=True,
            matched_parser_approval_status=(
                "APPROVED"
            ),
            matched_parser_status="ACTIVE",
        )

    assert (
        exception.value.guardrail_name
        == "SOURCE_COLUMNS_EXIST"
    )


def test_required_empty_value_is_blocked(
    tmp_path,
):
    workbook_path = (
        tmp_path / "empty-required.xlsx"
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Trade Data"

    sheet.append([
        "Trade ID",
        "Amount",
    ])

    sheet.append([
        None,
        100,
    ])

    workbook.save(workbook_path)

    specification = {
        "source_sheet": "Trade Data",
        "header_row": 1,
        "mappings": [
            {
                "source": "trade_id",
                "target": "trade_id",
                "transform": "identity",
                "required": True,
            },
            {
                "source": "amount",
                "target": "amount",
                "transform": "parse_decimal",
                "required": True,
            },
        ],
    }

    with pytest.raises(
        ParserExecutionError
    ) as exception:
        execute_declarative_parser(
            stored_path=str(
                workbook_path
            ),
            parser_spec=specification,
            parser_execution_authorized=True,
            parser_match_found=True,
            matched_parser_approval_status=(
                "APPROVED"
            ),
            matched_parser_status="ACTIVE",
        )

    assert (
        exception.value.guardrail_name
        == "REQUIRED_VALUE_PRESENT"
    )

    assert exception.value.row_number == 2

    assert (
        exception.value.column_name
        == "trade_id"
    )

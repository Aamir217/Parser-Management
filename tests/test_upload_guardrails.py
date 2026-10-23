from io import BytesIO

import pytest
from openpyxl import Workbook

from app.services.upload_guardrails import (
    UploadGuardrailError,
    sanitize_filename,
    validate_upload,
)


def create_valid_xlsx() -> bytes:
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Trades"

    sheet.append([
        "trade_id",
        "currency",
        "amount",
    ])

    sheet.append([
        "TRD-1001",
        "USD",
        1000,
    ])

    output = BytesIO()
    workbook.save(output)

    return output.getvalue()


def test_sanitize_filename():
    result = sanitize_filename(
        "../../Trade File 1.xlsx"
    )

    assert result == "Trade_File_1.xlsx"


def test_valid_xlsx_passes():
    content = create_valid_xlsx()

    result = validate_upload(
        filename="trades.xlsx",
        content=content,
    )

    assert result["sanitized_filename"] == (
        "trades.xlsx"
    )

    assert result["extension"] == ".xlsx"
    assert result["size_bytes"] > 0

    assert len(
        result["checksum_sha256"]
    ) == 64

    guardrail_names = {
        guardrail["name"]
        for guardrail
        in result["guardrails"]
    }

    assert "SAFE_FILENAME" in guardrail_names
    assert "ALLOWED_EXTENSION" in guardrail_names

    assert (
        "XLSX_ZIP_STRUCTURE"
        in guardrail_names
    )

    assert "SHA256_CHECKSUM" in guardrail_names


def test_csv_extension_is_rejected():
    with pytest.raises(
        UploadGuardrailError
    ) as exception:
        validate_upload(
            filename="trades.csv",
            content=b"column1,column2",
        )

    assert (
        exception.value.guardrail_name
        == "ALLOWED_EXTENSION"
    )


def test_fake_xlsx_is_rejected():
    with pytest.raises(
        UploadGuardrailError
    ) as exception:
        validate_upload(
            filename="fake.xlsx",
            content=(
                b"This is not an Excel workbook"
            ),
        )

    assert (
        exception.value.guardrail_name
        == "XLSX_ZIP_STRUCTURE"
    )


def test_empty_file_is_rejected():
    with pytest.raises(
        UploadGuardrailError
    ) as exception:
        validate_upload(
            filename="empty.xlsx",
            content=b"",
        )

    assert (
        exception.value.guardrail_name
        == "NON_EMPTY_FILE"
    )


def test_filename_path_is_removed():
    result = sanitize_filename(
        "../../../../folder/trades.xlsx"
    )

    assert result == "trades.xlsx"

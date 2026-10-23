from copy import deepcopy

from app.services.output_validator import (
    validate_parsed_records,
)


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
        ],
    }


def valid_records() -> list[dict]:
    return [
        {
            "trade_id": "TRD-1001",
            "trade_date": "2026-10-19",
            "currency": "USD",
            "amount": "125000.50",
        },
        {
            "trade_id": "TRD-1002",
            "trade_date": "2026-10-20",
            "currency": "EUR",
            "amount": "98000",
        },
    ]


def validate(
    records: list[dict],
):
    return validate_parsed_records(
        parsed_records=records,
        parser_spec=parser_spec(),
        source_row_count=len(records),
        parsed_row_count=len(records),
        rejected_row_count=0,
        output_truncated=False,
    )


def test_valid_output_passes():
    result = validate(
        valid_records()
    )

    assert (
        result["validation_status"]
        == "PASS"
    )

    assert result[
        "duplicate_record_count"
    ] == 0

    assert result[
        "missing_required_value_count"
    ] == 0

    assert result[
        "invalid_value_count"
    ] == 0


def test_duplicate_output_warns():
    records = valid_records()

    records.append(
        deepcopy(records[0])
    )

    result = validate(records)

    assert (
        result["validation_status"]
        == "WARN"
    )

    assert result[
        "duplicate_record_count"
    ] == 1


def test_empty_required_value_fails():
    records = valid_records()

    records[0]["trade_id"] = None

    result = validate(records)

    assert (
        result["validation_status"]
        == "FAIL"
    )

    assert result[
        "missing_required_value_count"
    ] == 1


def test_invalid_date_fails():
    records = valid_records()

    records[0][
        "trade_date"
    ] = "19-10-2026"

    result = validate(records)

    assert (
        result["validation_status"]
        == "FAIL"
    )

    assert result[
        "invalid_value_count"
    ] == 1


def test_invalid_decimal_fails():
    records = valid_records()

    records[0]["amount"] = "invalid"

    result = validate(records)

    assert (
        result["validation_status"]
        == "FAIL"
    )


def test_bad_currency_warns():
    records = valid_records()

    records[0]["currency"] = "US"

    result = validate(records)

    assert (
        result["validation_status"]
        == "WARN"
    )


def test_truncated_output_warns():
    records = valid_records()

    result = validate_parsed_records(
        parsed_records=records,
        parser_spec=parser_spec(),
        source_row_count=5000,
        parsed_row_count=2,
        rejected_row_count=0,
        output_truncated=True,
    )

    assert (
        result["validation_status"]
        == "WARN"
    )

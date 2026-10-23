from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app


def create_workbook(
    row_count: int = 2,
) -> bytes:
    workbook = Workbook()

    sheet = workbook.active
    sheet.title = "Trades"

    sheet.append([
        "trade_id",
        "currency",
        "amount",
    ])

    for index in range(
        1,
        row_count + 1,
    ):
        sheet.append([
            f"TRD-{index:04d}",
            "USD",
            float(index * 100),
        ])

    output = BytesIO()
    workbook.save(output)

    return output.getvalue()


def test_valid_unknown_format_upload():
    with TestClient(app) as client:
        response = client.post(
            "/v1/uploads",
            files={
                "uploaded_file": (
                    "unknown_format.xlsx",
                    create_workbook(),
                    (
                        "application/vnd."
                        "openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )

    assert response.status_code == 201

    body = response.json()

    # Part 8 continues from proposal generation
    # into the human-review interrupt.
    assert body["status"] == (
        "WAITING_FOR_HUMAN_REVIEW"
    )

    assert body["current_node"] == (
        "human_review"
    )

    assert body["progress_percent"] == 65

    # The registry must still report that no
    # approved parser was found.
    assert body[
        "parser_match_found"
    ] is False

    assert body[
        "parser_execution_authorized"
    ] is False

    assert body[
        "matched_parser_id"
    ] is None

    assert body[
        "matched_parser_version_id"
    ] is None

    # A proposal must exist and remain pending.
    assert body["proposal_id"]

    assert body["proposal_status"] == (
        "PENDING_REVIEW"
    )

    assert body["proposal_source"] in {
        "VERTEX_AI",
        "DETERMINISTIC_FALLBACK",
        "DETERMINISTIC",
    }

    assert body["parser_proposal"]

    assert len(
        body["proposal_hash"]
    ) == 64

    proposal = body[
        "parser_proposal"
    ]

    assert proposal[
        "execution_allowed"
    ] is False

    assert proposal[
        "approval_required"
    ] is True

    assert proposal[
        "proposal_source"
    ] in {
        "VERTEX_AI",
        "DETERMINISTIC_FALLBACK",
        "DETERMINISTIC",
    }

    assert (
        proposal["proposal_source"]
        == body["proposal_source"]
    )

    assert isinstance(
        proposal["parser_spec"],
        dict,
    )

    assert isinstance(
        proposal[
            "parser_spec"
        ]["mappings"],
        list,
    )

    assert len(
        proposal[
            "parser_spec"
        ]["mappings"]
    ) > 0

    validation = body[
        "proposal_validation"
    ]

    assert validation["status"] == (
        "PASSED"
    )

    assert validation[
        "structured_output"
    ] is True

    assert validation[
        "declarative_only"
    ] is True

    assert validation[
        "executable_code_present"
    ] is False

    assert validation[
        "human_approval_required"
    ] is True

    assert validation[
        "execution_allowed"
    ] is False

    # No parser may run before approval.
    assert body["parsed_records"] is None
    assert body["parsed_row_count"] is None

    executions = body[
        "node_executions"
    ]

    # Part 8 unknown-format path:
    # six completed nodes plus one WAITING node.
    assert len(executions) == 7

    expected_nodes = [
        "validate_upload",
        "store_original",
        "inspect_workbook",
        "create_fingerprint",
        "match_parser_registry",
        "generate_parser_proposal",
        "human_review",
    ]

    actual_nodes = [
        execution["node_name"]
        for execution in executions
    ]

    assert actual_nodes == expected_nodes

    human_review_execution = (
        executions[-1]
    )

    assert human_review_execution[
        "node_name"
    ] == "human_review"

    assert human_review_execution[
        "status"
    ] == "WAITING"

    assert human_review_execution[
        "guardrail_name"
    ] == "HUMAN_APPROVAL_REQUIRED"

    review_output = (
        human_review_execution[
            "output_state"
        ]
    )

    assert review_output[
        "proposal_status"
    ] == "PENDING_REVIEW"

    assert review_output[
        "parser_execution_authorized"
    ] is False

    assert review_output[
        "allowed_decisions"
    ] == [
        "APPROVE",
        "REJECT",
    ]

    assert (
        review_output["proposal_hash"]
        == body["proposal_hash"]
    )

def test_same_schema_has_same_fingerprint():
    with TestClient(app) as client:
        first_response = client.post(
            "/v1/uploads",
            files={
                "uploaded_file": (
                    "first.xlsx",
                    create_workbook(2),
                    (
                        "application/vnd."
                        "openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )

        second_response = client.post(
            "/v1/uploads",
            files={
                "uploaded_file": (
                    "second.xlsx",
                    create_workbook(10),
                    (
                        "application/vnd."
                        "openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    first_body = first_response.json()
    second_body = second_response.json()

    assert (
        first_body["schema_fingerprint"]
        == second_body["schema_fingerprint"]
    )


def test_fake_excel_upload_is_blocked():
    with TestClient(app) as client:
        response = client.post(
            "/v1/uploads",
            files={
                "uploaded_file": (
                    "fake.xlsx",
                    b"Not a real workbook",
                    (
                        "application/vnd."
                        "openxmlformats-officedocument."
                        "spreadsheetml.sheet"
                    ),
                )
            },
        )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert detail["status"] == "BLOCKED"

    assert (
        detail["guardrail_name"]
        == "XLSX_ZIP_STRUCTURE"
    )


def test_csv_upload_is_blocked():
    with TestClient(app) as client:
        response = client.post(
            "/v1/uploads",
            files={
                "uploaded_file": (
                    "trades.csv",
                    b"trade_id,currency,amount",
                    "text/csv",
                )
            },
        )

    assert response.status_code == 400

    detail = response.json()["detail"]

    assert (
        detail["guardrail_name"]
        == "ALLOWED_EXTENSION"
    )


def test_unknown_run_returns_404():
    with TestClient(app) as client:
        response = client.get(
            "/v1/runs/"
            "00000000-0000-0000-0000-000000000000"
        )

    assert response.status_code == 404

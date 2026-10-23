import json
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.llm_parser_proposal import (
    LlmParserProposalResponse,
)
from app.services.parser_registry import (
    ParserRegistryError,
    validate_parser_specification,
)


class VertexProposalError(RuntimeError):
    def __init__(
        self,
        message: str,
        guardrail_name: str,
    ) -> None:
        super().__init__(message)

        self.message = message
        self.guardrail_name = guardrail_name


def build_llm_schema_context(
    *,
    workbook_metadata: dict[str, Any],
    canonical_schema: dict[str, Any],
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    """
    Construct the only context sent to Vertex AI.

    Business rows, cell values, server paths,
    credentials, file bytes and access tokens are
    deliberately excluded.
    """

    safe_sheets: list[
        dict[str, Any]
    ] = []

    for sheet in workbook_metadata.get(
        "sheets",
        [],
    ):
        safe_profiles = []

        for profile in sheet.get(
            "column_profiles",
            [],
        ):
            safe_profiles.append(
                {
                    "position": (
                        profile.get(
                            "position"
                        )
                    ),
                    "normalized_name": (
                        profile.get(
                            "normalized_name"
                        )
                    ),
                    "inferred_type": (
                        profile.get(
                            "inferred_type"
                        )
                    ),
                    "sampled_non_null_count": (
                        profile.get(
                            "sampled_non_null_count"
                        )
                    ),
                    "sampled_null_count": (
                        profile.get(
                            "sampled_null_count"
                        )
                    ),
                }
            )

        safe_sheets.append(
            {
                "position": sheet.get(
                    "position"
                ),
                "name": sheet.get("name"),
                "normalized_name": (
                    sheet.get(
                        "normalized_name"
                    )
                ),
                "visibility": sheet.get(
                    "visibility"
                ),
                "is_hidden": sheet.get(
                    "is_hidden",
                    False,
                ),
                "header_row": sheet.get(
                    "header_row"
                ),
                "normalized_headers": (
                    sheet.get(
                        "normalized_headers",
                        [],
                    )
                ),
                "column_profiles": (
                    safe_profiles
                ),
                "formula_count": sheet.get(
                    "formula_count",
                    0,
                ),
                "merged_range_count": (
                    sheet.get(
                        "merged_range_count",
                        0,
                    )
                ),
            }
        )

    return {
        "schema_fingerprint": (
            schema_fingerprint
        ),
        "fingerprint_version": (
            fingerprint_version
        ),
        "canonical_schema": (
            canonical_schema
        ),
        "workbook_structure": {
            "sheet_count": (
                workbook_metadata.get(
                    "sheet_count",
                    0,
                )
            ),
            "hidden_sheet_count": (
                workbook_metadata.get(
                    "hidden_sheet_count",
                    0,
                )
            ),
            "sheets": safe_sheets,
        },
        "allowed_transformations": [
            "identity",
            "trim",
            "upper",
            "lower",
            "parse_date",
            "parse_decimal",
        ],
    }


def build_proposal_prompt(
    schema_context: dict[str, Any],
) -> str:
    """
    The response schema is configured separately.
    The prompt therefore describes the task and
    constraints without including sample output JSON.
    """

    context_json = json.dumps(
        schema_context,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":"),
    )

    return (
        "You are a parser proposal analyst. "
        "Analyze only the supplied workbook schema. "
        "Do not request, infer, reproduce, or expose "
        "business row values. "
        "Create a declarative parser proposal for "
        "human review. "
        "Use only source columns explicitly present "
        "in normalized_headers. "
        "Use each source column at most once. "
        "Use each target field at most once. "
        "Use only the supplied transformation "
        "allowlist. "
        "Do not generate Python, SQL, shell code, "
        "regular expressions, network calls, "
        "function calls, imports, or executable text. "
        "Select one visible business-data sheet. "
        "Keep target names lowercase snake_case. "
        "Mark a field required only when the schema "
        "provides a strong structural reason. "
        "If uncertain, mark the field optional and "
        "document the uncertainty as an assumption. "
        "Confidence describes schema interpretation "
        "only and never authorizes execution. "
        "The result is proposal-only and must remain "
        "subject to human approval.\n\n"
        "Workbook schema context:\n"
        f"{context_json}"
    )


def validate_llm_proposal_against_schema(
    *,
    response: LlmParserProposalResponse,
    workbook_metadata: dict[str, Any],
) -> None:
    """
    Ensure the model did not invent sheets or columns.
    """

    sheet_lookup = {
        sheet.get("name"): sheet
        for sheet in workbook_metadata.get(
            "sheets",
            [],
        )
        if isinstance(sheet, dict)
    }

    source_sheet = response.source_sheet

    if source_sheet not in sheet_lookup:
        raise VertexProposalError(
            message=(
                "Vertex AI proposed a source sheet "
                "that does not exist."
            ),
            guardrail_name=(
                "LLM_SOURCE_SHEET_EXISTS"
            ),
        )

    selected_sheet = sheet_lookup[
        source_sheet
    ]

    if selected_sheet.get(
        "is_hidden",
        False,
    ):
        raise VertexProposalError(
            message=(
                "Vertex AI selected a hidden "
                "source sheet."
            ),
            guardrail_name=(
                "VISIBLE_SOURCE_SHEET_REQUIRED"
            ),
        )

    expected_header_row = (
        selected_sheet.get(
            "header_row"
        )
    )

    if (
        response.header_row
        != expected_header_row
    ):
        raise VertexProposalError(
            message=(
                "Vertex AI proposed a header row "
                "different from deterministic "
                "inspection."
            ),
            guardrail_name=(
                "DETERMINISTIC_HEADER_ROW_REQUIRED"
            ),
        )

    available_columns = set(
        selected_sheet.get(
            "normalized_headers",
            [],
        )
    )

    proposed_sources = [
        mapping.source
        for mapping in response.mappings
    ]

    invented_columns = sorted(
        set(proposed_sources)
        - available_columns
    )

    if invented_columns:
        raise VertexProposalError(
            message=(
                "Vertex AI proposed unknown "
                f"source columns: {invented_columns}"
            ),
            guardrail_name=(
                "LLM_SOURCE_COLUMNS_EXIST"
            ),
        )

    if (
        len(proposed_sources)
        != len(set(proposed_sources))
    ):
        raise VertexProposalError(
            message=(
                "Vertex AI proposed duplicate "
                "source columns."
            ),
            guardrail_name=(
                "UNIQUE_SOURCE_COLUMNS_REQUIRED"
            ),
        )

    proposed_targets = [
        mapping.target
        for mapping in response.mappings
    ]

    if (
        len(proposed_targets)
        != len(set(proposed_targets))
    ):
        raise VertexProposalError(
            message=(
                "Vertex AI proposed duplicate "
                "target fields."
            ),
            guardrail_name=(
                "UNIQUE_TARGET_FIELDS_REQUIRED"
            ),
        )


def convert_llm_response_to_proposal(
    *,
    response: LlmParserProposalResponse,
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    parser_spec = {
        "source_sheet": (
            response.source_sheet
        ),
        "header_row": (
            response.header_row
        ),
        "mappings": [
            {
                "source": mapping.source,
                "target": mapping.target,
                "transform": (
                    mapping.transform
                ),
                "required": (
                    mapping.required
                ),
            }
            for mapping in response.mappings
        ],
        "assumptions": (
            response.assumptions
        ),
        "description": (
            response.proposal_notes
        ),
    }

    try:
        validate_parser_specification(
            parser_spec
        )

    except ParserRegistryError as exception:
        raise VertexProposalError(
            message=exception.message,
            guardrail_name=(
                exception.guardrail_name
            ),
        ) from exception

    return {
        "proposal_version": "1.0",
        "proposal_source": (
            "VERTEX_AI"
        ),
        "schema_fingerprint": (
            schema_fingerprint
        ),
        "fingerprint_version": (
            fingerprint_version
        ),
        "parser_name_suggestion": (
            response.parser_name_suggestion
        ),
        "parser_spec": parser_spec,
        "mapping_rationales": [
            {
                "source": mapping.source,
                "target": mapping.target,
                "rationale": (
                    mapping.rationale
                ),
            }
            for mapping in response.mappings
        ],
        "review_requirements": (
            response.review_requirements
        ),
        "confidence": (
            response.confidence
        ),
        "risk_level": (
            response.risk_level
        ),
        "proposal_notes": (
            response.proposal_notes
        ),
        "execution_allowed": False,
        "approval_required": True,
    }


def parse_structured_response(
    response: Any,
) -> LlmParserProposalResponse:
    """
    Parse and validate Vertex AI structured output.

    Depending on the installed google-genai version,
    response.parsed may contain:
    - LlmParserProposalResponse
    - a dictionary
    - another Pydantic-compatible object
    - None while response.text contains JSON
    """

    parsed_response = getattr(
        response,
        "parsed",
        None,
    )

    if isinstance(
        parsed_response,
        LlmParserProposalResponse,
    ):
        return parsed_response

    if isinstance(
        parsed_response,
        dict,
    ):
        try:
            return (
                LlmParserProposalResponse
                .model_validate(
                    parsed_response
                )
            )

        except ValidationError as exception:
            raise VertexProposalError(
                message=(
                    "Vertex AI structured output "
                    "failed Pydantic validation."
                ),
                guardrail_name=(
                    "VALID_LLM_PROPOSAL_REQUIRED"
                ),
            ) from exception

    if parsed_response is not None:
        if hasattr(
            parsed_response,
            "model_dump",
        ):
            try:
                parsed_dictionary = (
                    parsed_response.model_dump()
                )

                return (
                    LlmParserProposalResponse
                    .model_validate(
                        parsed_dictionary
                    )
                )

            except (
                ValidationError,
                TypeError,
                ValueError,
            ) as exception:
                raise VertexProposalError(
                    message=(
                        "Vertex AI parsed response "
                        "could not be validated."
                    ),
                    guardrail_name=(
                        "VALID_LLM_PROPOSAL_REQUIRED"
                    ),
                ) from exception

    response_text = getattr(
        response,
        "text",
        None,
    )

    if (
        isinstance(response_text, str)
        and response_text.strip()
    ):
        try:
            response_dictionary = json.loads(
                response_text
            )

        except json.JSONDecodeError as exception:
            raise VertexProposalError(
                message=(
                    "Vertex AI response text "
                    "was not valid JSON."
                ),
                guardrail_name=(
                    "STRUCTURED_LLM_OUTPUT_REQUIRED"
                ),
            ) from exception

        if not isinstance(
            response_dictionary,
            dict,
        ):
            raise VertexProposalError(
                message=(
                    "Vertex AI JSON response must "
                    "be an object."
                ),
                guardrail_name=(
                    "STRUCTURED_LLM_OUTPUT_REQUIRED"
                ),
            )

        try:
            return (
                LlmParserProposalResponse
                .model_validate(
                    response_dictionary
                )
            )

        except ValidationError as exception:
            raise VertexProposalError(
                message=(
                    "Vertex AI JSON response "
                    "failed Pydantic validation."
                ),
                guardrail_name=(
                    "VALID_LLM_PROPOSAL_REQUIRED"
                ),
            ) from exception

    raise VertexProposalError(
        message=(
            "Vertex AI returned no usable "
            "structured parser proposal."
        ),
        guardrail_name=(
            "STRUCTURED_LLM_OUTPUT_REQUIRED"
        ),
    )


def build_vertex_response_schema() -> dict[str, Any]:
    """
    Build a minimal response schema compatible with
    Vertex AI structured output.

    Strict length, range, uniqueness, and workbook
    schema validations are performed locally after
    the model responds.
    """

    mapping_schema = {
        "type": "OBJECT",
        "properties": {
            "source": {
                "type": "STRING",
                "description": (
                    "Normalized source column name "
                    "from the selected worksheet."
                ),
            },
            "target": {
                "type": "STRING",
                "description": (
                    "Proposed lowercase snake_case "
                    "target field name."
                ),
            },
            "transform": {
                "type": "STRING",
                "enum": [
                    "identity",
                    "trim",
                    "upper",
                    "lower",
                    "parse_date",
                    "parse_decimal",
                ],
                "description": (
                    "One deterministic allowlisted "
                    "transformation."
                ),
            },
            "required": {
                "type": "BOOLEAN",
                "description": (
                    "Whether an empty source value "
                    "must block parser execution."
                ),
            },
            "rationale": {
                "type": "STRING",
                "description": (
                    "Short reason for the mapping."
                ),
            },
        },
        "required": [
            "source",
            "target",
            "transform",
            "required",
            "rationale",
        ],
    }

    return {
        "type": "OBJECT",
        "properties": {
            "parser_name_suggestion": {
                "type": "STRING",
                "description": (
                    "Suggested human-readable "
                    "parser name."
                ),
            },
            "source_sheet": {
                "type": "STRING",
                "description": (
                    "Existing visible source "
                    "worksheet name."
                ),
            },
            "header_row": {
                "type": "INTEGER",
                "description": (
                    "Deterministically detected "
                    "header row."
                ),
            },
            "mappings": {
                "type": "ARRAY",
                "items": mapping_schema,
            },
            "assumptions": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING",
                },
            },
            "review_requirements": {
                "type": "ARRAY",
                "items": {
                    "type": "STRING",
                },
            },
            "confidence": {
                "type": "NUMBER",
                "description": (
                    "Confidence in schema "
                    "interpretation."
                ),
            },
            "risk_level": {
                "type": "STRING",
                "enum": [
                    "LOW",
                    "MEDIUM",
                    "HIGH",
                ],
            },
            "proposal_notes": {
                "type": "STRING",
                "description": (
                    "Summary for the human reviewer."
                ),
            },
        },
        "required": [
            "parser_name_suggestion",
            "source_sheet",
            "header_row",
            "mappings",
            "assumptions",
            "review_requirements",
            "confidence",
            "risk_level",
            "proposal_notes",
        ],
    }


def generate_vertex_parser_proposal(
    *,
    workbook_metadata: dict[str, Any],
    canonical_schema: dict[str, Any],
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    """
    Generate a schema-only parser proposal using
    Gemini on Vertex AI structured output.
    """

    if not settings.google_cloud_project:
        raise VertexProposalError(
            message=(
                "GOOGLE_CLOUD_PROJECT "
                "is not configured."
            ),
            guardrail_name=(
                "VERTEX_PROJECT_REQUIRED"
            ),
        )

    if not settings.google_cloud_location:
        raise VertexProposalError(
            message=(
                "GOOGLE_CLOUD_LOCATION "
                "is not configured."
            ),
            guardrail_name=(
                "VERTEX_LOCATION_REQUIRED"
            ),
        )

    schema_context = (
        build_llm_schema_context(
            workbook_metadata=(
                workbook_metadata
            ),
            canonical_schema=(
                canonical_schema
            ),
            schema_fingerprint=(
                schema_fingerprint
            ),
            fingerprint_version=(
                fingerprint_version
            ),
        )
    )

    prompt = build_proposal_prompt(
        schema_context
    )

    try:
        client = genai.Client(
            vertexai=True,
            project=(
                settings.google_cloud_project
            ),
            location=(
                settings.google_cloud_location
            ),
        )

        response = (
            client.models.generate_content(
                model=(
                    settings.vertex_model_name
                ),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=(
                        settings
                        .vertex_proposal_temperature
                    ),
                    max_output_tokens=(
                        settings
                        .vertex_proposal_max_output_tokens
                    ),
                    thinking_config=(
                        types.ThinkingConfig(
                            thinking_budget=(
                                settings
                                .vertex_proposal_thinking_budget
                            ),
                        )
                    ),
                    response_mime_type=(
                        "application/json"
                    ),
                    response_schema=(
                        build_vertex_response_schema()
                    ),
                ),
            )
        )

    except Exception as exception:
        raise VertexProposalError(
            message=(
                "Vertex AI proposal request failed: "
                f"{exception}"
            ),
            guardrail_name=(
                "VERTEX_PROPOSAL_REQUEST_FAILED"
            ),
        ) from exception

    parsed_response = response.parsed

    if parsed_response is None:
        raise VertexProposalError(
            message=(
                "Vertex AI returned no structured "
                "proposal."
            ),
            guardrail_name=(
                "STRUCTURED_LLM_OUTPUT_REQUIRED"
            ),
        )

    if isinstance(
        parsed_response,
        LlmParserProposalResponse,
    ):
        validated_response = (
            parsed_response
        )

    elif isinstance(
        parsed_response,
        dict,
    ):
        try:
            validated_response = (
                LlmParserProposalResponse
                .model_validate(
                    parsed_response
                )
            )

        except Exception as exception:
            raise VertexProposalError(
                message=(
                    "Vertex AI structured output "
                    "failed Pydantic validation."
                ),
                guardrail_name=(
                    "VALID_LLM_PROPOSAL_REQUIRED"
                ),
            ) from exception

    else:
        raise VertexProposalError(
            message=(
                "Vertex AI returned an unsupported "
                "structured response type."
            ),
            guardrail_name=(
                "VALID_LLM_PROPOSAL_REQUIRED"
            ),
        )

    validate_llm_proposal_against_schema(
        response=validated_response,
        workbook_metadata=(
            workbook_metadata
        ),
    )

    return convert_llm_response_to_proposal(
        response=validated_response,
        schema_fingerprint=(
            schema_fingerprint
        ),
        fingerprint_version=(
            fingerprint_version
        ),
    )


def is_retryable_vertex_error(
    exception: VertexProposalError,
) -> bool:
    """
    Retry only transient requests and unusable model
    responses.

    Deterministic workbook-schema violations are not
    retried because retries must not bypass local
    safety validation.
    """

    return exception.guardrail_name in {
        "VERTEX_PROPOSAL_REQUEST_FAILED",
        "STRUCTURED_LLM_OUTPUT_REQUIRED",
        "VALID_LLM_PROPOSAL_REQUIRED",
    }


def generate_vertex_parser_proposal_with_retry(
    *,
    workbook_metadata: dict[str, Any],
    canonical_schema: dict[str, Any],
    schema_fingerprint: str,
    fingerprint_version: str,
) -> dict[str, Any]:
    """
    Generate a Vertex AI parser proposal using a
    bounded retry policy.

    Every successful response still passes:
    - structured-response validation
    - workbook-schema validation
    - parser-specification validation

    After all retryable attempts fail, this function
    raises VertexProposalError so the calling node can
    activate the deterministic fallback.
    """

    import time

    maximum_attempts = max(
        1,
        int(
            settings
            .vertex_proposal_max_attempts
        ),
    )

    retry_delay_seconds = max(
        0.0,
        float(
            settings
            .vertex_proposal_retry_delay_seconds
        ),
    )

    attempt_errors: list[
        dict[str, Any]
    ] = []

    last_exception: (
        VertexProposalError | None
    ) = None

    for attempt_number in range(
        1,
        maximum_attempts + 1,
    ):
        try:
            proposal = (
                generate_vertex_parser_proposal(
                    workbook_metadata=(
                        workbook_metadata
                    ),
                    canonical_schema=(
                        canonical_schema
                    ),
                    schema_fingerprint=(
                        schema_fingerprint
                    ),
                    fingerprint_version=(
                        fingerprint_version
                    ),
                )
            )

            proposal[
                "vertex_attempt_number"
            ] = attempt_number

            proposal[
                "vertex_maximum_attempts"
            ] = maximum_attempts

            proposal[
                "vertex_previous_errors"
            ] = attempt_errors

            return proposal

        except VertexProposalError as exception:
            last_exception = exception

            attempt_errors.append(
                {
                    "attempt": (
                        attempt_number
                    ),
                    "guardrail": (
                        exception
                        .guardrail_name
                    ),
                    "message": (
                        exception.message
                    ),
                }
            )

            if not is_retryable_vertex_error(
                exception
            ):
                raise

            if (
                attempt_number
                < maximum_attempts
                and retry_delay_seconds > 0
            ):
                time.sleep(
                    retry_delay_seconds
                )

    if last_exception is None:
        raise VertexProposalError(
            message=(
                "Vertex AI proposal generation "
                "failed without response details."
            ),
            guardrail_name=(
                "VERTEX_PROPOSAL_REQUEST_FAILED"
            ),
        )

    raise VertexProposalError(
        message=(
            "Vertex AI did not return a valid "
            "structured parser proposal after "
            f"{maximum_attempts} attempts. "
            "Last guardrail: "
            f"{last_exception.guardrail_name}. "
            "Last error: "
            f"{last_exception.message}"
        ),
        guardrail_name=(
            last_exception.guardrail_name
        ),
    ) from last_exception

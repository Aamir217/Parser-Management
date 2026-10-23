from typing import Any


NODE_METADATA: dict[
    str,
    dict[str, str],
] = {
    "validate_upload": {
        "label": "Validate Upload",
        "description": (
            "Applies deterministic file-upload "
            "guardrails."
        ),
        "category": "Guardrail",
    },
    "store_original": {
        "label": "Store Original",
        "description": (
            "Stores the original workbook with an "
            "immutable file identity."
        ),
        "category": "Storage",
    },
    "inspect_workbook": {
        "label": "Inspect Workbook",
        "description": (
            "Inspects workbook sheets, headers, "
            "formulas and sampled column types."
        ),
        "category": "Inspection",
    },
    "create_fingerprint": {
        "label": "Create Fingerprint",
        "description": (
            "Creates the canonical workbook schema "
            "and SHA-256 fingerprint."
        ),
        "category": "Fingerprint",
    },
    "match_parser_registry": {
        "label": "Match Parser Registry",
        "description": (
            "Looks for an exact active and approved "
            "parser version."
        ),
        "category": "Registry",
    },
    "generate_parser_proposal": {
        "label": "LLM Parser Proposal",
        "description": (
            "Uses Vertex AI to propose a declarative "
            "parser. If Vertex AI cannot create a "
            "valid proposal, the deterministic "
            "fallback may be used."
        ),
        "category": "LLM",
    },
    "human_review": {
        "label": "Human Review",
        "description": (
            "Pauses the workflow for an explicit "
            "approve or reject decision."
        ),
        "category": "Human in the Loop",
    },
    "register_approved_parser": {
        "label": "Register Approved Parser",
        "description": (
            "Registers the human-approved parser "
            "as an active parser version."
        ),
        "category": "Registry",
    },
    "execute_approved_parser": {
        "label": "Execute Approved Parser",
        "description": (
            "Executes only an authorized, active "
            "and approved declarative parser."
        ),
        "category": "Execution",
    },
    "validate_parsed_output": {
        "label": "Validate Parsed Output",
        "description": (
            "Applies deterministic validation to "
            "the parsed records."
        ),
        "category": "Validation",
    },
    "create_validated_xlsx": {
        "label": "Create Validated XLSX",
        "description": (
            "Creates the final validated workbook "
            "for preview and download."
        ),
        "category": "Output",
    },
}


def get_node_metadata(
    node_name: str,
) -> dict[str, str]:
    """
    Return frontend metadata for a workflow node.

    Unknown future nodes remain visible using a
    generated friendly label.
    """

    metadata = NODE_METADATA.get(
        node_name
    )

    if metadata is not None:
        return metadata

    fallback_label = (
        node_name
        .replace("_", " ")
        .strip()
        .title()
    )

    return {
        "label": (
            fallback_label
            or "Unknown Node"
        ),
        "description": (
            "Workflow node execution."
        ),
        "category": "Workflow",
    }


def get_node_label(
    node_name: str,
) -> str:
    """
    Return the friendly frontend label.
    """

    return get_node_metadata(
        node_name
    )["label"]


def is_llm_node(
    node_name: str,
) -> bool:
    """
    Return True for the parser-proposal LLM node.
    """

    return (
        node_name
        == "generate_parser_proposal"
    )


def get_node_badge(
    execution: dict[str, Any],
) -> str:
    """
    Return the implementation badge for the LLM
    proposal node.

    Normal deterministic nodes do not receive a
    separate implementation badge.
    """

    node_name = str(
        execution.get(
            "node_name",
            "",
        )
    )

    if not is_llm_node(
        node_name
    ):
        return ""

    output_state = execution.get(
        "output_state",
        {},
    )

    if not isinstance(
        output_state,
        dict,
    ):
        output_state = {}

    proposal_source = output_state.get(
        "proposal_source"
    )

    labels = {
        "VERTEX_AI": "Vertex AI",
        "DETERMINISTIC_FALLBACK": (
            "Deterministic Fallback"
        ),
        "DETERMINISTIC": (
            "Deterministic"
        ),
    }

    return labels.get(
        proposal_source,
        "Proposal Generator",
    )


def build_node_button_label(
    execution: dict[str, Any],
) -> str:
    """
    Build the clickable label used in the standard
    workflow-node timeline.

    Examples:
    - Validate Upload
    - LLM Parser Proposal - Vertex AI
    - Human Review
    """

    node_name = str(
        execution.get(
            "node_name",
            "unknown_node",
        )
    )

    status = str(
        execution.get(
            "status",
            "UNKNOWN",
        )
    ).upper()

    status_symbols = {
        "PASSED": "✅",
        "COMPLETED": "✅",
        "WAITING": "⏸️",
        "RUNNING": "🔄",
        "PENDING": "⏳",
        "BLOCKED": "⛔",
        "FAILED": "❌",
    }

    symbol = status_symbols.get(
        status,
        "•",
    )

    friendly_label = get_node_label(
        node_name
    )

    badge = get_node_badge(
        execution
    )

    display_label = (
        f"{symbol} {friendly_label}"
    )

    if badge:
        display_label += (
            f" · {badge}"
        )

    return display_label

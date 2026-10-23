from typing import Literal

from langgraph.checkpoint.memory import (
    MemorySaver,
)
from langgraph.graph import (
    END,
    START,
    StateGraph,
)

from app.workflow.nodes.create_fingerprint import (
    create_fingerprint_node,
)
from app.workflow.nodes.create_validated_xlsx import (
    create_validated_xlsx_node,
)
from app.workflow.nodes.execute_approved_parser import (
    execute_approved_parser_node,
)
from app.workflow.nodes.generate_parser_proposal import (
    generate_parser_proposal_node,
)
from app.workflow.nodes.human_review import (
    human_review_node,
)
from app.workflow.nodes.inspect_workbook import (
    inspect_workbook_node,
)
from app.workflow.nodes.match_parser_registry import (
    match_parser_registry_node,
)
from app.workflow.nodes.register_approved_parser import (
    register_approved_parser_node,
)
from app.workflow.nodes.validate_parsed_output import (
    validate_parsed_output_node,
)
from app.workflow.state import (
    ParserWorkflowState,
)


def route_after_inspection(
    state: ParserWorkflowState,
) -> Literal[
    "create_fingerprint",
    "end",
]:
    if (
        state.get("workflow_status")
        == "INSPECTION_COMPLETED"
    ):
        return "create_fingerprint"

    return "end"


def route_after_fingerprint(
    state: ParserWorkflowState,
) -> Literal[
    "match_parser_registry",
    "end",
]:
    if (
        state.get("workflow_status")
        == "FINGERPRINT_COMPLETED"
    ):
        return "match_parser_registry"

    return "end"


def route_after_registry_match(
    state: ParserWorkflowState,
) -> Literal[
    "execute_approved_parser",
    "generate_parser_proposal",
    "end",
]:
    if (
        state.get("workflow_status")
        == "APPROVED_PARSER_FOUND"
        and state.get(
            "parser_execution_authorized"
        )
        is True
    ):
        return "execute_approved_parser"

    if (
        state.get("workflow_status")
        == "NO_APPROVED_PARSER_FOUND"
        and state.get(
            "parser_execution_authorized"
        )
        is False
    ):
        return "generate_parser_proposal"

    return "end"


def route_after_review(
    state: ParserWorkflowState,
) -> Literal[
    "register_approved_parser",
    "end",
]:
    if (
        state.get("review_decision")
        == "APPROVE"
        and state.get(
            "proposal_status"
        )
        == "APPROVED"
    ):
        return "register_approved_parser"

    return "end"


def route_after_registration(
    state: ParserWorkflowState,
) -> Literal[
    "execute_approved_parser",
    "end",
]:
    if (
        state.get("workflow_status")
        == "PARSER_REGISTERED"
        and state.get(
            "parser_execution_authorized"
        )
        is True
    ):
        return "execute_approved_parser"

    return "end"


def route_after_parser_execution(
    state: ParserWorkflowState,
) -> Literal[
    "validate_parsed_output",
    "end",
]:
    if (
        state.get("workflow_status")
        == "PARSING_COMPLETED"
    ):
        return "validate_parsed_output"

    return "end"


def route_after_validation(
    state: ParserWorkflowState,
) -> Literal[
    "create_validated_xlsx",
    "end",
]:
    if (
        state.get(
            "validation_status"
        )
        in {
            "PASS",
            "WARN",
        }
        and state.get(
            "workflow_status"
        )
        in {
            "WORKFLOW_COMPLETED",
            "WORKFLOW_COMPLETED_WITH_WARNINGS",
        }
    ):
        return "create_validated_xlsx"

    return "end"


def build_parser_workflow():
    graph_builder = StateGraph(
        ParserWorkflowState
    )

    graph_builder.add_node(
        "inspect_workbook",
        inspect_workbook_node,
    )

    graph_builder.add_node(
        "create_fingerprint",
        create_fingerprint_node,
    )

    graph_builder.add_node(
        "match_parser_registry",
        match_parser_registry_node,
    )

    graph_builder.add_node(
        "execute_approved_parser",
        execute_approved_parser_node,
    )

    graph_builder.add_node(
        "generate_parser_proposal",
        generate_parser_proposal_node,
    )

    graph_builder.add_node(
        "human_review",
        human_review_node,
    )

    graph_builder.add_node(
        "register_approved_parser",
        register_approved_parser_node,
    )

    graph_builder.add_node(
        "validate_parsed_output",
        validate_parsed_output_node,
    )

    graph_builder.add_node(
        "create_validated_xlsx",
        create_validated_xlsx_node,
    )

    graph_builder.add_edge(
        START,
        "inspect_workbook",
    )

    graph_builder.add_conditional_edges(
        "inspect_workbook",
        route_after_inspection,
        {
            "create_fingerprint": (
                "create_fingerprint"
            ),
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "create_fingerprint",
        route_after_fingerprint,
        {
            "match_parser_registry": (
                "match_parser_registry"
            ),
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "match_parser_registry",
        route_after_registry_match,
        {
            "execute_approved_parser": (
                "execute_approved_parser"
            ),
            "generate_parser_proposal": (
                "generate_parser_proposal"
            ),
            "end": END,
        },
    )

    graph_builder.add_edge(
        "generate_parser_proposal",
        "human_review",
    )

    graph_builder.add_conditional_edges(
        "human_review",
        route_after_review,
        {
            "register_approved_parser": (
                "register_approved_parser"
            ),
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "register_approved_parser",
        route_after_registration,
        {
            "execute_approved_parser": (
                "execute_approved_parser"
            ),
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "execute_approved_parser",
        route_after_parser_execution,
        {
            "validate_parsed_output": (
                "validate_parsed_output"
            ),
            "end": END,
        },
    )

    graph_builder.add_conditional_edges(
        "validate_parsed_output",
        route_after_validation,
        {
            "create_validated_xlsx": (
                "create_validated_xlsx"
            ),
            "end": END,
        },
    )

    graph_builder.add_edge(
        "create_validated_xlsx",
        END,
    )

    return graph_builder.compile(
        checkpointer=MemorySaver()
    )


inspection_graph = build_parser_workflow()

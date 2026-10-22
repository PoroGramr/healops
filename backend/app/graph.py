"""Bounded diagnostic graph: interpretation only, never operational authority."""

from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.diagnosis import diagnose


class DiagnosticState(TypedDict, total=False):
    logs: str
    status: str
    health: str
    classification: str
    diagnosis: dict
    proposal: str
    valid: bool
    next_step: str


def collect_context(state: DiagnosticState) -> dict:
    return {"logs": state.get("logs", "")[-8192:]}


def classify_incident(state: DiagnosticState) -> dict:
    return {"classification": "healthcheck" if state.get("health") == "unhealthy" else "exit"}


def diagnose_root_cause(state: DiagnosticState) -> dict:
    return {
        "diagnosis": diagnose(
            state.get("logs", ""), state.get("status", ""), state.get("health", "")
        )
    }


def propose_remediation(state: DiagnosticState) -> dict:
    # Deterministic policy; the LLM never controls this value.
    return {
        "proposal": "restart" if state.get("classification") in {"exit", "healthcheck"} else "none"
    }


def validate_remediation(state: DiagnosticState) -> dict:
    return {"valid": state.get("proposal") == "restart"}


def request_approval(state: DiagnosticState) -> dict:
    return {"next_step": "human_approval_required"}


def route(state: DiagnosticState) -> str:
    return "request_approval" if state.get("valid") else END


def build_graph():
    graph = StateGraph(DiagnosticState)
    for name, action in (
        ("collect_context", collect_context),
        ("classify_incident", classify_incident),
        ("diagnose_root_cause", diagnose_root_cause),
        ("propose_remediation", propose_remediation),
        ("validate_remediation", validate_remediation),
        ("request_approval", request_approval),
    ):
        graph.add_node(name, action)
    graph.set_entry_point("collect_context")
    graph.add_edge("collect_context", "classify_incident")
    graph.add_edge("classify_incident", "diagnose_root_cause")
    graph.add_edge("diagnose_root_cause", "propose_remediation")
    graph.add_edge("propose_remediation", "validate_remediation")
    graph.add_conditional_edges("validate_remediation", route)
    graph.add_edge("request_approval", END)
    return graph.compile()


DIAGNOSTIC_GRAPH = build_graph()

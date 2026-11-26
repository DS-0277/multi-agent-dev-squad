"""Multi-agent coordination loop built on a LangGraph state graph."""
from typing import TypedDict

from langgraph.graph import END, StateGraph

from src.agents.coder_agent import run_coder_agent
from src.agents.reviewer_agent import run_reviewer_agent
from src.agents.spec_agent import run_spec_agent
from src.schemas import CodeArtifact, QAReport, SpecArtifact

MAX_ITERATIONS = 4


class SquadState(TypedDict, total=False):
    user_request: str
    spec: SpecArtifact
    code: CodeArtifact
    report: QAReport
    iteration: int
    history: list[str]


def spec_node(state: SquadState) -> SquadState:
    spec = run_spec_agent(state["user_request"])
    return {"spec": spec, "iteration": 0, "history": [spec.model_dump_json()]}


def coder_node(state: SquadState) -> SquadState:
    iteration = state["iteration"] + 1
    code = run_coder_agent(
        state["spec"], iteration, state.get("code"), state.get("report")
    )
    history = state["history"] + [code.model_dump_json()]
    return {"code": code, "iteration": iteration, "history": history}


def qa_node(state: SquadState) -> SquadState:
    report = run_reviewer_agent(state["code"])
    if not report.tests_passed and state["iteration"] >= MAX_ITERATIONS:
        report = report.model_copy(update={"status": "MAX_CYCLES_EXCEEDED"})
    history = state["history"] + [report.model_dump_json()]
    return {"report": report, "history": history}


def route_after_qa(state: SquadState) -> str:
    if state["report"].status == "PASSED":
        return END
    if state["report"].status == "MAX_CYCLES_EXCEEDED":
        return END
    return "coder"


def build_graph():
    graph = StateGraph(SquadState)
    graph.add_node("spec", spec_node)
    graph.add_node("coder", coder_node)
    graph.add_node("qa", qa_node)
    graph.set_entry_point("spec")
    graph.add_edge("spec", "coder")
    graph.add_edge("coder", "qa")
    graph.add_conditional_edges("qa", route_after_qa)
    return graph.compile()


def run_squad(user_request: str) -> SquadState:
    app = build_graph()
    return app.invoke({"user_request": user_request})

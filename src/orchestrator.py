"""Multi-agent coordination loop built on a LangGraph state graph."""
from typing import Callable, Iterator, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.coder_agent import run_coder_agent
from src.agents.reviewer_agent import run_reviewer_agent
from src.agents.spec_agent import run_spec_agent
from src.bug_injector import inject_logic_bug
from src.failure_summary import UNKNOWN_FAILURE, failing_tests
from src.schemas import CodeArtifact, QAReport, SpecArtifact

MAX_ITERATIONS = 4


class SquadState(TypedDict, total=False):
    user_request: str
    spec: SpecArtifact
    code: CodeArtifact
    report: QAReport
    iteration: int
    injected_bug: str
    failing: list[str]
    prev_failing: list[str]


def build_graph(
    max_iterations: int = MAX_ITERATIONS,
    inject_bug: bool = False,
    spec_fn: Callable = run_spec_agent,
    coder_fn: Callable = run_coder_agent,
    qa_fn: Callable = run_reviewer_agent,
    bug_injector: Callable = inject_logic_bug,
):
    """Build the Spec -> Coder -> QA graph. Agents are injectable for testing."""

    def spec_node(state: SquadState) -> SquadState:
        return {"spec": spec_fn(state["user_request"]), "iteration": 0}

    def coder_node(state: SquadState) -> SquadState:
        iteration = state["iteration"] + 1
        report = state.get("report")
        failing, prev = state.get("failing"), state.get("prev_failing")
        if report is not None and failing and failing == prev:
            # Same tests failed twice in a row: the last fix did not work.
            note = (
                "STUCK: the same tests failed in the previous attempt too "
                f"({', '.join(failing)}). Your last fix did not work. The test "
                "itself may be wrong, or depend on real timing or thread "
                "scheduling. Fix or simplify that test as well as the code."
            )
            report = report.model_copy(
                update={"review_feedback": [note, *report.review_feedback]}
            )
        code = coder_fn(state["spec"], iteration, state.get("code"), report)
        update: SquadState = {"code": code, "iteration": iteration}
        if inject_bug and iteration == 1:
            code, description = bug_injector(code)
            update["code"] = code
            update["injected_bug"] = description
        return update

    def qa_node(state: SquadState) -> SquadState:
        report = qa_fn(state["code"])
        if not report.tests_passed and state["iteration"] >= max_iterations:
            report = report.model_copy(update={"status": "MAX_CYCLES_EXCEEDED"})
        failing = [] if report.tests_passed else (
            failing_tests(report.execution_output) or [UNKNOWN_FAILURE]
        )
        return {
            "report": report,
            "failing": failing,
            "prev_failing": state.get("failing", []),
        }

    def route_after_qa(state: SquadState) -> str:
        # Unconditional bound: passing or hitting the iteration ceiling ends the run.
        if state["report"].tests_passed or state["iteration"] >= max_iterations:
            return END
        return "coder"

    graph = StateGraph(SquadState)
    graph.add_node("spec", spec_node)
    graph.add_node("coder", coder_node)
    graph.add_node("qa", qa_node)
    graph.set_entry_point("spec")
    graph.add_edge("spec", "coder")
    graph.add_edge("coder", "qa")
    graph.add_conditional_edges("qa", route_after_qa)
    return graph.compile()


def stream_squad(
    user_request: str,
    max_iterations: int = MAX_ITERATIONS,
    inject_bug: bool = False,
    **agent_overrides,
) -> Iterator[tuple[str, dict]]:
    """Yield (node_name, state_update) after each agent finishes."""
    app = build_graph(max_iterations, inject_bug, **agent_overrides)
    config = {"recursion_limit": 2 * max_iterations + 5}
    for event in app.stream(
        {"user_request": user_request}, config=config, stream_mode="updates"
    ):
        for node, update in event.items():
            yield node, update


def run_squad(
    user_request: str,
    max_iterations: int = MAX_ITERATIONS,
    inject_bug: bool = False,
    **agent_overrides,
) -> SquadState:
    """Run the whole squad and return the final merged state."""
    final: SquadState = {"user_request": user_request}
    for _, update in stream_squad(
        user_request, max_iterations, inject_bug, **agent_overrides
    ):
        final.update(update)
    return final

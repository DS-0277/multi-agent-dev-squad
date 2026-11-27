"""Streamlit interface: watch the 3-agent squad collaborate in real time."""
import os
import sys
from pathlib import Path

# Allow `streamlit run src/app.py` to import the `src` package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st  # noqa: E402
from dotenv import load_dotenv  # noqa: E402

from src.orchestrator import MAX_ITERATIONS, stream_squad  # noqa: E402

load_dotenv()
try:  # Streamlit Community Cloud keeps keys in its secrets manager.
    if "OPENAI_API_KEY" in st.secrets:
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:
    pass

st.set_page_config(page_title="Multi-Agent Dev Squad", page_icon="🛠️", layout="wide")

EXAMPLES = {
    "Token Bucket rate limiter": (
        "Build a robust Python rate-limiting class using the Token Bucket algorithm "
        "with thread-safety, microsecond precision, burst allowance, and refill rate "
        "calculation."
    ),
    "LRU Cache with TTL": (
        "Build a Python LRU Cache with TTL eviction, thread-safe, with get, put and "
        "size methods."
    ),
}

MAX_RUNS_PER_SESSION = 5  # soft cost guard for the public demo

STATUS_LABELS = {
    "idle": "⚪ READY",
    "running": "🟡 IN PROGRESS",
    "PASSED": "🟢 CONVERGED (ALL TESTS PASS)",
    "MAX_CYCLES_EXCEEDED": "🔴 TERMINATED (MAX CYCLES)",
    "ERROR": "🔴 ERROR",
}


def new_run(inject_bug: bool) -> dict:
    return {
        "phase": "running", "iteration": 0, "spec": None, "code": None,
        "reports": [], "injected_bug": None, "inject_bug": inject_bug, "error": None,
    }


def render(run: dict, ph: dict) -> None:
    """Draw the whole dashboard from the run dict (works live and after a rerun)."""
    ph["status"].markdown(f"## {STATUS_LABELS[run['phase']]}")
    ph["badge"].markdown(f"## Iteration {run['iteration']} / {MAX_ITERATIONS}")

    with ph["timeline"].container():
        for i, rep in enumerate(run["reports"], start=1):
            if rep.tests_passed:
                st.markdown(f"**Iteration {i}:** ✅ all {rep.total_tests} tests passed")
            else:
                st.markdown(f"**Iteration {i}:** ❌ {rep.failed_tests} failed of {rep.total_tests}")
        if run["error"]:
            st.error(run["error"])

    with ph["spec"].container():
        spec = run["spec"]
        if spec is None:
            st.info("Waiting for the Spec Agent...")
        else:
            st.subheader(spec.feature_name)
            st.markdown("**Requirements**")
            st.markdown("\n".join(f"- {r}" for r in spec.requirements))
            st.markdown("**Acceptance criteria / test plan**")
            st.markdown("\n".join(f"- {t}" for t in spec.test_cases))
            st.markdown("**Interfaces**")
            st.code(spec.interfaces, language="python")

    with ph["coder"].container():
        code = run["code"]
        if code is None:
            st.info("Waiting for the Coder Agent...")
        else:
            st.caption(f"Iteration {code.iteration} output")
            if run["injected_bug"] and code.iteration == 1:
                st.warning(f"Adversarial bug injected: {run['injected_bug']}")
            st.markdown("**solution.py**")
            st.code(code.implementation_code, language="python", line_numbers=True)
            st.markdown("**test_solution.py**")
            st.code(code.test_code, language="python", line_numbers=True)

    with ph["qa"].container():
        if not run["reports"]:
            st.info("Waiting for the QA Agent...")
        for i, rep in reversed(list(enumerate(run["reports"], start=1))):
            icon = "✅" if rep.tests_passed else "❌"
            with st.expander(f"{icon} Iteration {i}: {rep.status}", expanded=(i == len(run["reports"]))):
                c1, c2, c3 = st.columns(3)
                c1.metric("Total tests", rep.total_tests)
                c2.metric("Failed", rep.failed_tests)
                c3.metric("Verdict", "PASS" if rep.tests_passed else "FAIL")
                st.markdown("**Raw pytest output**")
                st.code(rep.execution_output, language="text")
                if rep.review_feedback:
                    st.markdown("**Critique notes**")
                    st.markdown("\n".join(f"- {f}" for f in rep.review_feedback))


# ---------- Page layout ----------
st.title("🛠️ Multi-Agent Dev Squad")
st.caption("Spec Agent → Coder Agent → sandboxed pytest → QA Agent, looping until the tests pass.")

with st.sidebar:
    st.header("Settings")
    inject_bug = st.toggle(
        "Adversarial bug injection",
        help="Break the Coder's first pass on purpose to watch QA catch it and the Coder self-correct.",
    )
    st.markdown(f"**Max refinement cycles:** {MAX_ITERATIONS}")
    runs_ph = st.empty()
    st.caption("The pass/fail verdict comes from pytest's exit code, never from an AI opinion.")

example = st.selectbox("Example requests", list(EXAMPLES))
request = st.text_area("Feature request", value=EXAMPLES[example], height=110, key=f"req_{example}")
runs_used = st.session_state.get("runs_used", 0)
limit_reached = runs_used >= MAX_RUNS_PER_SESSION
runs_ph.markdown(f"**Runs this session:** {runs_used} / {MAX_RUNS_PER_SESSION}")
run_clicked = st.button(
    "Run squad", type="primary", disabled=(not request.strip() or limit_reached)
) and not limit_reached
if limit_reached:
    st.warning(
        f"Demo limit reached ({MAX_RUNS_PER_SESSION} runs per session). "
        "Refresh the page to start a new session."
    )

if not os.getenv("OPENAI_API_KEY"):
    st.error("OPENAI_API_KEY is not set. Add it to your local .env file (or to Streamlit secrets).")
    st.stop()

top_left, top_right = st.columns(2)
ph = {"status": top_left.empty(), "badge": top_right.empty(), "timeline": st.empty()}
spec_tab, coder_tab, qa_tab = st.tabs(["📋 Spec Board", "💻 Coder Terminal", "🧪 QA Test Runner Console"])
ph["spec"], ph["coder"], ph["qa"] = spec_tab.empty(), coder_tab.empty(), qa_tab.empty()

if run_clicked:
    st.session_state["runs_used"] = runs_used + 1
    runs_ph.markdown(f"**Runs this session:** {runs_used + 1} / {MAX_RUNS_PER_SESSION}")
    run = new_run(inject_bug)
    st.session_state["run"] = run
    render(run, ph)
    try:
        for node, update in stream_squad(request, inject_bug=inject_bug):
            if node == "spec":
                run["spec"] = update["spec"]
            elif node == "coder":
                run["code"] = update["code"]
                run["iteration"] = update["iteration"]
                if "injected_bug" in update:
                    run["injected_bug"] = update["injected_bug"]
            elif node == "qa":
                run["reports"].append(update["report"])
                run["phase"] = (
                    update["report"].status
                    if update["report"].status in ("PASSED", "MAX_CYCLES_EXCEEDED")
                    else "running"
                )
            render(run, ph)
    except Exception as exc:  # noqa: BLE001 - show any failure in the UI
        run["phase"] = "ERROR"
        run["error"] = f"{type(exc).__name__}: {exc}"
        render(run, ph)
elif "run" in st.session_state:
    render(st.session_state["run"], ph)
else:
    render({"phase": "idle", "iteration": 0, "spec": None, "code": None, "reports": [],
            "injected_bug": None, "inject_bug": False, "error": None}, ph)

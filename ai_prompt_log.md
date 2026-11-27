# AI Prompt Log

## Step 2: Initial AI Draft

- **Date:** 2026-11-26
- **Tool:** Claude Code (Claude Sonnet 5.5)
- **Approach:** The assignment's sample prompt was used with small adaptations. No extra security or hardening instructions were added, so the draft could be audited honestly in Step 3. The draft was committed unmodified.

### Adaptations to the sample prompt
- Orchestration framework: LangGraph (`StateGraph`).
- API key read from `.env` via `python-dotenv`; model name configurable via `OPENAI_MODEL` (default `gpt-4o-mini`).

### Prompt used

```text
You are a Principal AI Agent Architect specializing in autonomous multi-agent software engineering systems.
Build a production-ready, 3-agent software development squad in Python 3.11+ that iteratively writes, tests, and refines code until test suites pass.

Architecture & Requirements:

1. Structured State & Communication Schemas (src/schemas.py):
   - `SpecArtifact`: feature_name (str), requirements (list[str]), test_cases (list[str]), interfaces (str).
   - `CodeArtifact`: implementation_code (str), test_code (str), iteration: int.
   - `QAReport`: tests_passed (bool), total_tests (int), failed_tests (int), execution_output (str), review_feedback (list[str]), status (Literal["PASSED", "NEEDS_REVISION", "MAX_CYCLES_EXCEEDED"]).

2. The 3 Specialized Agents (src/agents/):
   - Spec Agent: Ingests user request, outputs a strongly typed `SpecArtifact`. Focuses strictly on edge cases, assertions, and architecture.
   - Coder Agent: Ingests `SpecArtifact` and optional previous `QAReport`. Generates `solution.py` and `test_solution.py` as a `CodeArtifact`.
   - Reviewer/QA Agent: Ingests `CodeArtifact`, runs tests via the sandbox runner, inspects syntax, and outputs a `QAReport`.

3. Sandboxed Execution Engine (src/sandbox.py):
   - Safely executes the generated code and pytest test file using an isolated Python `subprocess.run()`.
   - Enforce security constraints: 10-second execution timeout, isolated temporary working directory (`tempfile.TemporaryDirectory`), and capture of stdout, stderr, and exit codes.

4. Orchestration Loop (src/orchestrator.py):
   - Coordinate the agents: Spec Agent -> Coder Agent -> QA Agent -> [If FAIL -> back to Coder Agent with QA feedback].
   - Enforce a strict termination bound: `max_iterations = 4`. If tests do not pass after 4 attempts, terminate with `status="MAX_CYCLES_EXCEEDED"` and log the failure trace.
   - Prevent token bloat: Agents must exchange structured Pydantic summaries, NOT raw cumulative message histories.

Provide clean, modular, typed code split across the designated files.
```

### Files generated (unaudited draft)
`src/schemas.py`, `src/sandbox.py`, `src/agents/spec_agent.py`, `src/agents/coder_agent.py`, `src/agents/reviewer_agent.py`, `src/orchestrator.py`

---

## Step 3: Audit Findings

Draft under audit: commit `6baded5`. Result: **2 defects found and fixed, 2 areas good with no defect.**
Evidence came from a demo script that ran the draft before and after the fixes (a dummy key `sk-FAKE-for-demo` and a mocked LLM were used, so no real key and no API cost).

| # | Audit area | Status |
|---|---|---|
| 1 | Arbitrary code execution & sandbox escapes | Defect found, fixed |
| 2 | Context bloat & scratchpad accumulation | Good, no defect found |
| 3 | Agent collusion / sycophancy trap | Defect found, fixed |
| 4 | Infinite refinement loops | Good, no defect found |

### 1. Arbitrary code execution: DEFECT FOUND, FIXED

**Problem.** The draft already avoided `shell=True`, used a list of arguments, a 10s timeout and a `TemporaryDirectory`. But `subprocess.run` had no `env=` argument, so the child process inherited the parent's full environment. The app loads `.env` with `load_dotenv()`, so `OPENAI_API_KEY` was visible to the AI-generated code. A single `os.environ["OPENAI_API_KEY"]` in generated code could read or leak it.

**Evidence (before).** A sandboxed test asserting the key was invisible failed: the dummy key was readable inside the sandbox.

**Before (`src/sandbox.py`):**
```python
proc = subprocess.run(
    [sys.executable, "-m", "pytest", "test_solution.py", "-v"],
    cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
)
```

**After:**
```python
SAFE_ENV = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"}

proc = subprocess.run(
    [sys.executable, "-m", "pytest", "test_solution.py", "-v",
     "-p", "no:cacheprovider"],
    cwd=tmp, capture_output=True, text=True, timeout=TIMEOUT_SECONDS,
    shell=False, env=SAFE_ENV,
)
```

**Evidence (after).** The same check passes: the key is invisible inside the sandbox.

**Known limit.** This hides secrets but is not a full jail: generated code could still read ordinary files or use the network. Full isolation would need containers (Docker); documented as a boundary in the README.

### 2. Context bloat: GOOD, NO DEFECT FOUND

The Coder receives only the `SpecArtifact`, its latest `CodeArtifact`, and the latest `QAReport` (see `coder_agent.py`). Old iterations are never sent to the LLM. The draft's `history` list in the orchestrator state was unused clutter that never reached an LLM; it was removed as housekeeping.

### 3. Sycophancy trap: DEFECT FOUND, FIXED

**Problem.** In `reviewer_agent.py`, `tests_passed` came from the LLM's JSON answer, not from pytest. If the tests failed but the LLM said "looks great", the build was approved.

**Evidence (before).** A mocked LLM replying `tests_passed: true` with a genuinely failing test (`assert f() == 2`) produced `tests_passed = True, status = PASSED`.

**Before:**
```python
tests_passed = bool(verdict["tests_passed"])
```

**After:**
```python
# Deterministic: only the real pytest exit code decides pass/fail.
tests_passed = result.exit_code == 0 and not result.timed_out
```
The reviewer prompt was also changed so the LLM only returns `review_feedback` (critique notes) and never decides pass/fail.

**Evidence (after).** The same mocked lying LLM now yields `tests_passed = False, status = NEEDS_REVISION`.

### 4. Infinite refinement loops: GOOD, NO DEFECT FOUND

The orchestrator increments `iteration` in the coder node, and `qa_node` sets `MAX_CYCLES_EXCEEDED` whenever tests fail at `iteration >= MAX_ITERATIONS` (4), after which the graph routes to `END`. Automated proof (Test 6, exactly 4 iterations) comes in Step 5.

---

## Step 4: Web Interface and Live-Testing Findings

Built `src/app.py` (Streamlit) and made the orchestrator stream progress (`stream_squad`) so each panel updates live. Real OpenAI runs during testing exposed three more problems, all fixed:

1. **LLM-written bug injection was unreliable.** First design: ask the Coder to write one subtle bug. Result: the bug sometimes slipped past the Coder's own tests (run passed on iteration 1, so nothing to demonstrate) or caused a deadlock. **Fix:** `src/bug_injector.py` flips one operator mechanically (for example `>=` to `>`) in the Coder's correct first-pass code and keeps only a flip that makes the tests fail. It first checks the baseline passes, otherwise a broken test file could be mistaken for a caught bug (this second flaw was found by a real Token Bucket run whose test file had a syntax error).
2. **Coder rewrote everything on repair and introduced deadlocks.** **Fix:** the Coder prompt now demands the smallest possible change, `RLock` when methods call each other, no infinite loops, and fast tests.
3. **Opaque timeout message.** A hung run only reported "Timed out". **Fix:** the sandbox now says the run exceeded 10s and may have an infinite loop or deadlock, so the Coder can act on it.

**Model choice.** `gpt-4o-mini` and `gpt-4.1-mini` were flaky on bug-injection runs (several ended MAX_CYCLES). `gpt-4o` converged in the runs tested, so it is now the default (override with `OPENAI_MODEL`).

**Result.** Token Bucket with bug injection: 3 of 3 runs failed once with a clear trace, then passed on iteration 2. Full UI run via Streamlit's test harness ended CONVERGED. LLM output is non-deterministic, so a run can occasionally need more cycles or hit the 4-cycle ceiling; the circuit breaker handles that case.

---

## Step 5: Automated QA Test Suite

21 tests, all passing (`uv run pytest -v`, about 30s, no OpenAI calls). Agents and the LLM are replaced by scripted fakes.

- **Required Tests 1 to 6** are in `tests/test_sandbox.py` (passing run, failing assertion capture, infinite-loop timeout), `tests/test_schemas.py` (validation) and `tests/test_orchestration.py` (halts on iteration 1 pass; stops at exactly 4 with `MAX_CYCLES_EXCEEDED`).
- **Code change for Test 3:** the sandbox gained `SandboxTimeoutError`, raised by the low-level runner (`run_python`), so a timeout is a real exception as the assignment words it. `run_tests` still catches it and returns a `timed_out` result so the squad loop keeps running.
- **Extra tests lock in the audit fixes:** secrets invisible in the sandbox (Step 3 item 1), a lying LLM cannot override a failing exit code (item 3), bug injector only breaks code that passes, a custom iteration ceiling is respected.

---

## Step 6: Live Deployment Findings

The app was deployed to Streamlit Community Cloud and a real run confirmed the sandbox, pytest and Secrets work on the cloud server (Linux, Python 3.11). That run ended MAX_CYCLES_EXCEEDED on the Token Bucket request because the Coder's own tests were flaky (timing and thread assumptions), which also exercised the circuit breaker for real.

- **Run counter lag:** the sidebar "runs used" counter updated one interaction late; fixed with a placeholder updated immediately.
- **Flaky generated tests:** OpenAI's default temperature made runs vary. Prompt tightening did not help and was reverted. Lowering temperature to 0.2 on all three agents (`OPENAI_TEMPERATURE`) did, with a mock test asserting it is sent.
- **Result:** LRU Cache with bug injection, 3 of 3 runs: bug injected, caught by QA, repaired, ended CONVERGED in 2 to 3 iterations. Token Bucket remains the less reliable example; the circuit breaker handles the failure case.

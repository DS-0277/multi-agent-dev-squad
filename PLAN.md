# PLAN.md — 3-Agent Collaborative Software Development Squad

**Due:** Sun Nov 29, 2026, 11:59pm
**Repo:** https://github.com/DS-0277/multi-agent-dev-squad
**Deployment:** Streamlit Community Cloud (Option B in Step 6)
**Orchestration framework:** LangGraph
**Max refinement cycles:** 4

## How we work

1. I explain one step in detail → you approve.
2. I build that step → you review.
3. I commit and push to GitHub → I tick the status below.
4. Move to the next step.

**Status legend:** ⬜ Not started · 🟡 In progress · ✅ Done

## Progress overview

| Step | Title | Explained | Built | Pushed |
|---|---|---|---|---|
| 1 | Environment Setup & Project Layout | ✅ | ✅ | ✅ |
| 2 | Use AI to Create the Initial Draft | ✅ | ✅ | ✅ |
| 3 | Audit & Verify the AI Output | ✅ | ✅ | ✅ |
| 4 | Build the Interactive Web Interface | ✅ | ✅ | ✅ |
| 5 | Execute Structured Web Project QA Test Suite | ✅ | ✅ | ✅ |
| 6 | Deployment & Packaging (Streamlit Community Cloud) | ✅ | 🟡 repo ready; cloud deploy by student | ⬜ |
| — | Final deliverables (README, finalized audit log) | ⬜ | ⬜ | ⬜ |

---

## Step 1: Environment Setup & Project Layout — ✅

**Goal:** A working Python 3.11 project with the exact folder layout from the assignment.

- [x] Initialize project with `uv` in the existing `multi-agent-dev-squad` folder
- [x] Pin Python 3.11 (`uv python pin 3.11`)
- [x] Add dependencies: openai, pydantic, langgraph, langchain-openai, python-dotenv, pytest, pytest-asyncio, streamlit (fastapi and uvicorn deliberately left out: unused with Streamlit)
- [x] Create folders/files: `src/` (`schemas.py`, `sandbox.py`, `orchestrator.py`, `app.py`, `agents/` with three agent files), `tests/` (three test files), `ai_prompt_log.md`, `README.md` (stub)
- [x] Create `.env.example` (`OPENAI_API_KEY=your_openai_key_here`) and `.gitignore` (must ignore `.env`)
- [x] Connect the local folder (git init, remote added, existing remote README pulled in); pushed to `main` to the GitHub repo and push the first commit

**Done when:** `uv run python --version` shows 3.11, the layout matches the assignment, and the repo is on GitHub with no secrets.

---

## Step 2: Use AI to Create the Initial Draft — ✅

**Goal:** Generate the baseline squad with an AI coding tool, using the assignment's sample prompt, and keep the draft as-is for the audit.

- [x] Use the sample prompt (adapted) to generate the baseline code
- [x] Draft `schemas.py`: `SpecArtifact`, `CodeArtifact`, `QAReport`
- [x] Draft `sandbox.py`: subprocess test runner
- [x] Draft the three agents (spec, coder, reviewer)
- [x] Draft `orchestrator.py`: Spec → Coder → QA → retry loop, `max_iterations = 4`
- [x] Save the exact prompt and the raw output notes in `ai_prompt_log.md` (the "before" snapshot)
- [x] Commit the unmodified draft separately so the audit diff is visible in git history

**Done when:** All files exist with a first working version, and the original prompt is logged.

---

## Step 3: Audit & Verify the AI Output — ✅

**Goal:** Find and fix the four failure modes. Document each finding in `ai_prompt_log.md` (before → after).

- [x] **Audit 1, ACE and sandbox escapes:** no `shell=True`, args passed as a list, `timeout=10`, isolated `TemporaryDirectory`
- [x] **Audit 2, context bloat:** the Coder on iteration 2+ receives only `SpecArtifact` + latest `CodeArtifact` + latest `QAReport` (no growing history)
- [x] **Audit 3, sycophancy trap:** `tests_passed` is derived strictly from `exit_code == 0`, never from LLM judgment
- [x] **Audit 4, infinite loops:** `iteration >= max_iterations` unconditionally ends the run
- [x] Record at least two concrete flaws with the before/after code (needed for the video)
- [x] Commit and push the refactor

**Done when:** All four audits are checked, and `ai_prompt_log.md` shows the flaw, the risk and the fix for each.

---

## Step 4: Build the Interactive Web Interface (Streamlit) — ✅

**Goal:** `src/app.py` gives clear visibility into the squad.

- [x] Product request input box
- [x] Panels/tabs: **Spec Board**, **Coder Terminal** (syntax highlighted), **QA Test Runner Console** (raw pytest output and critique)
- [x] Iteration badge (e.g. "Iteration 2 / 4")
- [x] Convergence status: 🟡 IN PROGRESS / 🟢 CONVERGED / 🔴 TERMINATED (MAX CYCLES)
- [x] Adversarial Bug Injection toggle (flaw in the Coder's first pass, to show the QA catching it and the Coder self-correcting)
- [x] Run locally with `uv run streamlit run src/app.py` and test with the Token Bucket and LRU Cache examples

**Done when:** A full run works in the browser, including a bug-injection run that fails once and then passes.

---

## Step 5: Execute Structured Web Project QA Test Suite — ✅

**Goal:** Six automated tests under `/tests`, all passing with `pytest -v`.

- [x] `test_sandbox.py`:
  - [x] Test 1: passing execution (exit 0, `tests_passed == True`)
  - [x] Test 2: failing assertion capture (`assert 1 == 2`, exit != 0, trace captured)
  - [x] Test 3: infinite loop timeout (`while True: pass`, killed within 10s)
- [x] `test_schemas.py`:
  - [x] Test 4: schema serialization and validation (valid and invalid inputs)
- [x] `test_orchestration.py` (mocked agents, no API cost):
  - [x] Test 5: clean convergence on iteration 1 → `PASSED`, no extra iterations
  - [x] Test 6: continuous failures → stops at exactly 4 with `MAX_CYCLES_EXCEEDED`
- [x] Capture the `pytest -v` output for the video

**Done when:** `uv run pytest -v` shows all six passing.

---

## Step 6: Deployment & Packaging (Option B: Streamlit Community Cloud) — 🟡 (repo ready, cloud deploy pending)

**Goal:** A reproducible, publicly reachable app with secrets handled safely.

- [x] Make sure dependencies are deployable (`requirements.txt` exported from `uv.lock`; git history scanned: no keys)
- [x] Per-session run limit (5) added as a cost guard, with tests in `tests/test_app.py`
- [ ] Put `OPENAI_API_KEY` in Streamlit's **Secrets** manager (never committed)
- [ ] Confirm the host allows subprocess execution, and that the sandbox and pytest work there
- [ ] Deploy from the GitHub repo, with `src/app.py` as the entry point
- [ ] Test a live run (normal and bug-injection) on the deployed URL
- [ ] Note the live URL (for your submission)

**Done when:** The public `*.streamlit.app` URL completes an end-to-end run.

---

## Final deliverables (after Step 6)

- [ ] **README.md** with: Mermaid architecture diagram, install/setup (uv, Python 3.11), schema and context-passing docs, sandbox security boundaries, run commands (UI and `pytest -v`), AI audit log summary
- [ ] **ai_prompt_log.md** finalized

*(Video and LMS submission are handled by the student, outside this plan.)*

## Timeline (3 days left)

| Day | Target |
|---|---|
| Thu Nov 26 | Steps 1–3 |
| Fri Nov 27 | Steps 4–5 |
| Sat Nov 28 | Step 6, README |
| Sun Nov 29 | Final checks (video and submission by student) before 11:59pm |

## Change log

| Date | Update |
|---|---|
| 2026-11-26 | Plan created and approved |
| 2026-11-26 | Step 2 draft generated and committed unaudited and pushed |
| 2026-11-26 | Step 3 audit done: defects in items 1 and 3 fixed, items 2 and 4 good; pushed |
| 2026-11-26 | Step 4 built: Streamlit UI, mechanical bug injector, default model gpt-4o; pushed |
| 2026-11-26 | Step 5 built: 21 tests passing (6 required + 15 extra), SandboxTimeoutError added; pushed |
| 2026-11-26 | Step 6 repo prep: requirements.txt, run limit (24 tests pass); cloud deploy pending (student) |
| 2026-11-26 | Dropped fastapi/uvicorn from dependencies (unused with Streamlit) |
| 2026-11-26 | Step 1 built and pushed to GitHub |
| 2026-11-26 | Removed video and submission sections (handled by student) |

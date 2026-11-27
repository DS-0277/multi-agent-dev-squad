"""UI tests using Streamlit's headless harness. No OpenAI calls."""
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

import src.orchestrator

APP = str(Path(__file__).resolve().parent.parent / "src" / "app.py")


def empty_stream(*args, **kwargs):
    return iter(())


def test_page_loads_without_errors(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-FAKE-for-test")
    at = AppTest.from_file(APP, default_timeout=30).run()
    assert not at.exception
    assert any("READY" in m.value for m in at.markdown)


def test_run_limit_blocks_the_sixth_run(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-FAKE-for-test")
    with patch.object(src.orchestrator, "stream_squad", empty_stream):
        at = AppTest.from_file(APP, default_timeout=30).run()
        for _ in range(5):
            at.button[0].click().run()
            assert not at.exception
        assert at.session_state["runs_used"] == 5
        at.button[0].click().run()  # a sixth attempt must not start a run
        assert at.session_state["runs_used"] == 5
        assert at.button[0].disabled is True
        assert any("Demo limit reached" in w.value for w in at.warning)


def test_missing_api_key_shows_clear_error(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with patch("dotenv.load_dotenv", lambda *a, **k: False):
        at = AppTest.from_file(APP, default_timeout=30).run()
    assert any("OPENAI_API_KEY" in e.value for e in at.error)

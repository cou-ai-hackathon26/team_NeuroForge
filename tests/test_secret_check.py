import pytest

import modules.secret_check as sc

KEY = "AIza" + "x" * 49


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.setattr(sc, "_from_secrets", lambda name: "")
    for var in ("GEMINI_API_KEY", "GEMINI_MODEL", "ASR_BACKEND"):
        monkeypatch.delenv(var, raising=False)


def test_missing_key_is_reported(monkeypatch):
    monkeypatch.setattr(sc, "_get_gemini_settings", lambda: ("", "m"))
    monkeypatch.setattr(sc, "_get_api_settings", lambda: ("", "m"))
    status = sc.secret_status()
    assert status["gemini_key_set"] is False
    assert status["gemini_key_masked"] is None
    assert any("GEMINI_API_KEY" in w for w in status["warnings"])


def test_key_never_leaks(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr(sc, "_get_gemini_settings", lambda: (KEY, "m"))
    monkeypatch.setattr(sc, "_get_api_settings", lambda: (KEY, "m"))
    status = sc.secret_status()
    assert status["gemini_key_set"] and status["gemini_key_format_ok"]
    assert KEY not in repr(status)
    assert status["gemini_key_masked"].startswith("…xxxx")
    assert status["warnings"] == []


def test_model_mismatch_warns(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", KEY)
    monkeypatch.setattr(sc, "_get_gemini_settings", lambda: (KEY, "gemini-2.5-flash"))
    monkeypatch.setattr(sc, "_get_api_settings", lambda: (KEY, "gemini-3.8-flash"))
    assert any("ভিন্ন মডেল" in w for w in sc.secret_status()["warnings"])


def test_live_check_without_key(monkeypatch):
    monkeypatch.setattr(sc, "_get_gemini_settings", lambda: ("", "m"))
    assert sc.test_gemini_key()["ok"] is False


def test_quoted_key_warns(monkeypatch):
    bad = '"' + KEY + '"'
    monkeypatch.setenv("GEMINI_API_KEY", bad)
    monkeypatch.setattr(sc, "_get_gemini_settings", lambda: (bad, "m"))
    monkeypatch.setattr(sc, "_get_api_settings", lambda: (bad, "m"))
    status = sc.secret_status()
    assert status["gemini_key_format_ok"] is False
    assert any("কোটেশন" in w for w in status["warnings"])

"""ASR engine ordering and ElevenLabs request shape (no network)."""

import io

import pytest

from modules import asr
from modules.dialect_terms import stt_keyterms


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in ("ASR_BACKEND", "ASR_ORDER", "ELEVENLABS_KEYTERMS", "ELEVENLABS_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def test_default_order_is_elevenlabs_gemini_whisper():
    assert asr._engine_order() == ["elevenlabs", "gemini", "whisper"]


def test_asr_order_env_reorders_and_appends_missing(monkeypatch):
    monkeypatch.setenv("ASR_ORDER", "gemini, bogus, gemini")
    assert asr._engine_order() == ["gemini", "elevenlabs", "whisper"]


def test_pinned_backend(monkeypatch):
    monkeypatch.setenv("ASR_BACKEND", "gemini")
    assert asr._engine_order() == ["gemini"]
    monkeypatch.setenv("ASR_BACKEND", "whisper")
    assert asr._engine_order() == ["whisper", "gemini"]


def test_keyterms_within_elevenlabs_limits():
    terms = stt_keyterms()
    assert terms and len(terms) <= 1000
    assert all(len(t) <= 50 and len(t.split()) <= 5 for t in terms)
    assert len(terms) == len(set(terms))


class _Resp:
    status_code = 200

    def json(self):
        return {"text": "ঠিক আছে"}


def test_elevenlabs_sends_model_language_and_keyterms(monkeypatch):
    seen = {}
    monkeypatch.setenv("ELEVENLABS_KEYTERMS", "1")

    def fake_post(url, headers, data, files, timeout):
        seen["data"] = data
        return _Resp()

    monkeypatch.setattr(asr.requests, "post", fake_post)
    text, err = asr._transcribe_with_elevenlabs(b"x", ".wav")
    assert (text, err) == ("ঠিক আছে", None)
    fields = dict(seen["data"])
    assert fields["language_code"] == "ben"
    assert fields["model_id"] == asr.ELEVENLABS_STT_MODEL
    assert [v for k, v in seen["data"] if k == "keyterms"] == stt_keyterms()


def test_keyterms_off_by_default(monkeypatch):
    seen = {}

    def fake_post(url, headers, data, files, timeout):
        seen["data"] = data
        return _Resp()

    monkeypatch.setattr(asr.requests, "post", fake_post)
    asr._transcribe_with_elevenlabs(b"x", ".wav")
    assert not [k for k, _ in seen["data"] if k == "keyterms"]


def test_falls_through_to_next_engine_on_failure(monkeypatch):
    monkeypatch.setattr(asr, "_transcribe_with_elevenlabs", lambda p, s: ("", "boom"))
    monkeypatch.setattr(asr, "_get_gemini_settings", lambda: ("k", "m"))
    monkeypatch.setattr(asr, "_transcribe_with_gemini", lambda p, s: ("জ্বর", None))
    buf = io.BytesIO(b"abc")
    buf.name = "a.wav"
    result = asr.transcribe_audio(buf)
    assert result["success"] and result["debug"]["engine"] == "gemini"
    assert result["debug"]["earlier_engine_errors"] == ["boom"]

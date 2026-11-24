"""Developer-panel helpers: report how Gemini secrets are configured.

Nothing here ever returns the API key itself, only presence, source, length,
and the last four characters (enough to tell two keys apart).
"""

import os

import streamlit as st
from google import genai

from modules.asr import _get_elevenlabs_key, _get_gemini_settings
from modules.llm_extractor import _get_api_settings


def _from_secrets(name: str) -> str:
    try:
        if name in st.secrets:
            return str(st.secrets[name] or "").strip()
    except Exception:
        pass
    return ""


def _mask(key: str) -> str | None:
    if not key:
        return None
    if len(key) <= 8:
        return f"({len(key)} অক্ষর, খুব ছোট)"
    return f"…{key[-4:]} ({len(key)} অক্ষর)"


def secret_status() -> dict:
    """Where the Gemini key/model come from and whether the two modules agree."""
    secrets_key = _from_secrets("GEMINI_API_KEY")
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if secrets_key:
        key, source = secrets_key, "st.secrets (.streamlit/secrets.toml)"
    elif env_key:
        key, source = env_key, "environment variable"
    else:
        key, source = "", "পাওয়া যায়নি"

    asr_key, asr_model = _get_gemini_settings()
    extractor_key, extractor_model = _get_api_settings()

    format_ok = bool(key) and not any(c.isspace() or c in "\"'" for c in key)

    warnings = []
    if not key:
        warnings.append("GEMINI_API_KEY সেট করা নেই — অডিও ও এক্সট্র্যাকশন Gemini ব্যবহার করতে পারবে না।")
    elif not format_ok:
        warnings.append(
            "কী-এর ভেতরে স্পেস বা কোটেশন চিহ্ন আছে — কপি করার সময় বাড়তি অক্ষর ঢুকেছে কিনা দেখুন।"
        )
    if secrets_key and env_key and secrets_key != env_key:
        warnings.append("secrets.toml ও environment-এর GEMINI_API_KEY ভিন্ন; secrets.toml অগ্রাধিকার পাচ্ছে।")
    if asr_model != extractor_model:
        warnings.append(f"অডিও ({asr_model}) ও এক্সট্র্যাকশন ({extractor_model}) ভিন্ন মডেল ব্যবহার করছে।")
    if asr_key != extractor_key:
        warnings.append("অডিও ও এক্সট্র্যাকশন ভিন্ন API key ব্যবহার করছে।")

    return {
        "gemini_key_set": bool(key),
        "gemini_key_source": source,
        "gemini_key_masked": _mask(key),
        "gemini_key_format_ok": format_ok,
        "asr_model": asr_model,
        "extractor_model": extractor_model,
        "elevenlabs_key_set": bool(_get_elevenlabs_key()),
        "elevenlabs_key_masked": _mask(_get_elevenlabs_key()),
        "asr_backend_setting": os.getenv("ASR_BACKEND", "auto").strip().lower(),
        "whisper_model": os.getenv("WHISPER_MODEL", "small").strip() or "small",
        "warnings": warnings,
    }


def test_gemini_key(generate: bool = False) -> dict:
    """Live check. generate=False only asks Google about the model (no quota used);
    generate=True sends a tiny prompt, which counts as one request against quota."""
    key, model = _get_gemini_settings()
    stage = "generate" if generate else "key/model"
    if not key:
        return {"ok": False, "stage": "config", "error": "GEMINI_API_KEY সেট করা নেই।"}
    try:
        client = genai.Client(api_key=key)
        client.models.get(model=model)
        if generate:
            client.models.generate_content(model=model, contents="ok")
    except Exception as exc:  # report, never raise into the UI
        return {"ok": False, "stage": stage, "model": model, "error": str(exc)[:600]}
    return {"ok": True, "stage": stage, "model": model, "error": None}

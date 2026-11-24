"""Session state: defaults, resets, and callbacks that edit the extraction."""

import streamlit as st

from modules.asr import transcribe_audio
from modules.llm_extractor import extract_symptoms
from ui.constants import SYMPTOM_LABELS


def _defaults():
    return {
        "transcript": "",
        "transcript_box": "",
        "extraction": None,
        "result": None,
        "assessment_saved": False,
        "saved_assessment_id": None,
        "last_context_key": None,
        "asked_keys": [],
        "ext_version": 0,
        "sms_sent": False,
        "sms_sent_at": None,
    }


def init_state() -> None:
    for key, value in _defaults().items():
        st.session_state.setdefault(key, value)


def clear_result() -> None:
    """Drop the assessment so it must be re-run after any input change."""
    st.session_state["result"] = None
    st.session_state["assessment_saved"] = False
    st.session_state["saved_assessment_id"] = None
    st.session_state["sms_sent"] = False
    st.session_state["sms_sent_at"] = None


def reset_analysis() -> None:
    """Start over from a new transcript."""
    clear_result()
    st.session_state["extraction"] = None
    st.session_state["asked_keys"] = []
    st.session_state["ext_version"] += 1  # fresh widget keys for the chips


def _sync_symptom_list(ext: dict) -> None:
    free_text = [s for s in ext.get("symptoms") or [] if s not in SYMPTOM_LABELS]
    ext["symptoms"] = [f for f in SYMPTOM_LABELS if ext.get(f) is True] + free_text


def on_chips_change(widget_key: str) -> None:
    """Chip toggled: selected = present, deselected (was present) = denied."""
    ext = st.session_state["extraction"]
    selected = set(st.session_state.get(widget_key) or [])
    for field in SYMPTOM_LABELS:
        if field in selected:
            ext[field] = True
        elif ext.get(field) is True:
            ext[field] = False
    ext["user_confirmed"] = True
    _sync_symptom_list(ext)
    clear_result()


def answer_follow_up(key: str, value) -> None:
    """Record a হ্যাঁ/না/জানি না answer and apply it to the extraction."""
    ext = st.session_state["extraction"]
    st.session_state["asked_keys"].append(key)
    ext.setdefault("follow_up_answers", {})[key] = value
    if key in SYMPTOM_LABELS and value is not None:
        ext[key] = value
        ext["user_confirmed"] = True
        _sync_symptom_list(ext)
        st.session_state["ext_version"] += 1  # re-render chips with new defaults
        clear_result()


def transcribe_answer(audio_key: str, answer_key: str) -> None:
    """Mic answer to a follow-up: transcribe it into the answer text box."""
    audio = st.session_state.get(audio_key)
    if audio is None:
        return
    with st.spinner("উত্তর শোনা হচ্ছে..."):
        transcription = transcribe_audio(audio)
    text = (transcription.get("text") or "").strip()
    if not transcription.get("success") or not text:
        st.session_state["fu_audio_error"] = transcription.get(
            "error", "উত্তরটি বোঝা যায়নি। আবার বলুন অথবা লিখুন।"
        )
        return
    existing = (st.session_state.get(answer_key) or "").strip()
    st.session_state[answer_key] = f"{existing} {text}".strip()


def submit_text_answer(key: str, question: str, answer_key: str, context: dict) -> None:
    """Free-text follow-up answer: add it to the transcript and re-extract.

    Symptom values the user already set (chips / হ্যাঁ-না) are kept; the new
    extraction only fills in what was still unknown.
    """
    answer = (st.session_state.get(answer_key) or "").strip()
    if not answer:
        st.toast("উত্তর লিখুন, অথবা 'এড়িয়ে যান' চাপুন।")
        return

    old = st.session_state["extraction"] or {}
    combined = f"{st.session_state.get('transcript', '').strip()} {answer}".strip()

    with st.spinner("উত্তর বিশ্লেষণ করা হচ্ছে..."):
        new = extract_symptoms(combined, context=context)

    if old.get("user_confirmed"):
        for field in SYMPTOM_LABELS:
            if old.get(field) is not None:
                new[field] = old[field]
        new["user_confirmed"] = True
    for field in ("duration", "severity"):
        if not new.get(field) and old.get(field):
            new[field] = old[field]

    answers = dict(old.get("follow_up_answers") or {})
    answers[key] = answer
    new["follow_up_answers"] = answers
    new.setdefault("follow_up_log", list(old.get("follow_up_log") or []))
    new["follow_up_log"].append({"question": question, "answer": answer})
    _sync_symptom_list(new)

    st.session_state["asked_keys"].append(key)
    st.session_state["transcript"] = combined
    st.session_state["transcript_box"] = combined
    st.session_state["extraction"] = new
    st.session_state["ext_version"] += 1
    clear_result()


def mark_sms_unsent() -> None:
    st.session_state["sms_sent"] = False
    st.session_state["sms_sent_at"] = None

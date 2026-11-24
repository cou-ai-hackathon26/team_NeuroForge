"""Step 1: case details, voice/typed input, and symptom extraction."""

import streamlit as st

from modules.asr import transcribe_audio
from modules.llm_extractor import extract_symptoms
from ui.constants import SPEAKERS, STAGES
from ui.state import clear_result, reset_analysis


def render_case_info() -> dict:
    """Render the case fields and return the context dict used downstream."""
    st.subheader("১. রোগীর তথ্য ও বক্তব্য")

    col1, col2 = st.columns(2)
    speaker = col1.radio("কে কথা বলছেন?", list(SPEAKERS), horizontal=True, key="speaker")
    stage = col2.radio("অবস্থা", list(STAGES), horizontal=True, key="stage")
    pregnancy_status = STAGES[stage]

    weeks = None
    if pregnancy_status == "pregnant":
        weeks = st.number_input(
            "গর্ভাবস্থার কত সপ্তাহ চলছে? জানা না থাকলে ০ দিন",
            min_value=0, max_value=45, value=0, step=1, key="gestational_weeks",
        )

    # Only a health worker can measure BP; a mother speaking for herself skips it.
    bp_sys = bp_dia = 0
    if SPEAKERS[speaker] == "health_worker":
        col3, col4, col5 = st.columns([1, 1, 2])
        bp_sys = col3.number_input(
            "রক্তচাপ (উপরের)", min_value=0, max_value=260, value=0, step=1,
            key="bp_systolic", help="জানা না থাকলে ০ রাখুন",
        )
        bp_dia = col4.number_input(
            "রক্তচাপ (নিচের)", min_value=0, max_value=180, value=0, step=1,
            key="bp_diastolic", help="জানা না থাকলে ০ রাখুন",
        )
    else:
        col5 = st.container()
    village = col5.text_input("গ্রাম / ইউনিয়ন", key="village", placeholder="যেমন: চর রাজিবপুর")

    context = {
        "speaker": SPEAKERS[speaker],
        "pregnancy_status": pregnancy_status,
        "gestational_weeks": int(weeks) if weeks else None,
        "bp_systolic": int(bp_sys) or None,
        "bp_diastolic": int(bp_dia) or None,
        "village": village.strip(),
    }
    _invalidate_on_context_change(context)
    return context


def _invalidate_on_context_change(context: dict) -> None:
    """Clinical fields feed the triage, so a change voids the old result."""
    key = (
        context["pregnancy_status"],
        context["gestational_weeks"],
        context["bp_systolic"],
        context["bp_diastolic"],
    )
    previous = st.session_state["last_context_key"]
    st.session_state["last_context_key"] = key
    if previous is not None and previous != key and st.session_state["result"] is not None:
        clear_result()
        st.info("রোগীর তথ্য পরিবর্তিত হয়েছে। নিচে আবার 'ঝুঁকি মূল্যায়ন করুন' চাপুন।")


def render_speech_input(context: dict) -> None:
    if context["speaker"] == "health_worker":
        st.write("রোগীর সমস্যাগুলো বলুন অথবা লিখুন।")
    else:
        st.write("আসসালামু আলাইকুম। আমি মাতৃকণ্ঠ। আপনার শরীরের কোনো সমস্যা হচ্ছে? আমাকে বলুন।")

    _render_audio_input()

    st.markdown("#### ✍️ বক্তব্যের লেখা")
    transcript = st.text_area(
        "লেখাটি যাচাই করুন এবং প্রয়োজনে সংশোধন করুন",
        height=130,
        key="transcript_box",
        placeholder="সমস্যাটি এখানে লিখুন...",
    )
    st.session_state["transcript"] = transcript

    if st.button("লেখা বিশ্লেষণ করুন", type="primary", width="stretch"):
        _analyze(transcript.strip(), context)


def _render_audio_input() -> None:
    st.markdown("#### 🎙️ অডিও ইনপুট")
    audio = st.audio_input("মাইক্রোফোনে কথা বলুন", key="recorded_audio")
    if audio is None or not st.button("অডিও থেকে লেখা তৈরি করুন", width="stretch"):
        return

    with st.spinner("বাংলা কথা শনাক্ত করা হচ্ছে..."):
        transcription = transcribe_audio(audio)

    st.session_state["asr_debug"] = transcription.get("debug") or {
        "engine": None,
        "error": transcription.get("error"),
    }
    if not transcription.get("success"):
        st.error(transcription.get("error", "অডিও প্রসেস করা যায়নি।"))
        return

    text = transcription.get("text", "").strip()
    if not text:
        st.warning("কোনো নির্ভরযোগ্য লেখা পাওয়া যায়নি। আবার স্পষ্টভাবে কথা বলুন।")
        return

    st.session_state["transcript_box"] = text
    st.session_state["transcript"] = text
    reset_analysis()
    st.success("ট্রান্সক্রিপশন তৈরি হয়েছে। নিচে লেখাটি যাচাই করুন।")


def _analyze(transcript: str, context: dict) -> None:
    if not transcript:
        st.error("আগে কথা বলুন অথবা সমস্যাটি লিখুন।")
        return
    reset_analysis()
    with st.spinner("লক্ষণগুলো বিশ্লেষণ করা হচ্ছে..."):
        st.session_state["extraction"] = extract_symptoms(transcript, context=context)
    st.session_state["transcript"] = transcript

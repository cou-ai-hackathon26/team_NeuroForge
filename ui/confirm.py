"""Step 2: confirm extracted symptoms with chips and a follow-up question."""

import streamlit as st

from modules.conversation import next_follow_up
from modules.triage_engine import assess
from ui.constants import SYMPTOM_LABELS
from ui.state import (
    answer_follow_up,
    clear_result,
    on_chips_change,
    submit_text_answer,
    transcribe_answer,
)


def render_confirm(context: dict) -> None:
    ext = st.session_state["extraction"]
    if ext is None:
        return

    st.divider()
    st.subheader("২. শনাক্ত লক্ষণ নিশ্চিত করুন")
    _render_method_notice(ext.get("extraction_method", "unknown"))
    st.info(f"🗣️ {ext.get('transcript', '')}")

    _render_chips(ext)
    _render_extra_details(ext)
    _render_follow_up(ext, context)

    if st.button("ঝুঁকি মূল্যায়ন করুন", type="primary", width="stretch"):
        clear_result()
        with st.spinner("প্রাথমিক ঝুঁকি মূল্যায়ন করা হচ্ছে..."):
            st.session_state["result"] = assess(ext, context=context)


def _render_method_notice(method: str) -> None:
    if method == "gemini":
        st.success("Gemini AI বিশ্লেষণ সম্পন্ন হয়েছে।")
    elif method == "keyword_fallback":
        st.warning(
            "Gemini AI ব্যবহার করা যায়নি। প্রাথমিক keyword-based fallback ব্যবহার করা হয়েছে। "
            "এই ফলাফল নির্ভরযোগ্য ক্লিনিক্যাল মূল্যায়ন নয়।"
        )
    else:
        st.warning("লক্ষণ শনাক্তকরণ সম্পূর্ণ নির্ভরযোগ্য নয়। স্বাস্থ্যকর্মীর মাধ্যমে তথ্য যাচাই করুন।")


def _render_chips(ext: dict) -> None:
    widget_key = f"chips_{st.session_state['ext_version']}"
    st.pills(
        "লক্ষণ — ভুল হলে চাপ দিয়ে যোগ বা বাদ দিন",
        options=list(SYMPTOM_LABELS),
        selection_mode="multi",
        default=[f for f in SYMPTOM_LABELS if ext.get(f) is True],
        format_func=SYMPTOM_LABELS.get,
        key=widget_key,
        on_change=on_chips_change,
        args=(widget_key,),
    )
    denied = [SYMPTOM_LABELS[f] for f in SYMPTOM_LABELS if ext.get(f) is False]
    if denied:
        st.caption("নেই বলে নিশ্চিত: " + ", ".join(denied))
    st.caption("AI ভুল বুঝতে পারে। চিপ বাছাই না থাকা মানে লক্ষণটি নেই—এমন নয়।")


def _render_extra_details(ext: dict) -> None:
    details = []
    if ext.get("other_symptoms"):
        details.append("অন্যান্য: " + ", ".join(ext["other_symptoms"]))
    if ext.get("duration"):
        details.append(f"সময়কাল: {ext['duration']}")
    if ext.get("severity"):
        details.append(f"তীব্রতা: {ext['severity']}")
    if details:
        st.caption(" · ".join(details))


def _render_follow_up(ext: dict, context: dict) -> None:
    follow_up = next_follow_up(ext, asked_keys=st.session_state["asked_keys"], context=context)
    if not follow_up:
        return

    key, question = follow_up
    st.markdown("#### 💬 আরেকটি প্রশ্ন")
    st.info(question)

    if key in SYMPTOM_LABELS:
        yes, no, unsure = st.columns(3)
        yes.button("হ্যাঁ", key=f"fu_yes_{key}", width="stretch",
                   on_click=answer_follow_up, args=(key, True))
        no.button("না", key=f"fu_no_{key}", width="stretch",
                  on_click=answer_follow_up, args=(key, False))
        unsure.button("জানি না", key=f"fu_unsure_{key}", width="stretch",
                      on_click=answer_follow_up, args=(key, None))
        st.caption("'না' বললে লক্ষণটি তালিকা থেকে বাদ যাবে। নিশ্চিত না হলে 'জানি না' চাপুন।")
    else:
        answer_key = f"fu_text_{key}"
        audio_key = f"fu_audio_{key}"
        st.audio_input("🎙️ মুখে উত্তর দিন", key=audio_key,
                       on_change=transcribe_answer, args=(audio_key, answer_key))
        if st.session_state.get("fu_audio_error"):
            st.warning(st.session_state.pop("fu_audio_error"))
        st.text_input("আপনার উত্তর", key=answer_key,
                      placeholder="যেমন: দুই দিন ধরে, সাথে শ্বাসকষ্টও আছে")
        send, skip = st.columns([2, 1])
        send.button("উত্তর পাঠান", key=f"fu_send_{key}", type="secondary", width="stretch",
                    on_click=submit_text_answer, args=(key, question, answer_key, context))
        skip.button("এড়িয়ে যান", key=f"fu_skip_{key}", width="stretch",
                    on_click=answer_follow_up, args=(key, None))
        st.caption("উত্তরটি মূল বক্তব্যের সাথে যোগ করে আবার বিশ্লেষণ করা হবে।")

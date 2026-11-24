"""Sidebar developer panel: raw extraction / triage data for debugging."""

import streamlit as st

from modules.secret_check import secret_status, test_gemini_key


def render_debug_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🔧 ডেভেলপার তথ্য")
        _render_secret_check()
        asr = st.session_state.get("asr_debug")
        if asr:
            engine = asr.get("engine")
            label = {"gemini": "Gemini", "elevenlabs": "ElevenLabs", "whisper": "Whisper"}.get(engine, "কোনোটিই নয় (ব্যর্থ)")
            st.caption(f"অডিও → লেখা: **{label}**")
            with st.expander("অডিও ট্রান্সক্রিপশন (ASR)"):
                st.json(asr)
        ext = st.session_state.get("extraction")
        result = st.session_state.get("result")
        if ext is None and result is None:
            st.caption("বিশ্লেষণ করার পর এখানে কাঁচা ডেটা দেখা যাবে।")
            return
        if ext is not None:
            with st.expander("লক্ষণ এক্সট্র্যাকশন (JSON)"):
                st.json(ext)
        if result is not None:
            with st.expander("ঝুঁকি মূল্যায়ন (JSON)"):
                st.json(result if isinstance(result, dict) else getattr(result, "__dict__", str(result)))


def _render_secret_check() -> None:
    status = secret_status()
    icon = "✅" if status["gemini_key_set"] and not status["warnings"] else "⚠️"
    with st.expander(f"{icon} Gemini secret যাচাই"):
        for warning in status["warnings"]:
            st.warning(warning)
        st.json(status)
        st.caption("API key নিজে কখনো দেখানো হয় না; শুধু উৎস, দৈর্ঘ্য ও শেষ ৪ অক্ষর।")
        col_a, col_b = st.columns(2)
        if col_a.button("কী/মডেল পরীক্ষা", help="কোটা খরচ হয় না", key="dev_test_key"):
            st.session_state["dev_key_test"] = test_gemini_key(generate=False)
        if col_b.button("জেনারেট পরীক্ষা", help="১টি request খরচ হয়", key="dev_test_gen"):
            st.session_state["dev_key_test"] = test_gemini_key(generate=True)
        test = st.session_state.get("dev_key_test")
        if test:
            (st.success if test["ok"] else st.error)(
                f"{test['stage']}: {'সফল' if test['ok'] else 'ব্যর্থ'}"
            )
            st.json(test)

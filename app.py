"""মাতৃকণ্ঠ / Matrikontho: Streamlit entry point.

Each screen lives in ui/; clinical logic lives in modules/.
"""

import streamlit as st

st.set_page_config(page_title="মাতৃকণ্ঠ | Matrikontho", page_icon="🌸", layout="centered")

from modules.database import init_db  # noqa: E402
from ui.confirm import render_confirm  # noqa: E402
from ui.dashboard import render_dashboard  # noqa: E402
from ui.debug import render_debug_sidebar  # noqa: E402
from ui.header import load_stylesheet, render_header  # noqa: E402
from ui.limitations import render_limitations  # noqa: E402
from ui.record import render_case_info, render_speech_input  # noqa: E402
from ui.referral import render_referral  # noqa: E402
from ui.result import render_result  # noqa: E402
from ui.state import init_state  # noqa: E402

init_db()
init_state()
load_stylesheet()
render_header()

assess_tab, dashboard_tab, limits_tab = st.tabs(
    ["🎙️ নতুন মূল্যায়ন", "📋 স্বাস্থ্যকর্মী ড্যাশবোর্ড", "ℹ️ সীমাবদ্ধতা"]
)

with assess_tab:
    context = render_case_info()          # 1. case details
    render_speech_input(context)          # 1. voice / typed input -> extraction
    render_confirm(context)               # 2. confirm chips + follow-up -> result
    if st.session_state["result"] is not None:
        advice = render_result()          # 3. result card
        render_referral(context, advice)  # 4. referral SMS + save

with dashboard_tab:
    render_dashboard()

with limits_tab:
    render_limitations()

render_debug_sidebar()  # after the flow so it shows this run's data

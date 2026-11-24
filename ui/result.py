"""Step 3: the risk result card and health advice."""

from html import escape

import streamlit as st

from modules.advice_generator import advice_for
from ui.constants import DISCLAIMER, RISK_STYLE


def render_result() -> list:
    """Render the result card. Returns the advice list (saved with the record)."""
    res = st.session_state["result"]

    st.divider()
    st.subheader("৩. মূল্যায়নের ফলাফল")

    level = res.get("risk_level", "UNKNOWN")
    css, icon, label, action = RISK_STYLE.get(level, RISK_STYLE["UNKNOWN"])
    reasons = "".join(f"<li>{escape(r)}</li>" for r in res.get("reasons", []))
    recommendation = escape(res.get("recommendation", ""))

    st.markdown(
        f"""
        <div class="risk-card risk-{css}">
            <div class="risk-label">{icon} {label}</div>
            <div class="risk-action">{action}</div>
            {f'<div class="risk-section-title">কেন?</div><ul>{reasons}</ul>' if reasons else ''}
            {f'<div class="risk-section-title">করণীয়</div><p>{recommendation}</p>' if recommendation else ''}
        </div>
        <div class="risk-disclaimer">{DISCLAIMER}</div>
        """,
        unsafe_allow_html=True,
    )

    if not res.get("assessment_reliable"):
        st.warning("প্রাপ্ত তথ্যের ভিত্তিতে নির্ভরযোগ্য ঝুঁকি মূল্যায়ন করা সম্ভব হয়নি।")

    advice = advice_for(res)
    if advice:
        st.markdown("#### স্বাস্থ্য পরামর্শ")
        for item in advice:
            st.write(f"• {item}")
    return advice

"""Step 4: referral facility, simulated SMS, and saving the record."""

from datetime import datetime

import streamlit as st

from modules.database import save_assessment
from modules.referral_sms import make_sms
from ui.constants import FACILITIES
from ui.state import mark_sms_unsent

REFERRAL_LEVELS = ("HIGH", "MODERATE", "UNKNOWN")


def render_referral(context: dict, advice: list) -> None:
    res = st.session_state["result"]
    ext = st.session_state["extraction"]
    needs_referral = res.get("risk_level") in REFERRAL_LEVELS

    st.divider()
    st.subheader("৪. রেফারেল ও রেকর্ড" if needs_referral else "৪. রেকর্ড")

    facility = None
    if needs_referral:
        facility = st.selectbox(
            "কোথায় রেফার করবেন?", FACILITIES,
            key="referral_facility", on_change=mark_sms_unsent,
        )
    sms = make_sms(res, context=context, extraction=ext, facility=facility)

    if needs_referral:
        _render_sms(sms, facility)

    _render_save(context, ext, res, advice, sms, facility)


def _render_sms(sms: str, facility: str) -> None:
    st.markdown("**📱 SMS প্রিভিউ**")
    st.code(sms, language=None, wrap_lines=True)

    if st.session_state["sms_sent"]:
        st.success(
            f"✅ SMS পাঠানো হয়েছে (সিমুলেটেড) → {facility} · {st.session_state['sms_sent_at']}"
        )
        st.caption("ডেমো: কোনো আসল SMS পাঠানো হয়নি।")
    elif st.button("📤 SMS পাঠান (সিমুলেটেড)", width="stretch"):
        st.session_state["sms_sent"] = True
        st.session_state["sms_sent_at"] = datetime.now().strftime("%H:%M")
        st.toast("রেফারেল SMS পাঠানো হয়েছে (সিমুলেটেড)", icon="📤")
        st.rerun()


def _render_save(context, ext, res, advice, sms, facility) -> None:
    if st.session_state["assessment_saved"]:
        st.success(
            f"এই মূল্যায়নের রেকর্ড সংরক্ষণ করা হয়েছে। ID: {st.session_state['saved_assessment_id']}"
        )
        return

    if st.button("অ্যানোনিমাইজড রেকর্ড সংরক্ষণ করুন", width="stretch"):
        st.session_state["saved_assessment_id"] = save_assessment(
            transcript=st.session_state["transcript"],
            extraction=ext,
            result=res,
            advice=advice,
            sms=sms,
            gestational_weeks=context["gestational_weeks"],
            pregnancy_status=context["pregnancy_status"],
            speaker=context["speaker"],
            village=context["village"],
            bp_systolic=context["bp_systolic"],
            bp_diastolic=context["bp_diastolic"],
            referral_facility=facility,
            sms_sent=st.session_state["sms_sent"],
        )
        st.session_state["assessment_saved"] = True
        st.rerun()

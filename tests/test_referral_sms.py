"""Blood pressure in the referral SMS matches what triage acted on."""

import pytest

from modules.referral_sms import make_sms
from modules.triage_engine import assess

HIGH = {"risk_level": "HIGH", "reasons": ["রক্তচাপ খুব বেশি।"]}


def _ctx(sys_bp, dia_bp):
    return {"pregnancy_status": "pregnant", "bp_systolic": sys_bp, "bp_diastolic": dia_bp}


@pytest.mark.parametrize("sys_bp,dia_bp,shown", [
    (170, 115, "BP: 170/115"),
    (170, None, "BP: 170/?"),
    (None, 115, "BP: ?/115"),
    (170, 0, "BP: 170/?"),
])
def test_sms_shows_known_bp_values(sys_bp, dia_bp, shown):
    assert shown in make_sms(HIGH, context=_ctx(sys_bp, dia_bp))


@pytest.mark.parametrize("sys_bp,dia_bp", [(None, None), (0, 0), ("170", "115"), (-170, -110), (True, True)])
def test_sms_omits_bp_when_no_valid_value(sys_bp, dia_bp):
    assert "BP:" not in make_sms(HIGH, context=_ctx(sys_bp, dia_bp))


def test_single_severe_reading_referral_carries_the_reading():
    """End to end: a lone 170 makes the case HIGH and the SMS must say why."""
    ctx = _ctx(170, None)
    extraction = {
        "transcript": "আমি ভালো আছি",
        "extraction_method": "gemini",
        "extraction_success": True,
        "needs_clarification": False,
    }
    result = assess(extraction, context=ctx)
    assert result["risk_level"] == "HIGH"
    sms = make_sms(result, context=ctx)
    assert "জরুরি" in sms
    assert "BP: 170/?" in sms

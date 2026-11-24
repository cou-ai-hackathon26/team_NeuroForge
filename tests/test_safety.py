from modules.llm_extractor import SYMPTOM_FIELDS
from modules.triage_engine import assess


def test_emergency_cannot_be_overridden_by_uncertainty():
    x = {
        "transcript": "রক্ত যাচ্ছে, ঠিক বুঝতে পারছি না",
        "extraction_method": "keyword_fallback",
        "extraction_success": True,
        "needs_clarification": True,
        **{field: None for field in SYMPTOM_FIELDS},
        "bleeding": True,
    }
    assert assess(x, context={"pregnancy_status": "pregnant"})["risk_level"] == "HIGH"


def test_missing_input_is_never_low():
    assert assess(None)["risk_level"] == "UNKNOWN"
    assert assess({"transcript": "  "})["risk_level"] == "UNKNOWN"

from modules.llm_extractor import SYMPTOM_FIELDS, _fallback_extraction


def test_severe_headache_detected():
    x = _fallback_extraction("আমার প্রচণ্ড মাথাব্যথা করছে")
    assert x["severe_headache"] is True


def test_unmentioned_not_added():
    x = _fallback_extraction("আমি ভালো আছি")
    assert x["other_symptoms"] == []
    assert all(x[f] is not True for f in SYMPTOM_FIELDS)

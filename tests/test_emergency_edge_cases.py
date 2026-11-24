"""Edge cases for emergency detection: Bangla transcript -> extract_symptoms -> assess.

What the backend must guarantee (the safety contract):
  1. A described danger sign -> HIGH + requires_urgent_care.
  2. A case is never labelled LOW unless a reliable extraction found nothing.
  3. A clear denial ("রক্তপাত নেই") must not by itself raise HIGH.

Tests marked xfail(strict=True) are KNOWN GAPS found while writing this file.
They document the right answer; when a gap is fixed the test XPASSes, pytest
reports it as a failure, and the marker should be removed.
"""

import json

import pytest

import modules.llm_extractor as extractor
from modules.llm_extractor import SYMPTOM_FIELDS, extract_symptoms
from modules.triage_engine import RED_FLAGS, assess

PREGNANT = {"pregnancy_status": "pregnant", "gestational_weeks": 32}


def gap(reason):
    return pytest.mark.xfail(strict=True, reason=f"KNOWN GAP: {reason}")


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.setattr(extractor, "_get_api_settings", lambda: ("", "test-model"))


@pytest.fixture
def fake_gemini(monkeypatch):
    """genai.Client returns state['reply'] as the model text; no network."""
    state = {"reply": "{}"}

    class _Models:
        def generate_content(self, model, contents):
            return type("Resp", (), {"text": state["reply"]})()

    class _Client:
        def __init__(self, api_key):
            self.models = _Models()

    monkeypatch.setattr(extractor, "_get_api_settings", lambda: ("fake-key", "test-model"))
    monkeypatch.setattr(extractor.genai, "Client", _Client)
    return state


def gemini_json(**fields):
    body = {field: None for field in SYMPTOM_FIELDS}
    body.update({"symptoms": [], "other_symptoms": [], "notes": ""})
    body.update(fields)
    return json.dumps(body, ensure_ascii=False)


def triage(text, context=PREGNANT):
    extraction = extract_symptoms(text, context=context)
    return extraction, assess(extraction, context=context)


# =============================================================================
# 1. Keyword fallback: phrasings that already work
# =============================================================================

@pytest.mark.parametrize("field,text", [
    ("bleeding", "BLEEDING a lot"),                      # English, uppercase
    ("bleeding", "রক্তপাত শুরু হয়েছে, খুব ভয় লাগছে"),
    ("difficulty_breathing", "নিঃশ্বাস নিতে কষ্ট হচ্ছে"),
    ("convulsions", "রাতে খিচুনি উঠেছিল"),               # spelling without chandrabindu
    ("reduced_fetal_movement", "কাল থেকে বাচ্চা নড়ছে না"),  # "না" is part of the sign
    ("water_breaking", "পানি ভেঙ্গে গেছে"),               # alternate spelling
])
def test_fallback_detects_known_variant(no_api_key, field, text):
    extraction, result = triage(text)
    assert extraction[field] is True
    assert result["risk_level"] == "HIGH"
    assert result["requires_urgent_care"] is True


# =============================================================================
# 2. Keyword fallback: common everyday phrasings, misspellings and
#    transliterations. Anything still unrecognised must land on UNKNOWN.
# =============================================================================

MISSED_PHRASES = [
    ("bleeding", "রক্ত ঝরছে"),
    ("bleeding", "রক্ত বের হচ্ছে"),
    ("bleeding", "ব্লিডিং হচ্ছে"),                         # transliterated English
    ("severe_headache", "প্রচণ্ড মাথাব্যথা"),             # adjective before noun
    ("severe_headache", "মাথাব্যাথা খুব বেশি"),            # common misspelling ্যা
    ("severe_headache", "মাথা খুব ব্যথা করছে"),
    ("blurred_vision", "চোখে অন্ধকার দেখছি"),
    ("blurred_vision", "চোখে কিছু দেখতে পাচ্ছি না"),
    ("difficulty_breathing", "শ্বাস নিতে পারছি না"),
    ("reduced_fetal_movement", "বাচ্চা নড়াচড়া করছে না"),
    ("reduced_fetal_movement", "বাচ্চার নড়াচড়া বন্ধ"),
    ("reduced_fetal_movement", "পেটের বাচ্চা নড়ে না"),
    ("water_breaking", "পানি পড়ছে"),
    ("water_breaking", "পানি ভাঙছে"),
    ("severe_abdominal_pain", "পেটে প্রচণ্ড ব্যথা"),
    ("severe_abdominal_pain", "তলপেটে তীব্র ব্যথা"),
    ("swelling_face_hands", "মুখ-হাত ফোলা"),
    ("convulsions", "fit হয়েছে"),
]


@pytest.mark.parametrize("field,text", MISSED_PHRASES, ids=[t for _, t in MISSED_PHRASES])
def test_fallback_detects_common_phrasing(no_api_key, field, text):
    _, result = triage(text)
    assert result["risk_level"] == "HIGH"


VAGUE_COMPLAINTS = [
    "শরীর খুব খারাপ লাগছে",
    "কেমন যেন লাগছে",
    "মাথাব্যথা",  # plain headache, no severity word: not a red flag on its own
]


@pytest.mark.parametrize("text", VAGUE_COMPLAINTS)
def test_unrecognised_complaint_is_never_low(no_api_key, text):
    """Safety floor: a phrasing the keywords miss must not tell the patient she is fine."""
    _, result = triage(text)
    assert result["risk_level"] == "UNKNOWN"
    assert result["assessment_reliable"] is False


# =============================================================================
# 3. Text formatting noise (ASR / keyboard output)
# =============================================================================

@pytest.mark.parametrize("text", ["রক্ত  যাচ্ছে", "রক্ত\nযাচ্ছে", "রক্ত\tযাচ্ছে"])
def test_extra_whitespace_inside_keyword(no_api_key, text):
    assert triage(text)[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("text", ["শ্বাস‌কষ্ট হচ্ছে", "খিঁ‍চুনি হয়েছে"])
def test_zero_width_characters(no_api_key, text):
    assert triage(text)[1]["risk_level"] == "HIGH"


def test_leading_trailing_whitespace_and_punctuation(no_api_key):
    assert triage("   খিঁচুনি!!!   \n")[1]["risk_level"] == "HIGH"


# =============================================================================
# 4. Negation handling
# =============================================================================

@pytest.mark.parametrize("field,text", [
    ("bleeding", "রক্তপাত হচ্ছে না"),
    ("bleeding", "no bleeding"),
    ("difficulty_breathing", "শ্বাসকষ্ট নাই"),
    ("fever", "জ্বর নেই"),
])
def test_clear_denial_is_not_emergency(no_api_key, field, text):
    extraction, result = triage(text)
    assert extraction[field] is False
    assert result["risk_level"] != "HIGH"


@pytest.mark.parametrize("text", [
    "জ্বর নেই কিন্তু রক্ত যাচ্ছে",
    "শ্বাসকষ্ট নেই কিন্তু খিঁচুনি হয়েছে",
    "জ্বর নেই রক্ত যাচ্ছে",
    # mirror: the other symptom's denial comes AFTER the emergency
    "রক্ত যাচ্ছে, জ্বর নেই",
    "খিঁচুনি হয়েছে কিন্তু শ্বাসকষ্ট নেই",
    "no fever but bleeding",
])
def test_denial_of_other_symptom_does_not_hide_emergency(no_api_key, text):
    assert triage(text)[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("text", [
    "রক্তপাত হচ্ছে, ব্যথা নেই",
    "রক্তপাত হচ্ছে। পেটে ব্যথা নেই",
    "রক্ত যাচ্ছে তবে ব্যথা নেই",
    "bleeding, but no pain",
])
def test_denial_in_next_clause_does_not_hide_emergency(no_api_key, text):
    """A denial never reaches back across a clause break (, । কিন্তু তবে but)."""
    assert triage(text)[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("text,denied,reported", [
    ("জ্বর নেই কিন্তু রক্ত যাচ্ছে", "fever", "bleeding"),
    ("রক্ত যাচ্ছে, জ্বর নেই", "fever", "bleeding"),
    ("শ্বাসকষ্ট নেই কিন্তু খিঁচুনি হয়েছে", "difficulty_breathing", "convulsions"),
])
def test_each_symptom_keeps_its_own_denial(no_api_key, text, denied, reported):
    extraction = extract_symptoms(text, context=PREGNANT)
    assert extraction[denied] is False
    assert extraction[reported] is True


def test_negated_then_positive_mention(no_api_key):
    text = "গতকাল রক্তপাত নেই, কিন্তু আজ সকাল থেকে রক্তপাত হচ্ছে"
    assert triage(text)[1]["risk_level"] == "HIGH"


def test_cannot_is_not_a_denial(no_api_key):
    assert triage("I cannot stop bleeding")[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("field,text", [
    ("convulsions", "খিঁচুনি হয়নি"),
    ("convulsions", "খিঁচুনি হয় নি"),
    ("bleeding", "রক্তপাত হয়নি"),
    ("blurred_vision", "চোখে ঝাপসা দেখছি না"),
    ("convulsions", "খিঁচুনি হয়নি, খিঁচুনি নেই"),
])
def test_past_tense_and_verb_denials(no_api_key, field, text):
    extraction, result = triage(text)
    assert extraction[field] is False
    assert result["risk_level"] != "HIGH"


# =============================================================================
# 5. False positives
# =============================================================================

@pytest.mark.parametrize("text", [
    "blood test was normal",
    "blood pressure check করতে এসেছি",
    "blood sugar ঠিক আছে",
    "blood group জানি না",
    "Blood Report দেখাতে এসেছি",
])
def test_blood_word_without_bleeding(no_api_key, text):
    assert triage(text)[1]["risk_level"] != "HIGH"


@pytest.mark.parametrize("text", [
    "passing blood",
    "blood coming out",
    "blood test normal but now blood is coming",
])
def test_blood_still_detected_outside_benign_phrases(no_api_key, text):
    assert triage(text)[1]["risk_level"] == "HIGH"


def test_bangla_blood_pressure_word_is_not_bleeding(no_api_key):
    extraction, result = triage("রক্তচাপ মাপতে এসেছি")
    assert extraction["bleeding"] is None
    assert result["risk_level"] != "HIGH"


# =============================================================================
# 6. Multiple symptoms and mixed severity
# =============================================================================

def test_red_and_moderate_together_is_high(no_api_key):
    extraction, result = triage("জ্বর আছে আর খিঁচুনি হয়েছে")
    assert extraction["fever"] is True
    assert result["risk_level"] == "HIGH"
    assert "convulsions" in result["matched_flags"]


def test_every_red_flag_at_once(fake_gemini):
    fake_gemini["reply"] = gemini_json(**{k: True for k in RED_FLAGS})
    _, result = triage("সব সমস্যা")
    assert result["risk_level"] == "HIGH"
    assert set(result["matched_flags"]) == set(RED_FLAGS)


def test_fever_alone_via_gemini_is_moderate(fake_gemini):
    fake_gemini["reply"] = gemini_json(fever=True)
    assert triage("জ্বর এসেছে")[1]["risk_level"] == "MODERATE"


def test_fever_alone_via_fallback_is_unknown_not_low(no_api_key):
    assert triage("জ্বর এসেছে")[1]["risk_level"] == "UNKNOWN"


def test_unmapped_symptom_via_gemini_is_moderate_not_low(fake_gemini):
    fake_gemini["reply"] = gemini_json(other_symptoms=["মাথা ঘোরা"])
    assert triage("মাথা ঘোরে")[1]["risk_level"] == "MODERATE"


# =============================================================================
# 7. Gemini path: malformed / wrong model output
#    The patient clearly says "নিচ দিয়ে রক্ত যাচ্ছে" in every case below.
# =============================================================================

BLEEDING_TEXT = "নিচ দিয়ে রক্ত যাচ্ছে"


@pytest.mark.parametrize("reply", [
    "[]",                       # not an object
    "",                         # empty response
    '{"bleeding": tr',          # truncated JSON
    "I am not able to help.",   # prose
])
def test_unparseable_gemini_reply_falls_back_and_detects(fake_gemini, reply):
    fake_gemini["reply"] = reply
    extraction, result = triage(BLEEDING_TEXT)
    assert extraction["extraction_method"] == "keyword_fallback"
    assert result["risk_level"] == "HIGH"


def test_gemini_exception_falls_back_and_detects(monkeypatch):
    class _Boom:
        def __init__(self, api_key):
            raise RuntimeError("network down")

    monkeypatch.setattr(extractor, "_get_api_settings", lambda: ("fake-key", "m"))
    monkeypatch.setattr(extractor.genai, "Client", _Boom)
    assert triage(BLEEDING_TEXT)[1]["risk_level"] == "HIGH"


PARSEABLE_BUT_WRONG = {
    "string_true": gemini_json(bleeding="true"),
    "int_one": gemini_json(bleeding=1),
    "capitalised_key": json.dumps({"Bleeding": True}),
    "empty_object": "{}",
    "all_null": gemini_json(),
    "model_says_false": gemini_json(bleeding=False),
}


@pytest.mark.parametrize("reply", PARSEABLE_BUT_WRONG.values(), ids=PARSEABLE_BUT_WRONG.keys())
def test_wrong_gemini_output_never_downgrades_clear_emergency(fake_gemini, reply):
    fake_gemini["reply"] = reply
    assert triage(BLEEDING_TEXT)[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("reply", PARSEABLE_BUT_WRONG.values(), ids=PARSEABLE_BUT_WRONG.keys())
def test_wrong_gemini_output_is_never_low_for_clear_emergency(fake_gemini, reply):
    fake_gemini["reply"] = reply
    assert triage(BLEEDING_TEXT)[1]["risk_level"] != "LOW"


def test_gemini_all_false_on_healthy_statement_is_low(fake_gemini):
    fake_gemini["reply"] = gemini_json(**{f: False for f in SYMPTOM_FIELDS})
    _, result = triage("আমি ভালো আছি")
    assert result["risk_level"] == "LOW"
    assert result["assessment_reliable"] is True


# =============================================================================
# 8. Blood pressure thresholds (context, not speech)
# =============================================================================

@pytest.mark.parametrize("sys_bp,dia_bp,expected", [
    (160, 100, "HIGH"),
    (120, 110, "HIGH"),
    (159, 109, "MODERATE"),
    (140, 80, "MODERATE"),
    (130, 90, "MODERATE"),
    (139, 89, "LOW"),
    (110, 70, "LOW"),
])
def test_bp_thresholds(fake_gemini, sys_bp, dia_bp, expected):
    fake_gemini["reply"] = gemini_json()
    ctx = {**PREGNANT, "bp_systolic": sys_bp, "bp_diastolic": dia_bp}
    assert triage("আমি ভালো আছি", ctx)[1]["risk_level"] == expected


@pytest.mark.parametrize("sys_bp,dia_bp", [(170, None), (None, 115), (170, 0), (170, "")])
def test_single_severe_bp_value_is_emergency(fake_gemini, sys_bp, dia_bp):
    fake_gemini["reply"] = gemini_json()
    ctx = {**PREGNANT, "bp_systolic": sys_bp, "bp_diastolic": dia_bp}
    assert triage("আমি ভালো আছি", ctx)[1]["risk_level"] == "HIGH"


@pytest.mark.parametrize("sys_bp,dia_bp,expected", [
    (145, None, "MODERATE"),
    (None, 95, "MODERATE"),
    (130, None, "LOW"),
])
def test_single_bp_value_is_graded(fake_gemini, sys_bp, dia_bp, expected):
    fake_gemini["reply"] = gemini_json()
    ctx = {**PREGNANT, "bp_systolic": sys_bp, "bp_diastolic": dia_bp}
    assert triage("আমি ভালো আছি", ctx)[1]["risk_level"] == expected


def test_single_bp_reason_shows_missing_value(fake_gemini):
    fake_gemini["reply"] = gemini_json()
    ctx = {**PREGNANT, "bp_systolic": 170, "bp_diastolic": None}
    reasons = triage("আমি ভালো আছি", ctx)[1]["reasons"]
    assert any("170/?" in r for r in reasons)


@pytest.mark.parametrize("sys_bp,dia_bp", [("170", "115"), (-170, -110), (0, 0), (None, None), (True, True)])
def test_invalid_bp_is_ignored_without_crashing(fake_gemini, sys_bp, dia_bp):
    fake_gemini["reply"] = gemini_json()
    ctx = {**PREGNANT, "bp_systolic": sys_bp, "bp_diastolic": dia_bp}
    assert triage("আমি ভালো আছি", ctx)[1]["risk_level"] == "LOW"


def test_severe_bp_with_fallback_is_still_high(no_api_key):
    ctx = {**PREGNANT, "bp_systolic": 170, "bp_diastolic": 115}
    assert triage("আমি ভালো আছি", ctx)[1]["risk_level"] == "HIGH"


# =============================================================================
# 9. Pregnancy context never suppresses a red flag
# =============================================================================

@pytest.mark.parametrize("ctx", [
    {"pregnancy_status": "pregnant", "gestational_weeks": 12},
    {"pregnancy_status": "postpartum"},
    {"pregnancy_status": "not_pregnant"},
    {"pregnancy_status": "unknown"},
    {},
    None,
    "garbage",
])
def test_bleeding_is_high_in_every_context(no_api_key, ctx):
    extraction = extract_symptoms("রক্তপাত হচ্ছে", context=ctx)
    assert assess(extraction, context=ctx)["risk_level"] == "HIGH"


def test_preterm_water_breaking_reason_mentions_weeks(no_api_key):
    ctx = {"pregnancy_status": "pregnant", "gestational_weeks": 30}
    _, result = triage("পানি ভেঙে গেছে", ctx)
    assert result["risk_level"] == "HIGH"
    assert any("30" in r for r in result["reasons"])


def test_postpartum_bleeding_reason(no_api_key):
    ctx = {"pregnancy_status": "postpartum"}
    _, result = triage("রক্তপাত হচ্ছে", ctx)
    assert any("প্রসবের পর" in r for r in result["reasons"])


# =============================================================================
# 10. Empty / garbage input: never LOW, never crash
# =============================================================================

@pytest.mark.parametrize("text", ["", "   ", "আ", None, "...", "১২৩৪৫", "😀😀😀"])
def test_empty_or_garbage_input_is_never_low(no_api_key, text):
    _, result = triage(text)
    assert result["risk_level"] == "UNKNOWN"
    assert result["requires_urgent_care"] is False


@pytest.mark.parametrize("extraction", [None, "text", 42, [], {"transcript": "  "}])
def test_assess_malformed_extraction_is_unknown(extraction):
    assert assess(extraction)["risk_level"] == "UNKNOWN"


def test_flags_not_strict_true_are_ignored():
    """Only the boolean True raises a flag; truthy look-alikes do not."""
    for value in ("true", 1, "yes", [True]):
        ext = {"transcript": "x", "extraction_method": "gemini", "bleeding": value}
        assert assess(ext)["risk_level"] != "HIGH"


def test_very_long_statement_with_emergency_at_the_end(no_api_key):
    text = "আমি ভালো আছি। " * 300 + "কিন্তু এখন খিঁচুনি হচ্ছে"
    assert triage(text)[1]["risk_level"] == "HIGH"

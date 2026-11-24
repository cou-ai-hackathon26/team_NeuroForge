"""End-to-end emergency detection: Bangla transcript -> extract_symptoms -> assess.

Covers every red flag in data/clinical_rules.json through both extraction paths:
- keyword fallback (no API key), using realistic patient phrasings
- Gemini path, with the API client faked so no network call is made
"""

import json
import unicodedata

import pytest

import modules.llm_extractor as extractor
from modules.llm_extractor import SYMPTOM_FIELDS, extract_symptoms
from modules.triage_engine import RED_FLAGS, assess

PREGNANT = {"pregnancy_status": "pregnant", "gestational_weeks": 32}

# Several natural ways a patient might report each emergency.
EMERGENCY_PHRASES = {
    "bleeding": [
        "আমার রক্তপাত হচ্ছে",
        "নিচ দিয়ে রক্ত যাচ্ছে",
        "সকাল থেকে রক্ত পড়ছে",
    ],
    "severe_headache": [
        "আমার তীব্র মাথাব্যথা হচ্ছে",
        "মাথা প্রচণ্ড ব্যথা করছে",
        "অনেক মাথা ব্যথা, সহ্য করতে পারছি না",
    ],
    "blurred_vision": [
        "চোখে ঝাপসা দেখছি",
        "হঠাৎ চোখে কম দেখি",
    ],
    "swelling_face_hands": [
        "আমার মুখ ফুলে গেছে",
        "হাত ফুলে গেছে",
        "হঠাৎ ফুলে গেছি",
    ],
    "severe_abdominal_pain": [
        "তীব্র পেট ব্যথা হচ্ছে",
        "পেটে অনেক ব্যথা",
        "প্রচণ্ড পেট ব্যথা করছে",
    ],
    "difficulty_breathing": [
        "আমার শ্বাসকষ্ট হচ্ছে",
        "শ্বাস নিতে কষ্ট হচ্ছে",
        "দম নিতে কষ্ট হচ্ছে",
    ],
    "convulsions": [
        "একটু আগে খিঁচুনি হয়েছে",
        "খিচুনি হচ্ছিল",
    ],
    "reduced_fetal_movement": [
        "বাচ্চা কম নড়ছে",
        "বাচ্চার নড়াচড়া কম মনে হচ্ছে",
        "আজ সারাদিন বাচ্চা নড়ছে না",
    ],
    "water_breaking": [
        "পানি ভেঙে গেছে",
        "গর্ভের পানি বের হচ্ছে",
    ],
}

# Explicit denials must not raise an emergency on their own.
DENIALS = {
    "bleeding": "রক্তপাত নেই",
    "convulsions": "খিঁচুনি হয়নি, খিঁচুনি নেই",
    "difficulty_breathing": "শ্বাসকষ্ট নেই",
    "blurred_vision": "চোখে ঝাপসা দেখি না, ঝাপসা নেই",
    "bleeding#2": "রক্ত পড়ছে না",
    "bleeding#3": "রক্ত যাচ্ছে না",
}


def _cases():
    for field, phrases in EMERGENCY_PHRASES.items():
        for phrase in phrases:
            yield pytest.param(field, phrase, id=f"{field}:{phrase}")


@pytest.fixture
def no_api_key(monkeypatch):
    monkeypatch.setattr(extractor, "_get_api_settings", lambda: ("", "test-model"))


@pytest.fixture
def fake_gemini(monkeypatch):
    """Make genai.Client return a canned JSON reply set per test."""
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


def _gemini_reply(**flags):
    body = {field: None for field in SYMPTOM_FIELDS}
    body.update(flags)
    body.update({"symptoms": [], "other_symptoms": [], "notes": ""})
    return json.dumps(body, ensure_ascii=False)


def test_phrase_table_covers_every_red_flag():
    assert set(EMERGENCY_PHRASES) == set(RED_FLAGS)


# --- keyword fallback path ---------------------------------------------------

@pytest.mark.parametrize("field,phrase", list(_cases()))
def test_fallback_detects_emergency(no_api_key, field, phrase):
    extraction = extract_symptoms(phrase, context=PREGNANT)
    assert extraction["extraction_method"] == "keyword_fallback"
    assert extraction[field] is True, f"{field} not detected in: {phrase}"

    result = assess(extraction, context=PREGNANT)
    assert result["risk_level"] == "HIGH"
    assert result["requires_urgent_care"] is True
    assert RED_FLAGS[field]["id"] in result["rule_ids"]


@pytest.mark.parametrize("field,phrase", list(_cases()))
def test_fallback_detects_emergency_in_nfd_unicode(no_api_key, field, phrase):
    """ASR/keyboards may emit decomposed ড় / ঢ় / য় (consonant + nukta)."""
    decomposed = unicodedata.normalize("NFD", phrase)
    extraction = extract_symptoms(decomposed, context=PREGNANT)
    assert assess(extraction, context=PREGNANT)["risk_level"] == "HIGH"


def test_fallback_detects_multiple_emergencies_together(no_api_key):
    text = "রক্ত যাচ্ছে, খিঁচুনি হয়েছে আর শ্বাসকষ্ট হচ্ছে"
    result = assess(extract_symptoms(text, context=PREGNANT), context=PREGNANT)
    assert result["risk_level"] == "HIGH"
    assert {"bleeding", "convulsions", "difficulty_breathing"} <= set(result["matched_flags"])


def test_emergency_buried_in_long_statement(no_api_key):
    text = (
        "আমি আট মাসের গর্ভবতী, গতকাল বাজারে গিয়েছিলাম, খাওয়া দাওয়া ঠিক আছে, "
        "কিন্তু আজ সকাল থেকে চোখে ঝাপসা দেখছি"
    )
    assert assess(extract_symptoms(text, context=PREGNANT), context=PREGNANT)["risk_level"] == "HIGH"


@pytest.mark.parametrize("field,phrase", list(DENIALS.items()))
def test_fallback_denial_is_not_emergency(no_api_key, field, phrase):
    field = field.split("#")[0]
    extraction = extract_symptoms(phrase, context=PREGNANT)
    assert extraction[field] is not True
    assert assess(extraction, context=PREGNANT)["risk_level"] != "HIGH"


# --- Gemini path (API faked) -------------------------------------------------

@pytest.mark.parametrize("field", sorted(RED_FLAGS))
def test_gemini_flag_reaches_high(fake_gemini, field):
    fake_gemini["reply"] = _gemini_reply(**{field: True})
    extraction = extract_symptoms("রোগীর বক্তব্য", context=PREGNANT)
    assert extraction["extraction_method"] == "gemini"

    result = assess(extraction, context=PREGNANT)
    assert result["risk_level"] == "HIGH"
    assert result["rule_ids"] == [RED_FLAGS[field]["id"]]


def test_gemini_reply_in_markdown_fence_still_detected(fake_gemini):
    fake_gemini["reply"] = "```json\n" + _gemini_reply(convulsions=True) + "\n```"
    assert assess(extract_symptoms("খিঁচুনি", context=PREGNANT))["risk_level"] == "HIGH"


def test_gemini_non_boolean_value_is_not_trusted(fake_gemini):
    fake_gemini["reply"] = _gemini_reply(bleeding="yes")
    extraction = extract_symptoms("কিছু একটা", context=PREGNANT)
    assert extraction["bleeding"] is None


def test_gemini_garbage_falls_back_to_keywords_and_still_detects(fake_gemini):
    fake_gemini["reply"] = "sorry, I cannot help"
    extraction = extract_symptoms("নিচ দিয়ে রক্ত যাচ্ছে", context=PREGNANT)
    assert extraction["extraction_method"] == "keyword_fallback"
    assert assess(extraction, context=PREGNANT)["risk_level"] == "HIGH"


# --- dialect: keyword net also scans Gemini's standard-Bangla rewrite -------

DIALECT_TRANSCRIPT = "আঞ্চলিক ভাষার বক্তব্য যা কোনো keyword মেলে না"


def test_standard_bangla_rewrite_reaches_keyword_net(fake_gemini):
    body = json.loads(_gemini_reply())
    body["standard_bangla"] = "সকাল থেকে রক্ত পড়ছে"
    fake_gemini["reply"] = json.dumps(body, ensure_ascii=False)
    extraction = extract_symptoms(DIALECT_TRANSCRIPT, context=PREGNANT)
    assert extraction["standard_bangla"] == "সকাল থেকে রক্ত পড়ছে"
    assert extraction["bleeding"] is True
    assert "bleeding" in extraction["keyword_overrides"]
    assert assess(extraction, context=PREGNANT)["risk_level"] == "HIGH"


def test_standard_bangla_denial_adds_no_flag(fake_gemini):
    body = json.loads(_gemini_reply())
    body["standard_bangla"] = "রক্ত পড়ছে না"
    fake_gemini["reply"] = json.dumps(body, ensure_ascii=False)
    extraction = extract_symptoms(DIALECT_TRANSCRIPT, context=PREGNANT)
    assert extraction["bleeding"] is not True


# --- blood pressure emergency (from context, not speech) --------------------

@pytest.mark.parametrize("sys_bp,dia_bp", [(160, 100), (150, 110), (180, 120)])
def test_severe_blood_pressure_is_emergency(fake_gemini, sys_bp, dia_bp):
    fake_gemini["reply"] = _gemini_reply()
    ctx = {**PREGNANT, "bp_systolic": sys_bp, "bp_diastolic": dia_bp}
    result = assess(extract_symptoms("আমি ভালো আছি", context=ctx), context=ctx)
    assert result["risk_level"] == "HIGH"
    assert "DEMO-HIGH-BP" in result["rule_ids"]

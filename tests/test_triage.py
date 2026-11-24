import json

import pytest

from modules.llm_extractor import SYMPTOM_FIELDS
from modules.triage_engine import (
    MODERATE_FLAGS,
    RED_FLAGS,
    ClinicalRulesError,
    assess,
    load_clinical_rules,
)


def ext(method="gemini", other=None, **symptoms):
    data = {
        "transcript": "পরীক্ষামূলক বক্তব্য",
        "extraction_method": method,
        "extraction_success": True,
        "needs_clarification": False,
        "other_symptoms": other or [],
    }
    data.update({field: None for field in SYMPTOM_FIELDS})
    data.update(symptoms)
    return data


@pytest.mark.parametrize("field", sorted(RED_FLAGS))
def test_each_red_flag_alone_is_high(field):
    result = assess(ext(**{field: True}))
    assert result["risk_level"] == "HIGH"
    assert result["requires_urgent_care"] is True
    assert result["rule_ids"] == [RED_FLAGS[field]["id"]]


def test_red_flag_from_keyword_fallback_is_still_high():
    assert assess(ext(method="keyword_fallback", bleeding=True))["risk_level"] == "HIGH"


def test_fever_is_moderate():
    result = assess(ext(fever=True))
    assert result["risk_level"] == "MODERATE"
    assert result["rule_ids"] == [MODERATE_FLAGS["fever"]["id"]]


def test_unmapped_symptom_is_moderate():
    assert assess(ext(other=["মাথা ঘোরা"]))["risk_level"] == "MODERATE"


def test_denied_symptoms_are_low():
    assert assess(ext(bleeding=False, convulsions=False))["risk_level"] == "LOW"


def test_fallback_without_red_flags_is_unknown_not_low():
    assert assess(ext(method="keyword_fallback"))["risk_level"] == "UNKNOWN"


def test_needs_clarification_is_unknown_not_low():
    assert assess(ext(needs_clarification=True))["risk_level"] == "UNKNOWN"


@pytest.mark.parametrize("bp,level", [((165, 95), "HIGH"), ((120, 112), "HIGH"),
                                      ((145, 85), "MODERATE"), ((118, 76), "LOW")])
def test_blood_pressure_thresholds(bp, level):
    ctx = {"bp_systolic": bp[0], "bp_diastolic": bp[1]}
    assert assess(ext(), context=ctx)["risk_level"] == level


# --- rules file validation ---------------------------------------------------

def test_shipped_rules_cover_every_extractor_field():
    red, moderate = load_clinical_rules()
    assert set(red) | set(moderate) == set(SYMPTOM_FIELDS)


def _write_rules(tmp_path, red, moderate):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"red_flags": red, "moderate_flags": moderate}), encoding="utf-8")
    return path


def _entry(i):
    return {"id": f"T-{i}", "reason": "কারণ"}


def test_rules_reject_unknown_field(tmp_path):
    red = {f: _entry(i) for i, f in enumerate(SYMPTOM_FIELDS)}
    red["vaginal_bleeding"] = _entry(99)
    with pytest.raises(ClinicalRulesError, match="vaginal_bleeding"):
        load_clinical_rules(_write_rules(tmp_path, red, {"fever": _entry(0)}))


def test_rules_reject_unassigned_field(tmp_path):
    red = {f: _entry(i) for i, f in enumerate(SYMPTOM_FIELDS) if f not in ("bleeding", "fever")}
    with pytest.raises(ClinicalRulesError, match="bleeding"):
        load_clinical_rules(_write_rules(tmp_path, red, {"fever": _entry(0)}))


def test_rules_reject_field_in_both_tiers(tmp_path):
    red = {f: _entry(i) for i, f in enumerate(SYMPTOM_FIELDS)}
    with pytest.raises(ClinicalRulesError, match="both tiers"):
        load_clinical_rules(_write_rules(tmp_path, red, {"fever": _entry(0)}))


def test_rules_reject_legacy_schema(tmp_path):
    path = tmp_path / "rules.json"
    path.write_text(json.dumps({"high": {"vaginal_bleeding": "DEMO-HIGH-01"}}), encoding="utf-8")
    with pytest.raises(ClinicalRulesError):
        load_clinical_rules(path)

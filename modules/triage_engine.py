import json
from pathlib import Path

from modules.llm_extractor import SYMPTOM_FIELDS

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "clinical_rules.json"


class ClinicalRulesError(ValueError):
    """Raised when the clinical rules file is missing or malformed."""


def _parse_tier(raw, tier):
    entries = raw.get(tier)
    if not isinstance(entries, dict) or not entries:
        raise ClinicalRulesError(f"'{tier}' must be a non-empty object")
    parsed = {}
    for key, entry in entries.items():
        if key not in SYMPTOM_FIELDS:
            raise ClinicalRulesError(f"{tier}.{key}: not a symptom field the extractor produces")
        if not isinstance(entry, dict):
            raise ClinicalRulesError(f"{tier}.{key}: must be an object with 'id' and 'reason'")
        rule_id, reason = entry.get("id"), entry.get("reason")
        if not isinstance(rule_id, str) or not rule_id.strip():
            raise ClinicalRulesError(f"{tier}.{key}: missing 'id'")
        if not isinstance(reason, str) or not reason.strip():
            raise ClinicalRulesError(f"{tier}.{key}: missing 'reason'")
        parsed[key] = {"id": rule_id.strip(), "reason": reason.strip()}
    return parsed


def load_clinical_rules(path=RULES_PATH):
    """
    Load and validate the flag tiers from the clinical rules file.

    Fails loudly instead of falling back: a silently ignored rules file once
    hid a schema mismatch. Every extractor symptom field must be assigned to
    exactly one tier, otherwise a detected symptom could be ignored and the
    case scored LOW.
    """
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ClinicalRulesError(f"cannot read {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ClinicalRulesError("rules file must contain a JSON object")

    red = _parse_tier(raw, "red_flags")
    moderate = _parse_tier(raw, "moderate_flags")

    overlap = set(red) & set(moderate)
    if overlap:
        raise ClinicalRulesError(f"in both tiers: {sorted(overlap)}")
    unassigned = set(SYMPTOM_FIELDS) - set(red) - set(moderate)
    if unassigned:
        raise ClinicalRulesError(f"symptom fields with no tier: {sorted(unassigned)}")
    return red, moderate


RED_FLAGS, MODERATE_FLAGS = load_clinical_rules()


def _format_flag_reason(key, default_desc, pregnancy_status, gestational_weeks):
    if key == "bleeding":
        if pregnancy_status == "pregnant":
            return "গর্ভাবস্থায় রক্তপাতের কথা জানিয়েছেন।"
        if pregnancy_status == "postpartum":
            return "প্রসবের পর রক্তপাতের কথা জানিয়েছেন।"
        if pregnancy_status == "not_pregnant":
            return "অস্বাভাবিক রক্তপাতের কথা জানিয়েছেন।"
        return "রক্তপাতের কথা জানিয়েছেন (গর্ভাবস্থার তথ্য নিশ্চিত নয়)।"

    if key == "water_breaking" and isinstance(gestational_weeks, int) and 0 < gestational_weeks < 37:
        return f"নির্ধারিত সময়ের আগে ({gestational_weeks} সপ্তাহে) গর্ভের পানি বের হওয়ার কথা জানিয়েছেন।"

    if key == "reduced_fetal_movement" and isinstance(gestational_weeks, int) and gestational_weeks > 0:
        return f"{gestational_weeks} সপ্তাহে শিশুর নড়াচড়া কমে যাওয়ার কথা জানিয়েছেন।"

    return default_desc


def _bp_flags(context):
    """Return (red_reasons, moderate_reasons) from an optional BP reading in context.

    Thresholds follow the common severe (>=160/110) and raised (>=140/90)
    cut-offs. Demo rule only; not a validated protocol.

    Each value is graded on its own, so one known severe value is enough
    even when the other was left blank (the form stores blank as None).
    """
    if not isinstance(context, dict):
        return [], []

    def _valid(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    sys_bp = _valid(context.get("bp_systolic"))
    dia_bp = _valid(context.get("bp_diastolic"))
    if sys_bp is None and dia_bp is None:
        return [], []

    reading = f"{sys_bp or '?'}/{dia_bp or '?'}"
    if (sys_bp or 0) >= 160 or (dia_bp or 0) >= 110:
        return [f"রক্তচাপ খুব বেশি ({reading} mmHg)।"], []
    if (sys_bp or 0) >= 140 or (dia_bp or 0) >= 90:
        return [], [f"রক্তচাপ বেশি ({reading} mmHg)।"]
    return [], []


def assess(extraction, context=None):
    """
    Assign a screening priority from extracted symptoms and optional pregnancy context.

    This is not a medical diagnosis or a validated clinical protocol.
    """
    if not isinstance(extraction, dict):
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["লক্ষণসংক্রান্ত তথ্য পাওয়া যায়নি।"],
            "recommendation": (
                "স্বাস্থ্যকর্মীর সঙ্গে কথা বলুন। "
                "তথ্য না পাওয়াকে কম ঝুঁকি হিসেবে ধরা যাবে না।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    transcript = extraction.get("transcript", "")
    if not isinstance(transcript, str) or not transcript.strip():
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["কোনো বক্তব্য পাওয়া যায়নি।"],
            "recommendation": "আবার বক্তব্য রেকর্ড করুন অথবা স্বাস্থ্যকর্মীর সাহায্য নিন।",
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    ctx = context if isinstance(context, dict) else {}
    pregnancy_status = ctx.get("pregnancy_status", "unknown")
    gestational_weeks = ctx.get("gestational_weeks")

    matched_red_keys = [
        key for key in RED_FLAGS if extraction.get(key) is True
    ]
    found_red_flags = [
        _format_flag_reason(key, RED_FLAGS[key]["reason"], pregnancy_status, gestational_weeks)
        for key in matched_red_keys
    ]
    red_rule_ids = [RED_FLAGS[key]["id"] for key in matched_red_keys]

    matched_moderate_keys = [
        key for key in MODERATE_FLAGS if extraction.get(key) is True
    ]
    found_moderate_flags = [
        MODERATE_FLAGS[key]["reason"] for key in matched_moderate_keys
    ]
    moderate_rule_ids = [MODERATE_FLAGS[key]["id"] for key in matched_moderate_keys]

    bp_red, bp_moderate = _bp_flags(ctx)
    if bp_red:
        found_red_flags.extend(bp_red)
        matched_red_keys.append("high_bp")
        red_rule_ids.append("DEMO-HIGH-BP")
    if bp_moderate:
        found_moderate_flags.extend(bp_moderate)
        matched_moderate_keys.append("raised_bp")
        moderate_rule_ids.append("DEMO-MOD-BP")

    other_symptoms = [
        s.strip()
        for s in (extraction.get("other_symptoms") or [])
        if isinstance(s, str) and s.strip()
    ]

    # Any identified warning sign receives HIGH priority—even if extracted via fallback.
    if found_red_flags:
        return {
            "risk_level": "HIGH",
            "reasons": found_red_flags,
            "matched_flags": matched_red_keys,
            "rule_ids": red_rule_ids,
            "recommendation": (
                "দেরি না করে নিকটস্থ হাসপাতাল বা জরুরি মাতৃস্বাস্থ্য "
                "সেবাকেন্দ্রে যান। সম্ভব হলে একজন সহায়তাকারীকে সঙ্গে নিন।"
            ),
            "requires_urgent_care": True,
            "assessment_reliable": True,
        }

    # A fallback extraction is not sufficient to declare LOW or MODERATE safety.
    if extraction.get("extraction_method") != "gemini":
        return {
            "risk_level": "UNKNOWN",
            "reasons": [
                "স্বয়ংক্রিয় লক্ষণ শনাক্তকরণ নির্ভরযোগ্যভাবে সম্পন্ন হয়নি।",
                *found_moderate_flags,
            ],
            "matched_flags": matched_moderate_keys,
            "recommendation": (
                "লক্ষণগুলো স্বাস্থ্যকর্মীকে সরাসরি জানান। "
                "প্রয়োজনে আবার স্পষ্ট করে বক্তব্য দিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    # A successful extraction with moderate symptoms or unmapped symptoms needs review.
    if found_moderate_flags or other_symptoms:
        reasons = list(found_moderate_flags)
        if other_symptoms:
            reasons.append(
                f"অতিরিক্ত উপসর্গ উল্লেখ করেছেন: {', '.join(other_symptoms)}।"
            )

        return {
            "risk_level": "MODERATE",
            "reasons": reasons,
            "matched_flags": matched_moderate_keys,
            "rule_ids": moderate_rule_ids,
            "recommendation": (
                "আজই একজন স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন। "
                "অবস্থা খারাপ হলে জরুরি চিকিৎসা নিন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": True,
        }

    # Uncertain or incomplete extraction must not be labelled LOW.
    if extraction.get("needs_clarification") or extraction.get("extraction_success") is False:
        return {
            "risk_level": "UNKNOWN",
            "reasons": ["আরও তথ্য প্রয়োজন।"],
            "matched_flags": [],
            "recommendation": (
                "আরও বিস্তারিত তথ্য দিন অথবা স্বাস্থ্যকর্মীর সঙ্গে কথা বলুন।"
            ),
            "requires_urgent_care": False,
            "assessment_reliable": False,
        }

    low_reasons = [
        "প্রদত্ত বক্তব্যে এই প্রাথমিক স্ক্রিনিংয়ের সতর্কতামূলক "
        "লক্ষণ শনাক্ত হয়নি।"
    ]
    if pregnancy_status == "unknown":
        low_reasons.append(
            "গর্ভাবস্থার তথ্য নিশ্চিত করা হয়নি—প্রয়োজনে স্বাস্থ্যকর্মীর মাধ্যমে যাচাই করুন।"
        )

    return {
        "risk_level": "LOW",
        "reasons": low_reasons,
        "matched_flags": [],
        "recommendation": (
            "নিয়মিত ANC চেকআপ চালিয়ে যান। নতুন বা উদ্বেগজনক কোনো "
            "লক্ষণ দেখা দিলে দ্রুত স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন।"
        ),
        "requires_urgent_care": False,
        "assessment_reliable": True,
    }

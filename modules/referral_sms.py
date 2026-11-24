def _format_pregnancy_summary(context):
    if not isinstance(context, dict):
        return ""

    status = context.get("pregnancy_status")
    weeks = context.get("gestational_weeks")

    parts = []
    if status == "pregnant":
        parts.append("গর্ভবতী")
    elif status == "postpartum":
        parts.append("প্রসব-পরবর্তী")
    elif status == "not_pregnant":
        parts.append("গর্ভবতী নন")

    if isinstance(weeks, int) and weeks > 0:
        parts.append(f"{weeks} সপ্তাহ")

    return f" ({', '.join(parts)})" if parts else ""


def _format_case_details(context):
    if not isinstance(context, dict):
        return ""
    parts = []
    village = context.get("village")
    if isinstance(village, str) and village.strip():
        parts.append(f"এলাকা: {village.strip()}")
    # Same rule as triage: one known value is shown, the blank one as "?",
    # so a referral triggered by a single severe reading still carries it.
    def _valid(value):
        return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None

    sys_bp = _valid(context.get("bp_systolic"))
    dia_bp = _valid(context.get("bp_diastolic"))
    if sys_bp is not None or dia_bp is not None:
        parts.append(f"BP: {sys_bp or '?'}/{dia_bp or '?'}")
    return f" {'; '.join(parts)}।" if parts else ""


def _format_reasons_summary(result, extraction):
    if isinstance(result, dict):
        reasons = result.get("reasons")
        if isinstance(reasons, list):
            cleaned = [r.strip() for r in reasons if isinstance(r, str) and r.strip()]
            if cleaned:
                return f" কারণ: {' / '.join(cleaned[:2])}"

    if isinstance(extraction, dict):
        symptoms = extraction.get("symptoms")
        if isinstance(symptoms, list):
            cleaned = [s.strip() for s in symptoms if isinstance(s, str) and s.strip()]
            if cleaned:
                return f" লক্ষণ: {', '.join(cleaned[:3])}।"

    return ""


def make_sms(
    result,
    patient_name="রোগী",
    phone_number="",
    context=None,
    extraction=None,
    facility=None,
):
    """
    Generate a referral SMS draft. No SMS is actually sent.
    This is a screening summary, not a medical diagnosis.
    """
    clean_name = (
        patient_name.strip()
        if isinstance(patient_name, str) and patient_name.strip()
        else "রোগী"
    )

    if not isinstance(result, dict):
        return (
            f"মাতৃকণ্ঠ রেফারেল (যাচাই প্রয়োজন): {clean_name}। "
            "রোগীর তথ্য যাচাই করা প্রয়োজন। স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন। "
            "এটি একটি প্রাথমিক স্ক্রিনিং বার্তা, চিকিৎসকের রোগনির্ণয় নয়।"
        )

    level = str(result.get("risk_level", "UNKNOWN")).upper()

    if level == "HIGH":
        urgency = "জরুরি"
        instruction = "দ্রুত নিকটস্থ হাসপাতালে যাওয়ার পরামর্শ দেওয়া হয়েছে।"
    elif level == "MODERATE":
        urgency = "দ্রুত পরামর্শ"
        instruction = "আজই স্বাস্থ্যকর্মী বা চিকিৎসকের সঙ্গে যোগাযোগ করুন।"
    elif level == "LOW":
        urgency = "নিয়মিত"
        instruction = "নিয়মিত চেকআপ চালিয়ে যান।"
    else:
        urgency = "যাচাই প্রয়োজন"
        instruction = "স্বাস্থ্যকর্মীর মাধ্যমে রোগীর অবস্থা যাচাই করুন।"

    preg_tag = _format_pregnancy_summary(context)
    details = _format_reasons_summary(result, extraction) if level != "LOW" else ""
    contact_note = (
        f" যোগাযোগ: {phone_number.strip()}।"
        if isinstance(phone_number, str) and phone_number.strip()
        else ""
    )

    case_details = _format_case_details(context)
    facility_note = (
        f" রেফার: {facility.strip()}।"
        if isinstance(facility, str) and facility.strip()
        else ""
    )

    return (
        f"মাতৃকণ্ঠ রেফারেল ({urgency}): {clean_name}{preg_tag}।{case_details} "
        f"{instruction}{details}{facility_note}{contact_note} "
        f"এটি একটি প্রাথমিক স্ক্রিনিং বার্তা, চিকিৎসকের রোগনির্ণয় নয়।"
    )

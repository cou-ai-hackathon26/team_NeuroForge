FOLLOW_UP_QUESTIONS = {
    "convulsions": "আপনার কি সম্প্রতি খিঁচুনি বা হঠাৎ অজ্ঞান হয়ে যাওয়ার মতো ঘটনা ঘটেছে?",
    "bleeding": "আপনার কি এখনো রক্তপাত হচ্ছে? রক্তপাত কি বেশি হচ্ছে?",
    "severe_headache": "মাথাব্যথা কি খুব তীব্র? চোখে ঝাপসা দেখছেন কি?",
    "blurred_vision": "চোখে কি এখনো ঝাপসা দেখছেন বা আলো ঝলকানি দেখছেন?",
    "swelling_face_hands": "মুখ বা হাতে কি হঠাৎ ফোলাভাব দেখা দিয়েছে?",
    "severe_abdominal_pain": "পেটের ব্যথা কি তীব্র বা একটানা হচ্ছে?",
    "difficulty_breathing": "আপনার কি বিশ্রামের সময়ও শ্বাস নিতে কষ্ট হচ্ছে?",
    "reduced_fetal_movement": "আপনি কি শিশুর নড়াচড়া স্বাভাবিকের তুলনায় কম অনুভব করছেন?",
    "water_breaking": "আপনার কি যোনিপথ দিয়ে পানি বা তরল বের হচ্ছে?",
    "fever": "আপনার কি জ্বরের সঙ্গে কাঁপুনি বা খুব দুর্বল লাগছে?",
}


def next_question(extraction, asked_keys=None, context=None):
    """
    Return one relevant Bangla follow-up question, or None.

    This is a conversational aid, not a substitute for clinical assessment.
    """
    follow_up = next_follow_up(extraction, asked_keys=asked_keys, context=context)
    return follow_up[1] if follow_up else None


def next_follow_up(extraction, asked_keys=None, context=None):
    """
    Return (key, question) for the next follow-up, or None.

    key is a symptom field name when the answer can update that field,
    otherwise "other_symptoms" or "clarification".
    """
    if not isinstance(extraction, dict):
        return None

    seen = set(asked_keys) if isinstance(asked_keys, (set, list, tuple)) else set()
    ctx = context if isinstance(context, dict) else {}
    pregnancy_status = ctx.get("pregnancy_status")

    # Prioritize urgent / explicitly identified symptoms first.
    for symptom, question in FOLLOW_UP_QUESTIONS.items():
        if symptom in seen:
            continue

        # Skip fetal movement follow-up if user is explicitly marked not pregnant.
        if symptom == "reduced_fetal_movement" and pregnancy_status in ("not_pregnant", "postpartum"):
            continue

        if extraction.get(symptom) is True:
            return symptom, question

    if "other_symptoms" not in seen:
        other_symptoms = [
            s.strip()
            for s in (extraction.get("other_symptoms") or [])
            if isinstance(s, str) and s.strip()
        ]
        if other_symptoms:
            return (
                "other_symptoms",
                f"আপনি '{other_symptoms[0]}' এর কথা বলেছেন—এটি কতক্ষণ ধরে হচ্ছে "
                "এবং এর সঙ্গে অন্য কোনো সমস্যা আছে কি?",
            )

    if extraction.get("needs_clarification") and "clarification" not in seen:
        if extraction.get("duration"):
            return (
                "clarification",
                "আপনি কি আপনার সমস্যাটি আরেকটু বিস্তারিতভাবে বলতে পারবেন? "
                "কতটা তীব্র বা আর কী কষ্ট হচ্ছে সেটিও বলুন।",
            )
        return (
            "clarification",
            "আপনি কি আপনার সমস্যাটি আরেকটু বিস্তারিতভাবে বলতে পারবেন? "
            "কখন থেকে সমস্যা হচ্ছে সেটিও বলুন।",
        )

    return None

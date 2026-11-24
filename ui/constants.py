"""Static Bangla labels and lookup tables used by the UI."""

SYMPTOM_LABELS = {
    "bleeding": "রক্তপাত",
    "severe_headache": "তীব্র মাথাব্যথা",
    "blurred_vision": "চোখে ঝাপসা দেখা",
    "swelling_face_hands": "মুখ/হাত ফোলা",
    "severe_abdominal_pain": "তীব্র পেটব্যথা",
    "fever": "জ্বর",
    "difficulty_breathing": "শ্বাসকষ্ট",
    "convulsions": "খিঁচুনি",
    "reduced_fetal_movement": "শিশুর নড়াচড়া কম",
    "water_breaking": "পানি ভাঙা",
}

SPEAKERS = {
    "গর্ভবতী/প্রসূতি মা": "patient",
    "স্বাস্থ্যকর্মী": "health_worker",
}

STAGES = {
    "গর্ভকালীন": "pregnant",
    "প্রসবের পর": "postpartum",
    "জানি না": "unknown",
}

# Demo list only; not linked to any real referral system.
FACILITIES = [
    "নিকটস্থ উপজেলা স্বাস্থ্য কমপ্লেক্স",
    "সাভার উপজেলা স্বাস্থ্য কমপ্লেক্স",
    "ধামরাই উপজেলা স্বাস্থ্য কমপ্লেক্স",
    "কেরানীগঞ্জ উপজেলা স্বাস্থ্য কমপ্লেক্স",
    "মা ও শিশু কল্যাণ কেন্দ্র (MCWC)",
    "জেলা সদর হাসপাতাল",
]

# risk_level -> (css class, icon, label, headline action)
RISK_STYLE = {
    "HIGH": ("high", "🔴", "উচ্চ ঝুঁকি", "এখনই হাসপাতালে যান"),
    "MODERATE": ("moderate", "🟠", "মাঝারি ঝুঁকি", "আজই স্বাস্থ্যকর্মীর সঙ্গে যোগাযোগ করুন"),
    "LOW": ("low", "🟢", "প্রাথমিকভাবে কম ঝুঁকি", "নিয়মিত চেকআপ চালিয়ে যান"),
    "UNKNOWN": ("unknown", "⚪", "তথ্য অপর্যাপ্ত", "স্বাস্থ্যকর্মীর মাধ্যমে যাচাই করুন"),
}

DISCLAIMER = (
    "এই ফলাফলটি পরামর্শমূলক। অনুগ্রহ করে একজন "
    "স্বাস্থ্যসেবা পেশাদারের সঙ্গে পরামর্শ করুন।"
)

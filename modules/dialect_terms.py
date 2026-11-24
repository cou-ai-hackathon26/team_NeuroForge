"""Bias vocabulary for speech-to-text (ElevenLabs Scribe keyterm prompting).

Limits (batch): up to 1000 terms, <= 50 characters and <= 5 words each.
Keyterms are billed extra, so keep the list short and relevant.

The terms below are standard Bangla maternal-health words. Sylheti / Chittagonian
spellings of the same symptoms should be ADDED to DIALECT_TERMS after review by
a native speaker -- do not guess them.
"""

DANGER_SIGN_TERMS = [
    "রক্তপাত",
    "রক্ত পড়ছে",
    "পানি ভেঙে গেছে",
    "খিঁচুনি",
    "অজ্ঞান",
    "বাচ্চা নড়ছে না",
    "তীব্র মাথা ব্যথা",
    "চোখে ঝাপসা দেখা",
    "পা ফুলে গেছে",
    "মুখ ফুলে গেছে",
    "পেটে ব্যথা",
    "জ্বর",
    "বমি",
    "মাথা ঘোরা",
    "শ্বাসকষ্ট",
    "গর্ভাবস্থা",
    "প্রসব ব্যথা",
    "ম্যাডাম",
]

# Native-speaker-reviewed Sylheti / Chittagonian forms go here.
DIALECT_TERMS: list[str] = []


def stt_keyterms() -> list[str]:
    """Deduplicated keyterm list, within ElevenLabs batch limits."""
    seen: list[str] = []
    for term in DANGER_SIGN_TERMS + DIALECT_TERMS:
        term = term.strip()
        if term and len(term) <= 50 and len(term.split()) <= 5 and term not in seen:
            seen.append(term)
    return seen[:1000]

import json
import os
import re
import time
import unicodedata

import streamlit as st
from google import genai
from google.genai.errors import APIError

from modules.asr import GEMINI_MODEL_HARDCODED

SYMPTOM_FIELDS = [
    "bleeding",
    "severe_headache",
    "blurred_vision",
    "swelling_face_hands",
    "severe_abdominal_pain",
    "fever",
    "difficulty_breathing",
    "convulsions",
    "reduced_fetal_movement",
    "water_breaking",
]

# Bangla negates after the symptom ("রক্তপাত নেই"); English before it ("no bleeding").
NEGATION_MARKERS_AFTER = [
    "নেই",
    "নাই",
    "হচ্ছে না",
    "হয় না",
    "পড়ছে না",
    "যাচ্ছে না",
    "হয়নি",
    "হয় নি",
    "দেখি না",
    "দেখছি না",
]
NEGATION_MARKERS_BEFORE = [
    "no ",
    "not ",
    "without ",
]
NEGATION_MARKERS = NEGATION_MARKERS_AFTER + NEGATION_MARKERS_BEFORE

NEGATION_WINDOW_AFTER = 24
NEGATION_WINDOW_BEFORE = 12


# English markers match whole words only: "cannot stop bleeding" is not a denial.
_NEGATION_BEFORE_RE = re.compile(
    r"(?<![a-z])(?:" + "|".join(re.escape(m.strip()) for m in NEGATION_MARKERS_BEFORE) + r")\s"
)

# A denial never reaches across a clause break: in "রক্তপাত হচ্ছে, ব্যথা নেই"
# the "নেই" is about pain, not bleeding.
_CLAUSE_BREAK_RE = re.compile(r"[,;।!?.]|\b(?:but|however)\b|কিন্তু|তবে")

# Everyday phrases containing a bleeding keyword that do not report bleeding.
# Masked out before matching; "blood" on its own still counts.
_BENIGN_PHRASES_RE = re.compile(
    r"\bblood\s+(?:tests?|pressure|sugar|group|reports?|count|checks?|bank)\b"
)

# Zero-width space / non-joiner / joiner / word joiner / BOM: common in Bangla
# keyboard and ASR output, invisible, and they break substring matching.
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))

# Common misspellings folded to the spelling the keywords use.
_SPELLING_VARIANTS = {
    "ব্যাথা": "ব্যথা",
}


def _normalize(text):
    """
    Canonical form for keyword matching: drop zero-width characters, NFC
    (decomposed ে+া for ো, ড+় for ড় still match), lowercase, fold common
    misspellings, and collapse every whitespace run to one space.
    """
    text = unicodedata.normalize("NFC", (text or "").translate(_ZERO_WIDTH)).lower()
    for variant, canonical in _SPELLING_VARIANTS.items():
        text = text.replace(variant, canonical)
    return re.sub(r"\s+", " ", text)


def _get_api_settings():
    try:
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        model_name = st.secrets.get(
            "GEMINI_MODEL",
            "gemini-3.8-flash",
        )
    except Exception:
        api_key = os.getenv("GEMINI_API_KEY", "")
        model_name = os.getenv(
            "GEMINI_MODEL",
            "gemini-3.8-flash",
        )

    return (api_key or os.getenv("GEMINI_API_KEY", "")).strip(), GEMINI_MODEL_HARDCODED or model_name


def _empty_extraction(transcript, method="fallback"):
    data = {
        "transcript": transcript,
        "extraction_method": method,
        "extraction_success": False,
        "needs_clarification": True,
        "symptoms": [],
    }
    for field in SYMPTOM_FIELDS:
        data[field] = None
    data.update(
        {
            "other_symptoms": [],
            "duration": None,
            "severity": None,
            "notes": "নির্ভরযোগ্যভাবে লক্ষণ শনাক্ত করা যায়নি।",
        }
    )
    return data


def _parse_json(text):
    cleaned = (text or "").strip()

    # Remove Markdown code fences if the model adds them.
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        if start == -1:
            raise ValueError("Gemini did not return valid JSON.")
        decoder = json.JSONDecoder()
        parsed, _ = decoder.raw_decode(cleaned[start:])

    if not isinstance(parsed, dict):
        raise ValueError("Top-level JSON value must be an object.")

    return parsed


def _sanitize_str_list(value):
    if not isinstance(value, list):
        return []
    items = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if text and text not in items:
                items.append(text)
    return items


def _find_spans(text, keyword):
    return [(m.start(), m.end()) for m in re.finditer(re.escape(keyword), text)]


def _is_negated_at(text, start, end, other_spans):
    """
    Is the keyword match at text[start:end] denied?

    Bangla markers count only after the match, English markers only before it,
    and neither side reaches past another symptom's keyword. So in
    "জ্বর নেই কিন্তু রক্ত যাচ্ছে" the "নেই" belongs to fever, not bleeding.
    """
    after_end = min(len(text), end + NEGATION_WINDOW_AFTER)
    before_start = max(0, start - NEGATION_WINDOW_BEFORE)
    next_break = _CLAUSE_BREAK_RE.search(text, end, after_end)
    if next_break:
        after_end = next_break.start()
    for prev_break in _CLAUSE_BREAK_RE.finditer(text, before_start, start):
        before_start = prev_break.end()
    for other_start, other_end in other_spans:
        if end <= other_start < after_end:
            after_end = other_start
        if before_start < other_end <= start:
            before_start = other_end

    # The after-window includes the match so markers that overlap it
    # ("রক্ত পড়ছে" + " না" -> "পড়ছে না") are found. A marker lying
    # entirely inside the match is part of the symptom, not a denial:
    # "বাচ্চা নড়ছে না" reports an emergency.
    after = text[start:after_end]
    keyword_len = end - start
    for marker in NEGATION_MARKERS_AFTER:
        marker = _normalize(marker)
        if any(e > keyword_len for _, e in _find_spans(after, marker)):
            return True

    # Searching the full text (not a slice) lets the lookbehind see the letter
    # before a cut-off "not", so a window starting inside "cannot" is safe.
    return bool(_NEGATION_BEFORE_RE.search(text, before_start, start))


def _fallback_extraction(transcript):
    """
    Conservative keyword fallback.
    A keyword match is only a signal for further assessment,
    not a clinical diagnosis.
    """
    text = _normalize(transcript)
    # Blank out (same length, so positions stay put) phrases like "blood test".
    text = _BENIGN_PHRASES_RE.sub(lambda m: " " * len(m.group()), text)

    patterns = {
        "bleeding": [
            "রক্তপাত",
            "রক্ত যাচ্ছে",
            "রক্ত পড়ছে",
            "রক্ত পড়ছে",
            "রক্ত ঝরছে",
            "রক্ত বের হচ্ছে",
            "ব্লিডিং",
            "bleeding",
            "blood",
        ],
        # Severity words are kept: a plain "মাথাব্যথা" is not a red flag.
        "severe_headache": [
            "তীব্র মাথাব্যথা",
            "প্রচণ্ড মাথাব্যথা",
            "প্রচন্ড মাথাব্যথা",
            "খুব মাথাব্যথা",
            "মাথাব্যথা খুব",
            "মাথাব্যথা প্রচণ্ড",
            "মাথাব্যথা প্রচন্ড",
            "অনেক মাথাব্যথা",
            "মাথা খুব ব্যথা",
            "অনেক মাথা ব্যথা",
            "মাথা প্রচণ্ড ব্যথা",
            "মাথা প্রচন্ড ব্যথা",
        ],
        "blurred_vision": [
            "ঝাপসা",
            "চোখে ঝাপসা",
            "চোখে কম দেখি",
            "চোখে অন্ধকার",
            "চোখে দেখতে পাচ্ছি না",
            "চোখে কিছু দেখতে পাচ্ছি না",
        ],
        "swelling_face_hands": [
            "মুখ ফুলে",
            "হাত ফুলে",
            "হঠাৎ ফুলে",
            "মুখ ও হাত ফুলে",
            "মুখ ফোলা",
            "হাত ফোলা",
        ],
        "severe_abdominal_pain": [
            "তীব্র পেট ব্যথা",
            "প্রচণ্ড পেট ব্যথা",
            "প্রচন্ড পেট ব্যথা",
            "পেটে অনেক ব্যথা",
            "পেটে প্রচণ্ড ব্যথা",
            "পেটে প্রচন্ড ব্যথা",
            "পেটে তীব্র ব্যথা",
        ],
        "fever": [
            "জ্বর",
            "অনেক জ্বর",
        ],
        "difficulty_breathing": [
            "শ্বাসকষ্ট",
            "শ্বাস নিতে কষ্ট",
            "দম নিতে কষ্ট",
            "শ্বাস নিতে পারছি না",
            "দম নিতে পারছি না",
        ],
        "convulsions": [
            "খিঁচুনি",
            "খিচুনি",
            "fit হয়েছে",
            "fit হচ্ছে",
            "ফিট হয়েছে",
            "ফিট হচ্ছে",
        ],
        "reduced_fetal_movement": [
            "বাচ্চা নড়ছে না",
            "বাচ্চা নড়ছে না",
            "বাচ্চা কম নড়ছে",
            "বাচ্চা কম নড়ছে",
            "বাচ্চার নড়াচড়া কম",
            "বাচ্চার নড়াচড়া কম",
            "নড়াচড়া করছে না",
            "নড়াচড়া বন্ধ",
            "বাচ্চা নড়ে না",
        ],
        "water_breaking": [
            "পানি ভেঙে",
            "পানি ভেঙ্গে",
            "পানি ভাঙছে",
            "পানি পড়ছে",
            "পানি বের হচ্ছে",
            "গর্ভের পানি",
        ],
    }

    result = _empty_extraction(transcript, method="keyword_fallback")
    found = []

    spans = {
        symptom: [
            span
            for keyword in dict.fromkeys(_normalize(k) for k in keywords)
            for span in _find_spans(text, keyword)
        ]
        for symptom, keywords in patterns.items()
    }

    for symptom, own_spans in spans.items():
        if not own_spans:
            result[symptom] = None
            continue

        other_spans = [
            span for other, lst in spans.items() if other != symptom for span in lst
        ]
        # Reported if ANY mention is not denied: "গতকাল নেই… আজ হচ্ছে".
        if any(not _is_negated_at(text, s, e, other_spans) for s, e in own_spans):
            result[symptom] = True
            found.append(symptom)
        else:
            result[symptom] = False

    result["symptoms"] = found
    result["other_symptoms"] = []
    result["extraction_success"] = bool(found)
    result["needs_clarification"] = True

    if not found:
        result["notes"] = (
            "কোনো নির্দিষ্ট সতর্কতামূলক লক্ষণ শনাক্ত হয়নি। "
            "এটি লক্ষণ নেই—এমন প্রমাণ নয়।"
        )

    return result


def _format_context_block(context):
    if not isinstance(context, dict) or not context:
        return "Context: Not provided."

    status = context.get("pregnancy_status") or "unknown"
    weeks = context.get("gestational_weeks")
    weeks_text = f"{weeks} weeks" if weeks is not None else "unknown/not provided"
    return f"Context: pregnancy_status={status}, gestational_weeks={weeks_text}"


def extract_symptoms(transcript, context=None):
    """
    Extract symptom information from a Bangla transcript.

    Returns a structured dictionary. If the API is unavailable,
    returns conservative fallback data.
    """
    transcript = (transcript or "").strip()

    if len(transcript) < 3:
        return _empty_extraction(transcript)

    api_key, model_name = _get_api_settings()

    if not api_key:
        return _fallback_extraction(transcript)

    context_line = _format_context_block(context)

    prompt = f"""
তুমি মাতৃকণ্ঠ নামের একটি maternal-health screening support system-এর
symptom extraction component।

কাজ:
ব্যবহারকারীর বাংলা বক্তব্য থেকে কেবল স্পষ্টভাবে বলা লক্ষণগুলো শনাক্ত করো।
কোনো রোগ নির্ণয় করবে না। কোনো তথ্য অনুমান করবে না।
কোনো লক্ষণ উল্লেখ না থাকলে সেটিকে false লিখবে না; null লিখবে।
লক্ষণটি স্পষ্টভাবে অস্বীকার করলে false লিখবে।
অস্পষ্ট হলে null লিখবে।

বক্তব্যটি আঞ্চলিক ভাষায় (যেমন চট্টগ্রাম বা সিলেটের ভাষা) হতে পারে এবং
স্বয়ংক্রিয় ট্রান্সক্রিপশনের ভুল বা ল্যাটিন অক্ষর থাকতে পারে। অর্থ বুঝে লক্ষণ শনাক্ত করো,
তবে যা বলা হয়নি তা যোগ করবে না। "না"/"নাই" জাতীয় অস্বীকৃতি অবশ্যই বজায় রাখবে।
"standard_bangla"-তে বক্তব্যটি হুবহু অর্থে প্রমিত বাংলায় লিখবে; যে শব্দ বোঝা যায় না সেখানে [?] লিখবে।

শুধু valid JSON দেবে। কোনো Markdown বা অতিরিক্ত ব্যাখ্যা দেবে না।

JSON schema:
{{
  "standard_bangla": "",
  "symptoms": [],
  "bleeding": null,
  "severe_headache": null,
  "blurred_vision": null,
  "swelling_face_hands": null,
  "severe_abdominal_pain": null,
  "fever": null,
  "difficulty_breathing": null,
  "convulsions": null,
  "reduced_fetal_movement": null,
  "water_breaking": null,
  "other_symptoms": [],
  "duration": null,
  "severity": null,
  "notes": ""
}}

Boolean fields must be true, false, or null.
symptoms and other_symptoms must be arrays of strings.
Do not add keys outside this schema.

{context_line}
User statement:
{transcript}
"""

    try:
        client = genai.Client(api_key=api_key)

        response = None
        last_error = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                break
            except APIError as exc:
                last_error = exc
                status = str(getattr(exc, "code", ""))

                if status not in {"429", "500", "502", "503", "504"}:
                    raise

                if attempt == 2:
                    raise

                time.sleep(2 ** (attempt + 1))

        if response is None:
            raise last_error or RuntimeError("No response from Gemini.")

        raw_text = getattr(response, "text", None)

        if not raw_text:
            raise ValueError("Gemini returned an empty response.")

        data = _parse_json(raw_text)

        result = _empty_extraction(transcript, method="gemini")
        result["extraction_success"] = True
        result["needs_clarification"] = False

        detected_flags = []
        for field in SYMPTOM_FIELDS:
            value = data.get(field)
            if value not in (True, False, None):
                value = None
            result[field] = value
            if value is True:
                detected_flags.append(field)

        # Safety net: a parseable but wrong reply ("true" as a string, a
        # renamed key, {}, or a plain miss) must not downgrade an emergency
        # the keywords clearly see. Keywords can only add flags, never remove.
        # Also scan Gemini's standard-Bangla rewrite, so dialect speech still
        # reaches the (standard-spelling) keyword net.
        standard = data.get("standard_bangla")
        standard = standard.strip() if isinstance(standard, str) else ""
        result["standard_bangla"] = standard
        keyword_hits = _fallback_extraction(transcript)
        standard_hits = _fallback_extraction(standard) if standard else {}
        keyword_overrides = []
        for field in SYMPTOM_FIELDS:
            hit = keyword_hits[field] is True or standard_hits.get(field) is True
            if hit and result[field] is not True:
                result[field] = True
                detected_flags.append(field)
                keyword_overrides.append(field)
        result["keyword_overrides"] = keyword_overrides

        raw_symptoms = _sanitize_str_list(data.get("symptoms"))
        merged_symptoms = list(detected_flags)
        for item in raw_symptoms:
            if item not in merged_symptoms:
                merged_symptoms.append(item)

        result["symptoms"] = merged_symptoms
        result["other_symptoms"] = _sanitize_str_list(data.get("other_symptoms"))

        duration = data.get("duration")
        result["duration"] = duration.strip() if isinstance(duration, str) and duration.strip() else None

        severity = data.get("severity")
        result["severity"] = severity.strip() if isinstance(severity, str) and severity.strip() else None

        notes = data.get("notes")
        result["notes"] = notes.strip() if isinstance(notes, str) else ""

        return result

    except Exception:
        # Do not expose API keys or raw provider errors to the user.
        return _fallback_extraction(transcript)

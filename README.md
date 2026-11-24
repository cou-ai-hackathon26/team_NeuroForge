# Matrikontho (মাতৃকণ্ঠ) — MVP

Bangla voice-first maternal danger-sign screening and referral-support prototype, built for the **CoU AI Hackathon 2026**.

| Field | Details |
| :--- | :--- |
| **Team Name** | NeuroForge |
| **Team Members** | Ashraful Alam, Prachi Saha, Saidul Islam |
| **Live Demo** | [https://matrikonthomvp-pt8qusej9eu6uxxubuhsqk.streamlit.app/](https://matrikonthomvp-pt8qusej9eu6uxxubuhsqk.streamlit.app/) |
| **Login** | None. The app has no login, so no test credentials are needed. |

> **Safety Notice:** Matrikontho is a hackathon demonstration and a screening aid. It is not a diagnostic tool, a medical device, or a validated clinical decision-support system. Use synthetic data only.

---

## Problem and Solution

In rural Bangladesh, many pregnant women depend on community health workers and family members for first-level care. Danger signs such as vaginal bleeding, convulsions, severe headache with blurred vision, swelling of the face and hands, high fever, and reduced fetal movement are often recognised late. Assessment is subjective and paper-based, and referral is delayed. Existing digital tools usually need typing and formal Bangla or English.

**Matrikontho** lets a health worker, or a mother when a health worker cannot visit, describe symptoms by voice or text in Bangla. The app:
1. Transcribes the speech,
2. Extracts structured symptoms,
3. Assigns a risk level with the reasons, using deterministic, guideline-based rules,
4. Shows simple Bangla advice, and
5. Drafts a referral SMS and logs the case.

---

## Features and How the AI Works

**Pipeline:** `voice or text` → `speech-to-text` → `symptom extraction` → `rule-based triage` → `Bangla advice` → `referral SMS draft` → `case log`

* **Voice and text input with a confirmation step (`ui/record.py`, `ui/confirm.py`, `modules/conversation.py`):** The user records or uploads audio, or types. The transcript and detected symptoms are shown for confirmation before a result is produced. Mother self-screening is supported.
* **Speech-to-text (`modules/asr.py`):** Engines are tried in order: ElevenLabs Scribe (`scribe_v3`, Bangla) if `ELEVENLABS_API_KEY` is configured, then the Gemini API (`gemini-3.5-flash-lite`) if `GEMINI_API_KEY` is configured, then local `faster-whisper` as a last resort. The first engine that returns text is used.
* **AI symptom extraction (`modules/llm_extractor.py`):** Gemini fills a fixed symptom schema (bleeding, severe headache, blurred vision, reduced fetal movement, fever, swelling, convulsions, and others), plus gestational age and blood pressure when mentioned. If the API is unavailable or uncertain, a deterministic keyword fallback is used. *The keyword fallback is not AI.*
* **Dialect keyword safety net (`modules/dialect_terms.py`):** Contains curated regional Bangla symptom expressions and phonetic/lexical mappings (covering common Sylheti and Chittagonian danger-sign phrases) compiled by the team and verified against synthetic test cases (`tests/`). It acts as a deterministic safety net so critical symptoms are not missed when standard ASR/LLM extraction underperforms on regional dialects.
* **Deterministic rule-based triage (`modules/triage_engine.py`, `data/clinical_rules.json`):** A Python rule engine, not a trained model, so every result is explainable and auditable. The AI only handles understanding; the risk decision comes from the rules.
  * Any matched danger-sign rule gives **HIGH**.
  * Moderate-tier symptoms or unmapped symptoms give **MODERATE**.
  * If the transcript is empty, extraction is unreliable (fallback used), or more information is needed, the result is **UNKNOWN**. The system never reports **LOW** risk when it did not understand the input.
  * Each result lists the reasons and rule IDs that triggered it.
* **Bangla advice (`modules/advice_generator.py`, `data/bangla_advice.json`):** Risk-level-specific guidance in simple Bangla.
* **Referral SMS (`modules/referral_sms.py`, `ui/referral.py`):** For high-risk cases, an SMS text is generated for the nearest health facility. In this prototype, the SMS is simulated; no real SMS is sent.
* **Case log and dashboard (`modules/database.py`, `ui/dashboard.py`):** Cases are saved in SQLite, with a summary dashboard and CSV export.
* **Safety, privacy and limits (`ui/limitations.py`, `modules/secret_check.py`, `CLINICAL_SAFETY.md`, `PRIVACY.md`):** Limits are shown in the app, and a startup check helps prevent secrets from being exposed.

---

## Tech Stack, Models, APIs, Datasets

| Layer | Technology |
| :--- | :--- |
| **Language / Runtime** | Python 3.12 (project supports 3.11–3.12) |
| **UI** | Streamlit (mobile-friendly), custom CSS in `assets/styles.css` |
| **Speech-to-text** | ElevenLabs Scribe (`scribe_v3`) → Gemini (`gemini-3.5-flash-lite`) → local `faster-whisper` |
| **Symptom extraction** | Gemini (`gemini-3.5-flash-lite`) + deterministic keyword fallback |
| **Triage** | Python rule engine + `data/clinical_rules.json` |
| **Storage** | SQLite |
| **Packaging** | `uv`, `pyproject.toml`, `uv.lock` (`requirements.txt` for plain `pip`) |
| **Tests** | `pytest` |
| **Hosting** | Streamlit Community Cloud |

**Datasets:** No external dataset is used. Demo inputs are synthetic (`data/demo_cases.json`).

---

## AI Tools Used

### Models and APIs at Runtime
* **ElevenLabs Scribe (`scribe_v3`):** Bangla speech-to-text. Uploaded audio is sent to ElevenLabs.
* **Gemini API:** speech-to-text fallback and symptom extraction. Audio and text are sent to Google.
* **Faster-Whisper:** local last-resort speech recognition.

### AI Coding Assistants Used During Development
* **Claude & Google Gemini:** Used during development for scaffolding Streamlit UI screens, refining rule-engine logic, drafting pytest test cases, reviewing code, and structuring documentation.

*All code in this repository is understood and can be explained by the team.*

---

## Third-Party Code and Assets

* **Open-source libraries:** Streamlit, `google-genai` / Gemini SDK, `faster-whisper`, `pytest`, `uv`, and the other packages listed in `pyproject.toml` / `requirements.txt`.
* **Clinical rule source:** Rules are based on commonly cited maternal danger signs (e.g. WHO guidance) and were not adapted line-by-line from a specific protocol. Thresholds are provisional demo rules, not a validated clinical protocol.
* **Assets:** No third-party images or external fonts are used.

---

## Setup Steps

### Quick Start (`uv`)
```bash
### Tests
`uv run pytest -q` (see `TESTING.md`).

## Privacy
When API keys are configured, the audio or text a user provides is sent to ElevenLabs and/or Google (Gemini). Use synthetic data only. See `PRIVACY.md`.

## Limitations
- Screening aid, not a diagnosis; rules are provisional and need clinical review.
- Dialect support is limited. When the app cannot understand the input it returns UNKNOWN, never LOW.
- Referral SMS is simulated; no real message is sent.
- Accuracy depends on audio quality; free-tier API limits may apply.
- No real patient data; test with synthetic inputs only.
# Install uv once: [https://docs.astral.sh/uv/](https://docs.astral.sh/uv/)
uv sync                      # installs Python 3.12 and all dependencies into .venv
uv run streamlit run app.py  # opens http://localhost:8501

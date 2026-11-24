# Deployment
## Local first
Install Python 3.10–3.12, create a virtual environment, `pip install -r requirements.txt`, then `streamlit run app.py`.

## Optional AI services
- ASR: Faster-Whisper runs locally. First model use downloads model weights; CPU inference can be slow. Try `WHISPER_MODEL=tiny` or `base` on constrained machines.
- Extraction: set `GEMINI_API_KEY` in the server environment. Never put secrets in frontend code or commit `.env`.
- If either is unavailable, text entry and keyword extraction remain available.

## Free hosting assessment
Hugging Face Spaces (Streamlit SDK) may be used for a demo, subject to current CPU/RAM quotas and cold-start limits. A Whisper model may exceed available RAM or startup time. For a reliable judge demo, run locally on a laptop and prepare a text-input fallback. Verify current platform limits before deployment; free tiers can change.

## Troubleshooting
- Microphone unavailable: use a supported browser, allow microphone permission, or upload an audio file.
- Whisper error: use text fallback; reduce model size.
- Gemini error / invalid JSON: fallback extraction is used.
- SQLite file: `matrikontho.sqlite3` is created in the working directory.

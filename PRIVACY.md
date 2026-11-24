# Privacy
- Demo with synthetic patient information only.
- No raw audio is stored by the application; uploaded audio is processed in a temporary file and deleted after transcription.
- Transcripts and extracted symptom summaries are stored only after the user presses save; transcript is truncated in the database.
- SQLite is local and unencrypted in this MVP. Do not use real patient data.
- If Gemini is enabled, transcript text is sent to the configured external model provider. Obtain informed consent and review provider data terms before any real use.
- Provide clear consent, retention, deletion, access control, encryption, audit logs and data-processing agreements before field deployment.

# Deployment Notes

This project is designed primarily as a local tool.

## Recommended: local private mode

Run this on your own machine:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Local mode keeps the full feature set:

- YouTube captions
- Browser cookies from your own logged-in YouTube session
- OpenAI audio transcription
- OpenAI Chinese translation
- Resume from completed audio segments

## Experimental: public captions-only mode

There is still a restricted public mode:

```bash
PUBLIC_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Public mode disables:

- OpenAI audio transcription
- OpenAI Chinese translation
- Browser cookies / local YouTube login state

This mode is not recommended as the main product path. YouTube often blocks cloud server IPs with bot checks, and users' YouTube browser login cookies cannot be shared automatically with a Render/Railway backend.

## Render / Railway settings

If you still want to test the experimental public mode:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Environment: PUBLIC_MODE=true
```

Do not set `OPENAI_API_KEY` for a public captions-only test deployment.

Do not deploy `.env`, `.venv`, `app/outputs`, or `app/tmp`.

## Future public approach

For a genuinely public product, consider a browser extension or a local desktop wrapper so each user can use their own YouTube login state without uploading cookies to a server.

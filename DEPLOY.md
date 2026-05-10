# Deployment Notes

This project is designed primarily as a local tool.

## Recommended: local mode

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Local mode keeps the full feature set:

- YouTube captions
- Browser cookies from the user's own YouTube session
- Volcengine/Doubao ASR fallback
- TOS upload and resume state
- Local history and exports

## Experimental: public captions-only mode

```bash
PUBLIC_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Public mode disables:

- Volcengine/Doubao ASR
- Browser cookies / local YouTube login state

This is not recommended as the main product path. YouTube often blocks cloud server IPs, and users' YouTube login state cannot be shared safely with a hosted backend.

## Render / Railway test settings

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Environment: PUBLIC_MODE=true
```

Do not deploy `.env`, `.venv`, `app/outputs`, or `app/tmp`.

For a real public product, consider a browser extension or desktop wrapper so each user can use their own YouTube login state and ASR account.

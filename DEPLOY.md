# Public Deployment

This project has two runtime modes.

## Public captions-only mode

Use this for a public URL.

```bash
PUBLIC_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Public mode only reads available YouTube captions. It disables:

- OpenAI audio transcription
- OpenAI Chinese translation
- Browser cookies / local YouTube login state

Do not deploy `.env`, `.venv`, `app/outputs`, or `app/tmp`.

## Private local mode

Use this only on your own machine.

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Private mode keeps the full feature set: captions, translation, audio transcription, and resume.

## Render / Railway style setup

Install command:

```bash
pip install -r requirements.txt
```

Start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Environment variables:

```text
PUBLIC_MODE=true
```

Do not set `OPENAI_API_KEY` for the public captions-only deployment.

## Render quick path

Option A: manual Web Service

1. Push this project folder to GitHub.
2. In Render, create a new Web Service from that repository.
3. If this project is in a subfolder, set the Render root directory to that folder.
4. Use:

```text
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

5. Add environment variable:

```text
PUBLIC_MODE=true
```

Option B: Blueprint

If this folder is the repository root, Render can read `render.yaml` directly.

1. Push this folder as a GitHub repository.
2. In Render, create a new Blueprint from the repository.
3. Confirm the generated service settings.
4. Deploy.

## Notes

- The app needs a backend runtime because it calls `yt-dlp`.
- Pure static hosting will not work.
- Some YouTube videos require login or anti-bot verification; public mode does not use your local browser cookies, so those videos may fail.
- If the platform supports Node.js, install/enable it. `yt-dlp` can use Node as a JavaScript runtime, which helps with YouTube extraction.
- For 2.0 paid features, add authentication, limits, and explicit cost controls before enabling OpenAI features publicly.

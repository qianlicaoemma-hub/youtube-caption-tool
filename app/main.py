from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.transcriber import JobOptions, run_transcription

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TMP_DIR = BASE_DIR / "tmp"
OUTPUT_DIR = BASE_DIR / "outputs"
PUBLIC_MODE = os.getenv("PUBLIC_MODE", "").strip().lower() in {"1", "true", "yes", "on"}

TMP_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="YouTube Transcript Tool")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

jobs: dict[str, dict[str, Any]] = {}


class CreateJobRequest(BaseModel):
    url: str = Field(..., min_length=8)
    mode: str = Field(default="auto", pattern="^(auto|captions|audio)$")
    language: str = Field(default="auto", pattern="^(auto|zh|en)$")
    cookies_from_browser: str = Field(
        default="auto",
        pattern="^(|auto|chrome|chrome:Default|chrome:Profile 1|chrome:Profile 12|safari|firefox|edge)$",
    )
    cookies_file: str = ""
    # translate_to_zh 字段保留兼容历史 job.json，但 UI 已移除翻译选项
    translate_to_zh: bool = False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/jobs/{job_id}")
def job_page(job_id: str) -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "public_mode": PUBLIC_MODE,
        "allow_audio": not PUBLIC_MODE,
        "allow_translation": False,  # 暂未启用翻译模块
        "allow_browser_cookies": not PUBLIC_MODE,
    }


@app.post("/api/jobs")
def create_job(
    payload: CreateJobRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    _validate_public_request(payload)

    options = JobOptions(
        url=payload.url.strip(),
        mode=payload.mode,
        language=payload.language,
        cookies_from_browser=payload.cookies_from_browser or None,
        cookies_file=payload.cookies_file.strip() or None,
        translate_to_zh=payload.translate_to_zh,
    )
    existing_job_id = _find_existing_job(options)
    if existing_job_id:
        job = jobs.get(existing_job_id) or _load_job_from_disk(existing_job_id)
        if job and job.get("status") == "done":
            jobs[existing_job_id] = job
            return {"job_id": existing_job_id}
        if job and job.get("status") in {"queued", "running"} and existing_job_id in jobs:
            return {"job_id": existing_job_id}

        job = job or _new_job(existing_job_id, options)
        job["status"] = "queued"
        job["progress"] = "找到未完成任务，准备从已完成片段继续。"
        job["error"] = None
        job["updated_at"] = time.time()
        jobs[existing_job_id] = job
        _persist_job(existing_job_id)
        background_tasks.add_task(_run_job, existing_job_id, options)
        return {"job_id": existing_job_id}

    job_id = uuid4().hex
    jobs[job_id] = _new_job(job_id, options)
    _persist_job(job_id)
    background_tasks.add_task(_run_job, job_id, options)
    return {"job_id": job_id}


@app.get("/api/jobs/history")
def job_history(url: str) -> dict[str, Any]:
    return {"jobs": _jobs_for_url(url.strip())}


@app.get("/api/jobs/recent")
def recent_jobs(limit: int = 12) -> dict[str, Any]:
    """侧栏用：返回最近完成或处理中的任务列表。"""
    return {"jobs": _recent_jobs(limit)}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = _get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    _ensure_public_job_visible(job)
    if job.get("started_at"):
        job["elapsed_seconds"] = max(0, int(time.time() - job["started_at"]))
    if job.get("updated_at"):
        job["seconds_since_update"] = max(0, int(time.time() - job["updated_at"]))
    return job


@app.get("/api/jobs/{job_id}/download/{file_type}")
def download(job_id: str, file_type: str) -> FileResponse:
    files = _files_for_job(job_id)
    file_path = files.get(file_type)
    if not file_path:
        raise HTTPException(status_code=404, detail="文件不存在")

    path = Path(file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="文件已不存在")
    return FileResponse(path, filename=path.name)


@app.post("/api/jobs/{job_id}/copy")
def copy_to_clipboard(job_id: str) -> dict[str, str]:
    text = _text_for_job(job_id)
    if not text:
        raise HTTPException(status_code=404, detail="没有可复制的文本")

    try:
        subprocess.run(["pbcopy"], input=text, text=True, check=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"复制到系统剪贴板失败：{exc}") from exc

    return {"message": "已复制到系统剪贴板"}


@app.post("/api/jobs/{job_id}/save/{file_type}")
def save_to_downloads(job_id: str, file_type: str) -> dict[str, str]:
    files = _files_for_job(job_id)
    source = files.get(file_type)
    if not source:
        raise HTTPException(status_code=404, detail="文件不存在")

    source_path = Path(source)
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="文件已不存在")

    downloads_dir = Path.home() / "Downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_path(downloads_dir / source_path.name)
    shutil.copy2(source_path, target_path)

    return {"message": f"已保存到 {target_path}", "path": str(target_path)}


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    for index in range(1, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError("无法生成不重复的文件名")


def _files_for_job(job_id: str) -> dict[str, str]:
    job = _get_job(job_id)
    if job:
        _ensure_public_job_visible(job)
    if job and job.get("result"):
        return job.get("result", {}).get("files", {})

    job_output_dir = OUTPUT_DIR / job_id
    if not job_output_dir.exists():
        raise HTTPException(status_code=404, detail="任务未完成或不存在")

    files: dict[str, str] = {}
    for path in job_output_dir.iterdir():
        if path.suffix == ".md":
            files["markdown"] = str(path)
        elif path.suffix == ".txt":
            files["txt"] = str(path)
        elif path.suffix == ".docx":
            files["docx"] = str(path)
    return files


def _text_for_job(job_id: str) -> str:
    job = _get_job(job_id)
    if job and job.get("result"):
        return job.get("result", {}).get("text", "")

    files = _files_for_job(job_id)
    txt_path = files.get("txt")
    md_path = files.get("markdown")
    path = Path(txt_path or md_path or "")
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _run_job(job_id: str, options: JobOptions) -> None:
    def report(message: str, partial_result: dict[str, Any] | None = None) -> None:
        jobs[job_id]["progress"] = message
        jobs[job_id]["updated_at"] = time.time()
        if partial_result:
            jobs[job_id]["result"] = partial_result
        _persist_job(job_id)

    try:
        jobs[job_id]["status"] = "running"
        jobs[job_id]["started_at"] = time.time()
        jobs[job_id]["updated_at"] = time.time()
        _persist_job(job_id)
        result = run_transcription(options, TMP_DIR / job_id, OUTPUT_DIR / job_id, report)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["progress"] = "完成。"
        jobs[job_id]["updated_at"] = time.time()
        jobs[job_id]["result"] = result
        _persist_job(job_id)
    except Exception as exc:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(exc)
        jobs[job_id]["progress"] = "处理失败。"
        jobs[job_id]["updated_at"] = time.time()
        _persist_job(job_id)


def _new_job(job_id: str, options: JobOptions) -> dict[str, Any]:
    now = time.time()
    return {
        "id": job_id,
        "status": "queued",
        "progress": "已创建任务，等待开始。",
        "created_at": now,
        "started_at": None,
        "updated_at": now,
        "result": None,
        "error": None,
        "options": _options_payload(options),
        "signature": _job_signature(options),
    }


def _options_payload(options: JobOptions) -> dict[str, Any]:
    return asdict(options)


def _job_signature(options: JobOptions) -> str:
    payload = json.dumps(_options_payload(options), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _job_json_path(job_id: str) -> Path:
    return OUTPUT_DIR / job_id / "job.json"


def _persist_job(job_id: str) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    path = _job_json_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(job, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp_path.replace(path)


def _load_job_from_disk(job_id: str) -> dict[str, Any] | None:
    path = _job_json_path(job_id)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _get_job(job_id: str) -> dict[str, Any] | None:
    job = jobs.get(job_id)
    if job:
        return job
    return _load_job_from_disk(job_id)


def _find_existing_job(options: JobOptions) -> str | None:
    signature = _job_signature(options)
    candidates: list[dict[str, Any]] = []

    for path in OUTPUT_DIR.glob("*/job.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        if data.get("signature") != signature:
            continue
        candidates.append(data)

    if not candidates:
        return None

    candidates.sort(key=_existing_job_sort_key, reverse=True)
    job_id = candidates[0].get("id")
    return str(job_id) if job_id else None


def _jobs_for_url(url: str) -> list[dict[str, Any]]:
    url_key = _url_match_key(url)
    if not url_key:
        return []

    matches: list[dict[str, Any]] = []
    for path in OUTPUT_DIR.glob("*/job.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue

        options = data.get("options")
        if not isinstance(options, dict):
            continue
        if PUBLIC_MODE and not _is_public_options(options):
            continue
        if _url_match_key(str(options.get("url") or "")) != url_key:
            continue
        matches.append(_job_history_item(data))

    matches.sort(key=_history_sort_key, reverse=True)
    return matches[:8]


def _job_history_item(job: dict[str, Any]) -> dict[str, Any]:
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    return {
        "id": job.get("id"),
        "status": job.get("status"),
        "progress": job.get("progress"),
        "error": job.get("error"),
        "updated_at": job.get("updated_at"),
        "title": result.get("title") or "历史任务",
        "uploader": result.get("uploader") or "",
        "language": (job.get("options") or {}).get("language") or "auto",
        "url": (job.get("options") or {}).get("url") or "",
        "options": job.get("options") if isinstance(job.get("options"), dict) else {},
    }


def _recent_jobs(limit: int = 12) -> list[dict[str, Any]]:
    """所有任务里取最近 N 条，用于侧栏展示。"""
    items: list[dict[str, Any]] = []
    for path in OUTPUT_DIR.glob("*/job.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        options = data.get("options")
        if not isinstance(options, dict):
            continue
        if PUBLIC_MODE and not _is_public_options(options):
            continue
        items.append(_job_history_item(data))

    items.sort(key=_history_sort_key, reverse=True)
    return items[:limit]


def _history_sort_key(job: dict[str, Any]) -> tuple[int, float]:
    status_rank = 2 if job.get("status") == "done" else 1
    return (status_rank, _timestamp_value(job.get("updated_at")))


def _url_match_key(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")

    if host in {"youtube.com", "m.youtube.com"}:
        video_id = parse_qs(parsed.query).get("v", [""])[0]
        return f"youtube:{video_id}" if video_id else url.strip()

    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
        return f"youtube:{video_id}" if video_id else url.strip()

    return url.strip()


def _existing_job_sort_key(job: dict[str, Any]) -> tuple[int, float]:
    if job.get("status") == "done":
        return (2, _timestamp_value(job.get("updated_at")))
    return (1, _timestamp_value(job.get("updated_at")))


def _timestamp_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def _validate_public_request(payload: CreateJobRequest) -> None:
    if not PUBLIC_MODE:
        return
    if payload.mode != "captions":
        raise HTTPException(status_code=403, detail="公开版只支持读取 YouTube 字幕，不支持音频识别。")
    if payload.cookies_from_browser:
        raise HTTPException(status_code=403, detail="公开版不使用本机浏览器登录态。")
    if payload.cookies_file.strip():
        raise HTTPException(status_code=403, detail="公开版不支持 cookies 文件。")


def _ensure_public_job_visible(job: dict[str, Any]) -> None:
    if not PUBLIC_MODE:
        return
    options = job.get("options")
    if not isinstance(options, dict) or not _is_public_options(options):
        raise HTTPException(status_code=404, detail="任务不存在")


def _is_public_options(options: dict[str, Any]) -> bool:
    return (
        options.get("mode") == "captions"
        and not options.get("cookies_from_browser")
        and not options.get("cookies_file")
    )

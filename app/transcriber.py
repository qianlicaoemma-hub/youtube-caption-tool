from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from openai import OpenAI

Progress = Callable[..., None]
CHUNK_SECONDS = 120


@dataclass(frozen=True)
class JobOptions:
    url: str
    mode: str = "auto"
    language: str = "auto"
    cookies_from_browser: str | None = None
    cookies_file: str | None = None
    translate_to_zh: bool = False


@dataclass
class TranscriptBlock:
    speaker: str
    text: str


def run_transcription(
    options: JobOptions,
    work_dir: Path,
    output_dir: Path,
    progress: Progress,
) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    completed = False
    try:
        title = _get_title(options, progress)

        if options.mode in {"auto", "captions"}:
            try:
                progress("正在尝试读取 YouTube 自带字幕。")
                caption_text = _download_and_parse_captions(options, work_dir / "captions")
                if caption_text:
                    blocks = [TranscriptBlock("Speaker 1", _light_cleanup(caption_text))]
                    translation_blocks = _maybe_translate_to_zh(options, blocks, progress)
                    files = _write_outputs(output_dir, title, options.url, blocks, "YouTube captions", translation_blocks)
                    completed = True
                    return _result(title, options.url, "YouTube captions", blocks, files, translation_blocks)
                if options.mode == "captions":
                    raise RuntimeError("这个视频没有可用的 YouTube 字幕。")
            except Exception as exc:
                if options.mode == "captions":
                    raise RuntimeError(f"读取 YouTube 字幕失败：{exc}") from exc
                progress("没有拿到可用字幕，切换到音频识别。")

        progress("正在准备用 OpenAI 识别音频。")
        blocks = _transcribe_audio_with_openai(options, work_dir, output_dir, title, progress)
        translation_blocks = _maybe_translate_to_zh(options, blocks, progress)
        files = _write_outputs(output_dir, title, options.url, blocks, "OpenAI audio transcription", translation_blocks)
        completed = True
        return _result(title, options.url, "OpenAI audio transcription", blocks, files, translation_blocks)
    finally:
        if completed:
            shutil.rmtree(work_dir, ignore_errors=True)


def _result(
    title: str,
    url: str,
    source: str,
    blocks: list[TranscriptBlock],
    files: dict[str, str],
    translation_blocks: list[TranscriptBlock] | None = None,
) -> dict[str, Any]:
    return {
        "title": title,
        "url": url,
        "source": source,
        "text": _render_body(blocks, translation_blocks),
        "files": files,
    }


def _transcribe_audio_with_openai(
    options: JobOptions,
    work_dir: Path,
    output_dir: Path,
    title: str,
    progress: Progress,
) -> list[TranscriptBlock]:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY。请先复制 .env.example 为 .env，并填入你的 OpenAI API Key。")

    audio_dir = work_dir / "audio"
    chunk_dir = work_dir / "chunks"
    audio_dir.mkdir(parents=True, exist_ok=True)
    chunk_dir.mkdir(parents=True, exist_ok=True)
    segments_dir = output_dir / "segments"
    segments_dir.mkdir(parents=True, exist_ok=True)

    source_audio = _existing_source_audio(audio_dir)
    if source_audio:
        progress("发现上次保留的临时音频，直接复用。")
    else:
        progress("正在下载临时音频，不会下载视频画面。")
        source_audio = _download_audio(options, audio_dir)

    chunks = sorted(chunk_dir.glob("chunk_*.mp3"))
    if chunks:
        progress(f"发现上次保留的 {len(chunks)} 个音频片段，直接复用。")
    else:
        progress("正在压缩并切分音频，方便处理长视频。")
        chunks = _split_audio(source_audio, chunk_dir)
    if not chunks:
        raise RuntimeError("没有生成可识别的音频片段。")
    progress(f"音频已切成 {len(chunks)} 段，每段约 {CHUNK_SECONDS // 60} 分钟；下一步开始调用 OpenAI。")

    client = OpenAI(timeout=180, max_retries=1)
    blocks: list[TranscriptBlock] = []
    speaker_map: dict[str, str] = {}

    for index, chunk in enumerate(chunks, start=1):
        segment_path = segments_dir / f"segment_{index:03d}.json"
        response = _read_segment_response(segment_path)
        if response is not None:
            progress(f"发现第 {index}/{len(chunks)} 段已有识别结果，跳过 OpenAI 请求。")
        else:
            progress(f"正在识别第 {index}/{len(chunks)} 段音频；OpenAI 返回前此状态可能停留几分钟。")
            response = _transcribe_chunk_with_retry(client, chunk, options, index, len(chunks), progress)
            _write_segment_response(segment_path, response)

        blocks.extend(_blocks_from_openai_response(response, speaker_map))
        partial_blocks = _clean_blocks(_merge_adjacent_blocks(blocks))
        partial_files = _write_outputs(
            output_dir,
            title,
            options.url,
            partial_blocks,
            "OpenAI audio transcription",
        )
        partial_result = _result(title, options.url, "OpenAI audio transcription", partial_blocks, partial_files)
        progress(f"已完成第 {index}/{len(chunks)} 段音频识别，已显示并保存部分逐字稿。", partial_result=partial_result)

    merged = _merge_adjacent_blocks(blocks)
    return _clean_blocks(merged)


def _existing_source_audio(audio_dir: Path) -> Path | None:
    candidates = [path for path in audio_dir.glob("source.*") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def _read_segment_response(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _write_segment_response(path: Path, response: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = response.model_dump(mode="json") if hasattr(response, "model_dump") else response
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    tmp_path.replace(path)


def _clean_blocks(blocks: list[TranscriptBlock]) -> list[TranscriptBlock]:
    return [TranscriptBlock(block.speaker, _light_cleanup(block.text)) for block in blocks if block.text.strip()]


def _transcribe_chunk_with_retry(
    client: OpenAI,
    chunk: Path,
    options: JobOptions,
    index: int,
    total: int,
    progress: Progress,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, 4):
        try:
            progress(f"正在识别第 {index}/{total} 段音频，正在进行第 {attempt}/3 次 OpenAI 请求。")
            with chunk.open("rb") as audio_file:
                kwargs: dict[str, Any] = {
                    "model": "gpt-4o-transcribe-diarize",
                    "file": audio_file,
                    "response_format": "diarized_json",
                    "chunking_strategy": "auto",
                }
                if options.language in {"zh", "en"}:
                    kwargs["language"] = options.language

                try:
                    return client.audio.transcriptions.create(**kwargs)
                except TypeError:
                    kwargs.pop("chunking_strategy", None)
                    kwargs["extra_body"] = {"chunking_strategy": "auto"}
                    return client.audio.transcriptions.create(**kwargs)
        except Exception as exc:
            last_error = exc
            if attempt >= 3:
                break
            wait_seconds = attempt * 10
            progress(f"第 {index}/{total} 段第 {attempt}/3 次 OpenAI 请求失败，等待 {wait_seconds} 秒后再试。")
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"OpenAI 音频识别连接失败：第 {index}/{total} 段重试 3 次仍未成功。"
        "请稍后重试，或先使用 YouTube 字幕快路径。"
        f" 原始错误：{last_error}"
    )


def _maybe_translate_to_zh(
    options: JobOptions,
    blocks: list[TranscriptBlock],
    progress: Progress,
) -> list[TranscriptBlock] | None:
    if not options.translate_to_zh:
        return None
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("没有找到 OPENAI_API_KEY，无法生成中文翻译。")

    progress("正在生成中文逐字翻译。")
    return _translate_blocks_to_zh(blocks, progress)


def _translate_blocks_to_zh(blocks: list[TranscriptBlock], progress: Progress) -> list[TranscriptBlock]:
    client = OpenAI(timeout=600, max_retries=2)
    model = os.getenv("OPENAI_TRANSLATION_MODEL", "gpt-4o-mini")
    chunks: list[tuple[str, str]] = []

    for block in blocks:
        for text_chunk in _split_text_for_translation(block.text):
            chunks.append((block.speaker, text_chunk))

    translated: list[TranscriptBlock] = []
    current_speaker = ""
    current_parts: list[str] = []

    for index, (speaker, text_chunk) in enumerate(chunks, start=1):
        progress(f"正在翻译第 {index}/{len(chunks)} 段文本。")
        translation = _translate_text_chunk(client, model, text_chunk)
        if speaker != current_speaker:
            if current_parts:
                translated.append(TranscriptBlock(current_speaker, "\n\n".join(current_parts).strip()))
            current_speaker = speaker
            current_parts = [translation]
        else:
            current_parts.append(translation)

    if current_parts:
        translated.append(TranscriptBlock(current_speaker, "\n\n".join(current_parts).strip()))

    progress("中文逐字翻译完成。")
    return translated


def _split_text_for_translation(text: str, max_chars: int = 3600) -> list[str]:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(_split_long_text(paragraph, max_chars))
            continue

        if len(current) + len(paragraph) + 2 > max_chars:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current = f"{current}\n\n{paragraph}".strip()

    if current:
        chunks.append(current.strip())
    return chunks or [text.strip()]


def _split_long_text(text: str, max_chars: int) -> list[str]:
    parts = re.split(r"(?<=[.!?。！？])\s+", text)
    chunks: list[str] = []
    current = ""

    for part in parts:
        if len(part) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(part[start : start + max_chars] for start in range(0, len(part), max_chars))
            continue

        if len(current) + len(part) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = part
        else:
            current = f"{current} {part}".strip()

    if current:
        chunks.append(current.strip())
    return chunks


def _translate_text_chunk(client: OpenAI, model: str, text: str) -> str:
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是逐字稿翻译助手。把英文逐字稿翻译成中文，要求忠实、完整、口语化。"
                    "不要总结、不要提炼、不要删减信息、不要改写成正式书面稿。"
                    "保留原有段落含义和语气，只输出中文译文。"
                ),
            },
            {"role": "user", "content": text},
        ],
        temperature=0,
    )
    return (completion.choices[0].message.content or "").strip()


def _download_audio(options: JobOptions, output_dir: Path) -> Path:
    output_template = output_dir / "source.%(ext)s"
    command = [
        "yt-dlp",
        "-f",
        "bestaudio/best",
        "-o",
        str(output_template),
        "--no-playlist",
        options.url,
    ]
    _run_ytdlp(command, options, "下载音频失败")

    candidates = [path for path in output_dir.glob("source.*") if path.is_file()]
    if not candidates:
        raise RuntimeError("没有找到下载后的音频文件。")
    return max(candidates, key=lambda path: path.stat().st_size)


def _split_audio(source_audio: Path, chunk_dir: Path) -> list[Path]:
    output_template = chunk_dir / "chunk_%03d.mp3"
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_audio),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        "32k",
        "-f",
        "segment",
        "-segment_time",
        str(CHUNK_SECONDS),
        "-reset_timestamps",
        "1",
        str(output_template),
    ]
    _run(command, "切分音频失败")
    return sorted(chunk_dir.glob("chunk_*.mp3"))


def _download_and_parse_captions(options: JobOptions, output_dir: Path) -> str:
    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_template = output_dir / "%(title).120B-%(id)s.%(ext)s"
    command = [
        "yt-dlp",
        "--skip-download",
        "--write-subs",
        "--write-auto-subs",
        "--sub-langs",
        _subtitle_languages(options.language),
        "--sub-format",
        "vtt",
        "--no-playlist",
        "-o",
        str(output_template),
        options.url,
    ]
    _run_ytdlp(command, options, "读取字幕失败")

    vtt_files = sorted(output_dir.glob("*.vtt"), key=_caption_priority)
    for path in vtt_files:
        text = _parse_vtt(path.read_text(encoding="utf-8", errors="ignore"))
        if len(text) > 200:
            return text
    return ""


def _subtitle_languages(language: str) -> str:
    if language == "zh":
        return "zh.*,zh-Hans,zh-Hant,zh-CN,zh-TW"
    if language == "en":
        return "en.*,en"
    return "zh.*,zh-Hans,zh-Hant,zh-CN,zh-TW,en.*,en"


def _caption_priority(path: Path) -> tuple[int, str]:
    name = path.name.lower()
    if ".zh" in name or "chinese" in name:
        return (0, name)
    if ".en" in name or "english" in name:
        return (1, name)
    return (2, name)


def _get_title(options: JobOptions, progress: Progress) -> str:
    command = ["yt-dlp", "--dump-json", "--skip-download", "--no-playlist", options.url]
    try:
        completed = _run_ytdlp(command, options, "读取标题失败", timeout=60)
        data = json.loads(completed.stdout)
        title = data.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    except Exception:
        progress("暂时没有读到视频标题，继续处理正文。")
    return "YouTube Transcript"


def _yt_dlp_attempts(command: list[str], options: JobOptions) -> list[list[str]]:
    base = [*command]
    if shutil.which("node"):
        base[1:1] = ["--js-runtimes", "node", "--remote-components", "ejs:github"]

    if options.cookies_file:
        return [[*base, "--cookies", options.cookies_file]]

    if options.cookies_from_browser and options.cookies_from_browser != "auto":
        return [[*base, "--cookies-from-browser", options.cookies_from_browser]]

    attempts = [base]
    for browser in ("chrome:Profile 1", "chrome:Profile 12", "chrome:Default", "chrome:Profile 7", "safari", "firefox", "edge"):
        attempts.append([*base, "--cookies-from-browser", browser])
    return attempts


def _run_ytdlp(
    command: list[str],
    options: JobOptions,
    message: str,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    errors: list[str] = []
    for attempt in _yt_dlp_attempts(command, options):
        completed = subprocess.run(attempt, capture_output=True, text=True, timeout=timeout)
        if completed.returncode == 0:
            return completed
        detail = (completed.stderr or completed.stdout).strip()
        errors.append(detail[-1200:])

    final_error = errors[-1] if errors else "未知错误"
    raise RuntimeError(f"{message}：{final_error}")


def _append_cookie_args(command: list[str], options: JobOptions) -> None:
    if options.cookies_from_browser:
        command.extend(["--cookies-from-browser", options.cookies_from_browser])
    if options.cookies_file:
        command.extend(["--cookies", options.cookies_file])


def _run(command: list[str], message: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise RuntimeError(f"{message}：{detail[-1200:]}")
    return completed


def _parse_vtt(content: str) -> str:
    lines: list[str] = []
    last = ""
    skip_block = False

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line:
            skip_block = False
            continue
        if line.startswith(("WEBVTT", "Kind:", "Language:")):
            continue
        if line.startswith("NOTE"):
            skip_block = True
            continue
        if skip_block:
            continue
        if "-->" in line:
            continue
        if line.isdigit():
            continue

        line = re.sub(r"<[^>]+>", "", line)
        line = html.unescape(line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == last:
            continue
        lines.append(line)
        last = line

    return _join_caption_lines(lines)


def _join_caption_lines(lines: list[str]) -> str:
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        current.append(line)
        if re.search(r"[。！？.!?]$", line) or len(" ".join(current)) > 500:
            paragraphs.append(" ".join(current))
            current = []
    if current:
        paragraphs.append(" ".join(current))

    return "\n\n".join(paragraphs)


def _blocks_from_openai_response(response: Any, speaker_map: dict[str, str]) -> list[TranscriptBlock]:
    data = response.model_dump() if hasattr(response, "model_dump") else response
    if not isinstance(data, dict):
        return [TranscriptBlock("Speaker 1", str(response))]

    segments = data.get("segments") or data.get("words") or []
    blocks: list[TranscriptBlock] = []

    if isinstance(segments, list) and segments:
        for segment in segments:
            if not isinstance(segment, dict):
                continue
            text = str(segment.get("text") or segment.get("word") or "").strip()
            if not text:
                continue
            raw_speaker = str(segment.get("speaker") or segment.get("speaker_id") or "speaker_0")
            speaker = _speaker_label(raw_speaker, speaker_map)
            blocks.append(TranscriptBlock(speaker, text))

    if blocks:
        return _merge_adjacent_blocks(blocks)

    text = str(data.get("text") or "").strip()
    return [TranscriptBlock("Speaker 1", text)] if text else []


def _speaker_label(raw_speaker: str, speaker_map: dict[str, str]) -> str:
    if raw_speaker not in speaker_map:
        speaker_map[raw_speaker] = f"Speaker {len(speaker_map) + 1}"
    return speaker_map[raw_speaker]


def _merge_adjacent_blocks(blocks: list[TranscriptBlock]) -> list[TranscriptBlock]:
    merged: list[TranscriptBlock] = []
    for block in blocks:
        text = block.text.strip()
        if not text:
            continue
        if merged and merged[-1].speaker == block.speaker:
            merged[-1].text = f"{merged[-1].text} {text}".strip()
        else:
            merged.append(TranscriptBlock(block.speaker, text))
    return merged


def _light_cleanup(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\[(music|applause|laughter|音乐|掌声|笑声)\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(um|uh|er|ah)\b[,\s]*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"(^|[，,。.\s])(嗯+|呃+|啊+|额+)([，,。.\s]|$)", r"\1", cleaned)
    cleaned = re.sub(r"\b(\w+)(\s+\1\b){1,}", r"\1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"([\u4e00-\u9fff])(?:\s*\1){2,}", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _write_outputs(
    output_dir: Path,
    title: str,
    url: str,
    blocks: list[TranscriptBlock],
    source: str,
    translation_blocks: list[TranscriptBlock] | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(title)

    markdown = _render_markdown(title, url, source, blocks, translation_blocks)
    text = _render_text(title, url, source, blocks, translation_blocks)

    md_path = output_dir / f"{safe_name}.md"
    txt_path = output_dir / f"{safe_name}.txt"
    docx_path = output_dir / f"{safe_name}.docx"

    md_path.write_text(markdown, encoding="utf-8")
    txt_path.write_text(text, encoding="utf-8")
    _write_docx(docx_path, title, url, source, blocks, translation_blocks)

    return {
        "markdown": str(md_path),
        "txt": str(txt_path),
        "docx": str(docx_path),
    }


def _render_markdown(
    title: str,
    url: str,
    source: str,
    blocks: list[TranscriptBlock],
    translation_blocks: list[TranscriptBlock] | None = None,
) -> str:
    return f"# {title}\n\nSource: {url}\nMethod: {source}\n\n{_render_body(blocks, translation_blocks)}\n"


def _render_text(
    title: str,
    url: str,
    source: str,
    blocks: list[TranscriptBlock],
    translation_blocks: list[TranscriptBlock] | None = None,
) -> str:
    return f"{title}\n\nSource: {url}\nMethod: {source}\n\n{_render_body(blocks, translation_blocks)}\n"


def _render_body(
    blocks: list[TranscriptBlock],
    translation_blocks: list[TranscriptBlock] | None = None,
) -> str:
    original = "\n\n".join(f"{block.speaker}:\n{block.text.strip()}" for block in blocks if block.text.strip())
    if not translation_blocks:
        return f"## Transcript\n\n{original}"

    translation = "\n\n".join(
        f"{block.speaker}:\n{block.text.strip()}" for block in translation_blocks if block.text.strip()
    )
    return f"## Transcript\n\n{original}\n\n## 中文逐字翻译\n\n{translation}"


def _write_docx(
    path: Path,
    title: str,
    url: str,
    source: str,
    blocks: list[TranscriptBlock],
    translation_blocks: list[TranscriptBlock] | None = None,
) -> None:
    from docx import Document

    document = Document()
    document.add_heading(title, level=1)
    document.add_paragraph(f"Source: {url}")
    document.add_paragraph(f"Method: {source}")
    document.add_heading("Transcript", level=2)

    for block in blocks:
        speaker = document.add_paragraph()
        speaker.add_run(f"{block.speaker}:").bold = True
        document.add_paragraph(block.text.strip())

    if translation_blocks:
        document.add_heading("中文逐字翻译", level=2)
        for block in translation_blocks:
            speaker = document.add_paragraph()
            speaker.add_run(f"{block.speaker}:").bold = True
            document.add_paragraph(block.text.strip())

    document.save(path)


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[\\/:*?\"<>|]+", "-", name).strip()
    return cleaned[:100] or "youtube-transcript"

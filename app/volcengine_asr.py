"""火山引擎大模型录音文件识别（豆包 Seed-ASR 2.0）封装。

API 文档：https://www.volcengine.com/docs/6561/1354868
端点：     https://openspeech.bytedance.com/api/v3/auc/bigmodel/
鉴权：     x-api-key（语音控制台获取）
Resource:  volc.seedasr.auc

火山 ASR 要求音频是公网可访问的 URL，所以本模块会先把本地音频上传到
用户自己的火山 TOS 桶（对象存储），生成预签名 URL，再提交识别任务。
TOS 上传与签名由官方 `tos` Python SDK 处理。
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import requests
import tos

Progress = Callable[..., None]

SUBMIT_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit"
QUERY_URL = "https://openspeech.bytedance.com/api/v3/auc/bigmodel/query"
RESOURCE_ID = "volc.seedasr.auc"

FORMAT_MAP = {
    ".m4a": "m4a",
    ".mp3": "mp3",
    ".mp4": "mp4",
    ".wav": "wav",
    ".ogg": "ogg",
    ".flac": "flac",
    ".aac": "m4a",
    ".webm": "ogg",
}


@dataclass
class VolcCredentials:
    api_key: str
    access_key_id: str
    secret_access_key: str
    tos_bucket: str
    tos_region: str = "cn-beijing"

    @classmethod
    def from_env(cls) -> "VolcCredentials":
        api_key = os.getenv("VOLCENGINE_API_KEY", "").strip()
        ak = os.getenv("VOLCENGINE_ACCESS_KEY_ID", "").strip()
        sk = os.getenv("VOLCENGINE_SECRET_ACCESS_KEY", "").strip()
        bucket = os.getenv("VOLCENGINE_TOS_BUCKET", "").strip()
        region = os.getenv("VOLCENGINE_TOS_REGION", "cn-beijing").strip() or "cn-beijing"

        missing = []
        if not api_key:
            missing.append("VOLCENGINE_API_KEY")
        if not ak:
            missing.append("VOLCENGINE_ACCESS_KEY_ID")
        if not sk:
            missing.append("VOLCENGINE_SECRET_ACCESS_KEY")
        if not bucket:
            missing.append("VOLCENGINE_TOS_BUCKET")

        if missing:
            raise RuntimeError(
                "火山引擎配置不完整，缺少：" + ", ".join(missing) + "。\n"
                "请在 .env 文件里填入这些值。详见 INSTALL.md 第 7 步。"
            )

        return cls(api_key=api_key, access_key_id=ak, secret_access_key=sk,
                   tos_bucket=bucket, tos_region=region)

    @property
    def tos_endpoint(self) -> str:
        return f"tos-{self.tos_region}.volces.com"


def _detect_format(audio_path: Path) -> str:
    fmt = FORMAT_MAP.get(audio_path.suffix.lower())
    if not fmt:
        raise RuntimeError(
            f"不支持的音频格式：{audio_path.suffix}。"
            "支持 m4a / mp3 / wav / ogg / flac / mp4 / aac / webm。"
        )
    return fmt


# ---------- TOS 上传（用官方 SDK） ----------

def _make_tos_client(creds: VolcCredentials) -> tos.TosClientV2:
    return tos.TosClientV2(
        creds.access_key_id,
        creds.secret_access_key,
        creds.tos_endpoint,
        creds.tos_region,
    )


def upload_to_tos(audio_path: Path, creds: VolcCredentials,
                  progress: Progress) -> tuple[str, str]:
    """上传本地音频到 TOS，返回 (object_key, 预签名 GET URL)。"""
    fmt = _detect_format(audio_path)
    object_key = f"youtube-transcript/{uuid.uuid4()}.{fmt}"
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    progress(f"正在上传音频到火山 TOS（约 {file_size_mb:.1f} MB）。")

    client = _make_tos_client(creds)
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            with audio_path.open("rb") as f:
                client.put_object(creds.tos_bucket, object_key, content=f)
            break
        except (tos.exceptions.TosClientError, tos.exceptions.TosServerError,
                requests.exceptions.RequestException) as exc:
            last_error = exc
            if attempt < 3:
                wait = attempt * 5
                progress(f"上传失败，{wait} 秒后重试（{attempt}/3）：{exc}")
                time.sleep(wait)
    else:
        raise RuntimeError(f"TOS 上传重试 3 次仍失败：{last_error}")

    progress("音频上传完成，生成预签名访问链接。")
    pre = client.pre_signed_url(
        tos.HttpMethodType.Http_Method_Get,
        creds.tos_bucket,
        object_key,
        expires=86400,  # 24 小时有效，足够火山识别长视频
    )
    return object_key, pre.signed_url


def delete_from_tos(object_key: str, creds: VolcCredentials,
                    progress: Progress) -> None:
    """识别完成后删除 TOS 上传的音频，节省存储费用。"""
    try:
        client = _make_tos_client(creds)
        client.delete_object(creds.tos_bucket, object_key)
        progress("已清理 TOS 上的临时音频。")
    except Exception as exc:
        # 删不掉不要影响主流程，TOS 桶生命周期会兜底
        progress(f"清理 TOS 临时文件失败（不影响结果）：{exc}")


# ---------- 火山 ASR 任务接口 ----------

def _api_headers(api_key: str, request_id: str,
                 sequence: int | None = -1) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "X-Api-Resource-Id": RESOURCE_ID,
        "X-Api-Request-Id": request_id,
    }
    if sequence is not None:
        headers["X-Api-Sequence"] = str(sequence)
    return headers


def submit_task(audio_url: str, audio_format: str,
                creds: VolcCredentials, progress: Progress,
                enable_speakers: bool = True) -> str:
    """提交识别任务，返回 request_id。"""
    request_id = str(uuid.uuid4())
    headers = _api_headers(creds.api_key, request_id, sequence=-1)
    body = {
        "user": {"uid": "youtube-transcript-tool"},
        "audio": {"url": audio_url, "format": audio_format},
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,           # 文本规整（数字、单位等）
            "enable_punc": True,          # 自动标点
            "enable_ddc": True,           # 顺滑（去除口头重复）
            "show_utterances": True,      # 返回 utterance 级别
            "enable_speaker_info": enable_speakers,
        },
    }

    progress("正在向火山引擎提交识别任务。")

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = requests.post(SUBMIT_URL, headers=headers, json=body, timeout=30)
            status = resp.headers.get("X-Api-Status-Code", "")
            message = resp.headers.get("X-Api-Message", "")
            if status == "20000000":
                progress(f"任务已提交，request_id={request_id[:8]}... 等待识别中。")
                return request_id
            raise RuntimeError(
                f"火山提交失败：{status} {message}（HTTP {resp.status_code}）"
            )
        except (requests.exceptions.RequestException, RuntimeError) as exc:
            last_error = exc
            if attempt >= 3:
                break
            wait = attempt * 5
            progress(f"提交失败，{wait} 秒后重试（{attempt}/3）。")
            time.sleep(wait)

    raise RuntimeError(f"火山提交重试 3 次仍失败：{last_error}")


def poll_task(request_id: str, creds: VolcCredentials,
              progress: Progress, timeout: int = 1800,
              interval: int = 5) -> dict[str, Any]:
    """轮询任务状态，直到完成或超时。返回完整 JSON 响应。"""
    headers = _api_headers(creds.api_key, request_id, sequence=None)
    elapsed = 0
    consecutive_net_errors = 0

    while elapsed < timeout:
        try:
            resp = requests.post(QUERY_URL, headers=headers, json={}, timeout=30)
            consecutive_net_errors = 0
        except requests.exceptions.RequestException as exc:
            consecutive_net_errors += 1
            if consecutive_net_errors >= 3:
                raise RuntimeError(f"轮询连续 3 次网络错误：{exc}")
            wait = consecutive_net_errors * 5
            progress(f"轮询网络错误，{wait} 秒后重试。")
            time.sleep(wait)
            elapsed += wait
            continue

        status = resp.headers.get("X-Api-Status-Code", "")
        if status == "20000000":
            progress("识别完成，正在解析结果。")
            return resp.json()
        if status in ("20000001", "20000002"):
            progress(f"火山正在识别中，已等待 {elapsed} 秒。")
            time.sleep(interval)
            elapsed += interval
            continue
        if status == "20000003":
            progress("音频检测为静音，无识别内容。")
            return {"result": {"text": "", "utterances": []}}

        message = resp.headers.get("X-Api-Message", "")
        raise RuntimeError(f"火山查询失败：{status} {message}")

    raise RuntimeError(f"火山识别超时，超过 {timeout} 秒未返回。")


# ---------- 状态持久化（断点续跑） ----------

def _state_path(work_dir: Path) -> Path:
    return work_dir / "volcengine_state.json"


def _read_state(work_dir: Path) -> dict[str, Any]:
    path = _state_path(work_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_state(work_dir: Path, state: dict[str, Any]) -> None:
    path = _state_path(work_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tmp.replace(path)


# ---------- 顶层入口 ----------

def transcribe(audio_path: Path, work_dir: Path,
               progress: Progress, enable_speakers: bool = True) -> dict[str, Any]:
    """端到端：上传音频 → 提交任务 → 轮询 → 返回完整 JSON。

    支持断点续跑：work_dir 里持久化 tos_object_key、tos_url 和 request_id，
    意外中断后再次调用会跳过已完成的步骤。
    成功后自动清理 TOS 上的音频。
    """
    creds = VolcCredentials.from_env()
    work_dir.mkdir(parents=True, exist_ok=True)
    state = _read_state(work_dir)
    audio_format = _detect_format(audio_path)

    tos_url = state.get("tos_url")
    object_key = state.get("tos_object_key")
    if tos_url and object_key:
        progress("发现上次的 TOS 上传记录，跳过上传。")
    else:
        object_key, tos_url = upload_to_tos(audio_path, creds, progress)
        state["tos_object_key"] = object_key
        state["tos_url"] = tos_url
        state["uploaded_at"] = time.time()
        _write_state(work_dir, state)

    request_id = state.get("request_id")
    if request_id:
        progress(f"发现上次的火山任务 request_id={request_id[:8]}...，直接轮询结果。")
    else:
        request_id = submit_task(tos_url, audio_format, creds, progress,
                                 enable_speakers=enable_speakers)
        state["request_id"] = request_id
        state["submitted_at"] = time.time()
        _write_state(work_dir, state)

    response = poll_task(request_id, creds, progress)

    # 识别成功后清理 TOS 临时文件
    if object_key:
        delete_from_tos(object_key, creds, progress)

    return response


def parse_utterances(response: dict[str, Any]) -> list[tuple[str, str]]:
    """从火山响应解析为 (speaker_label, text) 列表。

    speaker_label 形如 "Speaker 1"、"Speaker 2"；
    无说话人信息时统一为 "Speaker 1"。
    """
    result = response.get("result") if isinstance(response, dict) else None
    if not isinstance(result, dict):
        return []

    utterances = result.get("utterances") or []
    if not isinstance(utterances, list) or not utterances:
        text = str(result.get("text") or "").strip()
        return [("Speaker 1", text)] if text else []

    blocks: list[tuple[str, str]] = []
    speaker_map: dict[str, str] = {}

    for utt in utterances:
        if not isinstance(utt, dict):
            continue
        text = str(utt.get("text") or "").strip()
        if not text:
            continue
        raw_speaker = utt.get("speaker")
        if raw_speaker is None:
            additions = utt.get("additions") or {}
            raw_speaker = additions.get("speaker") if isinstance(additions, dict) else None
        if raw_speaker is None:
            label = "Speaker 1"
        else:
            key = str(raw_speaker)
            if key not in speaker_map:
                speaker_map[key] = f"Speaker {len(speaker_map) + 1}"
            label = speaker_map[key]
        blocks.append((label, text))

    return blocks

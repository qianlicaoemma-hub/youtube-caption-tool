const form = document.querySelector("#transcriptForm");
const urlInput = document.querySelector("#urlInput");
const modeInput = document.querySelector("#modeInput");
const languageInput = document.querySelector("#languageInput");
const browserInput = document.querySelector("#browserInput");
const translateInput = document.querySelector("#translateInput");
const statusText = document.querySelector("#statusText");
const progressText = document.querySelector("#progressText");
const submitButton = document.querySelector("#submitButton");
const titleText = document.querySelector("#titleText");
const transcriptOutput = document.querySelector("#transcriptOutput");
const copyButton = document.querySelector("#copyButton");
const mdLink = document.querySelector("#mdLink");
const txtLink = document.querySelector("#txtLink");
const docxLink = document.querySelector("#docxLink");
const streamingIndicator = document.querySelector("#streamingIndicator");
const modeField = document.querySelector("#modeField");
const browserField = document.querySelector("#browserField");
const translateField = document.querySelector("#translateField");
const publicNotice = document.querySelector("#publicNotice");

let currentText = "";
let pollTimer = null;
let currentJobId = "";
let appConfig = {
  public_mode: false,
  allow_audio: true,
  allow_translation: true,
  allow_browser_cookies: true,
};

init();

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setBusy(true);
  resetResult();

  try {
    const payload = {
      url: urlInput.value.trim(),
      mode: appConfig.public_mode ? "captions" : modeInput.value,
      language: languageInput.value,
      cookies_from_browser: appConfig.allow_browser_cookies ? browserInput.value : "",
      translate_to_zh: appConfig.allow_translation ? translateInput.checked : false,
    };

    const didOpenHistory = await maybeOpenHistoricalJob(payload);
    if (didOpenHistory) {
      return;
    }

    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const data = await response.json();
    pollJob(data.job_id);
  } catch (error) {
    showError(error);
    setBusy(false);
  }
});

copyButton.addEventListener("click", async () => {
  if (!currentJobId) return;

  try {
    const data = await postJson(`/api/jobs/${currentJobId}/copy`);
    flashButton(copyButton, "已复制");
    progressText.textContent = data.message || "已复制到系统剪贴板。";
  } catch (error) {
    progressText.textContent = error.message || "复制失败，请手动选中文本复制。";
  }
});

mdLink.addEventListener("click", (event) => downloadFile(event, "markdown", mdLink));
txtLink.addEventListener("click", (event) => downloadFile(event, "txt", txtLink));
docxLink.addEventListener("click", (event) => downloadFile(event, "docx", docxLink));

async function init() {
  setBusy(true);
  await loadConfig();
  applyConfig();

  const initialJobId = jobIdFromLocation();
  if (initialJobId) {
    loadJob(initialJobId);
    return;
  }
  setBusy(false);
}

async function loadConfig() {
  try {
    const response = await fetch("/api/config");
    if (!response.ok) return;
    const data = await response.json();
    appConfig = { ...appConfig, ...data };
  } catch {
    appConfig.public_mode = false;
  }
}

function applyConfig() {
  if (!appConfig.public_mode) {
    return;
  }

  modeInput.value = "captions";
  modeInput.disabled = true;
  browserInput.value = "";
  browserInput.disabled = true;
  translateInput.checked = false;
  translateInput.disabled = true;

  for (const element of [modeField, browserField, translateField]) {
    if (element) element.hidden = true;
  }
  if (publicNotice) publicNotice.hidden = false;
}

function pollJob(jobId) {
  clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      const job = await response.json();

      statusText.textContent = statusLabel(job.status);
      progressText.textContent = progressLabel(job);
      setStreaming(job.status === "queued" || job.status === "running");

      if (job.result) {
        renderResult(job.id, job.result);
      }

      if (job.status === "done") {
        clearInterval(pollTimer);
        setStreaming(false);
        setBusy(false);
      }

      if (job.status === "error") {
        clearInterval(pollTimer);
        setStreaming(false);
        progressText.textContent = job.error ? `处理失败：${job.error}` : "处理失败。";
        if (!job.result) {
          throw new Error(job.error || "处理失败");
        }
        setBusy(false);
      }
    } catch (error) {
      clearInterval(pollTimer);
      showError(error);
      setBusy(false);
    }
  }, 1800);
}

async function loadJob(jobId) {
  clearInterval(pollTimer);
  setBusy(true);
  resetResult();
  titleText.textContent = "读取历史任务";

  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) {
      throw new Error(await response.text());
    }

    const job = await response.json();
    statusText.textContent = statusLabel(job.status);
    progressText.textContent = progressLabel(job);
    setStreaming(job.status === "queued" || job.status === "running");

    if (job.result) {
      renderResult(job.id, job.result);
    } else {
      currentJobId = job.id;
      titleText.textContent = "历史任务";
      transcriptOutput.textContent = job.error ? `处理失败：${job.error}` : "这个任务还没有生成可显示的结果。";
    }

    if (job.status === "queued" || job.status === "running") {
      pollJob(job.id);
      return;
    }

    setStreaming(false);
    setBusy(false);
  } catch (error) {
    showError(error);
    setBusy(false);
  }
}

async function maybeOpenHistoricalJob(payload) {
  const response = await fetch(`/api/jobs/history?url=${encodeURIComponent(payload.url)}`);
  if (!response.ok) {
    return false;
  }

  const data = await response.json();
  const jobs = Array.isArray(data.jobs) ? data.jobs : [];
  const completedJobs = jobs.filter((job) => job.status === "done" && job.id);
  if (completedJobs.some((job) => settingsMatch(job.options || {}, payload))) {
    return false;
  }

  const completed = completedJobs[0];
  if (!completed) {
    return false;
  }

  const message = [
    "发现这个视频已经有完成的历史结果，但本次设置和历史设置不同。",
    "",
    `历史设置：${describeOptions(completed.options || {})}`,
    `当前设置：${describeOptions(payload)}`,
    "",
    "打开历史结果吗？",
    "选择“取消”会继续按当前设置新建任务，可能产生 OpenAI 费用。",
  ].join("\n");

  if (!window.confirm(message)) {
    return false;
  }

  window.history.pushState({}, "", `/jobs/${completed.id}`);
  await loadJob(completed.id);
  return true;
}

function renderResult(jobId, result) {
  currentJobId = jobId;
  titleText.textContent = result.title || "逐字稿";
  currentText = result.text || "";
  transcriptOutput.textContent = currentText || "没有生成内容。";
  copyButton.disabled = !currentText;
  setDownload(mdLink, `/api/jobs/${jobId}/download/markdown`);
  setDownload(txtLink, `/api/jobs/${jobId}/download/txt`);
  setDownload(docxLink, `/api/jobs/${jobId}/download/docx`);
}

function setDownload(element, href) {
  element.href = href;
  element.setAttribute("download", "");
  element.classList.remove("disabled");
}

function resetResult() {
  titleText.textContent = "处理中";
  transcriptOutput.textContent = "";
  setStreaming(false);
  currentText = "";
  currentJobId = "";
  copyButton.disabled = true;
  for (const link of [mdLink, txtLink, docxLink]) {
    link.href = "#";
    link.removeAttribute("download");
    link.classList.add("disabled");
  }
}

function setBusy(isBusy) {
  submitButton.disabled = isBusy;
  submitButton.querySelector("span").textContent = isBusy ? "处理中" : "生成逐字稿";
}

function showError(error) {
  statusText.textContent = "失败";
  progressText.textContent = "处理失败。";
  setStreaming(false);
  if (!currentText) {
    transcriptOutput.textContent = error.message || String(error);
  }
}

function statusLabel(status) {
  if (status === "queued") return "排队中";
  if (status === "running") return "处理中";
  if (status === "done") return "完成";
  if (status === "error") return "失败";
  return "待处理";
}

function progressLabel(job) {
  const parts = [job.progress || "处理中。"];
  if (job.elapsed_seconds !== undefined && job.status === "running") {
    parts.push(`已用时 ${formatDuration(job.elapsed_seconds)}`);
  }
  if (job.seconds_since_update !== undefined && job.status === "running") {
    parts.push(`当前步骤已等待 ${formatDuration(job.seconds_since_update)}`);
  }
  return parts.join(" ｜ ");
}

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) return `${seconds} 秒`;
  return `${minutes} 分 ${String(seconds).padStart(2, "0")} 秒`;
}

function setStreaming(isStreaming) {
  if (!streamingIndicator) return;
  streamingIndicator.hidden = !isStreaming;
}

function settingsMatch(options, payload) {
  return (
    (options.mode || "auto") === payload.mode &&
    (options.language || "auto") === payload.language &&
    (options.cookies_from_browser || "") === (payload.cookies_from_browser || "") &&
    Boolean(options.translate_to_zh) === Boolean(payload.translate_to_zh)
  );
}

function describeOptions(options) {
  return [
    modeLabel(options.mode || "auto"),
    languageLabel(options.language || "auto"),
    browserLabel(options.cookies_from_browser || ""),
    options.translate_to_zh ? "含中文翻译" : "不含中文翻译",
  ].join(" / ");
}

function modeLabel(value) {
  if (value === "audio") return "强制音频识别";
  if (value === "captions") return "只读取字幕";
  return "字幕优先";
}

function languageLabel(value) {
  if (value === "zh") return "中文";
  if (value === "en") return "英文";
  return "自动语言";
}

function browserLabel(value) {
  if (!value) return "不使用登录态";
  if (value === "auto") return "自动尝试登录态";
  return `登录态 ${value}`;
}

function jobIdFromLocation() {
  const params = new URLSearchParams(window.location.search);
  const queryJobId = params.get("job_id");
  if (queryJobId) return queryJobId;

  const match = window.location.pathname.match(/^\/jobs\/([a-f0-9]{8,})$/i);
  return match ? match[1] : "";
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const didCopy = document.execCommand("copy");
  textarea.remove();

  if (!didCopy) {
    throw new Error("copy failed");
  }
}

async function downloadFile(event, fileType, element) {
  event.preventDefault();
  if (!currentJobId || element.classList.contains("disabled")) return;

  try {
    progressText.textContent = `正在保存 ${element.textContent} 到下载文件夹。`;
    const data = await postJson(`/api/jobs/${currentJobId}/save/${fileType}`);
    progressText.textContent = data.message || "已保存到下载文件夹。";
  } catch (error) {
    progressText.textContent = error.message || "保存失败。";
  }
}

function flashButton(button, text) {
  const original = button.textContent;
  button.textContent = text;
  setTimeout(() => {
    button.textContent = original;
  }, 1400);
}

async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  const text = await response.text();
  let data = {};

  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }

  if (!response.ok) {
    const detail = data.detail || data.message || response.statusText;
    throw new Error(detail);
  }

  return data;
}

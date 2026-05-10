const form = document.querySelector("#transcriptForm");
const urlInput = document.querySelector("#urlInput");
const modeInput = document.querySelector("#modeInput");
const languageInput = document.querySelector("#languageInput");
const browserInput = document.querySelector("#browserInput");
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
const publicNotice = document.querySelector("#publicNotice");

let currentText = "";
let pollTimer = null;
let currentJobId = "";
let appConfig = {
  public_mode: false,
  allow_audio: true,
  allow_translation: false,
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
      translate_to_zh: false,
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

  for (const element of [modeField, browserField]) {
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
    "选择“取消”会继续按当前设置新建任务，可能产生火山引擎识别费用。",
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
  submitButton.querySelector("span").textContent = isBusy ? "处理中" : "识别";
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
    (options.cookies_from_browser || "") === (payload.cookies_from_browser || "")
  );
}

function describeOptions(options) {
  return [
    modeLabel(options.mode || "auto"),
    languageLabel(options.language || "auto"),
    browserLabel(options.cookies_from_browser || ""),
  ].join(" / ");
}

function modeLabel(value) {
  if (value === "audio") return "AI 转录";
  if (value === "captions") return "仅用字幕";
  return "自动";
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

/* ============================================================
 * 以下是 UI 重设计追加的辅助逻辑（不修改上面任何已有函数）。
 * 1. 侧栏：最近任务列表
 * 2. 输入框下方的示例 chip：填充 URL，不自动提交
 * 3. 移动端侧栏开关
 * ============================================================ */

const recentList = document.querySelector("#recentList");
const sidebarEl = document.querySelector("#sidebar");
const sidebarToggle = document.querySelector("#sidebarToggle");

async function loadRecentJobs() {
  if (!recentList) return;
  try {
    const response = await fetch("/api/jobs/recent?limit=12");
    if (!response.ok) return;
    const data = await response.json();
    renderRecentJobs(Array.isArray(data.jobs) ? data.jobs : []);
  } catch {
    /* 静默失败：侧栏可用即可，不阻塞主流程 */
  }
}

function renderRecentJobs(jobs) {
  if (!recentList) return;
  if (!jobs.length) {
    recentList.innerHTML = '<p class="recent-empty">还没有任务。<br/>粘贴一个链接开始。</p>';
    return;
  }
  recentList.innerHTML = jobs.map(jobToCard).join("");
}

function jobToCard(job) {
  const isZh =
    (job.language && job.language === "zh") ||
    /[一-鿿]/.test(job.title || "");
  const badgeClass = isZh ? "badge-zh" : "badge-en";
  const badgeText = isZh ? "中" : "EN";
  const title = escapeHtml(job.title || "未命名");
  const subParts = [
    escapeHtml(job.uploader || ""),
    statusHint(job),
    relativeTime(job.updated_at),
  ].filter(Boolean);
  const sub = subParts.join(" · ");
  const isActive = job.id && job.id === currentJobId;
  return `
    <a href="/jobs/${job.id}" class="recent-card${isActive ? " is-active" : ""}" data-job-id="${job.id}">
      <span class="lang-badge ${badgeClass}">${badgeText}</span>
      <span class="recent-text">
        <span class="recent-title">${title}</span>
        <span class="recent-sub">${sub}</span>
      </span>
    </a>`;
}

function statusHint(job) {
  if (job.status === "running") return "处理中";
  if (job.status === "queued") return "排队中";
  if (job.status === "error") return "失败";
  return "";
}

function relativeTime(ts) {
  if (!ts) return "";
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (seconds < 60) return "刚刚";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} 小时前`;
  if (seconds < 86400 * 7) return `${Math.floor(seconds / 86400)} 天前`;
  const d = new Date(ts * 1000);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

/* 示例 URL chip：只填充输入框，不自动提交 */
document.querySelectorAll("[data-example-url]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const url = btn.getAttribute("data-example-url") || "";
    if (!urlInput) return;
    urlInput.value = url;
    urlInput.focus();
  });
});

/* 提交后稍后刷新一次侧栏，让新任务尽快出现 */
form.addEventListener("submit", () => {
  setTimeout(loadRecentJobs, 2500);
});

/* 移动端侧栏开关 */
if (sidebarToggle && sidebarEl) {
  sidebarToggle.addEventListener("click", () => {
    sidebarEl.classList.toggle("is-open");
  });
  /* 点击侧栏内的链接后自动收起 */
  sidebarEl.addEventListener("click", (event) => {
    if (event.target.closest(".recent-card")) {
      sidebarEl.classList.remove("is-open");
    }
  });
}

/* 桌面端：侧栏宽度可拖拽 */
const sidebarResizer = document.querySelector("#sidebarResizer");
if (sidebarResizer) {
  const SIDEBAR_MIN = 180;
  const SIDEBAR_MAX = 480;
  const STORAGE_KEY = "verbatim:sidebarWidth";

  // 启动时恢复保存的宽度
  const savedWidth = parseInt(localStorage.getItem(STORAGE_KEY) || "", 10);
  if (savedWidth >= SIDEBAR_MIN && savedWidth <= SIDEBAR_MAX) {
    document.documentElement.style.setProperty("--sidebar-width", `${savedWidth}px`);
  }

  let isResizing = false;
  let pendingWidth = 0;

  function applyWidth(width) {
    pendingWidth = Math.max(SIDEBAR_MIN, Math.min(SIDEBAR_MAX, Math.round(width)));
    document.documentElement.style.setProperty("--sidebar-width", `${pendingWidth}px`);
  }

  sidebarResizer.addEventListener("mousedown", (event) => {
    event.preventDefault();
    isResizing = true;
    sidebarResizer.classList.add("is-dragging");
    document.body.classList.add("is-resizing");
  });

  document.addEventListener("mousemove", (event) => {
    if (!isResizing) return;
    applyWidth(event.clientX);
  });

  function stopResize() {
    if (!isResizing) return;
    isResizing = false;
    sidebarResizer.classList.remove("is-dragging");
    document.body.classList.remove("is-resizing");
    if (pendingWidth) {
      localStorage.setItem(STORAGE_KEY, String(pendingWidth));
    }
  }

  document.addEventListener("mouseup", stopResize);
  document.addEventListener("mouseleave", stopResize);

  // 双击手柄重置默认宽度
  sidebarResizer.addEventListener("dblclick", () => {
    document.documentElement.style.removeProperty("--sidebar-width");
    localStorage.removeItem(STORAGE_KEY);
  });
}

/* 启动加载 + 30 秒一次自动刷新 */
loadRecentJobs();
setInterval(loadRecentJobs, 30000);

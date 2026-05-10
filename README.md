# Verbatim · YouTube 逐字稿工具

本地运行的 YouTube 逐字稿工具。粘贴视频链接，优先读取 YouTube 字幕；没有字幕时，再调用火山引擎/豆包大模型录音文件识别，输出 Markdown / TXT / Word。

适合整理播客、访谈、课程和长视频内容。推荐在自己的电脑上运行：可以使用本机 YouTube 登录态，API Key 和识别费用也都留在你自己的账户里。

## 功能

- 字幕优先：读取 YouTube 官方字幕 / 自动字幕，零成本
- AI 转录：无字幕时调用火山引擎/豆包 ASR
- 支持中英文视频
- 支持说话人标注，例如 `Speaker 1` / `Speaker 2`
- 导出 Markdown / TXT / Word
- 最近任务、历史结果、相同设置断点续跑
- 本地读取浏览器 YouTube 登录态，应对 YouTube 登录验证

## 成本

| 场景 | 处理方式 | 成本 |
|---|---|---|
| 有 YouTube 字幕 | 直接读字幕 | ¥0 |
| 无字幕视频 | 火山引擎/豆包 ASR | 约 ¥1.5/小时 |

4 小时无字幕视频约 ¥6。视频有字幕时不会调用付费 ASR。

## 准备

需要：

- macOS（主要验证环境）
- Python 3.11+
- `ffmpeg`
- `yt-dlp`
- Node.js（推荐）
- 火山引擎账号：语音 API Key、IAM AK/SK、TOS bucket

完整安装步骤见 [INSTALL.md](INSTALL.md)。

## 快速开始

```bash
git clone https://github.com/qianlicaoemma-hub/youtube-caption-tool.git youtube-transcript
cd youtube-transcript
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

然后编辑 `.env`，填入火山引擎配置。

启动：

```bash
./start.command
```

或：

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：`http://127.0.0.1:8000`

## 怎么用

默认选择「自动」即可：

- 有字幕：直接读取 YouTube 字幕
- 没字幕：自动切换到 AI 转录
- 只想零成本：高级设置里选「仅用字幕（无字幕则报错）」
- 想绕过字幕重新听音频：选「AI 转录」

如果 YouTube 提示 `Sign in to confirm you're not a bot`，先在本机浏览器登录 YouTube，再在页面里选择对应的「YouTube 登录态」。

## 输出原则

- 不总结
- 不提炼
- 不改写成正式书面稿
- 不加时间戳
- 只做轻度清洗
- 保留原始口语表达

## 分享给朋友

朋友可以 fork/clone 这个仓库在本地运行。每个人都应该配置自己的火山引擎账号和 `.env`，识别费用从自己的账户扣。

如果不配置火山账号，也可以只用字幕路径：选择「仅用字幕（无字幕则报错）」即可，零成本。

## 为什么不推荐公开部署

YouTube 经常会对云服务器 IP 触发登录验证或 bot 检查；公开部署也会让陌生用户消耗你的火山引擎余额。

所以推荐本地运行。`PUBLIC_MODE=true` 仅保留为实验性字幕模式，见 [DEPLOY.md](DEPLOY.md)。

## English

Verbatim is a local-first YouTube transcript tool. Paste a YouTube URL, read available YouTube captions first, and fall back to Volcengine/Doubao ASR when captions are unavailable.

Features:

- Captions-first workflow, free when YouTube captions exist
- Volcengine/Doubao ASR fallback for videos without captions
- Chinese and English support
- Speaker labels
- Markdown / TXT / Word export
- Local history and resume support
- Local browser cookie support for YouTube sign-in checks

Quick start:

```bash
git clone https://github.com/qianlicaoemma-hub/youtube-caption-tool.git youtube-transcript
cd youtube-transcript
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your own Volcengine credentials, then run:

```bash
./start.command
```

Open `http://127.0.0.1:8000`.

See [INSTALL.md](INSTALL.md) for the full setup guide.

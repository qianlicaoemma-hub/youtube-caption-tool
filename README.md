# YouTube 逐字稿工具

这是一个本地网页工具：粘贴 YouTube 链接，生成可复制到 Obsidian、飞书、Word 的逐字稿。

## 它会怎么处理

默认流程：

1. 先尝试读取 YouTube 自带字幕。
2. 如果没有字幕或读取失败，自动切换到 OpenAI 音频识别。
3. 音频识别会临时下载音频，不下载视频画面。
4. 长视频会自动切成小段处理。
5. 输出 Markdown、TXT、Word 三种格式。

如果你一定需要 Speaker 1 / Speaker 2 这种说话人标注，建议在页面里选择“强制音频识别”。YouTube 字幕通常没有可靠的说话人信息。

## 准备环境

你本机已经有 `ffmpeg` 和 `yt-dlp`。还需要安装 Python 依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

配置 OpenAI API Key：

```bash
cp .env.example .env
```

然后打开 `.env`，把里面的 `OPENAI_API_KEY` 改成你的真实 Key。

不要把 `.env` 发给别人，也不要提交到 Git。

## 启动

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## YouTube 要求登录怎么办

如果遇到 “Sign in to confirm you're not a bot”，先在浏览器里登录 YouTube，然后在页面的“YouTube 登录态”里选择你正在使用的浏览器，例如 Chrome 或 Safari。

这相当于让工具使用你自己的 YouTube 登录状态读取字幕或音频，不是绕过机制。

## 成本提醒

OpenAI 音频识别大约按分钟计费。1-2 小时播客通常是几元人民币量级，具体以 OpenAI 当前账单为准。

## 输出原则

- 不总结
- 不提炼
- 不改写成正式书面稿
- 不加时间戳
- 只做轻度清洗
- 保留原始口语表达

## 当前限制

- 音频识别失败时会保留已经完成的部分逐字稿。
- 再次用相同链接、处理方式、语言、登录态和翻译设置提交任务时，如果已有完成结果，会直接打开历史结果；如果是未完成任务，会自动复用任务，并跳过已经成功识别的音频片段。
- 如果服务重启，任务状态会从 `app/outputs/<job_id>/job.json` 恢复；片段识别结果保存在 `app/outputs/<job_id>/segments/`。

## 公开字幕版

如果要部署成公开链接，先使用免费字幕版：

```bash
PUBLIC_MODE=true uvicorn app.main:app --host 0.0.0.0 --port 8000
```

公开模式只允许读取 YouTube 可用字幕，会禁用 OpenAI 音频识别、中文翻译和本机浏览器登录态。

部署公开版前，请看 [DEPLOY.md](DEPLOY.md)。

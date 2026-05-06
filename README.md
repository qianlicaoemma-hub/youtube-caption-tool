# YouTube 逐字稿工具

一个本地运行的网页工具：粘贴 YouTube 链接，生成可复制到 Obsidian、飞书、Word 的完整逐字稿。

这个项目推荐在你自己的电脑上运行。这样工具可以在需要时读取你本机浏览器的 YouTube 登录态，也可以让 OpenAI API Key 和费用留在你自己账户下。

## 功能

- 读取 YouTube 官方字幕 / 自动字幕
- 支持中文和英文
- 可选 OpenAI 音频识别，支持 `Speaker 1` / `Speaker 2` 说话人标注
- 可选英文转中文逐字翻译
- 输出 Markdown / TXT / Word
- 长音频自动切片
- 失败后保留已完成片段，再次提交相同设置可断点续跑
- 浏览器里查看历史任务结果

## 准备环境

需要：

- Python 3.11+
- `ffmpeg`
- `yt-dlp`
- Node.js，推荐安装；`yt-dlp` 会用它辅助 YouTube 解析

安装 Python 依赖：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

配置 OpenAI API Key：

```bash
cp .env.example .env
```

然后编辑 `.env`，把 `OPENAI_API_KEY` 改成你自己的 Key。不要提交 `.env`。

如果只读取 YouTube 字幕、不勾选中文翻译、不使用强制音频识别，就不会调用 OpenAI。

## 启动

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开：

```text
http://127.0.0.1:8000
```

## YouTube 要求登录怎么办

如果遇到：

```text
Sign in to confirm you're not a bot
```

先在本机浏览器里登录 YouTube，然后在页面的“YouTube 登录态”里选择你正在使用的浏览器，例如 Chrome、Safari、Firefox 或 Edge。

这会让 `yt-dlp` 读取你自己本机的 YouTube 登录状态。登录态不会提交到 GitHub，也不应该上传到公共服务器。

## 使用建议

- 想省钱、速度快：优先选择“只读取 YouTube 字幕”。
- 想要说话人标注：选择“强制音频识别”。
- 想要中文稿：勾选“同时输出中文逐字翻译”。
- 长视频建议先不勾翻译，确认识别稳定后再翻译。

## 成本提醒

OpenAI 音频识别和中文翻译会产生费用，具体以 OpenAI 账单为准。

只读取 YouTube 字幕，且不勾选中文翻译，不会产生 OpenAI 费用。

## 输出原则

- 不总结
- 不提炼
- 不改写成正式书面稿
- 不加时间戳
- 只做轻度清洗
- 保留原始口语表达

## 为什么不推荐公开部署

这个工具不推荐直接做成所有人都能访问的公共网页。

原因是 YouTube 经常会对云服务器 IP 触发登录验证或 bot 检查。用户即使在自己的浏览器里登录了 YouTube，Render / Railway 等云端后端也拿不到用户的 youtube.com cookies。

如果要支持用户自己的 YouTube 登录态，最合适的方式是本地运行，或未来做浏览器插件。

`PUBLIC_MODE=true` 仍保留为实验性字幕模式，详见 [DEPLOY.md](DEPLOY.md)。

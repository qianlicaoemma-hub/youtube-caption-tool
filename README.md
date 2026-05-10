# YouTube 逐字稿工具

一个本地运行的网页工具：粘贴 YouTube 链接，生成可复制到 Obsidian、飞书、Word 的完整逐字稿。

工具优先读取 YouTube 自带字幕（零成本）；没有字幕时调用**火山引擎/豆包大模型录音文件识别**做音频识别（中文质量国内顶级）。

推荐在你自己的电脑上运行：可以使用本机浏览器的 YouTube 登录态，火山引擎账号和余额都留在你自己名下。

## 功能

- 优先读取 YouTube 官方字幕 / 自动字幕（中英文）
- 没字幕时调用火山引擎/豆包大模型录音文件识别（支持说话人 `Speaker 1` / `Speaker 2` 标注）
- 单文件支持最长 5 小时音频，无需切片
- 输出 Markdown / TXT / Word
- 失败后保留中间状态（已上传音频 + 已提交任务），再次提交相同设置可断点续跑
- 浏览器里查看历史任务结果

- Python 3.11+
- `ffmpeg`
- `yt-dlp`
- Node.js，推荐安装；`yt-dlp` 会用它辅助 YouTube 解析

需要：

- Python 3.11+
- `ffmpeg`
- `yt-dlp`
- Node.js（推荐安装；`yt-dlp` 会用它辅助 YouTube 解析）
- **火山引擎账号**（含语音控制台 API Key、IAM 访问密钥、TOS 桶）

详见 [INSTALL.md](INSTALL.md)。

## 快速安装

把这份仓库交给你的 AI 助手（Claude Code / Cursor 等），告诉它："帮我按 INSTALL.md 安装这个工具"，然后用自然语言对话即可。

手动安装：

```bash
git clone https://github.com/qianlicaoemma-hub/youtube-caption-tool.git youtube-transcript
cd youtube-transcript
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入火山引擎四件套
```

## 启动

**最简单：双击根目录的 `start.command`**

会自动激活 venv、启动服务、并在浏览器打开 `http://127.0.0.1:8000`。

> 首次双击会被 macOS Gatekeeper 拦截。处理：右键 → 打开 → 同意。

**或者命令行：**

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开：`http://127.0.0.1:8000`

**关闭工具**：在终端按 `Ctrl + C`，或直接关掉 `start.command` 启动的终端窗口。

## YouTube 要求登录怎么办

如果遇到：

```text
Sign in to confirm you're not a bot
```

先在本机浏览器里登录 YouTube，然后在页面的"YouTube 登录态"里选择你正在使用的浏览器（Chrome、Safari、Firefox、Edge 等）。

这会让 `yt-dlp` 读取你自己本机的 YouTube 登录状态。登录态不会提交到 GitHub，也不应该上传到公共服务器。

## 成本说明

| 视频类型 | 处理方式 | 4 小时视频成本 |
|---|---|---|
| 有 YouTube 字幕（任意语言） | 直接读字幕 | **¥0** |
| 无字幕的中文视频 | 火山引擎 ASR | 约 **¥6**（≈ $0.84） |
| 无字幕的英文视频 | 火山引擎 ASR | 约 **¥6**（≈ $0.84） |

火山引擎录音文件识别按音频时长计费，约 ¥1.5/小时。
英文视频一般都有 YouTube 字幕，95% 场景下不会调用付费 API。

## 输出原则

- 不总结
- 不提炼
- 不改写成正式书面稿
- 不加时间戳
- 只做轻度清洗（去口水词、明显重复卡顿）
- 保留原始口语表达

## 分享给朋友用

把这个仓库 fork 或推荐给朋友后，他们需要：

1. 自己注册一份火山引擎账号、配置 API Key + IAM AK/SK + TOS 桶（详见 [INSTALL.md](INSTALL.md) 第 7 步）
2. 在本地填好自己的 `.env`，识别费用从他们自己火山账户扣，跟你无关
3. 用自己电脑跑（音频识别不能共享他人 API Key，否则会泄露成本）

**如果朋友不想注册火山账号**：他们仍可以使用工具，但只有 YouTube 自带字幕的视频能转。在「高级设置」→「处理方式」里选「仅用字幕（无字幕则报错）」即可。这种用法零成本、无需任何 API Key。

## 为什么不推荐公开部署

这个工具不推荐直接做成所有人都能访问的公共网页。

原因：YouTube 经常会对云服务器 IP 触发登录验证或 bot 检查。即便只读字幕，云端 IP 同样会被风控拦截。
另外公开部署后，火山引擎识别费用会被陌生用户消耗。

如果要支持别人用自己的 YouTube 登录态和自己的火山账户，最合适的方式是**本地运行**或未来做浏览器插件。

`PUBLIC_MODE=true` 仍保留为实验性字幕模式，详见 [DEPLOY.md](DEPLOY.md)。

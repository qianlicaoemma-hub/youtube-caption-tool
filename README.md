# Verbatim · YouTube 逐字稿工具

> 粘贴 YouTube 链接 → 拿到带说话人标注、可复制到 Obsidian/飞书/Word 的完整逐字稿。

本地运行的网页工具。**优先读取 YouTube 自带字幕（零成本）**；遇到没字幕的视频，自动调用**火山引擎/豆包大模型录音文件识别**做音频识别（中文质量国内顶级）。

> [!NOTE]
> 当前仅支持 **macOS**。Windows/Linux 用户暂未验证（`start.command`、`pbcopy` 等依赖 macOS）。

<!-- 把当前 UI 截一张图放到 docs/screenshot.png，让 README 直观展示效果 -->
<!-- ![Verbatim UI](docs/screenshot.png) -->

---

## 谁会想用这个

适合你如果：

- 经常看长 YouTube 视频（播客、访谈、技术大会、AI 课程）想拿逐字稿做笔记 / 知识沉淀
- 想要**说话人分离**（Speaker 1 / Speaker 2 / ...），但 YouTube 自动字幕没有
- 中英文视频都要处理，且**对中文识别质量挑剔**
- 4 小时长视频不想等 60 分钟（走 Whisper 本地）
- 不想把视频 URL 上传给第三方 SaaS（隐私 / 合规考虑）

不适合你如果：

- 只看带字幕的英文视频，YouTube CC 直接复制就够（虽然这工具同样能让你一键复制带换行清洗的版本）
- 想一键 SaaS、不想配 API Key —— 推荐 Otter.ai、Notta 等付费云服务
- 用 Windows / Linux —— 当前未适配

## 它解决了什么

| 场景 | 普通做法 | 用 Verbatim |
|---|---|---|
| 1 小时英文 TED Talk | 看 YouTube CC 字幕，复制带时间戳乱码 | 1 秒读字幕 → 干净段落 + Markdown |
| 3 小时中文播客 | 自己录音再上传 Whisper，1 小时等待 | 12 分钟出稿，¥4.5 ，自带说话人分离 |
| 中英混合 AI 课程 | 字幕只有英文，再人工翻译 | YT 双字幕时**英中并排输出**，免翻译 |
| 4 小时录音文件 | 切片上传多次 | 单文件直传，不用切片，不超时 |

## 功能特性

- ✅ **字幕优先**：YouTube 有字幕（含自动字幕）直接读，零成本、几秒出结果
- ✅ **双语对照输出**：当 YouTube 提供英文 + 翻译字幕时，自动并列输出 `English` + `中文` 两段
- ✅ **AI 兜底**：没字幕时调用**豆包 Seed-ASR 2.0**，支持长音频（最长 5 小时）
- ✅ **说话人标注**：`Speaker 1` / `Speaker 2` 自动分离，多人对谈场景特别有用
- ✅ **轻度清洗**：去口水词（嗯/啊/uh/um）和明显重复，但**不总结、不改写、不删信息**
- ✅ **三种格式**：Markdown / TXT / Word（.docx）
- ✅ **历史任务**：左侧栏列出最近处理过的视频，点击直接看
- ✅ **断点续跑**：意外中断后重新提交相同链接，跳过已完成的步骤继续
- ✅ **一键启动**：`start.command` 双击即用

## 输出原则（重要）

- **不总结、不提炼、不改写成正式书面稿**
- **不加时间戳**
- **只做轻度清洗**（去口水词、明显重复卡顿）
- **保留原始口语表达**

如果你想要的是"AI 总结"或"思维导图"，**这工具不合适**。它只做"忠实转录"。

## 示例输出（节选）

```
# 139.【Agent 的综述】和苏煜聊 Agent 技术史
Source: https://www.youtube.com/watch?v=Xxz5uh0L1mE
Uploader: Zhang Xiaojun Podcast
Method: 火山引擎/豆包 ASR

## Transcript

Speaker 1:
今天非常荣幸请到苏煜老师跟我们一起来聊聊 Agent。
苏煜老师是我们这边非常资深的研究者，
对整个 Agent 技术的发展史有相当深入的理解。

Speaker 2:
谢谢主持人。我先简单回顾一下，从 ReAct 这一篇 22 年的论文开始，
到 Toolformer、AutoGPT、再到今天的 OpenClaw Moment……
```

## 成本

| 视频类型 | 处理方式 | 4 小时视频成本 |
|---|---|---|
| 有 YouTube 字幕（任意语言） | 直接读字幕 | **¥0** |
| 无字幕的中文视频 | 火山引擎 ASR | 约 **¥6**（≈ $0.84）|
| 无字幕的英文视频 | 火山引擎 ASR | 约 **¥6**（≈ $0.84）|

火山录音文件识别按音频时长计费，约 ¥1.5/小时。  
**英文视频 95% 有字幕，几乎不会扣费。**

## 安装

完整步骤见 [INSTALL.md](INSTALL.md)。

**速览**：你需要

1. macOS + Python 3.11+ + ffmpeg + yt-dlp + Node.js
2. **一个火山引擎账号**，并配置 4 个值（API Key / IAM AK / IAM SK / TOS 桶名）
3. 一份本仓库代码

> 不熟悉命令行？把这个 repo 交给 Claude Code / Cursor，告诉它"按 INSTALL.md 帮我装好"，全程自然语言对话即可。

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

**关闭服务**：在终端按 `Ctrl + C`，或直接关闭 `start.command` 启动的终端窗口。

## 使用建议

- **第一次试用**：先用一个**有字幕的英文短视频**（比如任意 TED Talk）走一遍流程。0 成本验证全链路。
- **跑长视频前**：确认 YouTube 是否能拿到字幕（`处理方式` 选「自动」），有字幕就秒出；没有再花钱。
- **想一定要说话人分离**：在「高级设置」选「AI 转录（绕过字幕）」，强制走火山，会自动分 Speaker。
- **YouTube 风控**：如果报 "Sign in to confirm you're not a bot"，先在本机浏览器登录 YouTube，再在「高级设置」→「YouTube 登录态」选你的浏览器。
- **省钱**：4 小时长视频如果有字幕，零成本；只在确认无字幕时再走 ASR。

## 分享给朋友用

把仓库分享给朋友后，他们需要：

1. 自己注册一份火山引擎账号、配自己的 4 件套（详见 [INSTALL.md 第 7 步](INSTALL.md)）
2. 在自己电脑本地填好 `.env`，识别费用从他们自己火山账户扣
3. 用自己电脑跑（**API Key 切勿共享给陌生人**，会被刷费用）

**朋友不想注册火山**？工具仍可用，只能转有 YouTube 字幕的视频。在「高级设置」→「处理方式」选「仅用字幕」即可，零成本零 Key。

## 已知限制

- **仅 macOS**：用了 `pbcopy`、`start.command` 等 macOS 特性
- **YouTube 风控**：偶发 "请登录验证"，需要切换浏览器登录态（详见上方使用建议）
- **不推荐公开部署**：云服务器 IP 容易触发 YouTube bot 检测，且火山 API Key 不能共享给陌生人
- **国内访问火山**：API 与 TOS 都在国内，海外网络访问 TOS 上传可能慢

## 技术栈

- **后端**：FastAPI（Python）
- **前端**：vanilla HTML/CSS/JS（无构建系统）
- **YouTube 抓取**：yt-dlp
- **音频处理**：ffmpeg
- **语音识别**：火山引擎大模型录音文件识别（豆包 Seed-ASR 2.0）
- **对象存储**：火山引擎 TOS（用户自己的桶）

## 反馈

- 报 bug、提需求：开 [GitHub Issue](https://github.com/qianlicaoemma-hub/youtube-caption-tool/issues)
- 安装卡住：把错误贴到 Issue 里，附带 macOS 版本、Python 版本、错误日志

## License

MIT License — 详见 [LICENSE](LICENSE)（如果还没添加，欢迎自由使用、修改、分享）。

---

`PUBLIC_MODE=true` 仍保留为实验性字幕模式，详见 [DEPLOY.md](DEPLOY.md)。

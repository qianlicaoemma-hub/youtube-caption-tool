# YouTube 逐字稿工具交接文档

更新时间：2026-05-05

## 项目目标

本地网页工具：用户输入 YouTube 链接后，生成方便复制到 Obsidian / 飞书 / Word 的完整逐字稿。

用户核心要求：

- 支持中文和英文识别
- 需要说话人标注，例如 `Speaker 1` / `Speaker 2`
- 不需要时间戳
- 输出完整内容，不总结、不提炼、不改写
- 只做轻度清洗：去掉明显口水词、无意义停顿和重复卡顿
- 保留原始口语表达，不改成正式书面稿
- 不删除有信息量的内容
- 输出 Markdown / TXT / DOCX，方便复制和保存

## 当前目录

工作目录：

```text
/Users/macbook/Desktop/AI学习/Codex/逐字稿
```

主要文件：

```text
app/main.py              FastAPI 后端、任务状态、复制/保存接口
app/transcriber.py       YouTube 字幕读取、音频下载、OpenAI 转写、翻译、导出
app/static/index.html    前端页面
app/static/app.js        前端交互
app/static/styles.css    前端样式
requirements.txt         Python 依赖
.env.example             API Key 示例
.env                     用户已填 OpenAI API Key，不要打印、不要提交
README.md                使用说明
HANDOFF.md               本文件
```

## 启动方式

依赖已安装在 `.venv`。

```bash
cd /Users/macbook/Desktop/AI学习/Codex/逐字稿
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

如果服务已在运行，重启：

```bash
pkill -f 'uvicorn app.main:app' || true
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000
```

前端 JS 有版本号缓存参数，目前是：

```html
/static/app.js?v=20260505-5
```

修改前端后建议更新版本号，并让用户 `Cmd + Shift + R` 强制刷新。

## 当前已实现

### 1. YouTube 字幕快路径

模式：

```text
只读取 YouTube 字幕
字幕优先，失败后音频识别
```

实现：

- `yt-dlp`
- 自动添加：
  - `--js-runtimes node`
  - `--remote-components ejs:github`
- cookies：
  - 页面默认 `自动尝试`
  - 已确认 `chrome:Profile 1` 在用户机器上能通过 YouTube 验证

相关代码：

- `app/transcriber.py`
  - `_download_and_parse_captions`
  - `_yt_dlp_attempts`
  - `_parse_vtt`

### 2. OpenAI 音频识别路径

模式：

```text
强制音频识别
```

实现：

- `yt-dlp` 下载临时音频，只下载音频，不下载视频画面
- `ffmpeg` 压缩并切片
- OpenAI `gpt-4o-transcribe-diarize`
- `response_format="diarized_json"`
- 输出 `Speaker 1` / `Speaker 2`

当前切片：

```python
CHUNK_SECONDS = 120
```

即每段约 2 分钟。

OpenAI 客户端：

```python
OpenAI(timeout=180, max_retries=1)
```

应用层每段最多再尝试 3 次，文案类似：

```text
正在识别第 1/1 段音频，正在进行第 1/3 次 OpenAI 请求。
```

### 3. 部分结果保存

已经实现：

- 每完成一个音频片段，立刻把已完成部分写入 Markdown / TXT / DOCX
- 页面运行中也会显示部分逐字稿
- 如果后续失败，页面不会清空已显示内容
- 复制/保存按钮可以对已有部分结果工作

相关代码：

- `app/transcriber.py`
  - `_transcribe_audio_with_openai`
  - 每段完成后调用 `_write_outputs`
  - 通过 `progress(..., partial_result=partial_result)` 更新内存任务状态
- `app/main.py`
  - `_run_job.report`
  - `jobs[job_id]["result"] = partial_result`
- `app/static/app.js`
  - 轮询时如果 `job.result` 存在，立刻 `renderResult`
  - 任务失败时，如果有部分结果，不覆盖正文

### 4. 保存/复制

因为 in-app browser 的剪贴板和下载权限不稳定，已改成后端执行：

- `POST /api/jobs/{job_id}/copy`
  - 使用 macOS `pbcopy`
- `POST /api/jobs/{job_id}/save/{file_type}`
  - 保存到 `/Users/macbook/Downloads`

支持：

```text
markdown
txt
docx
```

### 5. 浏览器查看历史任务

已经实现：

- `GET /jobs/{job_id}` 返回同一个前端页面
- 前端打开 `/jobs/<job_id>` 或 `/?job_id=<job_id>` 时，会自动调用 `GET /api/jobs/{job_id}`
- 如果任务已完成或有部分结果，会直接渲染逐字稿，并启用复制/保存按钮
- 如果任务仍在运行，会继续轮询
- `GET /api/jobs/history?url=...` 会按 YouTube video id 查询同视频历史任务
- 前端提交前会查历史；如果同视频已有完成结果但本次设置不同，会提示用户打开历史结果，避免误开新任务重复花费
- 如果用户取消提示，才会继续按当前设置新建任务

示例：

```text
http://127.0.0.1:8000/jobs/6512601d602f4dfaa1318500aae01447
```

### 6. 英文转中文逐字翻译

页面有复选框：

```text
同时输出中文逐字翻译
```

开启后输出结构：

```markdown
## Transcript

Speaker 1:
English transcript...

## 中文逐字翻译

Speaker 1:
对应中文翻译...
```

实现：

- `app/transcriber.py`
  - `_maybe_translate_to_zh`
  - `_translate_blocks_to_zh`
  - `_translate_text_chunk`
- 默认模型：

```python
OPENAI_TRANSLATION_MODEL or "gpt-4o-mini"
```

注意：翻译功能代码已加，但尚未充分实测。

## 已测试过的 case

### case 1: Zhang Xiaojun Podcast

URL:

```text
https://www.youtube.com/watch?v=Xxz5uh0L1mE&t=1s
```

结果：

```text
标题：139. 【Agent的综述】和苏煜聊Agent技术史、OpenClaw Moment、边界的消弭和社会的辐射
频道：Zhang Xiaojun Podcast
时长：2:17:49
YouTube 字幕：无
YouTube 自动字幕：无
音频：可下载
```

结论：

- 不能走字幕快路径
- 只能走音频识别
- 但它很长，不适合作为 OpenAI 音频识别首测

### case 2: Lenny / Anthropic

URL:

```text
https://www.youtube.com/watch?v=PplmzlgE0kg
```

结果：

- YouTube 自动字幕可读
- Markdown / TXT / DOCX 保存成功
- 复制成功

结论：

- 字幕快路径成功

### case 3: 小Lin说

URL:

```text
https://www.youtube.com/watch?v=gFtlAMEVmcs
```

结果：

```text
标题：【年度总结】一口气了解过去一年的全球经济｜关税战新格局
频道：小Lin说
时长：43:54
字幕：有中文 / 繁中 / 英文字幕
音频：可下载
```

字幕快路径成功，文件生成：

```text
app/outputs/1c7fa9f0114148c993f1148eb11daa16/【年度总结】一口气了解过去一年的全球经济｜关税战新格局.md
app/outputs/1c7fa9f0114148c993f1148eb11daa16/【年度总结】一口气了解过去一年的全球经济｜关税战新格局.txt
app/outputs/1c7fa9f0114148c993f1148eb11daa16/【年度总结】一口气了解过去一年的全球经济｜关税战新格局.docx
```

音频识别失败过，错误：

```text
OpenAI 音频识别连接失败：第 1/9 段重试 3 次仍未成功。请稍后重试，或先使用 YouTube 字幕快路径。 原始错误：Connection error.
```

当时是 5 分钟切片。后来已改成 2 分钟切片，但未对 case 3 重新完整验证。

### case 4: Zara Zhang

URL:

```text
https://www.youtube.com/watch?v=IZq9gMyci9w
```

已确认：

```text
标题：Vibe coded with Gemini 3: With, a video recorder that talks back
频道：Zara Zhang
时长：1:54
YouTube 官方字幕：无
YouTube 自动字幕：有
音频：可下载，约 1.5MB
```

建议测试：

```text
处理方式：强制音频识别
语言：英文
YouTube 登录态：自动尝试
翻译：先不要勾选
```

它只有 1:54，按当前 2 分钟切片应该是 1/1 段，适合验证 OpenAI 音频识别链路。

最新测试结果：

- 用户用 case4 跑了 `强制音频识别`
- 设置：英文、YouTube 登录态自动尝试、未勾选翻译
- 结果：成功
- 用户后续已确认 case4 勾选 `同时输出中文逐字翻译` 也已测过

结论：

- OpenAI 音频识别链路本身是通的
- 之前 case3 失败更像是长音频 / 网络稳定性问题，不是 OpenAI Key 或接口完全不可用

### case 5: Zara Zhang / pivot into AI

URL:

```text
https://www.youtube.com/watch?v=P_9cWdw0WGE
```

已确认：

```text
标题：How to pivot into AI (for non-technical people)
频道：Zara Zhang
时长：6:27
语言：英文
YouTube 自动字幕：有
音频：可下载
```

测试设置：

```text
处理方式：强制音频识别
语言：英文
YouTube 登录态：自动尝试
翻译：未勾选
```

结果：

- 第一次提交创建任务 `6512601d602f4dfaa1318500aae01447`
- 音频下载和切片成功，共 4 段
- 第 1/4 段 OpenAI 请求连续 3 次失败，错误为 `Connection error`
- 失败后 `app/tmp/<job_id>/audio/source.webm` 和 4 个 `chunk_*.mp3` 被保留
- `app/outputs/<job_id>/job.json` 被保留
- 用相同设置重新提交，返回同一个 `job_id`
- 续跑时复用已下载音频和切片，未重新下载
- 第二次提交最终成功，生成完整 Markdown / TXT / DOCX
- 4 个片段结果均已落盘：

```text
app/outputs/6512601d602f4dfaa1318500aae01447/segments/segment_001.json
app/outputs/6512601d602f4dfaa1318500aae01447/segments/segment_002.json
app/outputs/6512601d602f4dfaa1318500aae01447/segments/segment_003.json
app/outputs/6512601d602f4dfaa1318500aae01447/segments/segment_004.json
```

结论：

- 5-10 分钟英文视频的强制音频识别链路可以成功
- OpenAI 音频接口仍会偶发连接失败
- 断点续跑的 job 复用、tmp 保留、切片复用、segment 落盘已通过真实视频验证

## 当前重要问题

### 当前产品定位：GitHub 本地运行工具

最新决策：

- 暂停“所有人都能用的公开网页工具”路线
- 改成 GitHub 项目，让用户 clone 到自己电脑本地运行
- 原因：
  - YouTube 在 Render / 云服务器 IP 上容易触发 `Sign in to confirm you're not a bot`
  - 用户浏览器已登录 YouTube，并不会自动把 youtube.com cookies 提供给 Render 后端
  - 把用户 cookies 上传到公共服务有明显安全/隐私风险
  - 本地运行可以读取用户自己的浏览器登录态，和 `cathyzhang0905/lenny-podcast-transcript` 的 fallback 思路一致
  - OpenAI Key / 费用也由用户自己在本地 `.env` 配置和承担

目标：

- GitHub repo 公开
- README 面向本地用户
- 保留完整 Private 功能：
  - YouTube 字幕读取
  - YouTube 浏览器登录态
  - 中文逐字翻译
  - 强制音频识别
  - 断点续跑
  - 历史任务查看
- `PUBLIC_MODE` 仍保留，但标记为实验性，不推荐作为公共服务主路线

下一步：

1. 更新 README：改成本地安装/运行说明为主
2. 更新 DEPLOY：明确 Render/Public 只是实验性，云端会受 YouTube 风控影响
3. 更新 GitHub repo 可见性为 Public
4. 建议暂停或删除 Render service，避免误导公开用户

### 已实现但暂停主推：公开字幕版

目标：

- 先把“只读取 YouTube 字幕”这条路径做成大家都能访问的公开工具
- 不勾选中文翻译
- 不启用 OpenAI 音频识别
- 不产生用户 OpenAI API 费用

实现方式：

- 新增 `PUBLIC_MODE=true`
- 新增 `Procfile`，方便 Render / Railway 类平台启动
- 新增 `render.yaml`，如果本文件夹作为独立仓库根目录，可用 Render Blueprint 部署
- `requirements.txt` 已加入 `yt-dlp`，确保部署环境有 `yt-dlp` 命令
- 新增 `DEPLOY.md`，记录 Public / Private 模式和部署注意事项
- Public 模式下前端只展示字幕读取路径
- Public 模式下后端强制拦截：
  - `mode != "captions"`
  - `translate_to_zh=true`
  - `cookies_from_browser` / `cookies_file`
- Public 模式下 `yt-dlp` 只做无 cookies 请求，不会 fallback 到 Chrome/Safari/Firefox/Edge cookies
- Public 模式下 `/api/jobs/history` 和 `/jobs/{job_id}` 只暴露公开版字幕任务，避免泄露本地完整版历史任务
- 本地完整版继续用 `PUBLIC_MODE=false` 或不设置，保留翻译、强制音频识别、断点续跑等能力

启动示例：

```bash
PUBLIC_MODE=true .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

验收标准：

- 公开页面能读取 YouTube 可用字幕
- 公开页面不显示强制音频识别、中文翻译、YouTube 登录态
- 直接请求后端 API 也不能触发 OpenAI
- `.env` 和 OpenAI Key 不进入前端、不提交、不打印

### 2.0 版本迭代

2.0 再把付费能力放到 Public 网页：

- 中文逐字翻译
- 强制音频识别

上线前需要补：

- 访问控制或登录
- 单视频时长限制
- 每日额度和并发限制
- 明确费用提示和确认
- 更稳的后台任务队列
- 用户自带 OpenAI API Key、支付/额度系统，或仅授权用户使用你的 Key

本地使用不受 Public 模式影响，仍需正常支持翻译和强制音频识别。

GitHub 仓库：

```text
https://github.com/qianlicaoemma-hub/youtube-caption-tool
```

状态：

- 已初始化为独立 git 仓库
- 已创建私有 GitHub repo
- 已推送 `main`
- README 已加入 Render 部署按钮
- Render CLI 本机未安装；下一步需要用户在 Render 网页登录并授权 GitHub repo

### 1. OpenAI 音频识别不稳定

用户已经花了大约 `$0.92`，但之前因连接失败没有看到完整音频识别结果。

已经做的缓解：

- 从 15 分钟切片改到 5 分钟，后来又改到 2 分钟
- 加了每段 3 次应用层重试
- 加了部分结果实时显示和保存

已验证：

- case4 的 1:54 强制音频识别成功
- case4 勾选 `同时输出中文逐字翻译` 已测过
- case5 的 6:27 强制音频识别最终成功
- case5 第一次失败后，相同设置重新提交会复用同一个 `job_id` 和已下载音频切片

仍需验证：

- 30-40 分钟视频在 2 分钟切片下是否稳定

### 2. 断点续跑已实现

当前状态：

- 失败后会保留已完成部分
- 失败时会保留 `app/tmp/<job_id>` 下的原始音频和切片音频
- 每段识别成功后会落盘：

```text
app/outputs/<job_id>/segments/segment_001.json
app/outputs/<job_id>/segments/segment_002.json
```

- 任务状态会落盘：

```text
app/outputs/<job_id>/job.json
```

- 服务重启后，`GET /api/jobs/{job_id}` 在内存没有 job 时可以从 `job.json` 恢复状态
- 再次提交相同 URL / 处理方式 / 语言 / 登录态 / 翻译设置时，如果已有完成结果，会直接返回已完成 `job_id`
- 如果没有完成结果，但存在失败/未完成任务，会复用未完成 `job_id`
- 已成功的 segment 会跳过 OpenAI 请求，从第一个缺失片段继续
- 任务成功完成后会清理 `app/tmp/<job_id>`；失败时保留以便续跑

### 3. 进度显示仍是轮询

当前前端每 1.8 秒轮询：

```javascript
GET /api/jobs/{job_id}
```

对当前本地工具够用。后续可考虑 SSE，但没必要优先。

## 推荐下一步

1. 先本地用 Public 模式验收：

```bash
PUBLIC_MODE=true .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

2. 打开：

```text
http://127.0.0.1:8000
```

3. 确认公开版页面：
   - 只展示 YouTube 链接和语言
   - 不展示强制音频识别
   - 不展示中文翻译
   - 不展示 YouTube 登录态
   - 页面有“公开版只读取 YouTube 可用字幕”的提示

4. 用 2-3 个有英文/中文字幕的视频测试 `只读取 YouTube 字幕`。

5. 选择部署平台：
- 需要能跑 Python / FastAPI / yt-dlp / ffmpeg
- Public 字幕版不需要 OpenAI Key；不要在公开部署环境设置 `OPENAI_API_KEY`
- 不适合纯静态托管
   - 可考虑 Render / Railway / Fly.io / VPS

6. 部署前确认：
   - `PUBLIC_MODE=true`
   - 不上传 `.env`
   - 不暴露 OpenAI Key
   - 最好使用干净的 `app/outputs`，避免公网暴露本地历史任务

## 注意事项

- 不要打印 `.env` 内容
- 不要提交 `.env`
- 不要把 cookies 内容写进日志
- `yt-dlp --cookies-from-browser chrome:Profile 1` 已确认可用
- Safari cookies 会被 macOS 权限挡住，不建议依赖
- `node` 已安装，`deno` 未安装
- `ffmpeg` 已安装
- `yt-dlp` 版本：`2026.03.17`

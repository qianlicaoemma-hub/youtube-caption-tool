# 安装指南（给 AI Agent 读的版本）

> 这份文档是写给 **Claude Code / Cursor / 任何能执行命令的 AI 助手** 的。
> 如果你是普通用户，请把这个仓库交给你的 AI 助手，告诉它："帮我按 INSTALL.md 安装这个工具"，然后用自然语言和它对话即可。

---

## Agent 行为规范

阅读本文档的 AI Agent 请遵循：

1. **逐步执行**：每完成一步，告诉用户结果，再问是否继续。不要一口气跑完所有命令。
2. **先确认环境**：执行任何安装前，先用诊断命令检查用户环境，按实际情况选分支。
3. **失败要兜底**：每步都有"常见报错与修复"段落，遇到错误优先按文档处理，不要自己发挥。
4. **解释费用**：到 API Key 配置环节时，主动告诉用户大致成本，让用户决定。
5. **用平实中文**：用户是非技术背景，避免术语堆砌。"虚拟环境"说成"独立的 Python 运行空间"更好。

---

## 用户预期

- 操作系统：**macOS**（其他系统未验证）
- 准备时间：第一次安装约 **30–45 分钟**（含火山引擎注册和实名认证）
- 需要：网络、一个火山引擎账号（含语音控制台 API Key、IAM 访问密钥、TOS 对象存储桶）
- 付费：调用火山引擎录音文件识别 API（约 ¥1.5/小时音频，4 小时视频约 ¥6 ≈ $0.84）
- 视频如果有 YouTube 字幕，则不调用识别 API，零费用

---

## 第 0 步：环境诊断

Agent 先执行下面命令，根据输出判断后续动作：

```bash
# 检查必要工具
which python3 && python3 --version
which ffmpeg && ffmpeg -version | head -1
which yt-dlp && yt-dlp --version
which node && node --version
which brew && brew --version | head -1
```

**判断逻辑**：

| 工具 | 必要性 | 缺失时 |
|---|---|---|
| `python3` (≥3.11) | 必需 | 走第 1 步装 Homebrew + Python |
| `ffmpeg` | 必需 | 走第 2 步用 Homebrew 装 |
| `yt-dlp` | 必需 | 走第 3 步装（pip 装即可，但 brew 装更方便升级） |
| `node` | 推荐 | 缺失也能跑，但部分视频可能解析失败；建议提示用户装 |
| `brew` | 强烈推荐 | 缺失则按第 1.1 步先装 Homebrew |

如果**全部已存在且版本符合**，直接跳到第 4 步。

---

## 第 1 步：装 Homebrew 和 Python

### 1.1 装 Homebrew（macOS 包管理器）

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**告诉用户**：会要求输入 Mac 开机密码，输入后看不到字符是正常的，输完按回车即可。

安装完成后，按提示把 Homebrew 加入 PATH。Apple Silicon Mac 通常需要执行：

```bash
echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
eval "$(/opt/homebrew/bin/brew shellenv)"
```

验证：`brew --version` 应该输出版本号。

### 1.2 装 Python 3.11+

```bash
brew install python@3.12
```

验证：`python3 --version` 应该 ≥ 3.11。

**常见报错**：
- `command not found: brew` → 第 1.1 步没装好，回到 1.1
- 已有旧版 Python 3.9 → 不冲突，brew 装的 python3.12 会优先

---

## 第 2 步：装 ffmpeg

```bash
brew install ffmpeg
```

验证：`ffmpeg -version | head -1` 应该输出版本号。

**常见报错**：
- 安装时间长（5–10 分钟）→ 正常，ffmpeg 依赖多
- 提示磁盘空间不足 → 让用户清理后重试

---

## 第 3 步：装 yt-dlp 和 Node.js

```bash
brew install yt-dlp node
```

验证：
```bash
yt-dlp --version
node --version
```

**为什么装 Node**：yt-dlp 解析某些 YouTube 视频时需要 Node 运行时辅助。不装也能跑，但失败率更高。

---

## 第 4 步：拉取项目代码

询问用户希望把项目放在哪里。默认建议：`~/Documents/youtube-transcript`。

```bash
# 进入用户家目录
cd ~

# 创建文件夹并克隆
mkdir -p Documents
cd Documents
git clone https://github.com/qianlicaoemma-hub/youtube-caption-tool.git youtube-transcript
cd youtube-transcript
```

> Agent 注意：如果用户没装 git，先 `brew install git`。

如果用户拿到的是 zip 包，让他解压到这个位置即可。

---

## 第 5 步：创建独立 Python 环境

**告诉用户**：这一步是为了让这个工具有自己的独立 Python 运行空间，不会污染你电脑上的其他 Python 程序。

```bash
cd ~/Documents/youtube-transcript
python3 -m venv .venv
source .venv/bin/activate
```

验证：命令行最前面应该出现 `(.venv)` 标记。

**Agent 注意**：从这一步开始，所有 `pip` 和 `python` 命令都必须**在这个环境激活的状态下**执行。如果用户重新开终端，要先 `cd` 到项目目录再 `source .venv/bin/activate`。

---

## 第 6 步：安装 Python 依赖

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

预计耗时 1–3 分钟。

**常见报错**：
- `pip: command not found` → 没激活虚拟环境，回到第 5 步
- 网络超时 → 重试，或建议用户切换网络

---

## 第 7 步：配置火山引擎/豆包

> **告诉用户**：这一步是整个安装里最麻烦的一步，需要 20–30 分钟。
> 工具用火山引擎的"豆包大模型录音文件识别"识别没有字幕的视频。
> 你需要拿到 4 个值：API Key、Access Key ID、Secret Access Key、TOS 桶名。
> Agent 请逐项引导，不要一口气甩链接。

### 7.1 注册火山引擎账号

**告诉用户**：

> 打开 https://www.volcengine.com 点右上角"登录/注册"。
> 用手机号注册，按步骤完成**个人实名认证**（身份证 + 人脸识别）。
> 没有实名认证就拿不到 API Key，必须做。

完成后充值 ¥50 到账户余额（控制台右上角"账户"→"充值"）。¥50 够识别 30 小时音频。

### 7.2 开通语音服务并拿 API Key

**告诉用户**：

> 1. 登录后访问 https://console.volcengine.com/speech/service/
> 2. 找到「**语音识别 - 大模型录音文件识别**」（有时显示为"豆包语音 - 录音文件识别"）
> 3. 点"立即开通"，按页面提示完成开通
> 4. 进入「应用管理」→ 创建一个应用（名字随便，比如 `youtube-transcript`）
> 5. 应用创建后会显示 **API Key**，复制保存好

记下这个值，下面 `.env` 文件里要填到 `VOLCENGINE_API_KEY`。

### 7.3 创建 IAM 访问密钥（用于上传音频到 TOS）

**告诉用户**：

> 火山的录音识别 API 要求音频是**公网可访问的 URL**，所以工具会先把音频
> 上传到你自己的"火山 TOS 对象存储"。这一步是创建上传 TOS 用的密钥。
>
> 1. 访问 https://console.volcengine.com/iam/keymanage/
> 2. 点"新建密钥"
> 3. 创建后会显示 **Access Key ID** 和 **Secret Access Key**
>    - Secret Access Key **只会显示一次**，关闭页面就再也看不到，必须立刻复制保存
> 4. 如果不小心关掉了，删掉重新创建一个即可

记下这两个值，下面要填到 `VOLCENGINE_ACCESS_KEY_ID` 和 `VOLCENGINE_SECRET_ACCESS_KEY`。

### 7.4 创建 TOS 桶（存放上传的音频）

**告诉用户**：

> 1. 访问 https://console.volcengine.com/tos/bucket/create
> 2. 桶名：自己取一个全局唯一的名字，比如 `<你的昵称>-yt-transcript`
> 3. 区域：默认 `华北 2（北京）`，对应代号是 `cn-beijing`（推荐保持默认）
> 4. 存储类型：标准存储
> 5. 读写权限：**私有**（不要选公共读，工具会用预签名 URL 临时访问）
> 6. 其他选项保持默认，点"确定"

记下桶名（不是显示名，是英文 ID），下面要填到 `VOLCENGINE_TOS_BUCKET`。

> **建议设置生命周期规则**：进入桶 → 基础设置 → 生命周期管理 → 添加规则，
> 让 `youtube-transcript/` 路径下的文件 **7 天后自动删除**，
> 避免长期堆积音频占空间（每月不到 1 元成本）。

### 7.5 写入配置文件

```bash
cp .env.example .env
```

让用户用文本编辑器打开 `.env`，把四个 `your-xxx` 占位符全部替换为真实值，保存。

Agent 代填示例（**不要让用户在对话里发完整 Key，让用户自己粘贴到 `.env`**）：

```bash
# 仅在用户明确授权代填时使用，每个值替换为用户提供的真实值
sed -i '' "s|your-volcengine-speech-api-key|<API_KEY>|" .env
sed -i '' "s|your-iam-access-key-id|<AK_ID>|" .env
sed -i '' "s|your-iam-secret-access-key|<SK>|" .env
sed -i '' "s|your-tos-bucket-name|<BUCKET>|" .env
```

**安全提醒**：
- `.env` 已在 `.gitignore` 里，不会上传到 GitHub
- 不要把 Key 截图发到任何聊天工具
- Agent 不要把完整 Key 写进对话或日志里
- 一旦怀疑泄漏，立即去火山控制台删除并重新生成

### 7.6 验证配置

```bash
source .venv/bin/activate
python -c "from app.volcengine_asr import VolcCredentials; VolcCredentials.from_env(); print('OK')"
```

输出 `OK` 即代表 4 个变量都配好了。如果报错"火山引擎配置不完整"，回到 7.5 检查 `.env` 文件里有没有遗漏字段或多余空格。

---

## 第 8 步：启动服务

```bash
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

服务启动后，让用户在浏览器打开：

```
http://127.0.0.1:8000
```

应该看到工具网页。

**停止服务**：在终端按 `Ctrl + C`。

---

## 第 9 步：日常使用

每次想用工具时：

```bash
cd ~/Documents/youtube-transcript
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

然后浏览器打开 `http://127.0.0.1:8000`。

**Agent 可以提供两个便捷脚本**：

```bash
# 创建启动脚本
cat > ~/Documents/youtube-transcript/start.sh <<'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
EOF
chmod +x ~/Documents/youtube-transcript/start.sh
```

之后用户双击 `start.sh` 即可启动（首次双击会被 macOS 拦截，需要在"系统设置 → 隐私与安全性"里允许打开）。

---

## 常见问题速查

### "Sign in to confirm you're not a bot"

原因：YouTube 要求登录验证。

**修复**：
1. 让用户在 Chrome / Safari / Firefox 里登录 YouTube 账号
2. 在工具页面的 "YouTube 登录态" 选项里选对应浏览器
3. 重试

### `ffmpeg: command not found`

回第 2 步重装 ffmpeg。如果已装但找不到，运行：

```bash
which ffmpeg
echo $PATH
```

如果 `which ffmpeg` 输出路径但 `$PATH` 里没有，说明 PATH 配置没生效，重启终端或重新执行 `eval "$(/opt/homebrew/bin/brew shellenv)"`。

### "火山引擎配置不完整" 报错

回第 7 步，确认：
1. `.env` 文件在项目根目录（不是 `.env.example`）
2. 4 个 `VOLCENGINE_*` 变量都填了真实值，没有 `your-xxx` 占位符
3. 值没有多余空格、引号包裹
4. 重启服务

### "TOS 上传失败" 报错

可能原因：
1. **桶名错了**：桶名要填英文 ID（控制台桶列表里第一列），不是中文显示名
2. **区域不对**：检查 `VOLCENGINE_TOS_REGION` 是否和桶实际区域一致
3. **AK/SK 权限不足**：进入 IAM 控制台，给这个 AK 添加 `TOSFullAccess` 权限策略
4. **桶不存在**：检查桶是否已创建成功

### "火山提交失败：405xxxxx" 报错

进入 https://console.volcengine.com/speech/service/ 检查：
1. 是否已开通"大模型录音文件识别"服务
2. 应用是否已创建并启用
3. 账户余额是否充足（≥ ¥1）

### 端口 8000 被占用

```bash
# 换一个端口
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

浏览器打开 `http://127.0.0.1:8001`。

### 视频很长，处理超时

正常现象。1 小时视频识别约需 2–4 分钟，4 小时约 5–10 分钟。**不要关闭终端窗口**。
任务有断点续跑机制（已上传的音频和已提交的火山任务会持久化），意外中断后重新提交相同链接即可继续。

---

## Agent 收尾检查清单

完成安装后，Agent 应主动验证：

```bash
# 1. 虚拟环境正常
source ~/Documents/youtube-transcript/.venv/bin/activate
python -c "import fastapi, requests, yt_dlp; print('Python deps OK')"
python -c "from app.volcengine_asr import VolcCredentials; VolcCredentials.from_env(); print('Volcengine config OK')"

# 2. 系统工具正常
ffmpeg -version > /dev/null && echo "ffmpeg OK"
yt-dlp --version > /dev/null && echo "yt-dlp OK"

# 3. 配置文件存在
test -f ~/Documents/youtube-transcript/.env && echo ".env OK"

# 4. 试启动（5 秒后停掉）
cd ~/Documents/youtube-transcript
timeout 5 uvicorn app.main:app --host 127.0.0.1 --port 8000 2>&1 | head -5
```

全部通过后，告诉用户：

> ✅ 安装完成。现在可以用这条命令启动工具：
> ```
> cd ~/Documents/youtube-transcript && source .venv/bin/activate && uvicorn app.main:app --host 127.0.0.1 --port 8000
> ```
> 启动后浏览器打开 http://127.0.0.1:8000

---

## 给 Agent 的最后一条指令

如果用户在任何步骤卡住超过 2 次，**不要继续硬试**。直接让用户：

1. 把出错的命令和完整错误信息复制下来
2. 提交到这个仓库的 GitHub Issues
3. 等维护者回复

不要自行猜测修复方案，不要建议用户改系统配置（如 `sudo`、改 `~/.zshrc`），不要建议用户关闭安全检查。

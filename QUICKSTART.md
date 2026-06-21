# 小胰宝临床试验订阅系统 - 快速开始

**5 分钟上手：从环境配置到微信推送一条临床试验**

---

## 前置条件

```bash
✓ Python 3.10+
✓ uv 或 pip（推荐 uv）
✓ .env 凭据文件（见 Step 3）
```

---

## Step 1: 克隆项目 (1 min)

```bash
git clone <your-repo-url> clinicaltrials推送和订阅
cd clinicaltrials推送和订阅
```

---

## Step 2: 安装环境 (1 min)

```bash
# 使用 uv（推荐）
uv venv --python 3.12
source .venv/bin/activate
uv pip install requests python-dotenv openai

# 或使用传统 pip
# python3 -m venv .venv
# source .venv/bin/activate
# pip install -r requirements.txt
```

---

## Step 3: 配置凭据 (2 min)

复制模板并填写真实值：

```bash
cp .env.example .env
cp assets/config.yaml.template config.yaml   # 若不存在
```

编辑 `.env`：

```bash
# LLM 配置（至少配一个，建议多配几个做 fallback）
QWEN_API_KEY=your_key
ZHIPU_API_KEY=your_key
STEP_API_KEY=your_key
GEMINI_API_KEY=your_key

# FastGPT 配置
FASTGPT_BASE_URL=https://your-domain.com/api
FASTGPT_API_KEY=openapi-your-key
FASTGPT_DATASET_ID=your_dataset_id

# Telegram 配置
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_id

# GeWe 微信群推送（可选）
GEWE_ENABLED=false
GEWE_API_HOST=api.geweapi.com
GEWE_APP_ID=your_app_id
GEWE_TOKEN=your_token
GEWE_TO_WXID=["group-wxid-1","group-wxid-2"]
```

> 🔒 **安全提示**：`.env` 和 `config.yaml` 已在 `.gitignore` 中，**永远不要**提交含真实密钥的文件到 git。

---

## Step 4: CLI 指令速查

### 4.1 抓取过滤器（阶段 1）

控制从 ClinicalTrials.gov 抓哪些试验。

| 参数 | 说明 | 示例 |
|------|------|------|
| `--condition "疾病名"` | 指定病种（默认 Pancreatic Cancer） | `--condition "Lymphoma"` |
| `--china` | 仅抓取含中国中心的试验 | `--china` |
| `--top N` / `--N` | 取前 N 个试验（简写 `--5` = `--top 5`） | `--top 5` |
| `--status STATUS` | 试验状态（默认 RECRUITING） | `--status "ACTIVE_NOT_RECRUITING"` |
| `--days-back N` | 时间窗天数（0 = 不过滤） | `--days-back 0` |
| `--latest` | 按最近更新排序（默认开启） | `--latest` |

### 4.2 推送开关（阶段 2）

控制推送到哪些渠道。优先级：**CLI 参数 > config.yaml 默认值**。

| 参数 | 说明 | config.yaml 默认 |
|------|------|-----------------|
| `--send-tg` | Telegram | `true` |
| `--send-gewe-txt` | GeWe **文字**推送 | `true` |
| `--send-gewe-card` | GeWe **卡片**推送 | `false`（需显式开启） |
| `--send-feishu` | 飞书交互卡片 | `true` |
| `--send-fastgpt` | FastGPT 知识库同步 | `true` |

### 4.3 多渠道简写

| 参数 | 说明 | 示例 |
|------|------|------|
| `--channels 列表` | 逗号分隔多渠道同时推送 | `--channels tg,gewe_txt` |
| `--all-channels` | 开启所有渠道 | `--all-channels` |
| `--no-channels 列表` | 排除指定渠道 | `--no-channels gewe_card` |

### 4.4 交互菜单（无参数进入）

```bash
python3 main.py
```

```
📋 主菜单

1️⃣  自动流程 (抓取 → 翻译 → 上传)
2️⃣  手动菜单 (单独执行各步骤)
3️⃣  快捷推送: 10 个最近中国试验 → 微信文字 (GeWe 文字)  ← 默认开启，开箱即用
4️⃣  快捷推送: 10 个最近中国试验 → 微信卡片 (需先在 config.yaml 开启 gewe_card)
0️⃣  退出
```

### 4.5 独立子脚本（供 cron / 手动调用）

```bash
python3 daily_ctgov_check_tgbot.py        # 阶段1：抓取 + TG 简报
python3 ctgov_full_sync_rag.py            # 阶段1：RAG 精翻（JSON → 中文 Markdown）
python3 fastgpt_sync.py --once --mode=today   # 阶段2：同步当天文件到 FastGPT
python3 fastgpt_sync.py --once --mode=all     # 阶段2：同步全部历史文件
python3 push_existing_report.py --latest --send-gewe-txt  # 补发最新报告到微信
```

---

## Step 5: 常用指令示例

### 🎯 场景 1：测试搜索 + 微信推送（单条）

```bash
# 搜索淋巴瘤美国临床试验，推微信文字，不过滤时间
python3 main.py --condition "Lymphoma" --top 1 --send-gewe-txt --days-back 0
```

### 🎯 场景 2：中国中心 + 多渠道推送

```bash
# 搜索中国中心的乳腺癌，推 Telegram + 微信文字
python3 main.py --condition "Breast Cancer" --china --top 10 --channels tg,gewe_txt
```

### 🎯 场景 3：仅抓取不推送（生成 JSON 供后续处理）

```bash
python3 main.py --china --top 20 --condition "Lung Cancer"
# 阶段1 完成后不进入阶段2，JSON 落地在 output/{date}-Lung_Cancer/
```

### 🎯 场景 4：全渠道推送当天试验

```bash
python3 main.py --all-channels
```

### 🎯 场景 5：定时任务（cron）

```bash
# 自动全流程：抓取 → 翻译 → FastGPT 同步
python3 main.py --auto
```

### 🎯 场景 6：补发已有报告

```bash
# 推送最新报告到微信文字
python3 push_existing_report.py --latest --send-gewe-txt

# 推送指定文件到多个渠道
python3 push_existing_report.py \
  --file output/2026-06-21-Lymphoma/telegram_push_report.txt \
  --channels tg,gewe_txt,feishu
```

---

## Step 6: 验证运行

运行一条测试指令，观察输出：

```bash
python3 main.py --condition "Lymphoma" --top 1 --send-gewe-txt --days-back 0
```

预期输出：

```
============================================================
🏥 小胰宝临床试验智能订阅系统
============================================================

🔍 阶段1:抓取试验(condition=Lymphoma, china=False, top=1, days_back=0)
   抓取到 1 个试验
   1. NCT04269902 | Testing Early Treatment for Patients Wit...

🔄 阶段1:批量翻译 + 落地 JSON + 生成推送内容...
   ✅ 翻译完成:1 个试验,生成 1 组详情

📤 阶段2:推送到 1 个渠道: gewe_txt
   GeWe 文字: 汇总 + 1 组详情 + footer 已发送

============================================================
✅ 全部完成:阶段1 抓取翻译 1 个,阶段2 推送 1 个渠道
============================================================
```

---

## 🛠️ 切换病种（v3.0.0+）

系统支持任意癌症/罕见病，一次运行一种疾病：

```bash
# 各类癌症
python3 main.py --top 1 --condition "Breast Cancer" --china --send-gewe-txt    # 乳腺癌
python3 main.py --top 1 --condition "Lung Cancer" --china --send-gewe-txt      # 肺癌
python3 main.py --top 1 --condition "Gastric Cancer" --china --send-gewe-txt   # 胃癌

# 罕见病
python3 main.py --top 5 --condition "Gaucher Disease" --china                  # 戈谢病
```

落地目录、报告标题、FastGPT 集合名会自动按病种区分。新增病种中文映射见 `lib/branding.py` 的 `_DISEASE_CN`。

---

## 📁 输出目录结构

```
output/
└── 2026-06-21-Lymphoma/
    ├── NCT04269902.json              # 原始试验数据（sync_status=pending）
    ├── telegram_push_report.txt      # 推送简报（TG/GeWe 消费）
    ├── cn/
    │   └── 2026-06-21-NCT04269902-...-zh.md   # 中文精翻（FastGPT 消费）
    └── en/
        └── 2026-06-21-NCT04269902-....md      # 英文原文
```

---

## ❓ 常见问题

**Q: 微信推送失败但 TG 正常？**
A: 检查 `.env` 中 `GEWE_ENABLED=true` 且 `GEWE_APP_ID`/`GEWE_TOKEN`/`GEWE_TO_WXID` 已正确配置。GeWe 失败不影响 TG 主渠道。

**Q: 如何只推微信不推 Telegram？**
A: `python3 main.py --top 1 --send-gewe-txt --no-channels tg` 或改 `config.yaml` 中 `tg: false`。

**Q: 微信卡片怎么开？**
A: 编辑 `config.yaml` 设置 `channels.gewe_card: true`，然后运行时加 `--send-gewe-card`。

**Q: `--days-back 0` 是什么意思？**
A: 0 表示**不限制**时间窗，抓取 API 返回的全部结果。默认 30 天。

**Q: 支持 Windows 吗？**
A: 代码本身跨平台，但 GeWe 推送依赖个人微信生态，建议在 Linux/Mac 服务器上部署。

---

**🎉 完成！你现在可以按需搜索任意病种的临床试验并推送到微信/TG/飞书/FastGPT 了。**

更多架构细节见 [README.md](./README.md)，配置项逐条说明见 `references/config-reference.md`。

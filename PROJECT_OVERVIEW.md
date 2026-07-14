# Hot Topics Insight — 全球热点多模型辩论系统

## 项目概述

每日自动从 9 个国际新闻源采集 ~150 条热点新闻，经 embedding 聚类去重后选出 Top 10 热点话题，三个 LLM（DeepSeek / Qwen / Gemini）各自分析观点、交叉审阅、综合产出统一结论 + 各自理由，最终生成白色专业风格 HTML 报告（支持导出 Excel/Word/PDF）。

---

## 一、架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    Layer 1: 数据采集                         │
│            Glean (开源) + 11 个独立 Feed                     │
│                                                             │
│  Al Jazeera ──→ RSS ──→ 15 items ──┐                       │
│  Guardian   ──→ RSS ──→ 15 items ──┤                       │
│  NYT        ──→ RSS ──→ 15 items ──┤                       │
│  BBC        ──→ RSS ──→ 15 items ──┤                       │
│  HN         ──→ API ──→ 6 items  ──┼──→ glean-output.jsonl │
│  Twitter BBC──→ Nitter RSS→20 item─┤     (~150 条/次)      │
│  Twitter RT ──→ Nitter RSS→20 item─┤                       │
│  Twitter AP ──→ Nitter RSS→20 item─┤                       │
│  Bloomberg  ──→ Nitter RSS→20 item─┘                       │
│                                                             │
│  每条新闻 → DeepSeek 做一句话摘要（英文）                    │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 2: 聚类去重                         │
│              bridge.py — sentence-transformers               │
│                                                             │
│  读 JSONL → URL 去重 → 每条做 embedding (384 维向量)        │
│  模型: paraphrase-multilingual-MiniLM-L12-v2                 │
│  → 余弦相似度矩阵 → 贪心聚类 (threshold=0.70)                │
│                                                             │
│  热度公式: heat = 文章数 × (1 + 不同来源数 × 0.5)           │
│  同事件被越多源报道 → 热度越高 → 排前面                      │
│  ↓                                                          │
│  Top 10 话题进入辩论                                         │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 3: 多模型辩论                       │
│              analyze/debate.py — 2 Stages                   │
│                                                             │
│  Stage 1 — 独立分析观点（并行）                              │
│    DeepSeek → summary + significance + angle + confidence   │
│    Qwen     → summary + significance + angle + confidence   │
│    Gemini   → summary + significance + angle + confidence   │
│    (Claude/GPT 预留接口，配置 key 后自动激活)                │
│                                                             │
│  Stage 2 — 轮转交叉审阅 + 综合（并行）                       │
│    DeepSeek reviews Qwen    → agree/partial/disagree         │
│    Qwen reviews Gemini      → agree/partial/disagree         │
│    Gemini reviews DeepSeek  → agree/partial/disagree         │
│    ↓                                                        │
│    Synthesizer → final_agreement + justifications           │
│                 + agreement_level + bottom_line             │
└─────────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Layer 4: 输出                             │
│              output/render.py — HTML Report                  │
│                                                             │
│  Section 1: 新闻列表（表格，可点击跳转原文）                  │
│  Section 2: 辩论结果卡片                                    │
│    - Final Agreement（结论）                                 │
│    - Agreement Level（HIGH / PARTIAL / LOW）                 │
│    - Bottom Line（一句话总结）                               │
│    - Model Justifications（每个模型的立场和理由）            │
│                                                             │
│  导出按钮: Export Excel (.csv) / Export Word (.doc) / Print PDF │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、文件结构与职责

### 项目目录: `~/projects\hot-topics-insight\`

| 文件 | 行数 | 职责 |
|------|------|------|
| `main.py` | ~240 | CLI 入口，编排单次采集+辩论 |
| `bridge.py` | ~250 | **核心管道**: Glean JSONL → 聚类 → 辩论 → 输出 |
| `daily.ps1` | ~30 | 一键自动化脚本（Glean + bridge 串联） |
| `.env` | ~6 | API Keys (DeepSeek/Qwen/Gemini/Claude/GPT) |
| `.env.example` | ~6 | API Key 模板 |
| `requirements.txt` | ~6 | Python 依赖 |
| `analyze/clients.py` | ~200 | 五模型异步客户端 (Claude/GPT/DeepSeek/Gemini/Qwen) |
| `analyze/debate.py` | ~250 | 两阶段辩论引擎 |
| `output/render.py` | ~350 | HTML 报告渲染 (白色主题 + 导出功能) |
| `ingest/reddit.py` | ~90 | Reddit 直接 API 采集（备用） |
| `ingest/trends.py` | ~80 | Google Trends 采集（备用） |

### Glean 配置: `~/projects\glean\`

| 文件 | 职责 |
|------|------|
| `feeds.yaml` | 11 个独立 Feed 定义（每个源一个 Feed，各自 max_items） |
| `run.ps1` | Glean 单次运行脚本 |
| `.env` | DeepSeek API Key (Glean 用) |

---

## 三、每一步的详细流程

### Step 1: 数据采集 — Glean

**执行命令:**
```powershell
cd ~/projects\glean
.\run.ps1
```

**内部流程:**

1. Glean 读取 `feeds.yaml`，找到 11 个 Feed 定义
2. 逐个执行每个 Feed:
   - **RSS Feed** (Al Jazeera/Guardian/NYT/BBC): 通过 HTTP GET 获取 RSS XML，`feedparser` 解析出条目标题、链接、摘要、发布时间
   - **Hacker News**: 通过 Algolia API (`hn.algolia.com/api/v1/search_by_date`) 搜索过去 8 小时内 ≥30 赞的文章
   - **Twitter (Nitter RSS)**: Nitter 是 Twitter 的第三方开源前端，每个 Twitter 账号有一个 RSS 输出 (`nitter.net/<账号>/rss`)，免费无需 API Key。Glean 将其当作普通 RSS 处理
3. 每个 Feed 的 Pipeline:
   - `dedup`: URL 去重（SQLite 持久化，跨运行去重）
   - `summarize`: 调用 DeepSeek API，将每条新闻正文压缩为一句话英文摘要（≤25 words）
4. 每个 Feed 通过 `file sink` 追加写入同一个 `glean-output.jsonl` 文件
5. 11 个 Feed 全部跑完 → 总输出约 150 条（实际受各源 RSS 内容量影响）

**为什么拆成 11 个独立 Feed:**
Glean 的 `max_items` 是 per-feed 配额。如果所有源放在一个 Feed 里，前两个源就占满 50 条额度，后面的全丢。拆成独立 Feed 后每个源有独立配额，互不挤占，实现均匀分布。

**当前各源配额与产出:**

| Feed | 源 | max_items | 实际产出 |
|------|-----|-----------|---------|
| src-aljazeera | Al Jazeera RSS | 15 | ~15 |
| src-guardian | The Guardian RSS | 15 | ~15 |
| src-nytimes | NYT RSS | 15 | ~15 |
| src-bbc | BBC RSS | 15 | ~15 |
| src-hackernews | Hacker News API | 15 | ~6 (min_points 筛选) |
| src-twitter-bbc | BBCBreaking (Nitter) | 50 | ~20 |
| src-twitter-reuters | Reuters (Nitter) | 50 | ~20 |
| src-twitter-ap | AP (Nitter) | 50 | ~20 |
| src-twitter-bloomberg | Bloomberg (Nitter) | 50 | ~20 |
| src-reddit-worldnews | Reddit r/worldnews (safereddit) | 50 | 0 (当前被封) |
| src-reddit-technology | Reddit r/technology (safereddit) | 50 | 0 (当前被封) |
| **合计** | | | **~146** |

**Twitter 接入原理 (Nitter RSS):**
```
Twitter 账号 (@BBCBreaking)
    ↓ 第三方 Nitter 实例抓取
Nitter 生成 RSS Feed (nitter.net/BBCBreaking/rss)
    ↓ Glean 的 RSS source 读取
解析为标准新闻条目 → 进入 Pipeline
```

Nitter 是免费开源的，无需 X API Key。但受限于 Twitter 的反爬，每个 Nitter RSS 通常只包含该账号最近 ~20 条推文。

---

### Step 2: 聚类去重 — bridge.py

**执行命令:**
```powershell
cd ~/projects\hot-topics-insight
python bridge.py 10 2    # 10 topics, max 2 concurrent
```

**内部流程:**

#### 2.1 读取 JSONL
```python
read_glean_output(path)
```
- 读入 `glean-output.jsonl` 的每一行（每条是一个 JSON 对象）
- 按 `url` 字段去重（同一 URL 在多次运行间可能被重复写入）
- 返回去重后的条目列表

#### 2.2 Embedding 聚类
```python
cluster_topics(items, threshold=0.70)
```
- 加载 `paraphrase-multilingual-MiniLM-L12-v2` 模型（118M 参数，支持 50+ 语言，384 维向量）
- 对每条新闻构建文本: `"标题. 摘要"` → 编码为 384 维向量
- 计算所有向量两两之间的余弦相似度（N×N 矩阵）
- 贪心聚类:
  ```
  for each item i (not yet clustered):
      新建 cluster = [i]
      for each item j > i:
          if sim(i, j) > 0.70:
              加入 cluster
  ```
- 最后每个 cluster 生成一个 topic dict:
  - `title`: cluster 内第一条（通常是最早被报道的）
  - `source`: cluster 内所有来源名称去重拼接
  - `score` (热度): 文章数 × (1 + 不同来源数 × 0.5) × 100
  - `num_comments`: cluster 内文章数
  - `related_queries`: cluster 内前 3 条的摘要拼接，作为辩论时的上下文

#### 2.3 热度排序
- 按 `score` 降序排列
- 取 Top N（默认 10）进入辩论

**为什么用 sentence-transformers 而不是简单关键词匹配:**
- 同一事件在不同媒体的标题可能完全不同（"曼谷酒吧火灾 27 死" vs "Deadly blaze engulfs Bangkok pub"）
- Embedding 捕获语义相似度，跨语言也能匹配
- 多语言模型确保中文、英文、阿拉伯文标题都能被正确聚类

---

### Step 3: 多模型辩论 — analyze/debate.py

**入口:**
```python
insights = await analyze_topics(clients, topics, max_concurrent=2)
```

**五个模型的支持情况:**

| 模型 | 厂商 | API Key 环境变量 | 状态 |
|------|------|-----------------|------|
| DeepSeek | DeepSeek | `DEEPSEEK_API_KEY` | ✅ 主力 |
| Qwen (通义千问) | 阿里云 | `QWEN_API_KEY` | ✅ 可用 |
| Gemini | Google | `GEMINI_API_KEY` | ✅ 可用（偶发 503） |
| Claude | Anthropic | `ANTHROPIC_API_KEY` | ⚠️ Key 无效待换 |
| GPT | OpenAI | `OPENAI_API_KEY` | ⚠️ 余额不足 |

没有配置 Key 的模型自动跳过，不影响其他模型运行。至少 1 个模型即可跑通。

#### Stage 1: 独立分析观点（所有可用模型并行）

**发给模型的 Prompt:**
```
You are an expert global affairs analyst.

News: "<标题>"
Source: <来源>
This event is verified. What does it mean?
What are the broader implications?

Respond with JSON:
{
  "summary": "One-sentence summary",
  "significance": "Why this matters (1-2 sentences)",
  "angle": "Your analytical perspective (geopolitical/economic/technological/social/environmental)",
  "confidence": "high" | "medium" | "low"
}
```

三个模型各自独立返回分析结果，不互相看到对方的输出。

#### Stage 2: 交叉审阅 + 综合

**轮转审阅 (Round-Robin):**
```
DeepSeek 审阅 Qwen 的分析     → agree / partially_agree / disagree
Qwen 审阅 Gemini 的分析        → agree / partially_agree / disagree
Gemini 审阅 DeepSeek 的分析    → agree / partially_agree / disagree
```

**审阅 Prompt:**
```
Topic: "<标题>"
<其他模型>'s interpretation:
- Summary: ...
- Significance: ...
- Angle: ...
Do you agree with their interpretation? What did they miss?
```

**综合 (Synthesis):**
所有分析结果 + 审阅意见 → 发送给一个模型（优先 DeepSeek → Gemini → Qwen）做综合：

```
Synthesize what this event MEANS.
Output JSON:
{
  "final_agreement": "The key takeaway (2-3 sentences)",
  "agreement_level": "high" | "partial" | "low",
  "key_tension": "Where do analysts disagree?",
  "bottom_line": "One-line bottom line",
  "justifications": {
    "ModelName": "1-sentence summary of that model's position"
  }
}
```

**一致度判定的含义:**
- **HIGH**: 所有模型在核心意义上达成一致，只是角度不同
- **PARTIAL**: 基本事实一致，但对重要性或影响范围有分歧
- **LOW**: 对事件的解读存在根本性分歧

---

### Step 4: HTML 报告生成 — output/render.py

**调用:**
```python
render_report(insights, raw_items=items, output_path="output/report.html")
```

**两个输入:**
- `insights`: 辩论后的 TopicInsight 对象列表（10 条）
- `raw_items`: 原始新闻条目列表（~146 条）

**页面结构:**

```
┌──────────────────────────────────────────────┐
│  HEADER                                      │
│  Global Hot Topics — Daily Insight Report    │
│  时间戳 · 模型标签 · 源数量                    │
├──────────────────────────────────────────────┤
│  TOOLBAR                                     │
│  [Export Excel] [Export Word] [Print PDF]    │
├──────────────────────────────────────────────┤
│  SECTION 1: News Articles                    │
│  ┌──────────────────────────────────────┐    │
│  │ # │ Title │ Source │ Summary         │    │
│  │ 1 │ ...   │ BBC    │ ...             │    │
│  │ 2 │ ...   │ Reuters│ ...             │    │
│  │ ..│ ...                                  │
│  └──────────────────────────────────────┘    │
├──────────────────────────────────────────────┤
│  SECTION 2: Multi-LLM Debate Results         │
│                                              │
│  ┌──────────────────────────────────────┐    │
│  │ #1 <标题>                            │    │
│  │ [Al Jazeera] [BBC] [Reuters]         │    │
│  │                                      │    │
│  │ ┌─ HIGH AGREEMENT ──────────────┐    │    │
│  │ │ <final_agreement 文本>          │    │    │
│  │ └────────────────────────────────┘    │    │
│  │                                      │    │
│  │ MODEL JUSTIFICATIONS                 │    │
│  │ ┌──────────┐ ┌──────────┐ ┌──────┐  │    │
│  │ │ DeepSeek │ │ Qwen     │ │Gemini│  │    │
│  │ │ <理由>   │ │ <理由>   │ │<理由>│  │    │
│  │ └──────────┘ └──────────┘ └──────┘  │    │
│  └──────────────────────────────────────┘    │
│  ... (共 10 张卡片)                           │
└──────────────────────────────────────────────┘
```

**设计原则:**
- 白色/浅灰背景，专业商务风格，非深色 AI 风
- Segoe UI / system-ui 字体
- 蓝色强调色 (#1a56db)
- 响应式网格布局（自适应列数）
- 导出功能通过前端 JavaScript 实现:
  - **Excel**: 前端将数据拼成 CSV 字符串 → 浏览器下载为 .csv (UTF-8 BOM 确保中文不乱码)
  - **Word**: 前端拼 HTML → 下载为 .doc (MIME: application/msword)
  - **PDF**: `window.print()` → 浏览器打印对话框 → 选择"另存为 PDF"

---

## 四、模型客户端实现 — analyze/clients.py

每个模型客户端的核心方法是 `async def ask_<model>(system_prompt, user_prompt) -> dict | None`。

**统一的调用模式:**
1. 检查 API Key 是否存在 → 不存在则返回 None
2. 发送 system + user prompt
3. 解析返回的 JSON（自动处理 markdown code fence）
4. 异常时打印错误 + 返回 None（不中断流程）

**各模型的实现差异:**

| 模型 | SDK | 端点 | 默认模型 | 备注 |
|------|-----|------|---------|------|
| Claude | `anthropic.AsyncAnthropic` | api.anthropic.com | claude-sonnet-4-6 | system 参数单独传递 |
| GPT | `openai.AsyncOpenAI` | api.openai.com | gpt-4o-mini | 标准 OpenAI API |
| DeepSeek | `openai.AsyncOpenAI` | api.deepseek.com | deepseek-chat | OpenAI 兼容 |
| Qwen | `openai.AsyncOpenAI` | dashscope.aliyuncs.com/compatible-mode/v1 | qwen-plus | OpenAI 兼容 |
| Gemini | `google.genai.Client` | generativelanguage.googleapis.com | gemini-3.5-flash | 独立 SDK |

DeepSeek 和 Qwen 都复用了 OpenAI 的 `AsyncOpenAI` 客户端，只需改 `base_url` 参数。

---

## 五、Glean 配置详解 — feeds.yaml

```yaml
defaults:
  llm:
    provider: openai           # 使用 OpenAI 兼容接口
    model: deepseek-chat       # 实际调 DeepSeek
    base_url: https://api.deepseek.com
  bootstrap: send-all          # 首次运行处理全部条目

feeds:
  - name: src-aljazeera        # Feed 名称
    schedule: "every 2h"       # 定时任务的运行间隔（run 模式用）
    render: {max_items: 15}    # 此 Feed 最多输出 15 条
    sources:                   # 数据源
      [{type: rss, url: "https://www.aljazeera.com/xml/rss/all.xml"}]
    pipeline:                  # 处理流水线
      - dedup                  #   1. URL 去重
      - summarize:             #   2. LLM 摘要（DeepSeek 执行）
          prompt: "Summarize this in one sentence (max 25 words)."
    sinks:                     # 输出目标
      [{type: file, path: "C:/.../glean-output.jsonl", format: jsonl}]
```

**Pipeline 阶段说明:**
- `dedup`: 哈希去重（基于 canonical_url 的 SHA256），跨运行持久化在 SQLite
- `summarize`: 调用 LLM 为每条新闻生成一句话摘要
- `digest`: 设置输出标题（当前未使用，输出到文件时不显示）

**Sink 类型:**
- `file`: 写入本地文件（支持 text/jsonl/markdown 三种格式）
- `telegram/discord/slack/webhook`: 发送到对应平台（未使用）

---

## 六、运行时依赖

```
Python 3.12+

核心依赖:
  anthropic>=0.40.0        # Claude SDK
  openai>=1.60.0           # GPT / DeepSeek / Qwen SDK
  google-genai             # Gemini SDK
  sentence-transformers    # Embedding 聚类模型
  scikit-learn             # 余弦相似度计算
  ddgs                     # DuckDuckGo 搜索（fact-check 用，当前未启用）

Glean 依赖（~/projects\glean 独立环境）:
  glean==1.4.0             # 开源数据采集引擎（pip install -e .）
  feedparser               # RSS 解析
  aiosqlite                # SQLite 异步驱动
  aiohttp / httpx          # HTTP 客户端
  ... (共约 30 个包)
```

---

## 七、运行方式

### 方式 1: 一键脚本
```powershell
powershell -File ~/projects\hot-topics-insight\daily.ps1
```
自动完成 Glean 采集 + bridge 辩论 + 打开报告。

### 方式 2: 分步运行
```powershell
# 第一步: 采集新闻 (~2 分钟)
cd ~/projects\glean
.\run.ps1

# 第二步: 聚类 + 辩论 + 生成报告 (~5 分钟)
cd ~/projects\hot-topics-insight
python bridge.py 10 2

# 打开报告
start output/report.html
```

### 方式 3: Mock 模式（无 API Key 测试）
```powershell
python bridge.py 8 2 --mock
```

### 方式 4: 原始模式（不通过 Glean）
```powershell
# 使用内置的 Reddit + Google Trends 采集（不经过 Glean）
python main.py --topics 8 --mock-llm
```

---

## 八、如何添加新数据源

1. 在 `feeds.yaml` 中添加一个新 Feed:
```yaml
  - name: src-新源名
    schedule: "every 2h"
    render: {max_items: 15}
    sources: [{type: rss, url: "新源的RSS地址"}]
    pipeline: [dedup, {summarize: {prompt: "Summarize this in one sentence (max 25 words)."}}]
    sinks: [{type: file, path: "~/projects/glean/output/glean-output.jsonl", format: jsonl, required: false}]
```
2. 在 `run.ps1` 的 feed 列表中加入 `src-新源名`

支持的 source 类型: `rss` / `hn` / `reddit` / `search` / `scraper`

---

## 九、如何添加新 AI 模型

1. 在 `clients.py` 的 `LLMClients.__init__` 中添加客户端初始化
2. 添加 `ask_<model>` 方法
3. 在 `debate.py` 的 `MODEL_CHAIN` 列表中加入 `("key", "DisplayName")`
4. 在 `ask_fns` 字典中注册
5. 在 `render.py` 的 CSS 中添加对应颜色
6. 在 `.env` 中配置 API Key

---

## 十、限制与已知问题

| 问题 | 原因 | 影响 |
|------|------|------|
| Reddit 无法抓取 | GFW 封锁 + 数据中心 IP 被 Reddit 封 | Reddit 内容始终为空 |
| Twitter 内容偏少 | Nitter RSS 只有 ~20 条/账号 | Twitter 源覆盖有限 |
| Gemini 偶发 503 | Google 免费 tier 限流 | 部分话题只能用 2 模型 |
| Claude/GPT 未激活 | Key 无效 / 余额不足 | 暂未参与辩论 |
| Glean max 50/Feed | Glean 内置限制 | 已通过多 Feed 绕过 |
| 聚类阈值固定 0.70 | 手动设定，未调优 | 偶尔过度/不足合并 |

---

## 十一、项目状态总结

| 组件 | 状态 | 模型来源 |
|------|------|---------|
| 数据采集 | ✅ 9 源 ~146 条/次 | Glean (MIT 开源) |
| Embedding 聚类 | ✅ sentence-transformers | 自研 bridge.py |
| 多模型辩论 | ✅ 3 模型在线 | 自研 debate.py (参考 LLM-Debate/AI Council) |
| HTML 报告 | ✅ 白色专业风格 + 导出 | 自研 render.py |
| Reddit 采集 | ❌ 网络封锁 | Glean Reddit source |
| Claude | ⚠️ 待获取有效 Key | Anthropic SDK |
| GPT | ⚠️ 需充值 | OpenAI SDK |

---

*文档生成时间: 2026-07-13*
*项目路径: ~/projects\hot-topics-insight\*
*Glean 配置: ~/projects\glean\*

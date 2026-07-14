# Hot Topics Insight — 全球热点多模型辩论系统

## 完整项目文档

---

# 目录

1. [项目是什么](#1-项目是什么)
2. [核心概念解释](#2-核心概念解释)
3. [系统架构总览](#3-系统架构总览)
4. [数据从哪里来](#4-数据从哪里来)
5. [新闻如何被筛选和排序](#5-新闻如何被筛选和排序)
6. [AI 模型如何辩论](#6-ai-模型如何辩论)
7. [文件目录与职责说明](#7-文件目录与职责说明)
8. [如何运行本项目](#8-如何运行本项目)
9. [如何修改和扩展](#9-如何修改和扩展)
10. [常见问题与故障排除](#10-常见问题与故障排除)
11. [技术术语表](#11-技术术语表)

---

# 1. 项目是什么

## 1.1 一句话描述

**自动从全球 9 个新闻源抓取热点新闻，用 3 个 AI 模型从不同角度分析观点，最后生成一份带结论和理由的日报。**

## 1.2 它能做什么

假设现在是早上 8 点，你运行了这个项目。接下来的 5 分钟内，它会自动完成：

1. 从 BBC、路透社、纽约时报、半岛电视台等 9 个来源抓取约 150 条最新新闻
2. 把报道同一事件的新闻自动归类（比如"曼谷酒吧火灾"可能被 4 个媒体同时报道，系统会把它们合并为 1 个话题）
3. 选出最热的 10 个话题
4. 用程序自动搜索网络，验证每条新闻是否被可信媒体报道过（过滤假新闻）
5. 让 3 个 AI 模型各自从不同角度分析每个话题：
   - 一个关注**机会和积极面**（发展主义者）
   - 一个关注**风险和隐患**（风控专家）
   - 一个关注**宏观格局**（宏观策略师）
6. 综合三个模型的意见，产出一个统一结论
7. 生成一份白色专业风格的网页报告，支持导出 Excel / Word / PDF

# 2. 系统架构总览# 3. 系统架构总览

整个系统由四个层次组成，像一个流水线：

```
┌─────────────────────────────────────────────────────────────┐
│                 第一层：数据采集（Glean）                     │
│                                                             │
│  9 个新闻源 → 抓取 → 每篇做一句话摘要 → 存入 JSONL 文件       │
│  产出：~150 条新闻/次                                        │
├─────────────────────────────────────────────────────────────┤
│                 第二层：聚类与验证（bridge.py）               │
│                                                             │
│  读 JSONL → URL 去重 → Embedding 聚类 → 网络搜索验证          │
│  产出：Top 10 经过验证的热点话题                              │
├─────────────────────────────────────────────────────────────┤
│                 第三层：角色化辩论（debate.py）               │
│                                                             │
│  3 个 AI 各自从不同角度分析 → 综合器合并观点                   │
│  产出：每条话题的结论 + 各模型理由                            │
├─────────────────────────────────────────────────────────────┤
│                 第四层：报告生成（render.py）                 │
│                                                             │
│  新闻列表 + 辩论结果 → 白色专业 HTML 报告                     │
│  支持导出 Excel / Word / PDF                                 │
└─────────────────────────────────────────────────────────────┘
```

---

# 4. 数据从哪里来

## 4.1 数据采集工具：Glean

我们使用一个叫 **Glean** 的开源工具来做数据采集。Glean 是 GitHub 上一个 MIT 开源许可证的项目，专门用来从各种来源抓取内容、用 AI 做摘要、然后输出到文件或聊天工具。

在本项目中，Glean 安装在 `~/projects\glean\` 目录下。

### 为什么用 Glean 而不是自己写爬虫？

1. Glean 已经做好了 RSS、Reddit、Hacker News 等常见源的适配
2. Glean 自带 URL 去重、LLM 摘要、定时调度等功能
3. Glean 支持多源并发抓取，比自己写高效
4. 开源、免费、可修改

## 4.2 九个新闻源

每个新闻源是一个独立的"Feed"（信息流）。配置文件在 `~/projects\glean\feeds.yaml`。

### 传统新闻媒体（通过 RSS 抓取）

| Feed 名称 | 来源 | 每次抓取条数 | 地区/偏向 |
|-----------|------|-------------|----------|
| `src-aljazeera` | 半岛电视台 | 15 | 中东视角 |
| `src-guardian` | 英国卫报 | 15 | 欧洲自由派 |
| `src-nytimes` | 纽约时报 | 15 | 美国主流 |
| `src-bbc` | BBC 新闻 | 15 | 英国主流 |

### 科技与商业

| Feed 名称 | 来源 | 每次抓取条数 | 说明 |
|-----------|------|-------------|------|
| `src-hackernews` | Hacker News | ~6 | 科技圈热门讨论（需 ≥30 赞） |
| `src-twitter-bloomberg` | Bloomberg | ~20 | 财经新闻 |

### Twitter（通过 Nitter RSS 抓取）

Twitter/X 本身不提供免费的 RSS。但我们通过 **Nitter**（Twitter 的开源第三方前端）间接获取。Nitter 把每个 Twitter 账号的内容转成 RSS 格式，我们就可以像订阅普通新闻一样订阅 Twitter。

| Feed 名称 | Twitter 账号 | 说明 |
|-----------|-------------|------|
| `src-twitter-bbc` | @BBCBreaking | BBC 突发事件 |
| `src-twitter-reuters` | @Reuters | 路透社快讯 |
| `src-twitter-ap` | @AP | 美联社快讯 |

### 为什么 Twitter 只分到 20 条，而传统媒体 15 条？

这不是我们设的限制。Nitter 生成的 RSS 本身就只有 ~20 条内容（因为它只包含最近发布的推文）。传统媒体的 RSS 有完整的近期文章列表。

## 4.3 抓取流程（一键运行 arc_detailed.ps1 发生了什么）

```
1. 脚本读取 feeds.yaml → 找到 9 个 Feed 的定义
2. 逐个执行每个 Feed:
   a. 发送 HTTP 请求到各新闻源的 RSS 地址
   b. 收到 RSS 文件（XML 格式）→ 用 feedparser 库解析
   c. 提取标题、链接、摘要、发布时间
   d. URL 去重（如果同一 URL 之前抓过，跳过）
   e. 每篇文章调用 DeepSeek API → 生成一句英文摘要（≤25 词）
   f. 追加写入 glean-output.jsonl 文件
3. 9 个 Feed 全部跑完 → ~150 条新闻
```

## 4.4 为什么要拆成 9 个独立 Feed？

这是本项目的一个关键设计决策。

如果所有源放在一个 Feed 里，Glean 会按顺序处理：先抓完 Al Jazeera 的所有文章（~40 篇），再抓 Guardian 的（~40 篇）。但 Glean 有个硬限制：每个 Feed 最多输出 50 条。结果就是前两个源就占满了 50 条额度，后面 7 个源全部被丢弃。

**解决方案**：拆成 9 个独立 Feed。每个 Feed 有自己的 50 条配额，互不挤占：
```
src-aljazeera:  独立的 15/50
src-guardian:   独立的 15/50
src-nytimes:    独立的 15/50
src-bbc:        独立的 15/50
...
→ 每个源按自己的配额输出，完美均匀分布
```

---

# 5. 新闻如何被筛选和排序

## 5.1 步骤一：URL 去重

`bridge.py` 中的 `read_glean_output()` 函数读取 `glean-output.jsonl`，按 URL 去重。如果同一条新闻在多次运行间重复出现（Glean 追加写入导致的），只保留一条。

## 5.2 步骤二：Embedding 语义聚类

### 为什么需要聚类？

不同媒体会用不同方式报道同一事件：
- BBC: "At least 27 dead as fire engulfs popular Bangkok pub"
- Guardian: "Deadly Bangkok pub blaze revives concerns over fire safety"
- Reuters: "Bangkok nightclub fire kills 27, injures dozens"

对人类来说，这三条明显是同一事件。但计算机只看字面的话，"fire engulfs" ≠ "pub blaze" ≠ "nightclub fire"。

### 聚类原理

`bridge.py` 中的 `cluster_topics()` 函数：

1. 加载一个叫 `paraphrase-multilingual-MiniLM-L12-v2` 的 AI 模型。这个模型专门用来把文字转成"含义向量"
2. 对每条新闻，把 "标题 + 摘要" 输入模型 → 得到一个 384 维的向量（384 个数字）
3. 计算所有新闻两两之间的"余弦相似度"（一种衡量两个向量有多接近的数学方法）
4. 如果两条新闻的相似度 > 0.70（70%），认为它们是同一事件，归入一个 cluster
5. 贪心聚类算法：从第一条开始，找到所有和它相似的，合成一个话题。然后找下一条未归类的，重复

### 热度计算

每个话题的热度由以下公式决定：

```
热度 = 文章数 × (1 + 不同来源数 × 0.5) × 100
```

为什么这样设计？因为：
- 同一事件被越多媒体报道 → 越重要
- 被不同种类的媒体报道（BBC + 半岛 + 路透社）比被同一种媒体多次报道更有价值
- 这个公式确保了大新闻排前面

## 5.3 步骤三：程序化事实验证

这是最关键的筛选环节。在 AI 模型分析之前，我们先用程序自动判断"这条新闻是不是真的"。

### 为什么不让 AI 判断真伪？

之前的版本试过让 AI 模型自己判断新闻真伪，效果很差。原因是：
- AI 模型的知识有截止日期（如 DeepSeek 只知道 2024 年之前的事）
- 对于 2026 年 7 月的实时新闻，模型会说"这个人在我的知识里还活着，所以这是假新闻"
- 但实际上这个人可能今天刚去世，只是模型不知道

### 程序化验证怎么做

`bridge.py` 中的 `verify_topic()` 函数：

1. 用新闻标题在 DuckDuckGo 搜索引擎中搜索
2. 获取前 8 条搜索结果
3. 检查搜索结果中是否出现了**可信新闻网站的域名**：

```
可信源列表（23 个）:
bbc.co.uk, reuters.com, apnews.com, nytimes.com, theguardian.com,
aljazeera.com, cnn.com, washingtonpost.com, bloomberg.com, npr.org,
cnbc.com, abcnews.go.com, cbsnews.com, nbcnews.com, wsj.com,
economist.com, politico.com, thehindu.com, straitstimes.com,
japantimes.co.jp, dw.com, france24.com
```

4. **至少 1 个可信域名出现在搜索结果中 → 通过验证**
5. **0 个可信域名 → 被过滤（不进入 AI 辩论）**

### 验证示例

```
标题: "Sam Neill dies aged 78"
搜索 "Sam Neill dies aged 78"
结果中出现的域名: bbc.co.uk, theguardian.com, reuters.com
→ 3 个可信源 → 通过 ✓

标题: "Jayden Adams dies weeks after playing World Cup"
搜索 "Jayden Adams dies weeks after playing World Cup"
结果中出现的域名: (无已知可信源)
→ 0 个可信源 → 被过滤 ✗
```

这一步**不涉及任何 AI 判断**，纯粹是程序化的域名匹配。速度快、准确、不消耗 AI 额度。

---

# 6. AI 模型如何辩论

这是项目的核心环节，也是最复杂的部分。

## 6.1 辩论引擎的设计理念

传统的 LLM 辩论让模型互相审阅对方的观点，但这会产生两个问题：
1. 模型可能互扣"假新闻"帽子（Sam Neill 没死！Lindsey Graham 活着！）
2. 后审阅的模型容易被前面的带偏（LLM 有顺从性）

所以我们重新设计了辩论引擎，基于三个核心理念：

```
理念 1: 事实锚定（Factual Anchor）
  在 Prompt 中明确注入已验证的源信息，剥夺 LLM 对新闻真伪的裁判权。

理念 2: 角色博弈（Role-shifting）
  不让模型争论对错，而是分配固定角色去碰撞不同视角。

理念 3: 盲审机制（Blind Review）
  三个模型各自独立分析 → 综合器合并。模型之间互不可见。
```

## 6.2 三个 AI 模型的角色分配

`analyze/clients.py` 中定义了每个模型的"人设"：

### DeepSeek — 发展主义者（Growth Optimist）
```
"你是一个战略增长分析师。你关注机遇：
长期积极发展、技术突破、市场扩张、建设性趋势。
你的视角是乐观的，但基于数据。
你看到别人看不到的上行空间。"
```
→ DeepSeek 会告诉你这条新闻带来了什么**机会**。

### Qwen — 风控合规专家（Risk & Compliance）
```
"你是一个风险与合规分析师。你关注威胁：
监管风险、地缘政治紧张、供应链漏洞、安全隐患、潜在负面影响。
你的视角对乐观叙事持怀疑态度。
你的怀疑指向过分乐观的解读，而不是事件本身。"
```
→ Qwen 会告诉你这条新闻隐藏了什么**风险**。

### Gemini — 宏观策略师（Macro Strategist）
```
"你是一个宏观经济学家和地缘政治策略师。你关注结构性力量：
经济周期、全球秩序变迁、制度变革、长波趋势。
你把这件事和更大的图景联系起来。"
```
→ Gemini 会告诉你这条新闻在**宏观格局**中的位置。

## 6.3 Prompts 详解

### Stage 1 Prompt（发给每个模型的分析提示）

```
【已验证的新闻事件 — 禁止质疑其真实性】

该事件已被 6 个独立媒体来源确认。
验证方式：与 bbc.co.uk, theguardian.com, reuters.com 交叉比对

标题：Sam Neill dies aged 78

来源（6 家媒体）：Al Jazeera, BBC Breaking, HN: story, Reuters

热度分数：1050（越高 = 越多媒体报道此事）

多篇文章上下文：
[实际的多篇文章摘要内容]

验证证据：
Verified by: bbc.co.uk, theguardian.com, reuters.com
Search evidence:
1. Sam Neill, Jurassic Park actor, dies aged 78 - BBC News
    Sam Neill, the New Zealand actor best known for his role in Jurassic Park...
    URL: https://bbc.co.uk/news/...
2. Sam Neill obituary - The Guardian
    ...

---
通过你特定的分析视角，分析这个事件意味着什么。
返回 JSON:
{
  "summary": "一句话事实摘要",
  "significance": "为什么重要 — 通过你的分析视角（1-2句话）",
  "key_insight": "你最重要的原创洞察（1句话）"
}
```

注意 Prompt 的几个关键设计：
1. **开头大写声明**："已验证的新闻事件 — 禁止质疑其真实性"
2. **具体的源列表**：不是抽象的"多个源"，而是列明 BBC、Guardian、Reuters
3. **热度分数**：给模型一个"这件事很重要"的量化信号
4. **多篇文章上下文**：不只是标题，还有来自不同源的摘要片段
5. **搜索证据**：实际的搜索结果文本

这些元素共同构成了"事实锚定"——模型看到这些具体证据后，不会再质疑事件真实性。

### Stage 2 Prompt（发给综合器的合并提示）

```
三个专家独立分析了这个已验证的事件。合并他们的报告。

[DeepSeek (Growth Optimist)] 摘要: ... 关键洞察: ...
[Qwen (Risk & Compliance)] 摘要: ... 关键洞察: ...
[Gemini (Macro Strategist)] 摘要: ... 关键洞察: ...

综合：找出跨视角的共同点，标注分歧点，产出统一的底线结论。

返回 JSON:
{
  "final_agreement": "综合关键结论（2-3句话）",
  "agreement_level": "high" | "partial" | "low",
  "key_tension": "分析师在哪方面存在分歧？（1句话）",
  "bottom_line": "一句话底线",
  "deepseek_justification": "发展主义者核心立场",
  "qwen_justification": "风控专家核心立场",
  "gemini_justification": "宏观策略师核心立场"
}
```

## 6.4 一致度（Agreement Level）的含义

- **HIGH**（高一致）：三个角色在核心意义上达成共识。虽然角度不同（机会 vs 风险 vs 宏观），但都同意这件事的重要性。例如："7/10 的话题达到 HIGH，说明这是一条多维度都认同的重大新闻"

- **PARTIAL**（部分一致）：基本事实一致，但对影响范围或优先级有分歧。例如："台风造成损失这件事大家都同意，但损失有多严重、是否和气候变化有关，看法不同"

- **LOW**（低一致）：三个角色对事件的解读存在根本性分歧。这在真实新闻中很少见（本次运行 0 个 LOW），通常意味着事件本身非常复杂或信息不充分。

---

# 7. 文件目录与职责说明

## 8.1 主项目目录

所有路径相对于 `~/projects\hot-topics-insight\`

```
hot-topics-insight/
│
├── main.py                    # [入口] CLI 命令行入口
│   └── 功能: 使用内置采集器（Reddit + Google Trends）
│       运行一次完整的采集→辩论→输出流程
│       通常不直接使用，而是用 bridge.py
│
├── bridge.py                  # [核心管道] 全链路编排
│   └── 功能: 读取 Glean JSONL → Embedding 聚类
│       → 程序化事实验证 → LLM 角色辩论 → 输出报告
│       这是日常使用的主入口
│
├── daily.ps1                  # [脚本] 一键自动化
│   └── 功能: 串联 Glean 采集 + bridge.py，一键运行
│       用法: powershell -File daily.ps1
│
├── .env                       # [配置] API 密钥（敏感信息，不提交到 Git）
│   └── 内容: DEEPSEEK_API_KEY, QWEN_API_KEY, GEMINI_API_KEY 等
│
├── .env.example               # [模板] API 密钥模板
│   └── 功能: 新用户复制此文件为 .env 后填入自己的密钥
│
├── requirements.txt           # [依赖] Python 包列表
│   └── 内容: anthropic, openai, sentence-transformers 等
│
├── PROJECT_OVERVIEW.md        # [文档] 项目概览（面向有技术背景的读者）
│
├── analyze/                   # [核心] 分析引擎代码
│   ├── clients.py             #   LLM 客户端封装
│   │   └── 职责: 定义每个模型的连接方式、角色 Prompt、
│   │       搜索函数、JSON 解析等
│   ├── debate.py              #   辩论引擎
│   │   └── 职责: 实现两阶段辩论流程
│   │       Stage 1: 三个模型并行独立分析
│   │       Stage 2: 综合器合并观点
│   └── __init__.py            #   Python 包标识文件（空）
│
├── ingest/                    # [备用] 内置数据采集
│   ├── reddit.py              #   Reddit 直接 API 采集（备用）
│   ├── trends.py              #   Google Trends 采集（备用）
│   └── __init__.py            #   Python 包标识文件（空）
│
├── output/                    # [输出] 生成的报告
│   ├── render.py              #   HTML 报告渲染器
│   │   └── 职责: 将数据渲染为白色专业风格 HTML 页面
│   ├── report.html            #   生成的 HTML 报告
│   └── daily-digest.md        #   生成的 Markdown 日报
│
└── docs/                      # [文档]
    └── PROJECT_GUIDE.md       #   本文件
```

## 8.2 Glean 目录

所有路径相对于 `~/projects\glean\`

```
glean/
│
├── feeds.yaml                 # [配置] 9 个 Feed 的定义
│   └── 内容: 每个 Feed 的源类型、URL、抓取限制、
│       Pipeline 步骤、输出路径
│
├── .env                       # [配置] DeepSeek API Key（Glean 用）
│
├── run.ps1                    # [脚本] Glean 单次运行
│   └── 功能: 设置环境变量，运行所有 9 个 Feed
│
├── state.db                   # [数据] SQLite 状态数据库
│   └── 内容: URL 去重记录、Feed 运行历史、HTTP 缓存
│
├── output/
│   └── glean-output.jsonl     # [数据] 采集输出
│       └── 格式: 每行一条 JSON，包含标题、摘要、来源、URL
│
└── src/glean/                 # [源码] Glean 核心代码（开源，只读）
    ├── sources/               #   数据源插件
    ├── pipeline/              #   处理管道
    ├── sinks/                 #   输出插件
    ├── llm/                   #   LLM Provider
    └── ...
```

---

# 8. 如何运行本项目

## 9.1 环境准备

### 必需条件
- **操作系统**: Windows 10 或更高版本
- **Python**: 3.12 或更高版本
- **网络**: 能访问国际互联网（本项目的新闻源和 AI API 均在境外）
- **磁盘空间**: ~2GB（用于 Python 依赖和 AI 模型下载）

### 安装步骤

1. **安装 Python 依赖**
   ```powershell
   cd ~/projects\hot-topics-insight
   pip install -r requirements.txt
   ```

2. **安装 Glean 依赖**
   ```powershell
   cd ~/projects\glean
   pip install -e "."
   ```

3. **配置 API 密钥**
   ```powershell
   cd ~/projects\hot-topics-insight
   copy .env.example .env
   notepad .env
   # 编辑 .env，填入你的 API 密钥
   ```

4. **获取 API 密钥**
   - DeepSeek: 注册 [platform.deepseek.com](https://platform.deepseek.com) → API Keys
   - Qwen: 注册 [dashscope.aliyun.com](https://dashscope.aliyun.com) → API Keys
   - Gemini: 注册 [aistudio.google.com](https://aistudio.google.com) → Get API Key

## 9.2 运行方式

### 方式一：一键运行（推荐日常使用）

```powershell
cd ~/projects\hot-topics-insight
powershell -File daily.ps1
```

这个脚本会自动完成：
1. 运行 Glean 采集新闻（~2 分钟）
2. 运行 bridge.py 聚类验证辩论（~5 分钟）
3. 打开生成的 HTML 报告

### 方式二：分步运行（用于调试）

```powershell
# 第一步：采集新闻
cd ~/projects\glean
.\run.ps1

# 第二步：聚类 + 验证 + 辩论 + 生成报告
cd ~/projects\hot-topics-insight
python bridge.py 10 2
# 参数说明: 10 = 辩论 10 个话题, 2 = 最多同时 2 个话题并发

# 打开报告
start output/report.html
```

### 方式三：Mock 模式（无需 API Key，用于测试流程）

```powershell
cd ~/projects\hot-topics-insight
python bridge.py 8 2 --mock
```

Mock 模式使用模拟的 AI 分析结果，不会调用任何 API，用于测试聚类和报告生成流程。

## 9.3 如何设置定时自动运行

可以使用 Windows 自带的"任务计划程序"：

1. 打开"任务计划程序"（Win+R → `taskschd.msc`）
2. 创建基本任务 → 名称: "Hot Topics Daily"
3. 触发器: 每天 8:00 AM
4. 操作: 启动程序 → `powershell.exe`
5. 参数: `-File "~/projects\hot-topics-insight\daily.ps1"`

---

# 9. 如何修改和扩展

## 10.1 添加新的新闻源

编辑 `~/projects\glean\feeds.yaml`，在 `feeds:` 列表末尾添加：

```yaml
  - name: src-新源名
    schedule: "every 2h"
    render: {max_items: 15}
    sources: [{type: rss, url: "新源的RSS地址"}]
    pipeline: [dedup, {summarize: {prompt: "Summarize this in one sentence (max 25 words)."}}]
    sinks: [{type: file, path: "~/projects/glean/output/glean-output.jsonl", format: jsonl, required: false}]
```

支持的源类型：`rss`（RSS/Atom）、`hn`（Hacker News）、`reddit`（Reddit）、`search`（网页搜索）、`scraper`（网页抓取）。

然后在 `~/projects\glean\run.ps1` 的 `$feeds` 列表中加入 `src-新源名`。

## 10.2 添加新的 AI 模型

以添加"Claude"为例（已预留接口）：

1. **获取 API Key**：访问 [console.anthropic.com](https://console.anthropic.com)
2. **配置 Key**：在 `.env` 中添加 `ANTHROPIC_API_KEY=sk-ant-...`
3. **客户端代码已有**：`clients.py` 已包含 Claude 的客户端代码
4. **辩论引擎已有**：`debate.py` 的 `PERSONAS` 字典中可添加 Claude 的角色
5. **报告渲染已有**：`render.py` 已包含 Claude 的颜色和样式

其它模型（如 GPT、Mistral、Llama 等）按相同模式添加。

## 10.3 调整聚类阈值

`bridge.py` 中的 `CLUSTER_THRESHOLD = 0.70`

- 降低（如 0.60）：更多文章被合并为同一话题（可能过度合并）
- 提高（如 0.80）：更严格，只有高度相似的文章才合并（可能遗漏）

## 10.4 修改 AI 模型的角色

`analyze/clients.py` 中的 `DEEPSEEK_PERSONA`、`QWEN_PERSONA`、`GEMINI_PERSONA` 变量定义了角色。

修改这些文本即可改变模型的分析角度。例如，把 DeepSeek 从"发展主义者"改为"环境科学家"：
```python
DEEPSEEK_PERSONA = """You are an environmental scientist..."""
```

## 10.5 调整可信源列表

`bridge.py` 中的 `CREDIBLE_DOMAINS` 列表。添加或删除域名来调整验证标准。

---

# 10. 常见问题与故障排除

## 11.1 "No API keys found" 或模型不工作

**原因**: `.env` 文件未配置或配置错误。

**解决**:
```powershell
cd ~/projects\hot-topics-insight
notepad .env
```
确认文件中包含正确的 API Key，格式为：
```
DEEPSEEK_API_KEY=sk-你的真实key
QWEN_API_KEY=sk-你的真实key
GEMINI_API_KEY=你的真实key
```

## 11.2 Glean 采集结果为 0

**原因**: 网络连接问题或 Glean 配置错误。

**解决**:
1. 检查网络是否能访问境外网站
2. 检查 `feeds.yaml` 中的 URL 是否正确
3. 删除 `state.db` 后重试（这会清空去重缓存）

## 11.3 某些源始终没有数据

**原因**: 该源在当前网络环境下不可达。

**常见情况**:
- Reddit：对中国 IP 封锁，需要使用 VPN
- Twitter (Nitter)：Nitter 实例被 Cloudflare 保护，需要浏览器验证
- 部分 RSS 源被限制访问

**解决**: 检查 VPN 连接状态。

## 11.4 HTML 报告中文字符乱码

**原因**: 文件编码问题。

**解决**: 报告本身使用 UTF-8 编码，中文不会乱码。如果导出 Excel 时乱码，确保使用 Excel 的"从文本/CSV 导入"功能，选择 UTF-8 编码。

## 11.5 DuckDuckGo 搜索返回空结果

**原因**: DuckDuckGo 对频繁请求有速率限制。

**解决**: 等待几分钟后重试。每次运行 bridge.py 最多做 20 次搜索（Top 20 候选话题），通常在速率限制内。

## 11.6 Glean 报 "State DB path is outside allowed database roots"

**原因**: Glean 的安全限制——只允许在特定目录创建数据库文件。

**解决**: 设置环境变量：
```powershell
$env:GLEAN_DB_ROOT = "~/projects\glean"
$env:GLEAN_FILE_SINK_ROOTS = "~/projects\glean\output"
```

---

# 11. 技术术语表

| 术语 | 英文全称 | 解释 |
|------|---------|------|
| **LLM** | Large Language Model | 大语言模型，如 ChatGPT、DeepSeek |
| **API** | Application Programming Interface | 程序之间通信的接口 |
| **API Key** | — | 访问 API 所需的密钥 |
| **RSS** | Really Simple Syndication | 网站内容订阅的标准格式 |
| **JSON** | JavaScript Object Notation | 一种轻量级数据交换格式 |
| **JSONL** | JSON Lines | 每行一个 JSON 对象的文件格式 |
| **Embedding** | — | 将文字转为数字向量的技术 |
| **Cosine Similarity** | — | 衡量两个向量相似度的数学方法 |
| **Cluster** | — | 聚类结果中的一组相似项 |
| **Prompt** | — | 发给 AI 模型的指令文本 |
| **Prompt Engineering** | — | 设计和优化 Prompt 的方法 |
| **Pipeline** | — | 数据处理的流水线 |
| **Feed** | — | 信息源输出流，Glean 中的配置单元 |
| **Git** | — | 版本控制工具 |
| **Open Source** | — | 开源软件，代码公开可修改 |
| **MIT License** | — | 一种宽松的开源许可证 |
| **Sink** | — | Glean 中的数据输出目标 |
| **SDK** | Software Development Kit | 软件开发工具包 |
| **Nitter** | — | Twitter 的开源第三方前端 |
| **Bootstrap** | — | Glean 的首次运行策略 |
| **Dedup** | Deduplication | 去重 |
| **Overflow** | — | 超出限制被丢弃的数据 |

---

*文档版本: 2.0*
*最后更新: 2026-07-13*
*项目路径: ~/projects\hot-topics-insight\*
*Glean 版本: 1.4.0 (MIT License)*
*License: MIT*

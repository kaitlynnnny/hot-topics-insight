# Hot Topics Insight — Global Multi-LLM News Debate System

Daily automated pipeline: **9 news sources → clustering → programmatic fact verification → 3 LLMs role-based debate → professional HTML report**.

## Architecture

```
Glean (data collection) → bridge.py (clustering + verification) → debate.py (role-based analysis) → render.py (HTML report)

  9 News Sources     sentence-transformers    DeepSeek / Qwen / Gemini     White professional theme
  RSS + Nitter RSS     cosine clustering     Growth / Risk / Macro roles   Excel/Word/PDF export
```

## Quick Start

### 1. Prerequisites
- Python 3.12+
- Windows / macOS / Linux

### 2. Clone & Install
```bash
git clone https://github.com/YOUR_USERNAME/hot-topics-insight.git
cd hot-topics-insight
pip install -r requirements.txt
```

### 3. Set up Glean (Data Collection)
```bash
cd ..
git clone https://github.com/jaypetez/glean.git
cd glean
pip install -e "."
# Copy Glean's feeds.yaml from our project
copy ..\hot-topics-insight\glean-config\feeds.yaml .
copy ..\hot-topics-insight\glean-config\run.ps1 .
```

### 4. Configure API Keys
```bash
copy .env.example .env
# Edit .env and fill in your keys:
#   DEEPSEEK_API_KEY=sk-...     (platform.deepseek.com)
#   QWEN_API_KEY=sk-...         (dashscope.aliyun.com)
#   GEMINI_API_KEY=...          (aistudio.google.com)
#   ANTHROPIC_API_KEY=sk-ant-... (optional, console.anthropic.com)
#   OPENAI_API_KEY=sk-...       (optional, platform.openai.com)
```

At minimum, you need **DeepSeek** or **Qwen** API key. Gemini is optional (free tier has geo-restrictions).

### 5. Update Paths
Edit the following paths in `bridge.py` to match your setup:
- `GLEAN_JSONL`: path to Glean's output JSONL file
- Edit `feeds.yaml` sinks path to match your system

### 6. Run
```bash
# One-command daily run
powershell -File daily.ps1

# Or step by step:
cd ../glean && .\run.ps1          # Fetch news (~2 min)
cd ../hot-topics-insight
python bridge.py 10 2             # Cluster + verify + debate (~5 min)
start output/report.html          # Open report
```

## How It Works

1. **Glean** fetches ~150 articles from Al Jazeera, Guardian, NYT, BBC, Hacker News, and Twitter (via Nitter RSS). Each article is summarized by DeepSeek into one sentence.

2. **bridge.py** reads the JSONL output, uses `sentence-transformers` to cluster similar articles by embedding similarity, then programmatically verifies each topic by searching DuckDuckGo and checking if credible news domains appear.

3. **debate.py** runs 3 LLMs with fixed roles — Growth Optimist (DeepSeek), Risk & Compliance (Qwen), Macro Strategist (Gemini) — each analyzing verified topics independently. A Synthesizer merges their reports.

4. **render.py** generates a white professional HTML report with debate results first, then all news articles, plus Excel/Word/PDF export.

## File Structure

```
hot-topics-insight/
├── bridge.py              # Main pipeline orchestrator
├── daily.ps1              # One-click automation script
├── analyze/
│   ├── clients.py         # LLM client wrappers + role personas
│   └── debate.py          # 2-stage debate engine
├── output/
│   └── render.py          # HTML report generator
├── glean-config/           # Glean configuration files
│   ├── feeds.yaml          # 9 news feed definitions
│   └── run.ps1             # Glean run script
├── docs/
│   └── PROJECT_GUIDE.md   # Full documentation (Chinese)
├── .env.example            # API key template
└── requirements.txt        # Python dependencies
```


## Supported Models

| Model | Status | Cost |
|-------|--------|------|
| DeepSeek V3 | Recommended | ~$0.27/M tokens |
| Qwen Plus | Recommended | ~$0.50/M tokens |
| Gemini 3.5 Flash | Optional (geo-restricted) | Free tier |
| Claude Sonnet 4 | Optional | ~$3/M tokens |
| GPT-4o-mini | Optional | ~$0.15/M tokens |

## Documentation

Full project documentation (in Chinese) is available at `docs/PROJECT_GUIDE.md`. Covers architecture, data flow, every file's purpose, and troubleshooting.

## License

MIT — do whatever you want with it.

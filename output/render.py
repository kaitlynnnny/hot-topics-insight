"""
Generate an HTML report from debate results and news articles.
Section 1: debate results with agreement levels and justifications.
Section 2: all news articles in a sortable table.
Includes Excel/Word/PDF export via client-side JavaScript.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"

CSS = """
:root {
  --bg: #ffffff;
  --text: #1a1a1a;
  --text-secondary: #555;
  --border: #e0e0e0;
  --accent: #1a56db;
  --accent-light: #eff6ff;
  --agree-high: #059669;
  --agree-partial: #d97706;
  --agree-low: #dc2626;
  --card-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: #f8f9fa;
  color: var(--text);
  line-height: 1.6;
  font-size: 15px;
}
.container { max-width: 1000px; margin: 0 auto; padding: 2rem; }

/* ── Header ── */
header {
  background: white;
  border-bottom: 1px solid var(--border);
  padding: 1.5rem 2rem;
  margin-bottom: 2rem;
}
header h1 { font-size: 1.5rem; font-weight: 600; color: #111; }
header .meta { font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.25rem; }
header .models { margin-top: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
.model-tag {
  display: inline-block; padding: 0.2rem 0.65rem; border-radius: 4px;
  font-size: 0.75rem; font-weight: 600; letter-spacing: 0.02em;
}
.tag-deepseek { background: #eef2ff; color: #4338ca; }
.tag-qwen { background: #f0fdfa; color: #0f766e; }
.tag-gemini { background: #eff6ff; color: #1d4ed8; }
.tag-claude { background: #fff7ed; color: #c2410c; }
.tag-gpt { background: #ecfdf5; color: #047857; }
.sources-tag { background: #f5f5f5; color: #555; }

/* ── Buttons ── */
.toolbar { display: flex; gap: 0.75rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
.btn {
  display: inline-flex; align-items: center; gap: 0.4rem;
  padding: 0.5rem 1rem; border: 1px solid var(--border);
  border-radius: 6px; background: white; color: var(--text);
  font-size: 0.85rem; cursor: pointer; text-decoration: none;
  transition: all 0.15s;
}
.btn:hover { background: #f5f5f5; border-color: #ccc; }
.btn-primary { background: var(--accent); color: white; border-color: var(--accent); }
.btn-primary:hover { background: #1e40af; }

/* ── Section titles ── */
.section-title {
  font-size: 1.2rem; font-weight: 600; color: #111;
  padding-bottom: 0.5rem; border-bottom: 2px solid var(--accent);
  margin-bottom: 1.25rem; margin-top: 2rem;
}

/* ── News list ── */
.news-table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: var(--card-shadow); }
.news-table th {
  text-align: left; padding: 0.75rem 1rem; background: #fafafa;
  font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-secondary); border-bottom: 1px solid var(--border);
}
.news-table td { padding: 0.75rem 1rem; border-bottom: 1px solid #f0f0f0; font-size: 0.88rem; }
.news-table tr:hover td { background: #fafcff; }
.news-table .source-col { font-size: 0.75rem; color: var(--text-secondary); white-space: nowrap; }
.news-table .title-col a { color: var(--accent); text-decoration: none; }
.news-table .title-col a:hover { text-decoration: underline; }
.news-table .summary-col { font-size: 0.82rem; color: var(--text-secondary); max-width: 350px; }

/* ── Debate cards ── */
.debate-card {
  background: white; border: 1px solid var(--border); border-radius: 10px;
  padding: 1.5rem; margin-bottom: 1.5rem; box-shadow: var(--card-shadow);
}
.debate-card h3 { font-size: 1.05rem; font-weight: 600; margin-bottom: 0.35rem; color: #111; }
.debate-card h3 a { color: #111; text-decoration: none; }
.debate-card h3 a:hover { color: var(--accent); }
.debate-card .card-meta { font-size: 0.78rem; color: var(--text-secondary); margin-bottom: 1rem; }
.debate-card .source-pill {
  display: inline-block; padding: 0.1rem 0.5rem; border-radius: 3px;
  font-size: 0.7rem; font-weight: 600; background: #f5f5f5; color: #555; margin-right: 0.35rem;
}

/* Agreement badge */
.agreement-header {
  display: flex; align-items: center; gap: 0.75rem; margin-bottom: 1rem;
  padding: 0.75rem 1rem; border-radius: 6px;
}
.agreement-header.high { background: #ecfdf5; border-left: 3px solid var(--agree-high); }
.agreement-header.partial { background: #fffbeb; border-left: 3px solid var(--agree-partial); }
.agreement-header.low { background: #fef2f2; border-left: 3px solid var(--agree-low); }
.agreement-header .agree-level {
  font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.03em;
}
.agreement-header.high .agree-level { color: var(--agree-high); }
.agreement-header.partial .agree-level { color: var(--agree-partial); }
.agreement-header.low .agree-level { color: var(--agree-low); }

.final-agreement { font-size: 1rem; font-weight: 500; line-height: 1.6; margin-bottom: 1rem; color: #222; }

/* Justifications */
.justifications { margin-top: 1rem; }
.justifications h4 {
  font-size: 0.8rem; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.04em; color: var(--text-secondary); margin-bottom: 0.75rem;
}
.just-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 0.75rem; }
.just-item {
  padding: 0.75rem 1rem; border-radius: 6px; font-size: 0.85rem; line-height: 1.5;
}
.just-item.deepseek { background: #f8f9ff; border-left: 3px solid #4338ca; }
.just-item.qwen { background: #f9fdfc; border-left: 3px solid #0f766e; }
.just-item.gemini { background: #f8faff; border-left: 3px solid #1d4ed8; }
.just-item.claude { background: #fefaf5; border-left: 3px solid #c2410c; }
.just-item.gpt { background: #f8fdfa; border-left: 3px solid #047857; }
.just-item .just-model {
  font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: 0.04em; margin-bottom: 0.3rem;
}
.just-item.deepseek .just-model { color: #4338ca; }
.just-item.qwen .just-model { color: #0f766e; }
.just-item.gemini .just-model { color: #1d4ed8; }
.just-item.claude .just-model { color: #c2410c; }
.just-item.gpt .just-model { color: #047857; }

.tension { font-size: 0.82rem; color: var(--text-secondary); margin-top: 0.75rem; font-style: italic; }
.bottom-line { font-size: 0.88rem; font-weight: 600; color: var(--accent); margin-top: 0.4rem; }

footer { text-align: center; padding: 2rem; color: var(--text-secondary); font-size: 0.8rem; }

@media print {
  body { background: white; }
  .toolbar, .btn { display: none; }
  .debate-card { break-inside: avoid; box-shadow: none; }
}
"""

MODEL_CSS = {
    "DeepSeek": "deepseek", "Qwen": "qwen", "Gemini": "gemini",
    "Claude": "claude", "GPT": "gpt",
}
MODEL_TAG = {
    "DeepSeek": "tag-deepseek", "Qwen": "tag-qwen", "Gemini": "tag-gemini",
    "Claude": "tag-claude", "GPT": "tag-gpt",
}


def _excel_json(insights: list, raw_items: list[dict]) -> str:
    """Generate JSON data for export (used by JS to create Excel)."""
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "news_articles": [
            {"title": item.get("title", ""), "source": item.get("source_name", ""),
             "url": item.get("url", ""), "summary": item.get("summary", "")}
            for item in raw_items
        ],
        "debate_results": [
            {
                "title": ins.title,
                "source": ins.source_str,
                "final_agreement": ins.final_agreement,
                "agreement_level": ins.agreement_level,
                "key_tension": ins.key_tension,
                "bottom_line": ins.bottom_line,
                "justifications": {
                    "DeepSeek (Growth Optimist)": ins.deepseek_justification or "",
                    "Qwen (Risk & Compliance)": ins.qwen_justification or "",
                    "Gemini (Macro Strategist)": ins.gemini_justification or "",
                },
            }
            for ins in insights
        ],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def render_report(insights: list, raw_items: list[dict] | None = None, output_path: str | None = None) -> str:
    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = str(OUTPUT_DIR / "report.html")

    if raw_items is None:
        raw_items = []

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    export_json = _excel_json(insights, raw_items)

    # Active model badges
    active_models = set()
    for ins in insights:
        active_models.update(ins.active_models)
    model_tags = "\n".join(
        f'<span class="model-tag {MODEL_TAG.get(m, "")}">{m}</span>'
        for m in ["DeepSeek", "Qwen", "Gemini", "Claude", "GPT"] if m in active_models
    )

    # ── Section 1: News table ──
    news_rows = ""
    for i, item in enumerate(raw_items, 1):
        title = item.get("title", "")
        url = item.get("url", "")
        source = item.get("source_name", item.get("source_type", ""))
        summary = item.get("summary", "")
        title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title
        news_rows += f"""<tr>
  <td>{i}</td>
  <td class="title-col">{title_html}</td>
  <td class="source-col">{source}</td>
  <td class="summary-col">{summary}</td>
</tr>"""

    # ── Section 2: Debate cards ──
    debate_cards = ""
    for i, ins in enumerate(insights, 1):
        # Source pills
        pills = ""
        for src in ins.source_str.split("+"):
            src = src.strip()
            if src:
                pills += f'<span class="source-pill">{src}</span>'

        # Agreement header
        agree_class = ins.agreement_level or "unknown"
        agree_label = {"high": "HIGH AGREEMENT", "partial": "PARTIAL AGREEMENT", "low": "LOW AGREEMENT"}.get(agree_class, "UNKNOWN")

        # Justifications (now per-role from the Synthesizer)
        role_map = {
            "DeepSeek": ("Growth Optimist", ins.deepseek_justification),
            "Qwen": ("Risk & Compliance", ins.qwen_justification),
            "Gemini": ("Macro Strategist", ins.gemini_justification),
            "Claude": ("General Analyst", ""),
            "GPT": ("General Analyst", ""),
        }
        just_items = ""
        for model_name in ins.active_models:
            css = MODEL_CSS.get(model_name, "")
            role_label, justification = role_map.get(model_name, ("Analyst", ""))
            # Fallback: use model's analysis
            if not justification:
                analysis = ins.get_analysis(model_name)
                if analysis:
                    justification = analysis.get("key_insight", "") or analysis.get("summary", "")
            if justification:
                just_items += f"""<div class="just-item {css}">
  <div class="just-model">{model_name} — {role_label}</div>
  <div>{justification}</div>
</div>"""

        title_link = f'<a href="{ins.url}" target="_blank">{ins.title}</a>' if ins.url else ins.title

        debate_cards += f"""<div class="debate-card">
  <h3>#{i} {title_link}</h3>
  <div class="card-meta">{pills}</div>
  {f'<div class="agreement-header {agree_class}"><div class="agree-level">{agree_label}</div><div style="font-size:0.85rem">{ins.final_agreement}</div></div>' if ins.final_agreement else ''}
  {f'<div class="bottom-line">{ins.bottom_line}</div>' if ins.bottom_line else ''}
  <div class="justifications">
    <h4>Model Justifications</h4>
    <div class="just-grid">{just_items}</div>
  </div>
  {f'<div class="tension">{ins.key_tension}</div>' if ins.key_tension else ''}
  {f'<div class="error-banner" style="color:#dc2626;font-size:0.82rem;margin-top:0.5rem">{ins.error}</div>' if ins.error else ''}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Global Hot Topics — Daily Insight Report</title>
<style>{CSS}</style>
</head>
<body>
<header>
  <h1>Global Hot Topics — Daily Insight Report</h1>
  <div class="meta">{now} · {len(raw_items)} articles from Al Jazeera, Guardian, NYT, BBC, HN, Twitter (Nitter RSS)</div>
  <div class="models">{model_tags}<span class="model-tag sources-tag">{len(raw_items)} sources</span></div>
</header>

<div class="container">

<!-- Toolbar -->
<div class="toolbar">
  <button class="btn btn-primary" onclick="exportExcel()">Export Excel (.csv)</button>
  <button class="btn" onclick="exportWord()">Export Word (.doc)</button>
  <button class="btn" onclick="window.print()">Print / Save PDF</button>
</div>

<!-- ── Section 1: Multi-LLM Debate ── -->
<div class="section-title">Top 10 — Multi-LLM Debate Results</div>
{debate_cards}

<!-- ── Section 2: All News Articles ── -->
<div class="section-title">All News Articles</div>
<table class="news-table">
<thead><tr><th>#</th><th>Title</th><th>Source</th><th>Summary</th></tr></thead>
<tbody>{news_rows}</tbody>
</table>

</div>

<footer>Generated by Hot Topics Insight · {now} · Data from Al Jazeera, Guardian, NYT, BBC, HN, Nitter RSS</footer>

<script>
const EXPORT_DATA = {export_json};

function exportExcel() {{
  const rows = [['Topic','Source','Final Agreement','Agreement Level','Bottom Line','Key Tension']];
  EXPORT_DATA.debate_results.forEach(r => {{
    rows.push([r.title, r.source, r.final_agreement, r.agreement_level, r.bottom_line, r.key_tension]);
  }});
  rows.push([], ['--- NEWS ARTICLES ---']);
  EXPORT_DATA.news_articles.forEach(n => {{
    rows.push([n.title, n.source, n.url, n.summary]);
  }});
  const csv = rows.map(r => r.map(c => '"' + (c||'').replace(/"/g,'""') + '"').join(',')).join('\\n');
  const BOM = '\\uFEFF';
  download(BOM + csv, 'hot-topics-insight.csv', 'text/csv;charset=utf-8');
}}

function exportWord() {{
  let html = '<html><head><meta charset="UTF-8"><style>body{{font-family:Segoe UI,sans-serif;font-size:14px;line-height:1.6}}h2{{color:#1a56db}}h3{{margin-top:1.5em}}.just-item{{margin:0.5em 0;padding:0.5em 0.75em;border-left:3px solid #ccc}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px 10px;text-align:left}}th{{background:#f5f5f5}}</style></head><body>';
  html += '<h1>Global Hot Topics — Daily Insight Report</h1>';
  html += '<p>' + new Date().toISOString().slice(0,10) + '</p>';
  html += '<h2>News Articles</h2><table><tr><th>#</th><th>Title</th><th>Source</th><th>Summary</th></tr>';
  EXPORT_DATA.news_articles.forEach((n,i) => {{ html += '<tr><td>'+(i+1)+'</td><td>'+n.title+'</td><td>'+n.source+'</td><td>'+n.summary+'</td></tr>'; }});
  html += '</table>';
  html += '<h2>Debate Results</h2>';
  EXPORT_DATA.debate_results.forEach((r,i) => {{
    html += '<h3>'+(i+1)+'. '+r.title+'</h3>';
    html += '<p><strong>Final Agreement:</strong> '+r.final_agreement+'</p>';
    html += '<p><em>Agreement Level: '+r.agreement_level+'</em></p>';
    if (r.bottom_line) html += '<p><strong>Bottom Line:</strong> '+r.bottom_line+'</p>';
    if (r.justifications) {{
      html += '<h4>Justifications</h4>';
      Object.entries(r.justifications).forEach(([model,just]) => {{ html += '<div class="just-item"><strong>'+model+':</strong> '+just+'</div>'; }});
    }}
  }});
  html += '</body></html>';
  download(html, 'hot-topics-insight.doc', 'application/msword');
}}

function download(content, filename, mime) {{
  const blob = new Blob([content], {{type: mime}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}}
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path

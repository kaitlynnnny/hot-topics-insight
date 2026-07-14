# ========================================
# Hot Topics Insight — Daily Automation
# Run: powershell -File daily.ps1
# ========================================

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$GleanDir = Join-Path (Split-Path -Parent $ScriptDir) "glean"
$Today = Get-Date -Format "yyyy-MM-dd"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Hot Topics Insight — $Today" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# ── Step 1: Glean (fetch news) ──
Write-Host "`n[1/2] Fetching news via Glean..." -ForegroundColor Yellow
$env:GLEAN_FILE_SINK_ROOTS = "$GleanDir\output"
$env:GLEAN_DB_ROOT = $GleanDir
# Load API key from .env file
$envPath = Join-Path $ScriptDir ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]+)=(.*)') {
            $key = $matches[1].Trim()
            $val = $matches[2].Trim()
            if ($key -eq "OPENAI_API_KEY") { $env:OPENAI_API_KEY = $val }
            if ($key -eq "DEEPSEEK_API_KEY") { $env:DEEPSEEK_API_KEY = $val }
            if ($key -eq "QWEN_API_KEY") { $env:QWEN_API_KEY = $val }
            if ($key -eq "GEMINI_API_KEY") { $env:GEMINI_API_KEY = $val }
        }
    }
} else {
    Write-Host "[!] .env not found. Copy .env.example to .env and fill in your API keys." -ForegroundColor Red
    exit 1
}

# Clean old output for fresh run
Remove-Item "$GleanDir\output\glean-output.jsonl" -ErrorAction SilentlyContinue

Push-Location $GleanDir
try {
    python -m glean test-feed global-news -c feeds.yaml --send --db "$GleanDir\state.db"
    Write-Host "  Glean done." -ForegroundColor Green
} finally {
    Pop-Location
}

# ── Step 2: Bridge (cluster + debate) ──
Write-Host "`n[2/2] Clustering + Multi-LLM debate..." -ForegroundColor Yellow
Push-Location $ScriptDir
try {
    python bridge.py 10 2
    Write-Host "  Bridge done." -ForegroundColor Green
} finally {
    Pop-Location
}

# ── Open report ──
$Report = "$ScriptDir\output\report.html"
if (Test-Path $Report) {
    Start-Process $Report
    Write-Host "`nReport opened in browser." -ForegroundColor Green
}

Write-Host "`n[DONE] Daily insight generated: $Today" -ForegroundColor Cyan

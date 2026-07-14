# Glean run script — reads API keys from .env in the hot-topics-insight directory

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$envPath = Join-Path $ProjectDir ".env"

if (-not (Test-Path $envPath)) {
    Write-Host "[!] .env not found. Copy .env.example to .env and fill in your API keys." -ForegroundColor Red
    exit 1
}

# Load API keys from .env
Get-Content $envPath | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)') {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        if ($key -eq "OPENAI_API_KEY") { $env:OPENAI_API_KEY = $val }
    }
}

# Glean path settings
$env:GLEAN_FILE_SINK_ROOTS = "$PWD\output"
$env:GLEAN_DB_ROOT = "$PWD"

# All feeds (update this list if you modify feeds.yaml)
$feeds = @(
    "src-aljazeera", "src-guardian", "src-nytimes", "src-bbc",
    "src-hackernews",
    "src-twitter-bbc", "src-twitter-reuters", "src-twitter-ap", "src-twitter-bloomberg"
)

foreach ($f in $feeds) {
    Write-Host "=== $f ==="
    python -m glean test-feed $f -c feeds.yaml --send --db state.db 2>&1 | Select-Object -Last 2
}

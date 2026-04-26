Write-Host "`n--- Setup Interattivo Progetto ---" -ForegroundColor Cyan

# ===============================
# NODE VERSION
# ===============================
Write-Host "`nScegli versione Node.js LTS:" -ForegroundColor Yellow

$nodeChoices = @{
    "1" = "20"
    "2" = "22"
    "3" = "24"
}

$nodeChoices.Keys | Sort-Object | ForEach-Object {
    $k = $_
    Write-Host "$k) Node $($nodeChoices[$k])"
}

$nOpt = Read-Host "Opzione [1]"
if (-not $nOpt) { $nOpt = "1" }

$NODE_V = $nodeChoices[$nOpt]
if (-not $NODE_V) { $NODE_V = "20" }

# ===============================
# PYTHON VERSION
# ===============================
Write-Host "`nScegli versione Python:" -ForegroundColor Yellow

$pyChoices = @{
    "1" = "3.11"
    "2" = "3.12"
    "3" = "3.13"
    "4" = "3.14"
}

$pyChoices.Keys | Sort-Object | ForEach-Object {
    $k = $_
    Write-Host "$k) Python $($pyChoices[$k])"
}

$pOpt = Read-Host "Opzione [2]"
if (-not $pOpt) { $pOpt = "2" }

$PY_V = $pyChoices[$pOpt]
if (-not $PY_V) { $PY_V = "3.12" }

# ===============================
# CHECK TOOLS
# ===============================
if (-not (Get-Command fnm -ErrorAction SilentlyContinue)) {
    Write-Host "fnm non installato." -ForegroundColor Red
    exit
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv non installato." -ForegroundColor Red
    exit
}

# ===============================
# NODE SETUP
# ===============================
Write-Host "`n[1/2] Setup Node $NODE_V..." -ForegroundColor Cyan

fnm install $NODE_V
fnm use $NODE_V

# ===============================
# PYTHON SETUP
# ===============================
Write-Host "[2/2] Setup Python $PY_V..." -ForegroundColor Cyan

uv venv --python $PY_V --allow-existing

# Activate venv
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & .\.venv\Scripts\Activate.ps1
}

Write-Host "`nConfigurato!" -ForegroundColor Green
Write-Host "Node   : $(node -v)"
Write-Host "Python : $(python --version)"

<#
.SYNOPSIS
    Lance l'API EMS en local, sur une copie de la base de prod, pour tester les apps.

.DESCRIPTION
    - Copie la dernière sauvegarde de prod (EMS PROJET APP\ems_api\data\backups)
      dans ..\dev-data\ems.db (seulement la 1re fois, ou avec -FreshDb).
    - Bascule TEMPORAIREMENT config.ini vers http://127.0.0.1 et des dossiers
      de test dans ..\dev-data (les apps lisent config.ini AVANT EMS_API_URL :
      sans ça elles parleraient au serveur de prod 192.168.1.10).
    - Lance uvicorn avec --reload (le code modifié est rechargé à chaud).
    - À l'arrêt (Ctrl+C), remet config.ini d'origine (git restore).

    ⚠ Ne pas lancer build.ps1 pendant que ce script tourne : config.ini
      (version locale) serait embarqué dans les .exe.

.EXAMPLE
    .\dev_local.ps1             # démarre (réutilise dev-data\ems.db)
    .\dev_local.ps1 -FreshDb    # repart d'une copie neuve de la base prod
    .\dev_local.ps1 -Restore    # remet seulement config.ini (si fenêtre fermée brutalement)
#>
param(
    [switch]$FreshDb,
    [switch]$Restore,
    [int]$Port = 8765
)
$ErrorActionPreference = "Stop"

$ROOT    = $PSScriptRoot
$PARENT  = Split-Path $ROOT -Parent
$DEV     = Join-Path $PARENT "dev-data"
$BACKUPS = Join-Path $PARENT "EMS PROJET APP\ems_api\data\backups"
$PY      = Join-Path $ROOT ".venv\Scripts\python.exe"
$CFG     = Join-Path $ROOT "config.ini"
$MARKER  = "; >>> CONFIG DEV LOCALE (dev_local.ps1)"
$GIT     = (Get-Command git -ErrorAction SilentlyContinue).Source
if (-not $GIT) { $GIT = "$env:ProgramFiles\Git\cmd\git.exe" }

function Restore-Config {
    & $GIT -C $ROOT restore -- config.ini
    Write-Host "  config.ini d'origine restauré (pointe à nouveau vers la prod)." -ForegroundColor Green
}

# ── Restauration seule, ou reliquat d'une session interrompue ───────────────
$isDev = (Test-Path $CFG) -and ((Get-Content $CFG -Raw) -like "*$MARKER*")
if ($Restore) { Restore-Config; return }
if ($isDev) {
    Write-Host "  config.ini local trouvé (session précédente interrompue) → restauration." -ForegroundColor Yellow
    Restore-Config
}
& $GIT -C $ROOT diff --quiet -- config.ini
if ($LASTEXITCODE -ne 0) {
    Write-Host "  [ERREUR] config.ini a des modifications non commitées : je n'y touche pas." -ForegroundColor Red
    Write-Host "  Commitez-les ou annulez-les, puis relancez." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $PY)) { Write-Host "  [ERREUR] .venv absent : $PY" -ForegroundColor Red; exit 1 }

# WeasyPrint (PDF) : DLL Pango/GTK fournies par MSYS2 (pacman -S mingw-w64-x86_64-pango)
if (-not $env:WEASYPRINT_DLL_DIRECTORIES -and (Test-Path "C:\msys64\mingw64\bin\libpango-1.0-0.dll")) {
    $env:WEASYPRINT_DLL_DIRECTORIES = "C:\msys64\mingw64\bin"
}
if (-not $env:WEASYPRINT_DLL_DIRECTORIES) {
    Write-Host "  [WARN] Pango introuvable : la génération de PDF échouera." -ForegroundColor Yellow
}

# ── Base de test ─────────────────────────────────────────────────────────────
$db = Join-Path $DEV "ems.db"
foreach ($d in $DEV, "$DEV\AFFAIRES", "$DEV\INTERVENTIONS", "$DEV\GARANTIES", "$DEV\AMELIORATIONS") {
    New-Item -ItemType Directory -Force $d | Out-Null
}
if ($FreshDb -or -not (Test-Path $db)) {
    $src = Get-ChildItem $BACKUPS -Filter "ems_*.db" -ErrorAction SilentlyContinue | Sort-Object Name | Select-Object -Last 1
    if (-not $src) { Write-Host "  [ERREUR] Aucune sauvegarde trouvée dans $BACKUPS" -ForegroundColor Red; exit 1 }
    Remove-Item "$db*" -Force -ErrorAction SilentlyContinue   # ems.db + -wal/-shm éventuels
    Copy-Item $src.FullName $db
    Write-Host "  Base de test : copie de $($src.Name)" -ForegroundColor Green
} else {
    Write-Host "  Base de test : $db (réutilisée ; -FreshDb pour repartir de la prod)" -ForegroundColor Cyan
}

# ── config.ini local (UTF-8 SANS BOM : configparser refuse le BOM) ─────────
$cfgText = @"
$MARKER — NE PAS COMMITER, restauré automatiquement <<<
[server]
url = http://127.0.0.1:$Port

[files]
data_dir = $DEV
affaires_dir = $DEV\AFFAIRES
dossiers_root = $DEV\INTERVENTIONS
garanties_root = $DEV\GARANTIES
ameliorations_root = $DEV\AMELIORATIONS
commercial_group =
commercial_admins = BUILTIN\Administrators
"@
[IO.File]::WriteAllText($CFG, $cfgText, (New-Object Text.UTF8Encoding $false))

Write-Host ""
Write-Host "  API locale : http://127.0.0.1:$Port   (docs : /docs)" -ForegroundColor Cyan
Write-Host "  Apps       : dans un 2e terminal →  .\.venv\Scripts\python.exe ems_launcher.py" -ForegroundColor Cyan
Write-Host "  Arrêt      : Ctrl+C (config.ini sera restauré)" -ForegroundColor Cyan
Write-Host ""

try {
    Push-Location $ROOT
    & $PY -m uvicorn ems_api.main:app --host 127.0.0.1 --port $Port --reload --reload-dir ems_api --reload-dir shared --reload-dir ems_client
} finally {
    Pop-Location
    Restore-Config
}

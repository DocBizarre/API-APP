#Requires -Version 5.1
<#
.SYNOPSIS
    Compile tous les .exe EMS et les déploie dans EMS_Distribution/.

.DESCRIPTION
    - Compile les 7 applications via PyInstaller
    - Copie les .exe produits dans EMS_Distribution/
    - Copie config.ini dans EMS_Distribution/

.PARAMETER App
    Nom d'une app spécifique à compiler (ex: Bons, Parc, Launcher...).
    Si absent, compile tout.

.EXAMPLE
    .\build.ps1                  # compile tout
    .\build.ps1 -App Bons        # compile seulement EMS_Bons
#>
param(
    [string]$App = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ROOT    = $PSScriptRoot
$DIST    = Join-Path $ROOT "dist"
$DEPLOY  = Join-Path $ROOT "EMS_Distribution"

$SPECS = [ordered]@{
    "Launcher"     = "ems_launcher.spec"
    "Bons"         = "EMS_Bons.spec"
    "Parc"         = "EMS_Parc.spec"
    "Garanties"    = "EMS_Garanties.spec"
    "Amelioration" = "EMS_Amelioration.spec"
    "Pieces"       = "EMS_Pieces.spec"
    "BI"           = "EMS_BI.spec"
}

function Write-Header([string]$text) {
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Build-App([string]$name, [string]$spec) {
    Write-Header "Build : EMS_$name"
    $specPath = Join-Path $ROOT $spec
    if (-not (Test-Path $specPath)) {
        Write-Warning "Spec introuvable : $specPath"
        return $false
    }
    $cmd = $PYINSTALLER_CMD -split " "
    & $cmd[0] ($cmd[1..($cmd.Length-1)] + @($specPath, "--distpath", $DIST, "--workpath", (Join-Path $ROOT "build"), "--noconfirm", "--clean"))
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERREUR lors du build de $name (code $LASTEXITCODE)" -ForegroundColor Red
        return $false
    }
    Write-Host "OK : EMS_$name.exe" -ForegroundColor Green
    return $true
}

function Deploy-Exe([string]$name) {
    $src  = Join-Path $DIST "EMS_$name.exe"
    $dest = Join-Path $DEPLOY "EMS_$name.exe"
    if (Test-Path $src) {
        Copy-Item $src $dest -Force
        Write-Host "  Déployé : EMS_$name.exe" -ForegroundColor Green
    } else {
        Write-Warning "  Introuvable : $src"
    }
}

# ─── Vérifications préalables ─────────────────────────────────────────────────
$PYINSTALLER_CMD = if (Get-Command pyinstaller -ErrorAction SilentlyContinue) {
    "pyinstaller"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    "python -m PyInstaller"
} else {
    Write-Host "ERREUR : ni pyinstaller ni python trouvés dans le PATH." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Path $DIST   -Force | Out-Null
New-Item -ItemType Directory -Path $DEPLOY -Force | Out-Null

# ─── Sélection des apps à compiler ────────────────────────────────────────────
$toBuild = if ($App) {
    if (-not $SPECS.Contains($App)) {
        Write-Host "App inconnue : '$App'. Valeurs valides : $($SPECS.Keys -join ', ')" -ForegroundColor Red
        exit 1
    }
    [ordered]@{ $App = $SPECS[$App] }
} else {
    $SPECS
}

# ─── Build ────────────────────────────────────────────────────────────────────
$errors = 0
foreach ($entry in $toBuild.GetEnumerator()) {
    $ok = Build-App $entry.Key $entry.Value
    if (-not $ok) { $errors++ }
}

# ─── Déploiement vers EMS_Distribution/ ──────────────────────────────────────
Write-Header "Déploiement vers EMS_Distribution/"

foreach ($name in $toBuild.Keys) {
    Deploy-Exe $name
}

# Copier config.ini si absent ou plus vieux
$srcCfg  = Join-Path $ROOT "config.ini"
$destCfg = Join-Path $DEPLOY "config.ini"
if (Test-Path $srcCfg) {
    if (-not (Test-Path $destCfg)) {
        Copy-Item $srcCfg $destCfg
        Write-Host "  Copié : config.ini" -ForegroundColor Green
    } else {
        Write-Host "  config.ini déjà présent (non écrasé)" -ForegroundColor Yellow
    }
}

# ─── Résumé ───────────────────────────────────────────────────────────────────
Write-Header "Résumé"
if ($errors -eq 0) {
    Write-Host "Toutes les applications ont été compilées et déployées." -ForegroundColor Green
} else {
    Write-Host "$errors erreur(s) lors du build. Vérifiez les messages ci-dessus." -ForegroundColor Red
    exit 1
}

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

# ─── Bump de version (uniquement pour un build complet) ───────────────────────
$versionFile = "$ROOT\shared\version.py"
$currentVersionLine = Get-Content $versionFile | Where-Object { $_ -match '__version__' } | Select-Object -First 1
$currentVersion = [regex]::Match($currentVersionLine, '"([^"]+)"').Groups[1].Value

if (-not $App) {
    Write-Host ""
    Write-Host "  Version actuelle : $currentVersion" -ForegroundColor Cyan
    $newVersion = Read-Host "  Nouvelle version (Entree pour garder $currentVersion)"
    if ($newVersion -and $newVersion -ne $currentVersion) {
        if ($newVersion -notmatch '^\d+\.\d+\.\d+$') {
            Write-Host "  Format invalide (attendu : X.Y.Z)" -ForegroundColor Red
            exit 1
        }
        $content = Get-Content $versionFile -Raw
        $content = $content -replace '__version__ = "[^"]+"', "__version__ = `"$newVersion`""
        Set-Content $versionFile -Value $content.TrimEnd() -Encoding UTF8 -NoNewline
        Write-Host "  Version mise a jour : $currentVersion -> $newVersion" -ForegroundColor Green
    } else {
        Write-Host "  Version inchangee : $currentVersion" -ForegroundColor Yellow
    }
    Write-Host ""
}

$SPECS = [ordered]@{
    "Launcher"        = "ems_launcher.spec"
    "Affaire"         = "EMS_Affaire.spec"
    "Bons"            = "EMS_Bons.spec"
    "Parc"            = "EMS_Parc.spec"
    "Garanties"       = "EMS_Garanties.spec"
    "Amelioration"    = "EMS_Amelioration.spec"
    "Pieces"          = "EMS_Pieces.spec"
    "BI"              = "EMS_BI.spec"
    "ConvertisseurPDF" = "EMS_ConvertisseurPDF.spec"
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

# Copier suivi_affaires.html (interface web affaires — ouverte par EMS_Affaire.exe)
$srcHtml  = Join-Path $ROOT "suivi_affaires.html"
$destHtml = Join-Path $DEPLOY "suivi_affaires.html"
if (Test-Path $srcHtml) {
    Copy-Item $srcHtml $destHtml -Force
    Write-Host "  Déployé : suivi_affaires.html" -ForegroundColor Green
}

# ─── Résumé ───────────────────────────────────────────────────────────────────
Write-Header "Résumé"
if ($errors -eq 0) {
    Write-Host "Toutes les applications ont été compilées et déployées." -ForegroundColor Green
} else {
    Write-Host "$errors erreur(s) lors du build. Vérifiez les messages ci-dessus." -ForegroundColor Red
    exit 1
}

# ─── Zippage de EMS_Distribution/ ────────────────────────────────────────────
Write-Header "Création du package de mise à jour"

# Lire la version depuis shared/version.py
$versionLine = Get-Content "$ROOT\shared\version.py" | Where-Object { $_ -match '__version__' } | Select-Object -First 1
$version = [regex]::Match($versionLine, '"([^"]+)"').Groups[1].Value
if (-not $version) { $version = "0.0.0" }

$RELEASES = Join-Path $ROOT "releases"
New-Item -ItemType Directory -Path $RELEASES -Force | Out-Null

$zipName = "EMS_v$version.zip"
$zipPath = Join-Path $RELEASES $zipName

# Supprimer un zip existant de même nom
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

# Zipper le contenu de EMS_Distribution/ (pas le dossier lui-même)
$items = Get-ChildItem -Path $DEPLOY -File | Where-Object { $_.Extension -in '.exe', '.html', '.ini' }
if ($items) {
    Compress-Archive -Path $items.FullName -DestinationPath $zipPath
    $sizeMb = [math]::Round((Get-Item $zipPath).Length / 1MB, 1)
    Write-Host "  Package : $zipName ($sizeMb Mo)" -ForegroundColor Green
    Write-Host "  Chemin  : $zipPath" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Prochaine etape :" -ForegroundColor Cyan
    Write-Host "    1. Copier $zipName sur le serveur (partage ou static/)" -ForegroundColor White
    Write-Host "    2. Editer ems_api\data\updates.json : version=$version, url=<url_du_zip>" -ForegroundColor White
} else {
    Write-Warning "Aucun fichier trouvé dans $DEPLOY - zip non créé."
}

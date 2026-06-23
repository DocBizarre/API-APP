# ============================================================
# EMS - Publication d'une release
# Usage : .\publish_release.ps1
# ============================================================
#
# Ce script :
# 1. Trouve le dernier zip dans releases/
# 2. Le copie dans le dossier static/ du serveur (servi via /static)
# 3. Met a jour updates.json sur le serveur
#
# Pre-requis :
# - .\build.ps1 doit avoir ete lance au prealable
# - Le partage \\EMSVMA001\EMS_install doit etre accessible

# ----- Configuration -----
$SERVER_NAME = "EMSVMA001"
$SERVER_IP   = "192.168.1.10"
$SERVER_PORT = "8765"
$SHARE_PATH  = "\\$SERVER_NAME\EMS_install"
$ROOT        = $PSScriptRoot

function Write-Step { Write-Host ""; Write-Host "===== $args =====" -ForegroundColor Cyan }
function Write-Ok   { Write-Host "  [OK] $args" -ForegroundColor Green }
function Write-Err  { Write-Host "  [ERREUR] $args" -ForegroundColor Red }

# ----- 1. Trouver le dernier zip -----
Write-Step "Recherche du dernier package"

$releasesDir = Join-Path $ROOT "releases"
if (-not (Test-Path $releasesDir)) {
    Write-Err "Dossier releases/ introuvable. Lance d'abord .\build.ps1"
    exit 1
}

$latest = Get-ChildItem -Path $releasesDir -Filter "EMS_v*.zip" |
          Sort-Object LastWriteTime -Descending |
          Select-Object -First 1

if (-not $latest) {
    Write-Err "Aucun zip trouve dans releases/. Lance d'abord .\build.ps1"
    exit 1
}

$version = [regex]::Match($latest.Name, 'EMS_v(.+)\.zip').Groups[1].Value
$sizeMb  = [math]::Round($latest.Length / 1MB, 1)

Write-Ok "Package : $($latest.Name) ($sizeMb Mo)"
Write-Ok "Version : $version"

# ----- 2. Notes de version -----
Write-Host ""
Write-Host "  Notes de version (laisse vide si aucune) :" -ForegroundColor Yellow
$notes = Read-Host "  >"
if (-not $notes) { $notes = "Mise a jour v$version" }

# ----- 3. Verifier l'acces au serveur -----
Write-Step "Verification de l'acces au serveur"

if (-not (Test-Path $SHARE_PATH)) {
    Write-Err "Partage serveur inaccessible : $SHARE_PATH"
    exit 1
}
Write-Ok "Partage accessible"

# ----- 4. Copier le zip dans static/ -----
Write-Step "Copie du package vers le serveur"

$staticDir = "$SHARE_PATH\ems_api\static"
if (-not (Test-Path $staticDir)) {
    New-Item -ItemType Directory -Path $staticDir -Force | Out-Null
    Write-Ok "Dossier static/ cree sur le serveur"
}

# Supprimer les anciens zips pour ne pas saturer le disque
Get-ChildItem -Path $staticDir -Filter "EMS_v*.zip" |
    Where-Object { $_.Name -ne $latest.Name } |
    ForEach-Object {
        Remove-Item $_.FullName -Force
        Write-Host "  Archive supprimee : $($_.Name)" -ForegroundColor Gray
    }

Write-Host "  Copie en cours..." -ForegroundColor Gray
Copy-Item $latest.FullName "$staticDir\$($latest.Name)" -Force
Write-Ok "$($latest.Name) copie"

# ----- 5. Mettre a jour updates.json -----
Write-Step "Mise a jour du manifest"

$url = "http://${SERVER_IP}:${SERVER_PORT}/static/$($latest.Name)"

$manifest = [ordered]@{
    version  = $version
    url      = $url
    notes    = $notes
    required = $false
} | ConvertTo-Json

$manifestPath = "$SHARE_PATH\ems_api\data\updates.json"
Set-Content -Path $manifestPath -Value $manifest -Encoding UTF8

Write-Ok "updates.json mis a jour"

# ----- 6. Verification -----
Write-Step "Verification"

try {
    $r = Invoke-WebRequest "http://${SERVER_IP}:${SERVER_PORT}/updates/latest" -UseBasicParsing -TimeoutSec 5
    $data = $r.Content | ConvertFrom-Json
    if ($data.version -eq $version) {
        Write-Ok "API repond avec la bonne version : $($data.version)"
    } else {
        Write-Host "  [WARN] API repond version $($data.version) au lieu de $version" -ForegroundColor Yellow
        Write-Host "         Le service a peut-etre besoin d'etre redemarre." -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARN] API injoignable pour verification - elle repond peut-etre sur le reseau local uniquement." -ForegroundColor Yellow
}

# ----- Resume -----
Write-Host ""
Write-Host "  ============================================" -ForegroundColor Green
Write-Host "    RELEASE $version PUBLIEE" -ForegroundColor Green
Write-Host "  ============================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Les clients verront le badge de mise a jour" -ForegroundColor Gray
Write-Host "  au prochain demarrage du launcher." -ForegroundColor Gray
Write-Host ""

# ============================================================
# EMS - Push dev -> prod
# Usage : .\push_to_prod.ps1
# ============================================================
#
# Ce script :
# 1. Verifie que tu es dans le bon repertoire
# 2. Sauvegarde la DB de prod (rollback possible)
# 3. Copie le code vers le serveur (sans la DB, sans les logs, sans le cache)
# 4. Redemarre proprement le service sur le serveur
# 5. Verifie que le serveur repond apres redeploiement
#
# Pre-requis :
# - Le partage \\EMSVMA001\EMS_install doit exister et etre accessible en ecriture
# - PSRemoting active sur le serveur (Enable-PSRemoting -Force depuis le serveur)
#   Sinon le redemarrage devra se faire manuellement en RDP

# ----- Configuration (modifiable si necessaire) -----
$DEV_PATH    = "C:\Users\Stagiaire.be\Desktop\APP API"
$SERVER_NAME = "EMSVMA001"
$SERVER_IP   = "192.168.1.10"
$SERVER_PORT = "8765"
$SHARE_PATH  = "\\$SERVER_NAME\EMS_install"

# Couleurs pour la lisibilite
function Write-Step    { Write-Host ""; Write-Host "===== $args =====" -ForegroundColor Cyan }
function Write-Ok      { Write-Host "  [OK] $args" -ForegroundColor Green }
function Write-WarnMsg { Write-Host "  [WARN] $args" -ForegroundColor Yellow }
function Write-ErrMsg  { Write-Host "  [ERREUR] $args" -ForegroundColor Red }

# ----- 0. Verifications prealables -----
Write-Step "Verifications prealables"

if (-not (Test-Path "$DEV_PATH\ems_api\main.py")) {
    Write-ErrMsg "Repertoire dev introuvable : $DEV_PATH"
    Write-ErrMsg "Modifie la variable DEV_PATH en haut du script."
    exit 1
}
Write-Ok "Repertoire dev OK"

if (-not (Test-Path $SHARE_PATH)) {
    Write-ErrMsg "Partage serveur inaccessible : $SHARE_PATH"
    Write-ErrMsg "Verifie que le partage EMS_install existe sur le serveur."
    exit 1
}
Write-Ok "Partage serveur accessible"

# Test que le serveur repond actuellement (pour pouvoir comparer apres)
$serverWasResponding = $false
try {
    $null = Invoke-WebRequest "http://${SERVER_IP}:$SERVER_PORT/health" -UseBasicParsing -TimeoutSec 5
    $serverWasResponding = $true
    Write-Ok "Serveur actuel repond"
} catch {
    Write-WarnMsg "Serveur actuel ne repond pas (probablement deja casse, on continue)"
}

# ----- 1. Sauvegarde DB prod -----
Write-Step "Sauvegarde de la DB de prod"

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$dbBackupName = "ems.db.backup_$timestamp"

try {
    Copy-Item "$SHARE_PATH\ems_api\data\ems.db" "$SHARE_PATH\ems_api\data\$dbBackupName" -ErrorAction Stop
    Write-Ok "DB sauvegardee : $dbBackupName"
} catch {
    Write-ErrMsg "Echec sauvegarde DB : $_"
    $reponse = Read-Host "Continuer sans sauvegarde ? (o/N)"
    if ($reponse -ne "o") { exit 1 }
}

# ----- 2. Copie du code -----
Write-Step "Copie du code dev vers prod"

$folders = @("ems_api", "shared", "ems_client")
foreach ($folder in $folders) {
    Write-Host "  Copie de $folder ..."
    $src = "$DEV_PATH\$folder"
    $dst = "$SHARE_PATH\$folder"
    
    if (-not (Test-Path $src)) {
        Write-WarnMsg "Dossier dev introuvable : $src (ignore)"
        continue
    }
    
    # /MIR = mirror (synchro), /XD exclut les dossiers cache,
    # /XF exclut les bases et logs (ne JAMAIS ecraser la DB de prod)
    $result = robocopy $src $dst /MIR /XD __pycache__ .venv /XF *.db *.log *.db-journal /NJH /NJS /NDL /NFL /NC /NS
    
    # Robocopy renvoie 0-7 = succes, 8+ = erreur
    if ($LASTEXITCODE -ge 8) {
        Write-ErrMsg "Echec copie $folder (exit $LASTEXITCODE)"
        exit 1
    }
}
Write-Ok "Code copie"

# ----- 3. Redemarrage du service -----
Write-Step "Redemarrage du service sur le serveur"

$redemarre = $false
try {
    Invoke-Command -ComputerName $SERVER_NAME -ErrorAction Stop -ScriptBlock {
        # Tuer tous les python existants
        Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 2
        
        # Vider le cache Python (pour ne pas executer du vieux bytecode)
        Get-ChildItem -Path "C:\EMS" -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force
        
        # Relancer la tache
        schtasks /run /tn "EMS_API" | Out-Null
    }
    $redemarre = $true
    Write-Ok "Service redemarre via PSRemoting"
} catch {
    Write-WarnMsg "PSRemoting indisponible : $_"
    Write-Host ""
    Write-Host "  Connecte-toi en RDP au serveur et lance manuellement :" -ForegroundColor Yellow
    Write-Host '    Get-Process python | Stop-Process -Force' -ForegroundColor White
    Write-Host '    Get-ChildItem -Path C:\EMS -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force' -ForegroundColor White
    Write-Host '    schtasks /run /tn "EMS_API"' -ForegroundColor White
    Write-Host ""
    Read-Host "Appuie sur Entree quand le service a ete redemarre"
}

# ----- 4. Verification que le serveur repond apres redeploiement -----
Write-Step "Verification du serveur apres redeploiement"

Start-Sleep -Seconds 5  # Laisse le temps a uvicorn de demarrer

$serverOK = $false
$tentatives = 0
while ($tentatives -lt 6 -and -not $serverOK) {
    $tentatives++
    try {
        $null = Invoke-WebRequest "http://${SERVER_IP}:$SERVER_PORT/health" -UseBasicParsing -TimeoutSec 5
        $serverOK = $true
    } catch {
        Write-Host "  Tentative $tentatives/6 : pas encore pret, attente 3s..." -ForegroundColor Gray
        Start-Sleep -Seconds 3
    }
}

if ($serverOK) {
    Write-Ok "Serveur OK (repond sur /health)"
    
    # Test endpoint critique : document.html (pour verifier le bug d'import resolu)
    try {
        $inv = (Invoke-WebRequest "http://${SERVER_IP}:$SERVER_PORT/interventions" -UseBasicParsing -TimeoutSec 10 | ConvertFrom-Json)
        if ($inv.Count -gt 0) {
            $id = $inv[0].id
            $r = Invoke-WebRequest "http://${SERVER_IP}:$SERVER_PORT/interventions/$id/document.html" -UseBasicParsing -TimeoutSec 30
            $ctype = $r.Headers['Content-Type']
            if ($ctype -like "*text/html*") {
                Write-Ok "Endpoint document.html OK (Content-Type: $ctype)"
            } else {
                Write-WarnMsg "Endpoint document.html renvoie un mauvais Content-Type : $ctype"
            }
        }
    } catch {
        Write-WarnMsg "Test document.html echoue (peut etre normal si pas d'intervention) : $_"
    }
    
    Write-Host ""
    Write-Host "  ============================================" -ForegroundColor Green
    Write-Host "    DEPLOIEMENT REUSSI" -ForegroundColor Green
    Write-Host "  ============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  DB de prod sauvegardee : $dbBackupName" -ForegroundColor Gray
    Write-Host "  Pour rollback DB :" -ForegroundColor Gray
    Write-Host "    Copy-Item '$SHARE_PATH\ems_api\data\$dbBackupName' '$SHARE_PATH\ems_api\data\ems.db' -Force" -ForegroundColor Gray
    Write-Host ""
    exit 0
    
} else {
    Write-ErrMsg "Serveur ne repond PAS apres redeploiement !"
    Write-Host ""
    Write-Host "  Verifications a faire :" -ForegroundColor Yellow
    Write-Host "    1. RDP sur le serveur" -ForegroundColor White
    Write-Host "    2. Lancer manuellement : C:\EMS\.venv\Scripts\python.exe -m uvicorn ems_api.main:app --port 8765" -ForegroundColor White
    Write-Host "    3. Lire l'erreur affichee" -ForegroundColor White
    Write-Host ""
    Write-Host "  Pour rollback de la DB seulement :" -ForegroundColor Yellow
    Write-Host "    Copy-Item '$SHARE_PATH\ems_api\data\$dbBackupName' '$SHARE_PATH\ems_api\data\ems.db' -Force" -ForegroundColor White
    Write-Host ""
    exit 1
}

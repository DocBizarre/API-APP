"""
═══════════════════════════════════════════════════════════════════════════════
  Installation de l'API EMS comme service Windows (NSSM)
═══════════════════════════════════════════════════════════════════════════════

Permet de faire tourner l'API EMS en arrière-plan, au démarrage du PC,
sans fenêtre noire visible. Nécessite NSSM (Non-Sucking Service Manager).

PRÉREQUIS :
  1. Télécharger NSSM : https://nssm.cc/download
  2. Extraire nssm.exe dans C:/Windows/System32/
     (ou ajuster le chemin dans ce script)
  3. Avoir Python avec ems_api installé

INSTALLATION :
    python install_service.py install

DÉSINSTALLATION :
    python install_service.py remove

GESTION :
    net start EMS_API
    net stop EMS_API

═══════════════════════════════════════════════════════════════════════════════
"""
import sys
import subprocess
from pathlib import Path

NOM_SERVICE = "EMS_API"
HERE = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable
PORT = "8765"


def run(cmd):
    print(">", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.stdout: print(r.stdout)
    if r.stderr: print(r.stderr, file=sys.stderr)
    return r.returncode


def install():
    # Vérifier que nssm est dispo
    r = subprocess.run(["where", "nssm"], capture_output=True, text=True)
    if r.returncode != 0:
        print("⚠ nssm.exe introuvable dans le PATH.")
        print("  Téléchargez-le depuis https://nssm.cc/download")
        print("  et placez nssm.exe dans C:\\Windows\\System32\\")
        return 1

    # Créer le service
    run(["nssm", "install", NOM_SERVICE,
         PYTHON_EXE, "-m", "uvicorn",
         "ems_api.main:app", "--host", "0.0.0.0", "--port", PORT])
    # Définir le dossier de travail
    run(["nssm", "set", NOM_SERVICE, "AppDirectory", str(HERE)])
    # Description
    run(["nssm", "set", NOM_SERVICE, "Description",
         "EMS API — backend des applications Emeraude Moteurs Systèmes"])
    # Démarrage automatique
    run(["nssm", "set", NOM_SERVICE, "Start", "SERVICE_AUTO_START"])
    # Redirection des logs
    logs = HERE / "logs"
    logs.mkdir(exist_ok=True)
    run(["nssm", "set", NOM_SERVICE, "AppStdout", str(logs / "api.log")])
    run(["nssm", "set", NOM_SERVICE, "AppStderr", str(logs / "api-err.log")])
    # Rotation des logs
    run(["nssm", "set", NOM_SERVICE, "AppRotateFiles", "1"])
    run(["nssm", "set", NOM_SERVICE, "AppRotateBytes", "10485760"])  # 10 Mo

    print(f"\n✅ Service {NOM_SERVICE} installé.")
    print(f"   Démarrer : net start {NOM_SERVICE}")
    print(f"   Logs     : {logs}")


def remove():
    run(["nssm", "stop", NOM_SERVICE])
    run(["nssm", "remove", NOM_SERVICE, "confirm"])
    print(f"✅ Service {NOM_SERVICE} désinstallé.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "install":
        install()
    elif cmd == "remove":
        remove()
    else:
        print(f"Commande inconnue : {cmd}. Utiliser install ou remove.")
        sys.exit(1)

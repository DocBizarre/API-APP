"""
Module de mise à jour automatique EMS.

Flux :
  1. check_for_update(api_url, current_version) → dict info ou None
  2. download_and_apply(info, install_dir, callbacks…)
     → télécharge le zip, extrait dans %TEMP%, écrit un script batch
       qui remplace les fichiers après la fermeture du launcher.
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import threading
import zipfile
from pathlib import Path
from typing import Callable, Optional

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False


# ─── Comparaison de versions ──────────────────────────────────────────────────

def _ver(s: str) -> tuple:
    try:
        return tuple(int(x) for x in str(s).strip().split("."))
    except Exception:
        return (0,)


# ─── Vérification ─────────────────────────────────────────────────────────────

def check_for_update(api_url: str, current_version: str) -> Optional[dict]:
    """
    Interroge GET {api_url}/updates/latest.
    Retourne le dict info si la version distante est plus récente, sinon None.
    Échoue silencieusement (timeout, serveur absent, etc.).
    """
    if not _HAS_REQUESTS:
        return None
    try:
        r = _requests.get(f"{api_url.rstrip('/')}/updates/latest", timeout=5)
        if not r.ok:
            return None
        data = r.json()
        if _ver(data.get("version", "0")) > _ver(current_version):
            return data
    except Exception:
        pass
    return None


# ─── Téléchargement & application ────────────────────────────────────────────

def download_and_apply(
    update_info: dict,
    install_dir: Path,
    on_progress: Optional[Callable[[str, int], None]] = None,
    on_done: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Lance le téléchargement dans un thread background.

    Callbacks (appelés depuis le thread background) :
      on_progress(message, pct)  pct ∈ [0-100] ou -1 si inconnu
      on_done(batch_path)        chemin du .bat prêt à être lancé
      on_error(message)
    """
    threading.Thread(
        target=_worker,
        args=(update_info, install_dir, on_progress, on_done, on_error),
        daemon=True,
    ).start()


def _worker(update_info, install_dir, on_progress, on_done, on_error):
    url = update_info.get("url", "").strip()
    version = update_info.get("version", "inconnue")

    if not url:
        if on_error:
            on_error("Aucune URL de téléchargement n'est configurée dans le manifest.")
        return

    if not _HAS_REQUESTS:
        if on_error:
            on_error("Module 'requests' indisponible — impossible de télécharger.")
        return

    tmp_root = Path(tempfile.gettempdir())
    tmp_zip = tmp_root / f"ems_update_{version}.zip"
    tmp_dir = tmp_root / f"ems_update_{version}"

    try:
        # ── Téléchargement ────────────────────────────────────────────────────
        if on_progress:
            on_progress("Connexion au serveur…", -1)

        r = _requests.get(url, stream=True, timeout=120)
        r.raise_for_status()

        total = int(r.headers.get("content-length", 0))
        downloaded = 0
        tmp_zip.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_zip, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if on_progress:
                        pct = int(downloaded * 100 / total) if total else -1
                        size_mb = downloaded / 1_048_576
                        on_progress(f"Téléchargement… {size_mb:.1f} Mo", pct)

        # ── Extraction ────────────────────────────────────────────────────────
        if on_progress:
            on_progress("Extraction de l'archive…", -1)

        if tmp_dir.exists():
            import shutil
            shutil.rmtree(tmp_dir)

        with zipfile.ZipFile(tmp_zip, "r") as zf:
            zf.extractall(tmp_dir)

        tmp_zip.unlink(missing_ok=True)

        # ── Écriture du script d'application ─────────────────────────────────
        launcher_exe = install_dir / "EMS_Launcher.exe"
        batch_path = tmp_root / "ems_apply_update.bat"

        script = (
            "@echo off\r\n"
            "chcp 65001 > nul\r\n"
            "echo Mise a jour EMS en cours, veuillez patienter...\r\n"
            "timeout /t 3 /nobreak > nul\r\n"
            f"xcopy /E /Y /I \"{tmp_dir}\\*\" \"{install_dir}\\\"\r\n"
            "if %ERRORLEVEL% neq 0 (\r\n"
            "    echo ERREUR lors de la copie des fichiers.\r\n"
            "    pause\r\n"
            "    exit /b 1\r\n"
            ")\r\n"
            f"rmdir /S /Q \"{tmp_dir}\"\r\n"
            f"start \"\" \"{launcher_exe}\"\r\n"
            "del \"%~f0\"\r\n"
        )
        batch_path.write_text(script, encoding="utf-8")

        if on_done:
            on_done(str(batch_path))

    except Exception as exc:
        tmp_zip.unlink(missing_ok=True)
        if on_error:
            on_error(str(exc))


def launch_batch_and_quit(batch_path: str, quit_callback: Callable) -> None:
    """
    Lance le script d'application en arrière-plan puis ferme l'application.
    Appeler depuis le thread principal (Tkinter).
    """
    import subprocess
    subprocess.Popen(
        ["cmd.exe", "/c", batch_path],
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    quit_callback()

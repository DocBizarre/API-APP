#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMS – Suivi d'Affaires  (lanceur web autonome).

Le processus reste vivant après l'ouverture du navigateur afin de servir
les requêtes locales (ouverture de dossiers côté client).
Il s'éteint automatiquement quand le navigateur est fermé (via heartbeat).
"""

import json
import os
import re
import subprocess
import sys
import threading
import time
import webbrowser
from configparser import ConfigParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# Timestamp du dernier heartbeat reçu depuis le navigateur.
# Initialisé à l'instant courant pour laisser le temps à la page de charger.
_last_beat: float = 0.0
_server: HTTPServer | None = None

# Délai (secondes) sans heartbeat avant extinction automatique.
_BEAT_TIMEOUT = 20
# Intervalle de vérification du watchdog.
_WATCHDOG_INTERVAL = 5

# Groupe AD (ex. "DOMAINE\EMS-Commercial") autorisé sur COMMERCIAL, et
# trustee(s) gardant le contrôle total (IT/admin) — lus depuis config.ini.
_COMMERCIAL_GROUP: str = ""
_COMMERCIAL_ADMINS: str = "BUILTIN\\Administrators"


def _read_config():
    """Retourne (api_url, dossiers_root, commercial_group, commercial_admins) depuis config.ini."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent.parent
    for ini in (base / "config.ini", Path(__file__).resolve().parent.parent / "config.ini"):
        if ini.is_file():
            try:
                cfg = ConfigParser()
                cfg.read(ini, encoding="utf-8")
                url = cfg.get("server", "url", fallback="").strip()
                root = cfg.get("files", "dossiers_root", fallback="").strip()
                group = cfg.get("files", "commercial_group", fallback="").strip()
                admins = cfg.get("files", "commercial_admins", fallback="").strip() or "BUILTIN\\Administrators"
                if url:
                    return url.rstrip("/"), root, group, admins
            except Exception:
                continue
    return "http://localhost:8765", "", "", "BUILTIN\\Administrators"


_FOCUS_FOLDER_PS = r"""
$sh = New-Object -ComObject Shell.Application
$target = '__TARGET__'
$win = $sh.Windows() | Where-Object { $_.Document.Folder.Self.Path -ieq $target } | Select-Object -First 1
if (-not $win) {
    $sh.Open($target)
    Start-Sleep -Milliseconds 500
    $win = $sh.Windows() | Where-Object { $_.Document.Folder.Self.Path -ieq $target } | Select-Object -First 1
}
if ($win) {
    $hwnd = [IntPtr]$win.HWND
    Add-Type -Name Win32Focus -Namespace EMS -MemberDefinition '
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);
        [DllImport("user32.dll")] public static extern bool AttachThreadInput(uint idAttach, uint idAttachTo, bool fAttach);
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
        [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr hWnd);
        [DllImport("kernel32.dll")] public static extern uint GetCurrentThreadId();
    '
    $fg = [EMS.Win32Focus]::GetForegroundWindow()
    $dummy = [uint32]0
    $fgThread = [EMS.Win32Focus]::GetWindowThreadProcessId($fg, [ref]$dummy)
    $curThread = [EMS.Win32Focus]::GetCurrentThreadId()
    [EMS.Win32Focus]::AttachThreadInput($fgThread, $curThread, $true) | Out-Null
    [EMS.Win32Focus]::ShowWindow($hwnd, 9) | Out-Null
    [EMS.Win32Focus]::BringWindowToTop($hwnd) | Out-Null
    [EMS.Win32Focus]::SetForegroundWindow($hwnd) | Out-Null
    [EMS.Win32Focus]::AttachThreadInput($fgThread, $curThread, $false) | Out-Null
}
"""


ARBORESCENCE = {
    "COMMERCIAL": [],
    "ACHAT": ["FOURNISSEURS", "NOMENCLATURES"],
    "TECHNIQUE": [
        "SPECIFICATIONS",
        "ETUDE ET PLANS",
        "FABRICATION - MONTAGE",
        "ESSAI USINE",
        "PHOTO ATELIER",
    ],
    "QUALITE - CERTIFICATION": [],
}


def _restrict_commercial_access(folder: Path) -> None:
    """Casse l'héritage NTFS sur COMMERCIAL et le restreint au groupe AD configuré.

    Sans groupe configuré (_COMMERCIAL_GROUP vide), ne fait rien : le dossier
    reste ouvert comme le reste de l'arborescence.
    """
    if sys.platform != "win32" or not _COMMERCIAL_GROUP:
        return
    try:
        subprocess.run(["icacls", str(folder), "/inheritance:r"],
                        capture_output=True, timeout=10, check=False)
        grants = [f"{_COMMERCIAL_GROUP}:(OI)(CI)M"]
        grants += [f"{a.strip()}:(OI)(CI)F" for a in _COMMERCIAL_ADMINS.split(",") if a.strip()]
        args = ["icacls", str(folder)]
        for g in grants:
            args += ["/grant:r", g]
        subprocess.run(args, capture_output=True, timeout=10, check=False)
    except Exception:
        pass


def _create_arborescence(base: Path) -> None:
    for folder, subfolders in ARBORESCENCE.items():
        d = base / folder
        is_new = not d.exists()
        d.mkdir(parents=True, exist_ok=True)
        for sub in subfolders:
            (d / sub).mkdir(parents=True, exist_ok=True)
        if folder == "COMMERCIAL" and is_new:
            _restrict_commercial_access(d)


def _watchdog():
    """Éteint le serveur si aucun heartbeat reçu depuis _BEAT_TIMEOUT secondes."""
    while True:
        time.sleep(_WATCHDOG_INTERVAL)
        if _server is None:
            break
        if time.monotonic() - _last_beat > _BEAT_TIMEOUT:
            _server.shutdown()
            break


class _LocalHandler(BaseHTTPRequestHandler):
    """Même logique qu'ouvrir_fichier() dans les autres apps EMS."""

    def do_GET(self):
        global _last_beat
        parsed = urlparse(self.path)

        if parsed.path == "/heartbeat":
            _last_beat = time.monotonic()

        elif parsed.path == "/open-folder":
            path = unquote(parse_qs(parsed.query).get("path", [""])[0])
            if path:
                try:
                    p = Path(path)
                    p.mkdir(parents=True, exist_ok=True)
                    _create_arborescence(p)
                    if sys.platform == "win32":
                        # Shell.Application.Open() ouvre Explorer, mais Windows ne lui
                        # donne pas le focus (protection anti-vol de focus) car l'appel
                        # vient d'un process qui n'est pas au premier plan. On force donc
                        # ensuite la fenêtre au premier plan via AttachThreadInput, qui
                        # contourne cette protection.
                        path_ps = str(p).replace("'", "''")
                        script = _FOCUS_FOLDER_PS.replace("__TARGET__", path_ps)
                        subprocess.Popen(
                            ["powershell", "-NoProfile", "-NonInteractive",
                             "-WindowStyle", "Hidden", "-Command", script],
                            creationflags=0x08000000,  # CREATE_NO_WINDOW
                        )
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", str(p)])
                    else:
                        subprocess.Popen(["xdg-open", str(p)])
                except Exception:
                    pass

        elif parsed.path == "/ensure-arborescence":
            path = unquote(parse_qs(parsed.query).get("path", [""])[0])
            if path:
                try:
                    p = Path(path)
                    p.mkdir(parents=True, exist_ok=True)
                    _create_arborescence(p)
                except Exception:
                    pass

        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def log_message(self, *args):
        pass


def main():
    global _server, _last_beat, _COMMERCIAL_GROUP, _COMMERCIAL_ADMINS

    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent

    api_url, dossiers_root, _COMMERCIAL_GROUP, _COMMERCIAL_ADMINS = _read_config()

    # Lier le serveur local sur un port libre avant de patcher le HTML.
    _server = HTTPServer(("127.0.0.1", 0), _LocalHandler)
    local_port = _server.server_address[1]

    html = base / "suivi_affaires.html"

    # Windows strip les query params sur file://, on patche directement le HTML.
    try:
        content = html.read_text(encoding="utf-8")
        content = re.sub(
            r"\|\| 'http://[^']+'",
            f"|| '{api_url}'",
            content,
        )
        content = re.sub(
            r"const LOCAL_PORT = \d+;",
            f"const LOCAL_PORT = {local_port};",
            content,
        )
        content = re.sub(
            r"const DOSSIERS_ROOT = (?:'[^']*'|\"[^\"]*\");",
            f"const DOSSIERS_ROOT = {json.dumps(dossiers_root)};",
            content,
        )
        html.write_text(content, encoding="utf-8")
    except Exception:
        pass

    webbrowser.open(html.as_uri())

    # Initialiser le beat APRÈS l'ouverture du navigateur pour lui laisser
    # le temps de charger la page et d'envoyer le premier heartbeat.
    _last_beat = time.monotonic()

    # Watchdog daemon : éteint le serveur si le navigateur est fermé.
    threading.Thread(target=_watchdog, daemon=True).start()

    # serve_forever() retourne quand _server.shutdown() est appelé.
    _server.serve_forever()


if __name__ == "__main__":
    main()

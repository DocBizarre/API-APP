#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMS – Suivi d'Affaires  (lanceur web autonome).

Le processus reste vivant après l'ouverture du navigateur afin de servir
les requêtes locales (ouverture de dossiers côté client).
"""

import json
import os
import sys
import webbrowser
from configparser import ConfigParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote


def _read_config():
    """Retourne (api_url, dossiers_root) depuis config.ini."""
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent.parent
    for ini in (base / "config.ini", Path(__file__).resolve().parent.parent / "config.ini"):
        if ini.is_file():
            try:
                cfg = ConfigParser()
                cfg.read(ini, encoding="utf-8")
                url = cfg.get("server", "url", fallback="").strip()
                root = cfg.get("files", "dossiers_root", fallback="").strip()
                if url:
                    return url.rstrip("/"), root
            except Exception:
                continue
    return "http://localhost:8765", ""


class _LocalHandler(BaseHTTPRequestHandler):
    """Même logique qu'ouvrir_fichier() dans les autres apps EMS."""

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/open-folder":
            path = unquote(parse_qs(parsed.query).get("path", [""])[0])
            if path:
                import subprocess
                Path(path).mkdir(parents=True, exist_ok=True)  # même logique que les autres apps
                if sys.platform == "win32":
                    subprocess.Popen(["explorer", path])
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", path])
                else:
                    subprocess.Popen(["xdg-open", path])
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
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent

    api_url, dossiers_root = _read_config()

    # Lier le serveur local sur un port libre avant de patcher le HTML.
    server = HTTPServer(("127.0.0.1", 0), _LocalHandler)
    local_port = server.server_address[1]

    html = base / "suivi_affaires.html"

    # Windows strip les query params sur file://, on patche directement le HTML.
    try:
        content = html.read_text(encoding="utf-8")
        content = content.replace(
            "|| 'http://localhost:8765'",
            f"|| '{api_url}'"
        ).replace(
            "const LOCAL_PORT = 0;",
            f"const LOCAL_PORT = {local_port};"
        ).replace(
            "const DOSSIERS_ROOT = '';",
            f"const DOSSIERS_ROOT = {json.dumps(dossiers_root)};"
        )
        html.write_text(content, encoding="utf-8")
    except Exception:
        pass

    webbrowser.open(html.as_uri())

    # Bloquer le processus pour garder le serveur local en vie.
    # (Un thread daemon serait tué dès la fin de main().)
    server.serve_forever()


if __name__ == "__main__":
    main()

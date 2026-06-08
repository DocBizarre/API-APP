#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMS - Outil Business Intelligence (version API).

Recupere la base SQLite depuis l'API EMS, l'encode en base64 et l'injecte
dans le HTML du dashboard.

Peut etre lance :
  - via ems_launcher.py  (automatique)
  - directement :  python app_bi.py
"""

import base64
import http.server
import socket
import sys
import threading
import time
import webbrowser
from configparser import ConfigParser
from pathlib import Path

# urllib pour requete HTTP sans dependances externes
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

# Constantes
_HERE       = Path(__file__).resolve().parent
_BI_HTML    = _HERE / "ems_bi.html"
_PORT_START = 17430
_TITLE      = "EMS - Business Intelligence"
_DEFAULT_API = "http://192.168.1.47:8765"


def _read_api_url() -> str:
    """Lit l'URL de l'API depuis config.ini ou retourne defaut."""
    # En .exe (PyInstaller), le config.ini est a cote de l'exe
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
    else:
        base = _HERE.parent  # racine du projet (au-dessus de BI_app/)

    candidats = [
        base / "config.ini",
        _HERE / "config.ini",
    ]
    for cfg_path in candidats:
        if cfg_path.is_file():
            try:
                cp = ConfigParser()
                cp.read(cfg_path, encoding="utf-8")
                url = cp.get("server", "url", fallback="").strip()
                if url:
                    return url.rstrip("/")
            except Exception:
                pass
    return _DEFAULT_API


def telecharger_db_via_api() -> bytes | None:
    """Recupere le fichier ems.db depuis l'API.
    
    Retourne les bytes du fichier, ou None en cas d'echec.
    """
    api_url = _read_api_url()
    full_url = f"{api_url}/admin/export-db"
    print(f"[EMS BI] Recuperation de la base depuis : {full_url}")
    try:
        with urlopen(full_url, timeout=30) as resp:
            data = resp.read()
            print(f"[EMS BI] Base recuperee : {len(data) / 1024:.1f} Ko")
            return data
    except HTTPError as e:
        print(f"[EMS BI] HTTPError : {e.code} {e.reason}")
    except URLError as e:
        print(f"[EMS BI] URLError : {e.reason}")
    except Exception as e:
        print(f"[EMS BI] Erreur : {e}")
    return None


def generer_html(db_bytes: bytes | None) -> str:
    """Lit ems_bi.html et insere un bloc <script> avec la DB encodee en base64
    juste avant la fermeture </head>.
    Si db_bytes est None, retourne le HTML brut (mode upload manuel)."""
    if not _BI_HTML.is_file():
        raise FileNotFoundError(
            f"Fichier ems_bi.html introuvable : {_BI_HTML}\n"
            "Placez app_bi.py dans le meme dossier que ems_bi.html.")

    html = _BI_HTML.read_text(encoding="utf-8")

    if db_bytes is None:
        return html

    db_b64 = base64.b64encode(db_bytes).decode("ascii")
    inject = (
        '\n<script>\n'
        '// Injection automatique par app_bi.py (depuis l\'API EMS)\n'
        f'window.EMS_DB_B64  = "{db_b64}";\n'
        'window.EMS_DB_NAME = "ems.db (API)";\n'
        '</script>\n'
    )

    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        html = inject + html
    return html


def trouver_port(debut: int = _PORT_START) -> int:
    for port in range(debut, debut + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError(f"Aucun port disponible entre {debut} et {debut + 20}.")


def lancer_serveur(html_content: str, port: int) -> http.server.HTTPServer:
    """Sert le HTML genere sur http://127.0.0.1:{port}/"""
    content_bytes = html_content.encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content_bytes)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content_bytes)
            else:
                self.send_response(204)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def afficher_fenetre_statut(db_ok: bool, port: int, api_url: str):
    """Petite fenetre Tkinter indiquant le statut + bouton recharger."""
    try:
        import tkinter as tk
    except ImportError:
        return

    C = {
        "bg":     "#f5f7fa",
        "header": "#002b5c",
        "accent": "#c62828",
        "text":   "#1a2332",
        "muted":  "#6b7785",
        "green":  "#1e7e3e",
        "blue":   "#0056b3",
    }
    url = f"http://127.0.0.1:{port}/"

    root = tk.Tk()
    root.title(_TITLE)
    root.geometry("470x270")
    root.resizable(False, False)
    root.configure(bg=C["bg"])

    head = tk.Frame(root, bg=C["header"], height=70)
    head.pack(fill="x")
    head.pack_propagate(False)
    tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
    hin = tk.Frame(head, bg=C["header"])
    hin.pack(side="left", fill="both", expand=True, padx=18)
    tk.Label(hin, text="Business Intelligence",
             font=("Segoe UI", 14, "bold"),
             bg=C["header"], fg="white").pack(anchor="w", pady=(14, 0))
    tk.Label(hin, text="Emeraude Moteurs Systemes",
             font=("Segoe UI", 9),
             bg=C["header"], fg="#aac4e8").pack(anchor="w")

    body = tk.Frame(root, bg=C["bg"])
    body.pack(fill="both", expand=True, padx=22, pady=14)

    # Statut API
    tk.Label(body, text="API EMS :", font=("Segoe UI", 9, "bold"),
             bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    api_txt = f"OK - {api_url}" if db_ok else f"INJOIGNABLE - {api_url}"
    api_col = C["green"] if db_ok else C["accent"]
    tk.Label(body, text=api_txt, font=("Segoe UI", 9),
             bg=C["bg"], fg=api_col, wraplength=420,
             justify="left").pack(anchor="w", pady=(0, 10))

    tk.Label(body, text="Interface :", font=("Segoe UI", 9, "bold"),
             bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    tk.Label(body, text=url, font=("Consolas", 9),
             bg=C["bg"], fg=C["blue"]).pack(anchor="w", pady=(0, 14))

    btns = tk.Frame(body, bg=C["bg"])
    btns.pack(fill="x")

    def rouvrir():
        webbrowser.open(url)

    def fermer():
        root.destroy()

    tk.Button(btns, text="Rouvrir dans le navigateur",
              font=("Segoe UI", 9, "bold"),
              bg=C["blue"], fg="white", relief="flat", bd=0,
              padx=12, pady=6, cursor="hand2",
              activebackground="#003d80", activeforeground="white",
              command=rouvrir).pack(side="left", padx=(0, 8))

    tk.Button(btns, text="Fermer",
              font=("Segoe UI", 9),
              bg=C["muted"], fg="white", relief="flat", bd=0,
              padx=12, pady=6, cursor="hand2",
              activebackground="#525c66", activeforeground="white",
              command=fermer).pack(side="left")

    root.mainloop()


def main():
    api_url = _read_api_url()
    print(f"[EMS BI] API cible : {api_url}")

    # 1. Recuperer la DB depuis l'API
    db_bytes = telecharger_db_via_api()
    db_ok = db_bytes is not None
    if not db_ok:
        print("[EMS BI] AVERTISSEMENT : API injoignable, "
              "interface de chargement manuel.")

    # 2. Generer le HTML
    try:
        html = generer_html(db_bytes)
    except FileNotFoundError as e:
        print(f"[EMS BI] ERREUR : {e}")
        try:
            import tkinter.messagebox as mb
            mb.showerror("EMS - BI", str(e))
        except Exception:
            pass
        sys.exit(1)

    # 3. Demarrer le serveur HTTP local
    try:
        port   = trouver_port()
        server = lancer_serveur(html, port)
        url    = f"http://127.0.0.1:{port}/"
        print(f"[EMS BI] Serveur demarre sur {url}")
    except OSError as e:
        print(f"[EMS BI] ERREUR reseau : {e}")
        sys.exit(1)

    # 4. Ouvrir le navigateur
    time.sleep(0.3)
    webbrowser.open(url)
    print(f"[EMS BI] Navigateur ouvert -> {url}")

    # 5. Fenetre statut (bloquante)
    afficher_fenetre_statut(db_ok, port, api_url)

    # 6. Arret propre
    server.shutdown()
    print("[EMS BI] Serveur arrete.")


if __name__ == "__main__":
    main()

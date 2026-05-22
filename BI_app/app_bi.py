#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMS – Outil Business Intelligence
Lanceur Python : injecte la base de données dans le HTML et ouvre le navigateur.

Peut être lancé :
  • via ems_launcher.py  (automatique)
  • directement :  python app_bi.py

La base de données est recherchée dans les emplacements habituels du projet EMS.
"""

import base64
import http.server
import os
import re
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

# ─── Constantes ───────────────────────────────────────────────────────────────
_HERE       = Path(__file__).resolve().parent
_BI_HTML    = _HERE / "ems_bi.html"          # HTML de l'outil BI (même dossier)
_PORT_START = 17430                            # Port de départ (change si occupé)
_TITLE      = "EMS – Business Intelligence"

# Chemins candidats pour la base SQLite (du plus probable au moins probable)
_DB_CANDIDATES = [
    _HERE          / "ems_project" / "data" / "ems.db",
    _HERE          / "data"        / "ems.db",
    _HERE.parent   / "ems_project" / "data" / "ems.db",
    _HERE.parent   / "data"        / "ems.db",
    _HERE          / "ems.db",
    _HERE.parent   / "ems.db",
]


# ─── Recherche de la DB ───────────────────────────────────────────────────────
def trouver_db() -> Path | None:
    for p in _DB_CANDIDATES:
        if p.is_file():
            return p
    return None


# ─── Injection base64 dans le HTML ────────────────────────────────────────────
def generer_html(db_path: Path | None) -> str:
    """
    Lit ems_bi.html et insère un bloc <script> avec la DB encodée en base64
    juste avant la fermeture </head>.
    Si db_path est None, retourne le HTML brut sans injection.
    """
    if not _BI_HTML.is_file():
        raise FileNotFoundError(
            f"Fichier ems_bi.html introuvable : {_BI_HTML}\n"
            "Placez app_bi.py dans le même dossier que ems_bi.html.")

    html = _BI_HTML.read_text(encoding="utf-8")

    if db_path is None:
        # Pas de DB : on laisse l'interface de chargement manuel
        return html

    # Lire et encoder la DB
    db_bytes  = db_path.read_bytes()
    db_b64    = base64.b64encode(db_bytes).decode("ascii")
    db_name   = db_path.name

    inject = (
        f'\n<script>\n'
        f'// ── Injection automatique par app_bi.py ──\n'
        f'window.EMS_DB_B64  = "{db_b64}";\n'
        f'window.EMS_DB_NAME = "{db_name}";\n'
        f'</script>\n'
    )

    # Insérer juste avant </head>
    if "</head>" in html:
        html = html.replace("</head>", inject + "</head>", 1)
    else:
        # Fallback : avant le premier <script>
        html = inject + html

    return html


# ─── Serveur HTTP local ────────────────────────────────────────────────────────
def trouver_port(debut: int = _PORT_START) -> int:
    for port in range(debut, debut + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError("Aucun port disponible entre "
                  f"{debut} et {debut + 20}.")


def lancer_serveur(html_content: str, port: int) -> http.server.HTTPServer:
    """
    Crée un handler HTTP minimaliste qui sert le HTML généré sur /.
    Les autres requêtes (wasm, favicons…) sont ignorées avec 204.
    """
    content_bytes = html_content.encode("utf-8")

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content_bytes)))
                # Pas de cache : chaque rechargement lit la DB fraîche
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(content_bytes)
            else:
                # sql-wasm.wasm et autres ressources locales : laisser passer
                self.send_response(204)
                self.end_headers()

        def log_message(self, fmt, *args):
            pass  # Silence les logs HTTP dans la console

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ─── Interface Tkinter de statut (optionnelle) ────────────────────────────────
def afficher_fenetre_statut(db_path: Path | None, port: int):
    """
    Petite fenêtre Tkinter indiquant que le BI est ouvert et permettant
    de le rouvrir ou de l'arrêter.  N'apparaît que si Tkinter est dispo.
    """
    try:
        import tkinter as tk
    except ImportError:
        return  # Tkinter non dispo : mode silencieux

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
    root.geometry("420x230")
    root.resizable(False, False)
    root.configure(bg=C["bg"])

    # En-tête
    head = tk.Frame(root, bg=C["header"], height=70)
    head.pack(fill="x")
    head.pack_propagate(False)
    tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
    hin = tk.Frame(head, bg=C["header"])
    hin.pack(side="left", fill="both", expand=True, padx=18)
    tk.Label(hin, text="📈 Business Intelligence",
             font=("Segoe UI", 14, "bold"),
             bg=C["header"], fg="white").pack(anchor="w", pady=(14, 0))
    tk.Label(hin, text="Emeraude Moteurs Systèmes",
             font=("Segoe UI", 9),
             bg=C["header"], fg="#aac4e8").pack(anchor="w")

    body = tk.Frame(root, bg=C["bg"])
    body.pack(fill="both", expand=True, padx=22, pady=14)

    # DB chargée
    db_txt = str(db_path) if db_path else "⚠ Base non trouvée — chargez-la manuellement"
    db_col = C["text"] if db_path else C["accent"]
    tk.Label(body, text="Base de données :", font=("Segoe UI", 9, "bold"),
             bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    tk.Label(body, text=db_txt, font=("Segoe UI", 9),
             bg=C["bg"], fg=db_col, wraplength=370,
             justify="left").pack(anchor="w", pady=(0, 10))

    # URL
    tk.Label(body, text="Interface :", font=("Segoe UI", 9, "bold"),
             bg=C["bg"], fg=C["muted"]).pack(anchor="w")
    tk.Label(body, text=url, font=("Consolas", 9),
             bg=C["bg"], fg=C["blue"]).pack(anchor="w", pady=(0, 14))

    # Boutons
    btns = tk.Frame(body, bg=C["bg"])
    btns.pack(fill="x")

    def rouvrir():
        webbrowser.open(url)

    def fermer():
        root.destroy()

    tk.Button(btns, text="🔄  Rouvrir dans le navigateur",
              font=("Segoe UI", 9, "bold"),
              bg=C["blue"], fg="white", relief="flat", bd=0,
              padx=12, pady=6, cursor="hand2",
              activebackground="#003d80", activeforeground="white",
              command=rouvrir).pack(side="left", padx=(0, 8))

    tk.Button(btns, text="✕  Fermer",
              font=("Segoe UI", 9),
              bg=C["muted"], fg="white", relief="flat", bd=0,
              padx=12, pady=6, cursor="hand2",
              activebackground="#525c66", activeforeground="white",
              command=fermer).pack(side="left")

    root.mainloop()


# ─── Point d'entrée ───────────────────────────────────────────────────────────
def main():
    # 1. Trouver la DB
    db_path = trouver_db()
    if db_path:
        print(f"[EMS BI] Base trouvée : {db_path}")
    else:
        print("[EMS BI] ⚠ Base de données introuvable — interface de chargement manuel.")

    # 2. Générer le HTML avec DB injectée
    try:
        html = generer_html(db_path)
    except FileNotFoundError as e:
        print(f"[EMS BI] ERREUR : {e}")
        # Fallback Tkinter pour afficher l'erreur
        try:
            import tkinter.messagebox as mb
            mb.showerror("EMS – BI", str(e))
        except Exception:
            pass
        sys.exit(1)

    # 3. Démarrer le serveur HTTP local
    try:
        port   = trouver_port()
        server = lancer_serveur(html, port)
        url    = f"http://127.0.0.1:{port}/"
        print(f"[EMS BI] Serveur démarré sur {url}")
    except OSError as e:
        print(f"[EMS BI] ERREUR réseau : {e}")
        sys.exit(1)

    # 4. Ouvrir le navigateur
    time.sleep(0.3)  # Laisser le serveur s'initialiser
    webbrowser.open(url)
    print(f"[EMS BI] Navigateur ouvert → {url}")

    # 5. Fenêtre Tkinter de statut (bloquante jusqu'à fermeture)
    afficher_fenetre_statut(db_path, port)

    # 6. Arrêter proprement le serveur à la fermeture de la fenêtre
    server.shutdown()
    print("[EMS BI] Serveur arrêté.")


if __name__ == "__main__":
    main()

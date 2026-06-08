#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
  EMS – LANCEUR  (menu d'accueil)
═══════════════════════════════════════════════════════════════════════════════

Menu central qui ouvre l'une des applications EMS.
Compatible PyInstaller : utilise multiprocessing au lieu de subprocess.

Auteur : Paul MARTINEAU — Emeraude Moteurs Systèmes
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
import multiprocessing
from pathlib import Path

import tkinter as tk
from tkinter import messagebox

try:
    from shared.version import __version__, APP_NAME
except ImportError:
    __version__ = "1.8.0"
    APP_NAME = "EMS – Emeraude Moteurs Systèmes"


_HERE = Path(__file__).resolve().parent


def _demarrer_app(app_key, here_str):
    """
    Worker exécuté dans un sous-processus. Configure sys.path pour le
    sous-dossier de l'app puis lance la fenêtre principale correspondante.
    Imports DANS la fonction pour éviter les conflits entre les `database.py`
    / `logo_data.py` des différentes apps au niveau du launcher.
    """
    here = Path(here_str)
    sous_dossiers = {
        "bons":          here / "ems_project",
        "parc":          here / "ems_project",
        "pieces":          here / "pieces_app",
        "garanties":     here / "garanties_app",
        "amelioration":  here / "amelioration_app",
        "BI":            here / "BI_app",
    }
    dossier = sous_dossiers.get(app_key)
    if dossier and dossier.is_dir():
        sys.path.insert(0, str(dossier))
        try:
            os.chdir(dossier)
        except OSError:
            pass

    if app_key == "bons":
        from main import AppEMS
        AppEMS(mode="bons").mainloop()

    elif app_key == "parc":
        from main import AppEMS
        AppEMS(mode="parc").mainloop()

    elif app_key == "pieces":
        from app_pieces import PiecesApp
        PiecesApp().mainloop()

    elif app_key == "garanties":
        from app_garanties import GarantiesApp
        GarantiesApp().mainloop()

    elif app_key == "amelioration":
        from app_amelioration import AmeliorationApp
        AmeliorationApp().mainloop()

    elif app_key == "BI":
        import app_bi
        app_bi.main()


APPS = [
    {"key": "BI",           "titre": "Business Intelligence",
     "desc": "Analyse d'affaire",
     "icone": "📈", "couleur": "#b8bb0e", "dossier": "BI_app"},
    {"key": "bons",         "titre": "Bons d'intervention",
     "desc": "Création et suivi des bons d'intervention",
     "icone": "🔧", "couleur": "#0056b3", "dossier": "ems_project"},
    {"key": "parc",         "titre": "Gestion de parc",
     "desc": "Saisie des clients, moteurs et techniciens",
     "icone": "🗂", "couleur": "#00796b", "dossier": "ems_project"},
    {"key": "pieces",         "titre": "Gestion des pièces",
     "desc": "référencement des pièces",
     "icone": "🧰", "couleur": "#9BB3B0", "dossier": "ems_project"},
    {"key": "garanties",    "titre": "Garanties",
     "desc": "Dossiers des garanties appareils",
     "icone": "🛡", "couleur": "#aa14cf", "dossier": "garanties_app"},
    {"key": "amelioration", "titre": "Amélioration continue",
    "desc": "Tickets de demande d'amélioration des clients",
    "icone": "💡", "couleur": "#1e7e3e", "dossier": "amelioration_app"},
]


def _app_disponible(app):
    return (_HERE / app["dossier"]).is_dir()


def _lancer(app_key, fenetre=None):
    """Démarre l'application dans un processus séparé via multiprocessing."""
    try:
        p = multiprocessing.Process(
            target=_demarrer_app,
            args=(app_key, str(_HERE)),
            daemon=False,
        )
        p.start()
    except Exception as e:
        messagebox.showerror(
            "Erreur de lancement",
            f"Impossible de démarrer l'application :\n{e}")
        return
    if fenetre is not None:
        fenetre.destroy()


def _charger_logo(hauteur=52):
    """tk.PhotoImage du logo EMS (logo_data base64 → assets → None)."""
    try:
        import base64, io, importlib.util
        data = None
        for base in (_HERE / "shared", _HERE, _HERE / "ems_project",
                     _HERE.parent / "shared", _HERE.parent / "ems_project"):
            f = base / "logo_data.py"
            if f.is_file():
                spec = importlib.util.spec_from_file_location("logo_data", f)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                data = base64.b64decode(mod.LOGO_EMS_B64)
                break
        if data is None:
            for base in (_HERE, _HERE / "ems_project"):
                p = base / "assets" / "logo_ems.png"
                if p.is_file():
                    data = p.read_bytes()
                    break
        if data is None:
            return None
        try:
            from PIL import Image, ImageTk
            im = Image.open(io.BytesIO(data))
            r = hauteur / im.height
            im = im.resize((max(1, int(im.width * r)), hauteur),
                           Image.LANCZOS)
            return ImageTk.PhotoImage(im)
        except Exception:
            img = tk.PhotoImage(data=base64.b64encode(data).decode())
            fac = max(1, img.height() // hauteur)
            return img.subsample(fac, fac) if fac > 1 else img
    except Exception:
        return None


C = {
    "bg": "#f5f7fa", "header": "#002b5c", "accent": "#c62828",
    "card": "#ffffff", "border": "#d8dee5",
    "text": "#1a2332", "muted": "#6b7785",
}

class ParametresSyncDialog(tk.Toplevel):
    """Configuration de la synchronisation : serveur central + ID appareil."""
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Paramètres de synchronisation")
        self.geometry("520x420")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.grab_set()

        # Charger la config actuelle
        try:
            from ems_client import sync_config
            self._sync_config = sync_config
            cfg = sync_config.load()
        except Exception as e:
            self._sync_config = None
            cfg = {"server_url": "", "local_url": "", "device_id": ""}
            messagebox.showwarning(
                "Module manquant",
                f"Le module de synchronisation n'a pas pu être chargé :\n{e}")

        # En-tete
        head = tk.Frame(self, bg=C["header"], height=60)
        head.pack(fill="x"); head.pack_propagate(False)
        tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
        tk.Label(head, text="⚙️  Synchronisation",
                 font=("Segoe UI", 14, "bold"),
                 bg=C["header"], fg="white").pack(side="left", padx=16)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=18)

        # Adresse serveur central
        tk.Label(body, text="Adresse du serveur central",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(body, text="Le serveur de l'atelier (base partagée). "
                            "Ex : http://192.168.1.50:8765",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"]).pack(anchor="w")
        self.server_var = tk.StringVar(value=cfg.get("server_url", ""))
        tk.Entry(body, textvariable=self.server_var, width=50,
                 font=("Consolas", 10)).pack(anchor="w", pady=(2, 14), ipady=3)

        # Identifiant appareil
        tk.Label(body, text="Identifiant de cet appareil",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(body, text="Vide = poste bureau. Sur une tablette : T1, T2... "
                            "(évite les collisions de numéros de bon)",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"],
                 wraplength=460, justify="left").pack(anchor="w")
        self.device_var = tk.StringVar(value=cfg.get("device_id", ""))
        tk.Entry(body, textvariable=self.device_var, width=20,
                 font=("Consolas", 10)).pack(anchor="w", pady=(2, 14), ipady=3)

        # Adresse locale (cache) - rarement modifiee
        tk.Label(body, text="Adresse de l'API locale (cache)",
                 font=("Segoe UI", 10, "bold"),
                 bg=C["bg"], fg=C["text"]).pack(anchor="w")
        tk.Label(body, text="En général http://127.0.0.1:8765 (ne pas changer "
                            "sauf cas particulier)",
                 font=("Segoe UI", 8), bg=C["bg"], fg=C["muted"]).pack(anchor="w")
        self.local_var = tk.StringVar(value=cfg.get("local_url", ""))
        tk.Entry(body, textvariable=self.local_var, width=50,
                 font=("Consolas", 10)).pack(anchor="w", pady=(2, 16), ipady=3)

        # Zone de statut du test
        self.status_lbl = tk.Label(body, text="", font=("Segoe UI", 9),
                                    bg=C["bg"], anchor="w")
        self.status_lbl.pack(anchor="w", pady=(0, 8))

        # Boutons
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(side="bottom", fill="x", padx=24, pady=14)
        tk.Button(bf, text="🔌 Tester la connexion", font=("Segoe UI", 9, "bold"),
                  bg="#0056b3", fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._tester).pack(side="left")
        tk.Button(bf, text="💾 Enregistrer", font=("Segoe UI", 9, "bold"),
                  bg="#1e7e3e", fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self._save).pack(side="right")
        tk.Button(bf, text="Annuler", font=("Segoe UI", 9),
                  bg="#888", fg="white", relief="flat", padx=12, pady=6,
                  cursor="hand2", command=self.destroy).pack(side="right", padx=8)

    def _tester(self):
        """Teste si le serveur central repond a l'adresse saisie."""
        url = self.server_var.get().strip().rstrip("/")
        if not url:
            self.status_lbl.config(text="⚠ Adresse serveur vide.", fg=C["accent"])
            return
        self.status_lbl.config(text="Test en cours...", fg=C["muted"])
        self.update_idletasks()
        try:
            import requests
            r = requests.get(f"{url}/health", timeout=4)
            if r.ok:
                self.status_lbl.config(
                    text="✅ Serveur central joignable !", fg="#1e7e3e")
            else:
                self.status_lbl.config(
                    text=f"❌ Réponse inattendue ({r.status_code})",
                    fg=C["accent"])
        except Exception:
            self.status_lbl.config(
                text="❌ Serveur injoignable à cette adresse.", fg=C["accent"])

    def _save(self):
        if not self._sync_config:
            messagebox.showerror("Erreur",
                "Module de synchronisation indisponible.")
            return
        self._sync_config.save({
            "server_url": self.server_var.get().strip().rstrip("/"),
            "device_id":  self.device_var.get().strip(),
            "local_url":  self.local_var.get().strip().rstrip("/"),
        })
        messagebox.showinfo("Enregistré",
            "Paramètres de synchronisation enregistrés.")
        self.destroy()


class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME}  v{__version__}")
        self.geometry("560x740")
        self.resizable(False, False)
        self.configure(bg=C["bg"])

        head = tk.Frame(self, bg=C["header"], height=90)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
        logo = _charger_logo()
        if logo is not None:
            ll = tk.Label(head, image=logo, bg=C["header"])
            ll.image = logo
            ll.pack(side="left", padx=(18, 8), pady=10)
        hin = tk.Frame(head, bg=C["header"])
        hin.pack(side="left", fill="both", expand=True, padx=14)
        tk.Label(hin, text="Emeraude Moteurs Systèmes",
                 font=("Segoe UI", 17, "bold"),
                 bg=C["header"], fg="white").pack(anchor="w", pady=(20, 0))
        tk.Label(hin, text="Choisissez une application à ouvrir",
                 font=("Segoe UI", 10),
                 bg=C["header"], fg="#aac4e8").pack(anchor="w")

        # Bouton parametres synchro (en haut a droite du header)
        tk.Button(head, text="⚙️", font=("Segoe UI", 16),
                  bg=C["header"], fg="white", relief="flat", bd=0,
                  cursor="hand2", activebackground="#013a7a",
                  command=self._ouvrir_params).pack(side="right", padx=16)

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=16)
        for app in APPS:
            self._carte(body, app)

        foot = tk.Frame(self, bg=C["bg"])
        foot.pack(fill="x", padx=10, pady=(0, 0))
        tk.Label(foot,
                 text="Les applications partagent la même base de "
                      "données. Vous pouvez en ouvrir plusieurs en même temps.",
                 font=("Segoe UI", 7), bg=C["bg"], fg=C["muted"],
                 justify="center").pack()
    
    def _ouvrir_params(self):
        ParametresSyncDialog(self)

    def _carte(self, parent, app):
        dispo = _app_disponible(app)

        outer = tk.Frame(parent, bg=C["border"])
        outer.pack(fill="x", pady=7)
        card = tk.Frame(outer, bg=C["card"], cursor="hand2" if dispo else "")
        card.pack(fill="x", padx=1, pady=1)

        tk.Frame(card, bg=app["couleur"], width=5).pack(side="left", fill="y")

        right = tk.Frame(card, bg=C["card"], width=140)
        right.pack(side="right", fill="y", padx=(0, 16))
        right.pack_propagate(False)

        inner = tk.Frame(card, bg=C["card"])
        inner.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        ligne = tk.Frame(inner, bg=C["card"])
        ligne.pack(fill="x", expand=True)
        tk.Label(ligne, text=app["icone"], font=("Segoe UI", 20),
                 bg=C["card"]).pack(side="left", padx=(0, 12))
        txt = tk.Frame(ligne, bg=C["card"])
        txt.pack(side="left", fill="x", expand=True)
        tk.Label(txt, text=app["titre"], font=("Segoe UI", 13, "bold"),
                 bg=C["card"], fg=C["text"], anchor="w").pack(anchor="w")
        tk.Label(txt, text=app["desc"], font=("Segoe UI", 9),
                 bg=C["card"], fg=C["muted"], anchor="w",
                 wraplength=300, justify="left").pack(anchor="w")

        if dispo:
            btn = tk.Button(
                right, text="Ouvrir  ▸", font=("Segoe UI", 10, "bold"),
                bg=app["couleur"], fg="white", relief="flat", bd=0,
                padx=14, pady=7, cursor="hand2",
                activebackground=app["couleur"], activeforeground="white",
                command=lambda k=app["key"]: _lancer(k, self))
            btn.place(relx=0.5, rely=0.5, anchor="center")
            for w in (card, inner, ligne, txt):
                w.bind("<Button-1>", lambda _e, k=app["key"]: _lancer(k, self))
        else:
            tk.Label(right,
                     text="⚠ Introuvable",
                     font=("Segoe UI", 8, "italic"),
                     bg=C["card"], fg=C["accent"],
                     wraplength=120, justify="center").place(
                         relx=0.5, rely=0.5, anchor="center")


if __name__ == "__main__":
    # OBLIGATOIRE pour PyInstaller + multiprocessing sur Windows
    multiprocessing.freeze_support()
    Launcher().mainloop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EMS – Gestion des Affaires (application autonome).

Suivi des affaires clients : numéro automatique, dossier racine,
informations générales, équipements (moteur, inverseur, groupe, pompe),
objectifs et suivi par item.
"""

import sys
import os
import json
from pathlib import Path
from datetime import date, datetime

_HERE = Path(__file__).resolve().parent
_ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else _HERE.parent

for p in (_ROOT, _HERE):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from ems_client import api as db
except ImportError as e:
    import tkinter as _tk
    from tkinter import messagebox as _mb
    _r = _tk.Tk(); _r.withdraw()
    _mb.showerror("Dépendances manquantes",
                  f"Impossible d'importer les modules requis :\n{e}")
    sys.exit(1)

_ok, _msg = db.check_api()
if not _ok:
    import tkinter as _tk
    from tkinter import messagebox as _mb
    _r = _tk.Tk(); _r.withdraw()
    if not _mb.askokcancel("Serveur introuvable",
                           f"{_msg}\n\nContinuer quand même ?"):
        sys.exit(0)

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

# ─── Palette ─────────────────────────────────────────────────────────────────
C = {
    "bg":        "#f5f7fa",
    "surface":   "#ffffff",
    "header":    "#d97706",   # orange affaire
    "accent":    "#c62828",
    "text":      "#1a2332",
    "muted":     "#6b7785",
    "btn":       "#0056b3",
    "btn2":      "#d97706",
    "btn2h":     "#b45309",
    "danger":    "#c62828",
    "border":    "#d8dee5",
    "row_even":  "#f7f9fc",
    "row_odd":   "#ffffff",
    "tag_ec":    "#f59e0b",
    "tag_att":   "#6366f1",
    "tag_clos":  "#10b981",
    "tag_ann":   "#9ca3af",
    "item_todo": "#6b7785",
    "item_ec":   "#f59e0b",
    "item_done": "#10b981",
    "item_nc":   "#c62828",
    "nav_sel":   "#fde68a",
    "warn":      "#e67e22",
}
F = {
    "title":  ("Segoe UI", 16, "bold"),
    "h1":     ("Segoe UI", 13, "bold"),
    "body":   ("Segoe UI", 10),
    "bold":   ("Segoe UI", 10, "bold"),
    "small":  ("Segoe UI", 9),
}

STATUTS_AFFAIRE = ["En cours", "En attente", "Clos", "Annulé"]
STATUTS_ITEM    = ["À faire", "En cours", "Terminé", "NC"]
TYPES_ITEM      = [
    "Moteur principal",
    "Inverseur / Réducteur",
    "Groupe électrogène",
    "Pompe / Auxiliaire",
    "Autre",
]

# Templates de propriétés par type (labels libres, juste des suggestions)
TEMPLATES_PAR_TYPE = {
    "Moteur principal": [
        "Puissance (kW)", "Régime (tr/min)", "Nb cylindres",
        "Cylindrée (cm³)", "Nb heures", "Sens rotation",
        "Norme émissions", "Fluide refroidissement",
    ],
    "Inverseur / Réducteur": [
        "Rapport réduction", "Couple max (Nm)", "Nb heures",
        "Type commande", "Fluide",
    ],
    "Groupe électrogène": [
        "Puissance (kVA)", "Puissance (kW)", "Tension (V)",
        "Fréquence (Hz)", "Nb heures", "Facteur de puissance",
    ],
    "Pompe / Auxiliaire": [
        "Type", "Débit (L/min)", "Pression (bar)",
        "Fluide", "Moteur entraînement",
    ],
    "Autre": [],
}


# ─── Helpers ─────────────────────────────────────────────────────────────────

def row_get(d, key, default=""):
    if d is None:
        return default
    v = d.get(key)
    return v if v not in (None, "") else default


def mk_btn(parent, text, cmd, color=None, **kw):
    color = color or C["btn"]
    return tk.Button(parent, text=text, command=cmd,
                     bg=color, fg="white", relief="flat", bd=0,
                     padx=10, pady=5, cursor="hand2", font=F["body"],
                     activebackground=color, activeforeground="white", **kw)


def section_bar(parent, text):
    f = tk.Frame(parent, bg=C["header"], height=26)
    f.pack(fill="x", pady=(12, 4))
    f.pack_propagate(False)
    tk.Label(f, text=f"  {text}", bg=C["header"], fg="white",
             font=F["bold"], anchor="w").pack(side="left", fill="y")


class DateEntry(ttk.Entry):
    """Champ date DD/MM/AAAA avec masque."""
    FMT = "%d/%m/%Y"

    def __init__(self, master, textvariable=None, **kw):
        kw.setdefault("width", 14)
        super().__init__(master, textvariable=textvariable, **kw)
        self._var = textvariable or tk.StringVar()
        if textvariable is None:
            self.configure(textvariable=self._var)
        self.bind("<FocusOut>", self._validate)

    def _validate(self, *_):
        v = self._var.get().strip()
        if not v:
            return
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d%m%Y", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(v, fmt)
                self._var.set(dt.strftime(self.FMT))
                return
            except ValueError:
                continue

    @staticmethod
    def is_valid(s: str) -> bool:
        try:
            datetime.strptime(s.strip(), "%d/%m/%Y")
            return True
        except ValueError:
            return False


# ─── Éditeur de propriétés clé→valeur libre ──────────────────────────────────

class ProprietesEditor(tk.Frame):
    """
    Widget affichant une liste de lignes [Nom de propriété] → [Valeur] [✕].
    L'utilisateur peut ajouter, renommer ou supprimer n'importe quelle ligne.
    Les données sont sérialisées/désérialisées en dict Python via get()/set().
    """

    def __init__(self, master, **kw):
        super().__init__(master, bg=C["bg"], **kw)
        self._rows: list[tuple[tk.StringVar, tk.StringVar]] = []  # (nom_var, val_var)
        self._rows_frame = tk.Frame(self, bg=C["bg"])
        self._rows_frame.pack(fill="x")
        add_btn = tk.Button(self, text="＋ Ajouter une propriété",
                            font=F["small"], bg=C["bg"], fg=C["btn"],
                            relief="flat", bd=0, cursor="hand2",
                            activeforeground=C["btn2"],
                            command=lambda: self._add_row("", ""))
        add_btn.pack(anchor="w", pady=(4, 0))

    def _add_row(self, nom: str, val: str) -> tuple:
        nom_var = tk.StringVar(value=nom)
        val_var = tk.StringVar(value=val)
        self._rows.append((nom_var, val_var))

        row_f = tk.Frame(self._rows_frame, bg=C["bg"])
        row_f.pack(fill="x", pady=1)

        nom_entry = ttk.Entry(row_f, textvariable=nom_var, width=22,
                              font=F["small"])
        nom_entry.pack(side="left", padx=(0, 4))
        tk.Label(row_f, text="→", bg=C["bg"], font=F["small"],
                 fg=C["muted"]).pack(side="left", padx=(0, 4))
        ttk.Entry(row_f, textvariable=val_var, width=22,
                  font=F["small"]).pack(side="left", padx=(0, 4))

        def _del(f=row_f, pair=(nom_var, val_var)):
            if pair in self._rows:
                self._rows.remove(pair)
            f.destroy()

        tk.Button(row_f, text="✕", font=("Segoe UI", 8), bg=C["bg"],
                  fg=C["danger"], relief="flat", bd=0, cursor="hand2",
                  command=_del).pack(side="left")

        return nom_var, val_var

    def load_template(self, type_item: str):
        """Charge le template du type donné (ne remplace que les lignes vides)."""
        existing_names = {v.get().strip() for v, _ in self._rows if v.get().strip()}
        for label in TEMPLATES_PAR_TYPE.get(type_item, []):
            if label not in existing_names:
                self._add_row(label, "")

    def set(self, data: dict):
        """Remplace toutes les lignes avec le contenu de data."""
        # vider
        for w in self._rows_frame.winfo_children():
            w.destroy()
        self._rows.clear()
        for nom, val in data.items():
            self._add_row(str(nom), str(val))

    def get(self) -> dict:
        """Retourne un dict {nom: valeur} en ignorant les noms vides."""
        result = {}
        for nom_var, val_var in self._rows:
            nom = nom_var.get().strip()
            if nom:
                result[nom] = val_var.get().strip()
        return result

    def update_from_moteur(self, moteur: dict):
        """Met à jour les valeurs existantes avec les champs connus du moteur."""
        mapping = {
            "Nb cylindres":     row_get(moteur, "cylindree"),
            "Cylindrée (cm³)":  row_get(moteur, "cylindree"),
        }
        existing = {nom_var.get().strip(): val_var
                    for nom_var, val_var in self._rows}
        for nom, val in mapping.items():
            if nom in existing and val and not existing[nom].get():
                existing[nom].set(val)


# ─── Dialogue Item d'affaire ─────────────────────────────────────────────────

class ItemDialog(tk.Toplevel):
    def __init__(self, parent, affaire_id, item=None, on_save=None):
        super().__init__(parent)
        self.affaire_id = affaire_id
        self.item = item
        self.on_save = on_save
        self.title("Nouvel équipement" if not item else "Modifier équipement")
        self.configure(bg=C["bg"])
        self.resizable(False, False)
        self.grab_set()

        self.type_var    = tk.StringVar(value=row_get(item, "type_item", "Moteur principal"))
        self.libelle_var = tk.StringVar(value=row_get(item, "libelle"))
        self.marque_var  = tk.StringVar(value=row_get(item, "marque"))
        self.ref_var     = tk.StringVar(value=row_get(item, "reference"))
        self.serie_var   = tk.StringVar(value=row_get(item, "num_serie"))
        self.statut_var  = tk.StringVar(value=row_get(item, "statut", "À faire"))
        self.obj_var     = tk.StringVar(value=row_get(item, "objectif"))
        self._details    = json.loads(row_get(item, "details_json") or "{}")

        # Chargement des composants de la base
        self._search_var    = tk.StringVar()
        self._moteur_by_lbl: dict[str, dict] = {}
        self._info_lbl_var  = tk.StringVar()
        try:
            moteurs = db.get_moteurs()
            for m in moteurs:
                serie  = row_get(m, "num_serie", "—")
                marque = row_get(m, "marque")
                navire = row_get(m, "navire")
                client = row_get(m, "client_nom")
                parts  = [serie]
                if marque: parts.append(marque)
                if navire: parts.append(navire)
                if client: parts.append(f"({client})")
                label = "  –  ".join(parts)
                self._moteur_by_lbl[label] = m
        except Exception:
            pass

        self._build()

    def _build(self):
        # ── Zone de recherche base de données ────────────────────────────────
        search_frame = tk.LabelFrame(self, text="  Importer depuis la base (optionnel)  ",
                                     bg=C["bg"], fg=C["header"], font=F["bold"],
                                     labelanchor="nw", bd=2, relief="groove")
        search_frame.pack(fill="x", padx=16, pady=(12, 4))

        sf = tk.Frame(search_frame, bg=C["bg"])
        sf.pack(fill="x", padx=10, pady=6)
        tk.Label(sf, text="Moteur enregistré :", bg=C["bg"], font=F["body"],
                 width=18, anchor="e").pack(side="left", padx=(0, 6))
        self._search_combo = SearchableCombobox(
            sf, textvariable=self._search_var,
            values=list(self._moteur_by_lbl.keys()),
            width=48, max_visible=10)
        self._search_combo.pack(side="left", fill="x", expand=True)
        self._search_combo.bind("<<ComboboxSelected>>", self._on_moteur_selected)

        self._info_lbl = tk.Label(search_frame, textvariable=self._info_lbl_var,
                                  bg="#fff8e7", fg="#92400e", font=F["small"],
                                  anchor="w", padx=10, pady=3)
        # affiché dynamiquement seulement si un moteur est sélectionné

        # ── Formulaire scrollable ─────────────────────────────────────────────
        outer = tk.Frame(self, bg=C["bg"])
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg=C["bg"], highlightthickness=0)
        ys = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        f = tk.Frame(canvas, bg=C["bg"])
        canvas_win = canvas.create_window((0, 0), window=f, anchor="nw")

        def _on_frame_cfg(*_):
            canvas.configure(scrollregion=canvas.bbox("all"))
        def _on_canvas_cfg(ev):
            canvas.itemconfig(canvas_win, width=ev.width)
        f.bind("<Configure>", _on_frame_cfg)
        canvas.bind("<Configure>", _on_canvas_cfg)
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        def lbl(text, row, col=0):
            tk.Label(f, text=text, bg=C["bg"], font=F["body"],
                     anchor="e", width=20).grid(row=row, column=col,
                                                sticky="e", padx=(0, 6), pady=4)

        # Type + bouton modèle
        lbl("Type *", 0)
        type_row = tk.Frame(f, bg=C["bg"])
        type_row.grid(row=0, column=1, sticky="w", pady=4)
        type_cb = ttk.Combobox(type_row, textvariable=self.type_var,
                               values=TYPES_ITEM, state="readonly", width=26)
        type_cb.pack(side="left")
        tk.Button(type_row, text="📋 Modèle", font=F["small"],
                  bg=C["bg"], fg=C["btn2"], relief="flat", bd=0, cursor="hand2",
                  command=self._charger_modele).pack(side="left", padx=(10, 0))

        # Libellé
        lbl("Désignation / Libellé", 1)
        ttk.Entry(f, textvariable=self.libelle_var, width=32).grid(
            row=1, column=1, sticky="w", pady=4)

        # Marque
        lbl("Marque", 2)
        marques = db.get_marques() if hasattr(db, "get_marques") else []
        SearchableCombobox(f, textvariable=self.marque_var,
                           values=marques, width=30).grid(
            row=2, column=1, sticky="w", pady=4)

        # Référence
        lbl("Référence constructeur", 3)
        ttk.Entry(f, textvariable=self.ref_var, width=32).grid(
            row=3, column=1, sticky="w", pady=4)

        # N° série
        lbl("N° série", 4)
        ttk.Entry(f, textvariable=self.serie_var, width=32).grid(
            row=4, column=1, sticky="w", pady=4)

        # Statut
        lbl("Statut", 5)
        ttk.Combobox(f, textvariable=self.statut_var,
                     values=STATUTS_ITEM, state="readonly",
                     width=20).grid(row=5, column=1, sticky="w", pady=4)

        # ── Propriétés modulables ─────────────────────────────────────────────
        tk.Label(f, text="", bg=C["bg"]).grid(row=6, column=0)
        prop_frame = tk.LabelFrame(f, text="  Propriétés techniques  ",
                                   bg=C["bg"], fg=C["header"],
                                   font=F["bold"], bd=2, relief="groove")
        prop_frame.grid(row=7, column=0, columnspan=2, sticky="ew",
                        padx=6, pady=6)
        self._props_editor = ProprietesEditor(prop_frame)
        self._props_editor.pack(fill="x", padx=10, pady=8)

        if self._details:
            self._props_editor.set(self._details)
        else:
            self._props_editor.load_template(self.type_var.get())

        # Objectif
        lbl("Objectif", 8)
        ttk.Entry(f, textvariable=self.obj_var, width=32).grid(
            row=8, column=1, sticky="w", pady=4)

        # Suivi
        lbl("Suivi / Notes", 9)
        self._suivi_text = tk.Text(f, width=32, height=5, font=F["body"],
                                   relief="groove", bg=C["surface"])
        self._suivi_text.grid(row=9, column=1, sticky="w", pady=4)
        if self.item:
            self._suivi_text.insert("1.0", row_get(self.item, "suivi"))

        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(fill="x", padx=16, pady=10)
        mk_btn(bf, "💾 Enregistrer", self._save).pack(side="left", padx=6)
        mk_btn(bf, "Annuler", self.destroy, color=C["muted"]).pack(side="left", padx=6)

    def _charger_modele(self):
        self._props_editor.load_template(self.type_var.get())

    def _on_moteur_selected(self, *_):
        label = self._search_var.get()
        m = self._moteur_by_lbl.get(label)
        if not m:
            return

        self.marque_var.set(row_get(m, "marque"))
        self.ref_var.set(row_get(m, "ref_constructeur"))
        self.serie_var.set(row_get(m, "num_serie"))
        if not self.libelle_var.get():
            self.libelle_var.set(row_get(m, "type_moteur") or row_get(m, "navire"))

        # Injecter les valeurs connues dans l'éditeur de propriétés
        self._props_editor.update_from_moteur(m)

        # Bandeau d'info
        parts = []
        for label_txt, key in [("Navire", "navire"), ("Machine", "machine"),
                                ("Client", "client_nom")]:
            v = row_get(m, key)
            if v:
                parts.append(f"{label_txt} : {v}")
        if parts:
            self._info_lbl_var.set("  " + "   |   ".join(parts))
            self._info_lbl.pack(fill="x", padx=0, pady=(0, 4))

    def _refresh_details(self):
        pass  # remplacé par ProprietesEditor

    def _save(self):
        type_item = self.type_var.get()
        details   = self._props_editor.get()
        suivi     = self._suivi_text.get("1.0", "end-1c").strip()
        data = {
            "type_item":    type_item,
            "libelle":      self.libelle_var.get().strip(),
            "marque":       self.marque_var.get().strip(),
            "reference":    self.ref_var.get().strip(),
            "num_serie":    self.serie_var.get().strip(),
            "statut":       self.statut_var.get(),
            "objectif":     self.obj_var.get().strip(),
            "suivi":        suivi,
            "details_json": json.dumps(details, ensure_ascii=False),
        }
        try:
            if self.item:
                db.update_affaire_item(self.affaire_id, self.item["id"], data)
            else:
                db.create_affaire_item(self.affaire_id, data)
            if self.on_save:
                self.on_save()
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)


# ─── Dialogue Affaire ─────────────────────────────────────────────────────────

class AffaireDialog(tk.Toplevel):
    def __init__(self, parent, app, affaire=None, on_save=None):
        super().__init__(parent)
        self.app = app
        self.affaire = affaire
        self.on_save = on_save
        self.title("Nouvelle affaire" if not affaire
                   else f"Affaire – {row_get(affaire, 'num_affaire')}")
        self.configure(bg=C["bg"])
        self.minsize(820, 640)
        self.grab_set()

        self._clients = db.get_clients()
        self._techs   = [t["nom"] for t in db.get_techniciens()]

        # Variables
        a = affaire or {}
        self.client_var   = tk.StringVar()
        self.projet_var   = tk.StringVar(value=row_get(a, "nom_projet"))
        self.navire_var   = tk.StringVar(value=row_get(a, "navire_machine"))
        self.ref_var      = tk.StringVar(value=row_get(a, "ref_interne"))
        self.charge_var   = tk.StringVar(value=row_get(a, "charge_affaire"))
        self.debut_var    = tk.StringVar(value=row_get(a, "date_debut"))
        self.fin_var      = tk.StringVar(value=row_get(a, "date_fin_prevue"))
        self.cloture_var  = tk.StringVar(value=row_get(a, "date_cloture"))
        self.statut_var   = tk.StringVar(value=row_get(a, "statut", "En cours"))
        self.num_var      = tk.StringVar(value=row_get(a, "num_affaire"))

        if affaire and affaire.get("client_id"):
            c = next((x for x in self._clients
                      if x["id"] == affaire["client_id"]), None)
            if c:
                self.client_var.set(c["nom"])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=0, pady=0)

        self._tab_info  = tk.Frame(nb, bg=C["bg"])
        self._tab_items = tk.Frame(nb, bg=C["bg"])
        nb.add(self._tab_info,  text="  Informations  ")
        nb.add(self._tab_items, text="  Équipements  ")

        self._build_info()
        self._build_items()

        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(fill="x", padx=16, pady=10)
        mk_btn(bf, "💾 Enregistrer", self._save).pack(side="left", padx=6)
        mk_btn(bf, "Annuler", self.destroy, color=C["muted"]).pack(side="left", padx=6)
        if affaire:
            mk_btn(bf, "📁 Ouvrir dossier", self._open_folder,
                   color=C["btn2"]).pack(side="right", padx=6)

    # ── Onglet Informations ───────────────────────────────────────────────────
    def _build_info(self):
        p = self._tab_info
        f = tk.Frame(p, bg=C["bg"])
        f.pack(padx=20, pady=14, fill="both")

        def row_field(label, widget_factory, r):
            tk.Label(f, text=label, bg=C["bg"], font=F["body"],
                     anchor="e", width=22).grid(row=r, column=0,
                                                sticky="e", padx=(0, 8), pady=4)
            w = widget_factory(f)
            w.grid(row=r, column=1, sticky="w", pady=4)
            return w

        # N° affaire (readonly si existant)
        tk.Label(f, text="N° Affaire", bg=C["bg"], font=F["body"],
                 anchor="e", width=22).grid(row=0, column=0, sticky="e", padx=(0, 8), pady=4)
        num_e = ttk.Entry(f, textvariable=self.num_var, width=20,
                          state="readonly" if self.affaire else "normal")
        num_e.grid(row=0, column=1, sticky="w", pady=4)
        if not self.affaire:
            tk.Label(f, text="(auto-généré si vide)", bg=C["bg"],
                     font=F["small"], fg=C["muted"]).grid(row=0, column=2, sticky="w", padx=6)

        # Client
        tk.Label(f, text="Client", bg=C["bg"], font=F["body"],
                 anchor="e", width=22).grid(row=1, column=0, sticky="e", padx=(0, 8), pady=4)
        SearchableCombobox(f, textvariable=self.client_var,
                           values=[c["nom"] for c in self._clients],
                           width=34).grid(row=1, column=1, sticky="w", pady=4)

        row_field("Nom du projet",           lambda p: ttk.Entry(p, textvariable=self.projet_var, width=36), 2)
        row_field("Navire / Machine",        lambda p: ttk.Entry(p, textvariable=self.navire_var, width=36), 3)
        row_field("Référence interne",       lambda p: ttk.Entry(p, textvariable=self.ref_var, width=36), 4)

        # Chargé d'affaire
        tk.Label(f, text="Chargé d'affaire", bg=C["bg"], font=F["body"],
                 anchor="e", width=22).grid(row=5, column=0, sticky="e", padx=(0, 8), pady=4)
        SearchableCombobox(f, textvariable=self.charge_var,
                           values=self._techs, width=34).grid(row=5, column=1, sticky="w", pady=4)

        # Dates
        row_field("Date de début",           lambda p: DateEntry(p, textvariable=self.debut_var), 6)
        row_field("Date de fin prévue",      lambda p: DateEntry(p, textvariable=self.fin_var), 7)
        row_field("Date de clôture",         lambda p: DateEntry(p, textvariable=self.cloture_var), 8)

        # Statut
        tk.Label(f, text="Statut", bg=C["bg"], font=F["body"],
                 anchor="e", width=22).grid(row=9, column=0, sticky="e", padx=(0, 8), pady=4)
        ttk.Combobox(f, textvariable=self.statut_var,
                     values=STATUTS_AFFAIRE, state="readonly",
                     width=20).grid(row=9, column=1, sticky="w", pady=4)

        # Description
        tk.Label(f, text="Description", bg=C["bg"], font=F["body"],
                 anchor="ne", width=22).grid(row=10, column=0, sticky="ne", padx=(0, 8), pady=4)
        self._desc_text = tk.Text(f, width=36, height=4, font=F["body"],
                                  relief="groove", bg=C["surface"])
        self._desc_text.grid(row=10, column=1, sticky="w", pady=4)
        if self.affaire:
            self._desc_text.insert("1.0", row_get(self.affaire, "description"))

        # Commentaires
        tk.Label(f, text="Commentaires", bg=C["bg"], font=F["body"],
                 anchor="ne", width=22).grid(row=11, column=0, sticky="ne", padx=(0, 8), pady=4)
        self._comm_text = tk.Text(f, width=36, height=3, font=F["body"],
                                  relief="groove", bg=C["surface"])
        self._comm_text.grid(row=11, column=1, sticky="w", pady=4)
        if self.affaire:
            self._comm_text.insert("1.0", row_get(self.affaire, "commentaires"))

    # ── Onglet Équipements ────────────────────────────────────────────────────
    def _build_items(self):
        p = self._tab_items

        tb = tk.Frame(p, bg=C["bg"])
        tb.pack(fill="x", padx=12, pady=8)
        mk_btn(tb, "➕ Ajouter équipement", self._add_item).pack(side="left", padx=4)
        mk_btn(tb, "✏️ Modifier", self._edit_item, color=C["btn2"]).pack(side="left", padx=4)
        mk_btn(tb, "🗑️ Supprimer", self._del_item, color=C["danger"]).pack(side="left", padx=4)

        cols = ("type_item", "libelle", "marque", "num_serie", "statut", "objectif")
        hdrs = ("Type", "Désignation", "Marque", "N° Série", "Statut", "Objectif")
        widths = (130, 160, 100, 100, 80, 200)

        self._items_tree = ttk.Treeview(p, columns=cols, show="headings",
                                         selectmode="browse", height=12)
        for col, hdr, w in zip(cols, hdrs, widths):
            self._items_tree.heading(col, text=hdr)
            self._items_tree.column(col, width=w, minwidth=60, anchor="w")

        ys = ttk.Scrollbar(p, orient="vertical", command=self._items_tree.yview)
        self._items_tree.configure(yscrollcommand=ys.set)
        self._items_tree.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=4)
        ys.pack(side="left", fill="y", pady=4)

        self._items_tree.tag_configure("todo",  foreground=C["item_todo"])
        self._items_tree.tag_configure("ec",    foreground=C["item_ec"])
        self._items_tree.tag_configure("done",  foreground=C["item_done"])
        self._items_tree.tag_configure("nc",    foreground=C["item_nc"], font=F["bold"])
        self._items_tree.bind("<Double-1>", lambda _: self._edit_item())

        self._items_data = []
        if self.affaire:
            self._load_items()
        else:
            tk.Label(p, text="Enregistrez l'affaire pour pouvoir ajouter des équipements.",
                     bg=C["bg"], fg=C["muted"], font=F["small"]).pack(pady=20)

    def _load_items(self):
        self._items_tree.delete(*self._items_tree.get_children())
        self._items_data = db.get_affaire_items(self.affaire["id"])
        _tag_map = {"À faire": "todo", "En cours": "ec", "Terminé": "done", "NC": "nc"}
        for it in self._items_data:
            tag = _tag_map.get(row_get(it, "statut"), "todo")
            self._items_tree.insert("", "end", iid=it["id"],
                values=(row_get(it, "type_item"),
                        row_get(it, "libelle"),
                        row_get(it, "marque"),
                        row_get(it, "num_serie"),
                        row_get(it, "statut"),
                        row_get(it, "objectif")),
                tags=(tag,))

    def _selected_item(self):
        sel = self._items_tree.selection()
        if not sel:
            return None
        iid = sel[0]
        return next((it for it in self._items_data if it["id"] == iid), None)

    def _add_item(self):
        if not self.affaire:
            messagebox.showinfo("Info",
                "Enregistrez d'abord l'affaire avant d'ajouter des équipements.")
            return
        ItemDialog(self, self.affaire["id"], on_save=self._load_items)

    def _edit_item(self):
        it = self._selected_item()
        if not it:
            messagebox.showwarning("Sélection", "Sélectionnez un équipement.")
            return
        ItemDialog(self, self.affaire["id"], item=it, on_save=self._load_items)

    def _del_item(self):
        it = self._selected_item()
        if not it:
            messagebox.showwarning("Sélection", "Sélectionnez un équipement.")
            return
        if messagebox.askyesno("Supprimer",
                               f"Supprimer '{row_get(it, 'libelle') or row_get(it, 'type_item')}' ?"):
            db.delete_affaire_item(self.affaire["id"], it["id"])
            self._load_items()

    # ── Sauvegarde ────────────────────────────────────────────────────────────
    def _save(self):
        client = next((c for c in self._clients
                       if c["nom"] == self.client_var.get()), None)
        data = {
            "num_affaire":    self.num_var.get().strip() or None,
            "client_id":      client["id"] if client else None,
            "nom_projet":     self.projet_var.get().strip(),
            "navire_machine": self.navire_var.get().strip(),
            "ref_interne":    self.ref_var.get().strip(),
            "charge_affaire": self.charge_var.get().strip(),
            "date_debut":     self.debut_var.get().strip(),
            "date_fin_prevue": self.fin_var.get().strip(),
            "date_cloture":   self.cloture_var.get().strip(),
            "statut":         self.statut_var.get(),
            "description":    self._desc_text.get("1.0", "end-1c").strip(),
            "commentaires":   self._comm_text.get("1.0", "end-1c").strip(),
        }
        if not data["nom_projet"] and not data["navire_machine"]:
            messagebox.showwarning("Champ requis",
                "Renseignez au moins le nom du projet ou le navire/machine.",
                parent=self)
            return
        try:
            if self.affaire:
                result = db.update_affaire(self.affaire["id"], data)
            else:
                result = db.create_affaire(data)
            if self.on_save:
                self.on_save(result)
            self.destroy()
        except Exception as e:
            messagebox.showerror("Erreur", str(e), parent=self)

    def _open_folder(self):
        dossier = row_get(self.affaire, "dossier_path")
        if dossier and Path(dossier).exists():
            os.startfile(dossier)
        else:
            messagebox.showinfo("Dossier introuvable",
                "Le dossier de cette affaire n'existe pas encore ou n'est pas accessible.",
                parent=self)


# ─── Combobox avec recherche textuelle (identique à main.py) ─────────────────

class SearchableCombobox(tk.Frame):
    def __init__(self, master, textvariable=None, values=None, width=44,
                 case_sensitive=False, max_visible=8, **kw):
        for k in ("state", "values", "textvariable", "validate", "validatecommand"):
            kw.pop(k, None)
        super().__init__(master, bg=master.cget("bg") if "bg" not in kw else kw.get("bg"))

        self._all_values     = list(values or [])
        self._filtered       = list(self._all_values)
        self._case_sensitive = case_sensitive
        self._max_visible    = max_visible
        self.var             = textvariable or tk.StringVar()
        self._suppress_trace = False
        self._is_open        = False

        top = tk.Frame(self, bg=self.cget("bg"))
        top.pack(fill="x")
        self.entry = ttk.Entry(top, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        self.arrow = tk.Label(top, text="▾", bg="#e8eaed", fg="#444",
                               font=("Segoe UI", 9, "bold"),
                               cursor="hand2", padx=6, pady=1, bd=1, relief="solid")
        self.arrow.pack(side="left", fill="y")
        self.arrow.bind("<Button-1>", lambda _e: self.toggle_dropdown())

        self._list_holder = tk.Frame(self, bg="#9ba5b1")
        self._list_inner  = tk.Frame(self._list_holder, bg="white")
        self._list_inner.pack(fill="both", expand=True, padx=1, pady=1)
        self._listbox = tk.Listbox(self._list_inner, font=("Segoe UI", 10),
                                    bd=0, highlightthickness=0,
                                    selectbackground=C["nav_sel"],
                                    selectforeground="white",
                                    activestyle="none",
                                    exportselection=False,
                                    height=1)
        self._listbox.pack(side="left", fill="both", expand=True)
        self._scrollbar = ttk.Scrollbar(self._list_inner, orient="vertical",
                                         command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=self._scrollbar.set)

        self.var.trace_add("write", self._on_text_change)
        self.entry.bind("<Down>",     self._on_arrow_down)
        self.entry.bind("<Up>",       self._on_arrow_up)
        self.entry.bind("<Return>",   self._on_enter)
        self.entry.bind("<Escape>",   self._on_escape)
        self.entry.bind("<FocusOut>", self._on_focus_out)
        self._listbox.bind("<ButtonRelease-1>", self._on_listbox_click)
        self._listbox.bind("<Return>",          self._on_listbox_enter)
        self._listbox.bind("<Double-Button-1>", self._on_listbox_enter)
        self._listbox.bind("<Escape>",
                            lambda _e: (self._close_dropdown(), self.entry.focus_set()))
        def _wheel_lb(ev):
            self._listbox.yview_scroll(int(-1 * (ev.delta / 120)), "units")
            return "break"
        for w in (self._listbox, self._list_holder, self._list_inner):
            w.bind("<MouseWheel>", _wheel_lb)

    def get(self):         return self.var.get()
    def set(self, value):
        self._suppress_trace = True
        self.var.set(value)
        self._suppress_trace = False
        self._filtered = list(self._all_values)
        self._close_dropdown()

    def set_values(self, values):
        self._all_values = list(values or [])
        self._filtered   = list(self._all_values)
        if self._is_open:
            self._refresh_listbox()

    def configure(self, **kw):
        if "values" in kw:
            self.set_values(kw.pop("values"))
        fg = kw.pop("foreground", kw.pop("fg", None))
        if fg is not None:
            try: self.entry.configure(foreground=fg)
            except tk.TclError: pass
        if kw: super().configure(**kw)
    config = configure

    @staticmethod
    def _norm(s):
        s = str(s).lower()
        return s.translate(str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc"))

    def _filter(self, query):
        if not query:
            return list(self._all_values)
        q = self._norm(query) if not self._case_sensitive else query
        starts, contains = [], []
        for v in self._all_values:
            nv = self._norm(v) if not self._case_sensitive else v
            if nv.startswith(q):    starts.append(v)
            elif q in nv:           contains.append(v)
        return starts + contains

    def _on_text_change(self, *_):
        if self._suppress_trace: return
        query = self.var.get()
        self._filtered = self._filter(query)
        if query:
            self._open_dropdown(); self._refresh_listbox()
        else:
            self._close_dropdown()

    def _on_arrow_down(self, _ev=None):
        if not self._is_open:
            self._filtered = self._filter(self.var.get())
            self._open_dropdown(); self._refresh_listbox()
        if self._listbox.size() > 0:
            self._listbox.focus_set()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(0); self._listbox.activate(0)
            self._listbox.see(0)
        return "break"

    def _on_arrow_up(self, _ev=None):
        if self._is_open and self._listbox.size() > 0:
            last = self._listbox.size() - 1
            self._listbox.focus_set()
            self._listbox.selection_clear(0, "end")
            self._listbox.selection_set(last); self._listbox.activate(last)
            self._listbox.see(last)
        return "break"

    def _on_enter(self, _ev=None):
        if self._is_open and self._filtered:
            self._select_value(self._filtered[0])
        return "break"

    def _on_escape(self, _ev=None):
        self._close_dropdown(); return "break"

    def _on_focus_out(self, _ev=None):
        self.after(120, self._maybe_close)

    def _maybe_close(self):
        try:
            focused = self.focus_get()
        except (tk.TclError, KeyError):
            focused = None
        w = focused
        try:
            while w is not None:
                if w is self._listbox or w is self.entry: return
                w = w.master
        except (tk.TclError, AttributeError):
            pass
        self._close_dropdown()
        v = self.var.get().strip()
        try:
            clr = C["warn"] if v and v not in self._all_values else "black"
            self.entry.configure(foreground=clr)
        except tk.TclError:
            pass

    def _on_listbox_click(self, ev):
        try:
            idx = self._listbox.nearest(ev.y)
            if 0 <= idx < len(self._filtered):
                self._select_value(self._filtered[idx])
        except (tk.TclError, IndexError):
            pass
        return "break"

    def _on_listbox_enter(self, _ev=None):
        sel = self._listbox.curselection()
        if sel and sel[0] < len(self._filtered):
            self._select_value(self._filtered[sel[0]])
        return "break"

    def _select_value(self, value):
        self._suppress_trace = True
        self.var.set(value)
        self._suppress_trace = False
        self._close_dropdown()
        try:
            self.entry.icursor("end")
            self.entry.configure(foreground="black")
            self.entry.focus_set()
        except tk.TclError:
            pass
        try: self.event_generate("<<ComboboxSelected>>")
        except tk.TclError: pass

    def toggle_dropdown(self):
        if self._is_open:
            self._close_dropdown()
        else:
            self._filtered = self._filter(self.var.get())
            self._open_dropdown(); self._refresh_listbox()
            self.entry.focus_set()

    def _open_dropdown(self):
        if self._is_open: return
        self._list_holder.pack(fill="x", pady=(2, 0))
        self._is_open = True

    def _close_dropdown(self):
        if not self._is_open: return
        try: self._list_holder.pack_forget()
        except tk.TclError: pass
        self._is_open = False

    def _refresh_listbox(self):
        if not self._is_open: return
        try:
            self._listbox.delete(0, "end")
            if not self._filtered:
                self._listbox.insert("end", "  (aucune correspondance)")
                self._listbox.itemconfigure(0, foreground="#9ba5b1")
                self._listbox.configure(height=1)
                self._scrollbar.pack_forget()
            else:
                for v in self._filtered:
                    self._listbox.insert("end", "  " + v)
                n = len(self._filtered)
                visible = min(self._max_visible, n)
                self._listbox.configure(height=visible)
                if n > visible:
                    self._scrollbar.pack(side="right", fill="y")
                else:
                    self._scrollbar.pack_forget()
        except tk.TclError:
            pass


# ─── Application principale ───────────────────────────────────────────────────

class AffaireApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EMS – Affaires")
        self.geometry("1050x680")
        self.configure(bg=C["bg"])
        self._build_header()
        self._build_toolbar()
        self._build_list()
        self._load()

    def _build_header(self):
        head = tk.Frame(self, bg=C["header"], height=60)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
        tk.Label(head, text="📋  Gestion des Affaires",
                 font=F["title"], bg=C["header"], fg="white").pack(
                     side="left", padx=20, pady=10)
        tk.Label(head, text=f"API : {db._client.base_url}",
                 font=F["small"], bg=C["header"], fg="#fde68a").pack(
                     side="right", padx=16)

    def _build_toolbar(self):
        bar = tk.Frame(self, bg=C["bg"], pady=6)
        bar.pack(fill="x", padx=12)

        mk_btn(bar, "➕ Nouvelle affaire", self._new).pack(side="left", padx=4)
        mk_btn(bar, "✏️ Modifier", self._edit, color=C["btn2"]).pack(side="left", padx=4)
        mk_btn(bar, "🗑️ Supprimer", self._delete, color=C["danger"]).pack(side="left", padx=4)
        mk_btn(bar, "📁 Ouvrir dossier", self._open_folder, color="#555").pack(side="left", padx=4)
        mk_btn(bar, "🔄 Actualiser", self._load, color="#555").pack(side="left", padx=4)

        # Filtres à droite
        rf = tk.Frame(bar, bg=C["bg"])
        rf.pack(side="right", padx=4)
        tk.Label(rf, text="Statut :", bg=C["bg"], font=F["body"]).pack(side="left")
        self._statut_var = tk.StringVar(value="Tous")
        cb = ttk.Combobox(rf, textvariable=self._statut_var,
                          values=["Tous"] + STATUTS_AFFAIRE,
                          state="readonly", width=14)
        cb.pack(side="left", padx=(4, 12))
        cb.bind("<<ComboboxSelected>>", lambda _: self._load())

        tk.Label(rf, text="Recherche :", bg=C["bg"], font=F["body"]).pack(side="left")
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._load())
        ttk.Entry(rf, textvariable=self._search_var, width=22).pack(side="left", padx=4)

    def _build_list(self):
        cols  = ("num_affaire", "client_nom", "nom_projet", "navire_machine",
                 "charge_affaire", "date_debut", "date_fin_prevue", "statut", "nb_items")
        hdrs  = ("N° Affaire", "Client", "Projet", "Navire / Machine",
                 "Chargé d'affaire", "Début", "Fin prévue", "Statut", "Équip.")
        widths = (110, 130, 160, 130, 120, 90, 90, 80, 55)

        frm = tk.Frame(self, bg=C["bg"])
        frm.pack(fill="both", expand=True, padx=12, pady=4)

        self._tree = ttk.Treeview(frm, columns=cols, show="headings",
                                   selectmode="browse")
        for col, hdr, w in zip(cols, hdrs, widths):
            self._tree.heading(col, text=hdr,
                               command=lambda c=col: self._sort(c))
            self._tree.column(col, width=w, minwidth=50, anchor="w")

        ys = ttk.Scrollbar(frm, orient="vertical",   command=self._tree.yview)
        xs = ttk.Scrollbar(frm, orient="horizontal",  command=self._tree.xview)
        self._tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)

        self._tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        self._tree.tag_configure("ec",   foreground=C["tag_ec"])
        self._tree.tag_configure("att",  foreground=C["tag_att"])
        self._tree.tag_configure("clos", foreground=C["tag_clos"])
        self._tree.tag_configure("ann",  foreground=C["tag_ann"])

        self._tree.bind("<Double-1>", lambda _: self._edit())

        self._status_lbl = tk.Label(self, text="", bg=C["bg"],
                                    font=F["small"], fg=C["muted"])
        self._status_lbl.pack(anchor="w", padx=16, pady=(0, 6))

        self._data = []
        self._sort_col = "num_affaire"
        self._sort_asc = False

    # ── Chargement ─────────────────────────────────────────────────────────────
    def _load(self, *_):
        statut = self._statut_var.get()
        search = self._search_var.get().strip()
        try:
            self._data = db.get_affaires(
                statut="" if statut == "Tous" else statut,
                search=search,
            )
        except Exception as e:
            messagebox.showerror("Erreur API", str(e))
            return
        self._refresh_tree()

    def _refresh_tree(self):
        self._tree.delete(*self._tree.get_children())
        _tag_map = {
            "En cours":  "ec",
            "En attente": "att",
            "Clos":      "clos",
            "Annulé":    "ann",
        }
        for a in self._data:
            tag = _tag_map.get(row_get(a, "statut"), "")
            self._tree.insert("", "end", iid=a["id"],
                values=(
                    row_get(a, "num_affaire"),
                    row_get(a, "client_nom"),
                    row_get(a, "nom_projet"),
                    row_get(a, "navire_machine"),
                    row_get(a, "charge_affaire"),
                    row_get(a, "date_debut"),
                    row_get(a, "date_fin_prevue"),
                    row_get(a, "statut"),
                    str(a.get("nb_items", 0)),
                ),
                tags=(tag,))
        self._status_lbl.config(
            text=f"{len(self._data)} affaire(s)")

    def _sort(self, col):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        self._data.sort(key=lambda x: (row_get(x, col) or "").lower(),
                        reverse=not self._sort_asc)
        self._refresh_tree()

    # ── Actions ────────────────────────────────────────────────────────────────
    def _selected(self):
        sel = self._tree.selection()
        if not sel:
            return None
        iid = sel[0]
        return next((a for a in self._data if a["id"] == iid), None)

    def _new(self):
        def on_save(result):
            self._load()
            if result:
                # Rouvrir en mode édition pour pouvoir ajouter des items
                new_aff = db.get_affaire(result["id"])
                if new_aff:
                    AffaireDialog(self, self, affaire=new_aff,
                                  on_save=lambda _: self._load())
        AffaireDialog(self, self, on_save=on_save)

    def _edit(self):
        a = self._selected()
        if not a:
            messagebox.showwarning("Sélection", "Sélectionnez une affaire.")
            return
        AffaireDialog(self, self, affaire=a,
                      on_save=lambda _: self._load())

    def _delete(self):
        a = self._selected()
        if not a:
            messagebox.showwarning("Sélection", "Sélectionnez une affaire.")
            return
        num = row_get(a, "num_affaire")
        if messagebox.askyesno("Supprimer",
                               f"Supprimer l'affaire {num} et tous ses équipements ?"):
            try:
                db.delete_affaire(a["id"])
                self._load()
            except Exception as e:
                messagebox.showerror("Erreur", str(e))

    def _open_folder(self):
        a = self._selected()
        if not a:
            messagebox.showwarning("Sélection", "Sélectionnez une affaire.")
            return
        dossier = row_get(a, "dossier_path")
        if dossier and Path(dossier).exists():
            os.startfile(dossier)
        else:
            messagebox.showinfo("Dossier introuvable",
                "Le dossier n'existe pas encore ou n'est pas accessible.")


if __name__ == "__main__":
    AffaireApp().mainloop()

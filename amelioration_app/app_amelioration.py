#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
  EMS – AMÉLIORATION CONTINUE  (application autonome)
═══════════════════════════════════════════════════════════════════════════════

Application séparée et indépendante du logiciel principal de suivi des
interventions.

• Lancement :  python app_amelioration.py

• Dépendances : les fichiers  database.py  et  amelioration_generator.py  doivent
  être présents (soit à côté de ce script, soit dans le projet EMS principal —
  voir la résolution de chemin ci-dessous).

Auteur : Paul MARTINEAU — Emeraude Moteurs Systèmes
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
from pathlib import Path

_HERE = Path(__file__).resolve().parent

if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = _HERE.parent

for p in (_ROOT, _HERE):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

try:
    from ems_client import api as db
    from shared import amelioration_generator as amgen
except ImportError as e:
    import tkinter as _tk
    from tkinter import messagebox as _mb
    _r = _tk.Tk(); _r.withdraw()
    _mb.showerror(
        "Dependances manquantes",
        f"Impossible d'importer les modules requis :\n{e}\n\n"
        "Verifiez que l'application est lancee depuis le dossier EMS "
        "ou que le serveur API est joignable.")
    sys.exit(1)

# Vérification connexion API avant d'afficher l'UI
_ok, _msg = db.check_api()
if not _ok:
    import tkinter as _tk
    from tkinter import messagebox as _mb
    _r = _tk.Tk(); _r.withdraw()
    if not _mb.askokcancel(
        "Serveur introuvable",
        f"{_msg}\n\nVérifiez que le serveur EMS est démarré.\n\n"
        "Continuer quand même ?"):
        sys.exit(0)

_BASE_INFO = f"API : {db._client.base_url}"
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import date, datetime


# ─── Palette & polices (identité visuelle EMS) ───────────────────────────────
C = {
    # ─── Fonds ────────────────────────────────────────────────────────────────
    "bg":         "#f5f7fa",   # gris très clair (au lieu de bleu pâle)
    "bg_alt":     "#eaeef3",   # gris légèrement plus marqué
    "surface":    "#ffffff",   # cartes/inputs
    # ─── Identité EMS ─────────────────────────────────────────────────────────
    "header":     "#1e7e3e",   # VERT AMELIO
    "header_alt": "#06631a",   # bleu intermédiaire
    "nav_sel":    "#70da87",   # bleu sélection nav
    "accent":     "#c62828",   # rouge EMS (du logo) — pour accents
    # ─── Texte ────────────────────────────────────────────────────────────────
    "text":       "#1a2332",   # presque noir
    "text_muted": "#6b7785",   # gris moyen
    "text_light": "#9ba5b1",   # gris clair
    # ─── Boutons ──────────────────────────────────────────────────────────────
    "btn":        "#0056b3",   # bleu primaire
    "btn_hover":  "#003d80",
    "btn2":       "#1e7e3e",   # vert action positive
    "btn2_hover": "#155a2c",
    "btn3":       "#6b7785",   # gris pour annuler/neutre
    "btn3_hover": "#525c66",
    "danger":     "#c62828",
    "danger_hover":"#a32020",
    "warn":       "#e67e22",   # orange chaud
    # ─── Tableaux ─────────────────────────────────────────────────────────────
    "row_even":   "#f7f9fc",   # bandes très discrètes
    "row_odd":    "#ffffff",
    "row_hover":  "#e3eaf3",
    "border":     "#d8dee5",   # bordures douces
    # ─── États / urgence ──────────────────────────────────────────────────────
    "urg_normale":  "#6b7785",
    "urg_urgente":  "#e67e22",
    "urg_critique": "#c62828",
    "ec":           "#f59e0b",  # En cours - ambre
    "ec_bg":        "#fff7ed",
    "afact":        "#6366f1",  # À facturer - indigo (intermédiaire)
    "afact_bg":     "#eef2ff",
    "fact":         "#3b82f6",  # Facturé - bleu vif
    "fact_bg":      "#eff6ff",
    "clos":         "#10b981",  # Clos - vert
    "clos_bg":      "#ecfdf5",
}

F = {
    "title":      ("Segoe UI", 16, "bold"),
    "subtitle":   ("Segoe UI", 10),
    "h1":         ("Segoe UI", 14, "bold"),
    "h2":         ("Segoe UI", 12, "bold"),
    "h3":         ("Segoe UI", 10, "bold"),
    "body":       ("Segoe UI", 10),
    "body_bold":  ("Segoe UI", 10, "bold"),
    "small":      ("Segoe UI", 9),
    "small_bold": ("Segoe UI", 9, "bold"),
    "tiny":       ("Segoe UI", 8),
    "mono":       ("Consolas", 10),
    "stat_value": ("Segoe UI", 26, "bold"),
    "stat_label": ("Segoe UI", 9),
}



# ─── Helpers UI ──────────────────────────────────────────────────────────────
def row_get(row, key, default=""):
    if row is None:
        return default
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def mk_header(parent, title, subtitle=""):
    bar = tk.Frame(parent, bg=C["header"], height=64)
    bar.pack(fill="x")
    bar.pack_propagate(False)
    tk.Frame(bar, bg=C["accent"], width=4).pack(side="left", fill="y")
    inner = tk.Frame(bar, bg=C["header"])
    inner.pack(side="left", fill="both", expand=True, padx=20)
    tk.Label(inner, text=title, font=F["title"],
             bg=C["header"], fg="white").pack(side="top", anchor="w", pady=(10, 0))
    if subtitle:
        tk.Label(inner, text=subtitle, font=F["subtitle"],
                 bg=C["header"], fg="#f0c8c8").pack(side="top", anchor="w")


def mk_btn(parent, text, cmd, color=None, **kw):
    bg = color or C["btn"]
    hover_map = {C["btn"]: C["btn_hover"], C["btn2"]: C["btn2_hover"],
                 C["btn3"]: C["btn3_hover"], C["danger"]: C["danger_hover"]}
    hover_bg = hover_map.get(bg, bg)
    b = tk.Button(parent, text=text, command=cmd, bg=bg, fg="white",
                  font=F["body_bold"], relief="flat", bd=0, padx=14, pady=6,
                  cursor="hand2", activebackground=hover_bg,
                  activeforeground="white", **kw)
    b.bind("<Enter>", lambda _e: b.configure(bg=hover_bg))
    b.bind("<Leave>", lambda _e: b.configure(bg=bg))
    return b


def mk_tree(parent, cols, col_defs, height=18):
    wrapper = tk.Frame(parent, bg=C["border"])
    frame = tk.Frame(wrapper, bg=C["surface"])
    frame.pack(fill="both", expand=True, padx=1, pady=1)
    vsb = ttk.Scrollbar(frame, orient="vertical")
    hsb = ttk.Scrollbar(frame, orient="horizontal")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=height,
                        yscrollcommand=vsb.set, xscrollcommand=hsb.set,
                        style="EMS.Treeview")
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)
    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(fill="both", expand=True)
    tree.tag_configure("even", background=C["row_even"])
    tree.tag_configure("odd", background=C["row_odd"])
    for cd in col_defs:
        if len(cd) == 4:
            cid, lbl, w, anchor = cd
        else:
            cid, lbl, w = cd
            anchor = "w"
        tree.heading(cid, text=lbl, anchor=anchor)
        tree.column(cid, width=w, minwidth=50, anchor=anchor)
    return wrapper, tree


def fill_tree(tree, rows):
    tree.delete(*tree.get_children())
    for i, r in enumerate(rows):
        tree.insert("", "end", iid=str(i), values=r,
                    tags=("even" if i % 2 == 0 else "odd",))


class DateEntry(ttk.Entry):
    """Champ date JJ/MM/AAAA avec validation simple."""
    def __init__(self, master, textvariable=None, width=14, **kw):
        self.var = textvariable or tk.StringVar()
        super().__init__(master, textvariable=self.var, width=width, **kw)
        self.bind("<FocusOut>", self._check)

    @staticmethod
    def is_valid(s):
        s = (s or "").strip()
        if not s:
            return True
        try:
            datetime.strptime(s, "%d/%m/%Y")
            return True
        except ValueError:
            return False

    def _check(self, _e=None):
        if self.is_valid(self.var.get()):
            self.configure(foreground="black")
        else:
            self.configure(foreground=C["danger"])


class SearchableCombobox(tk.Frame):
    """Combobox avec recherche in-flow (liste sous le champ, suit le scroll)."""
    def __init__(self, master, textvariable=None, values=None, width=44,
                 max_visible=8, **kw):
        super().__init__(master, bg=master.cget("bg"))
        self._all = list(values or [])
        self._filtered = list(self._all)
        self._max_visible = max_visible
        self.var = textvariable or tk.StringVar()
        self._suppress = False
        self._open = False

        top = tk.Frame(self, bg=self.cget("bg"))
        top.pack(fill="x")
        self.entry = ttk.Entry(top, textvariable=self.var, width=width)
        self.entry.pack(side="left", fill="x", expand=True)
        self.arrow = tk.Label(top, text="▾", bg="#e8eaed", fg="#444",
                               font=("Segoe UI", 9, "bold"), cursor="hand2",
                               padx=6, pady=1, bd=1, relief="solid")
        self.arrow.pack(side="left", fill="y")
        self.arrow.bind("<Button-1>", lambda _e: self._toggle())

        self._holder = tk.Frame(self, bg="#9ba5b1")
        inner = tk.Frame(self._holder, bg="white")
        inner.pack(fill="both", expand=True, padx=1, pady=1)
        self._lb = tk.Listbox(inner, font=("Segoe UI", 10), bd=0,
                               highlightthickness=0, activestyle="none",
                               selectbackground=C["nav_sel"],
                               selectforeground="white", exportselection=False,
                               height=1)
        self._lb.pack(side="left", fill="both", expand=True)
        self._sb = ttk.Scrollbar(inner, orient="vertical",
                                  command=self._lb.yview)
        self._lb.configure(yscrollcommand=self._sb.set)

        self.var.trace_add("write", self._on_change)
        self.entry.bind("<Down>", self._nav_down)
        self.entry.bind("<Return>", self._enter)
        self.entry.bind("<Escape>", lambda _e: self._close())
        self.entry.bind("<FocusOut>",
                        lambda _e: self.after(120, self._maybe_close))
        self._lb.bind("<ButtonRelease-1>", self._click)
        self._lb.bind("<Return>", self._lb_enter)
        self._lb.bind("<Double-Button-1>", self._lb_enter)

    def get(self):
        return self.var.get()

    def set(self, v):
        self._suppress = True
        self.var.set(v)
        self._suppress = False
        self._close()

    def set_values(self, values):
        self._all = list(values or [])
        self._filtered = list(self._all)

    def bind_selected(self, fn):
        self.bind("<<ComboboxSelected>>", fn)

    @staticmethod
    def _norm(s):
        s = str(s or "").lower()
        return s.translate(str.maketrans("àâäéèêëîïôöùûüç",
                                          "aaaeeeeiioouuuc"))

    def _filter(self, q):
        if not q:
            return list(self._all)
        qn = self._norm(q)
        st = [v for v in self._all if self._norm(v).startswith(qn)]
        ct = [v for v in self._all
              if qn in self._norm(v) and not self._norm(v).startswith(qn)]
        return st + ct

    def _on_change(self, *_):
        if self._suppress:
            return
        q = self.var.get()
        self._filtered = self._filter(q)
        if q:
            self._open_dd()
            self._refresh()
        else:
            self._close()

    def _nav_down(self, _e=None):
        if not self._open:
            self._filtered = self._filter(self.var.get())
            self._open_dd()
            self._refresh()
        if self._lb.size():
            self._lb.focus_set()
            self._lb.selection_clear(0, "end")
            self._lb.selection_set(0)
            self._lb.activate(0)
        return "break"

    def _enter(self, _e=None):
        if self._open and self._filtered:
            self._select(self._filtered[0])
        return "break"

    def _click(self, ev):
        try:
            i = self._lb.nearest(ev.y)
            if 0 <= i < len(self._filtered):
                self._select(self._filtered[i])
        except (tk.TclError, IndexError):
            pass
        return "break"

    def _lb_enter(self, _e=None):
        s = self._lb.curselection()
        if s and s[0] < len(self._filtered):
            self._select(self._filtered[s[0]])
        return "break"

    def _select(self, v):
        self._suppress = True
        self.var.set(v)
        self._suppress = False
        self._close()
        try:
            self.entry.icursor("end")
            self.entry.focus_set()
            self.event_generate("<<ComboboxSelected>>")
        except tk.TclError:
            pass

    def _toggle(self):
        if self._open:
            self._close()
        else:
            self._filtered = self._filter(self.var.get())
            self._open_dd()
            self._refresh()
            self.entry.focus_set()

    def _open_dd(self):
        if not self._open:
            self._holder.pack(fill="x", pady=(2, 0))
            self._open = True

    def _close(self):
        if self._open:
            try:
                self._holder.pack_forget()
            except tk.TclError:
                pass
            self._open = False

    def _maybe_close(self):
        try:
            f = self.focus_get()
        except (tk.TclError, KeyError):
            f = None
        w = f
        try:
            while w is not None:
                if w is self._lb or w is self.entry:
                    return
                w = w.master
        except (tk.TclError, AttributeError):
            pass
        self._close()

    def _refresh(self):
        if not self._open:
            return
        try:
            self._lb.delete(0, "end")
            if not self._filtered:
                self._lb.insert("end", "  (aucune correspondance)")
                self._lb.itemconfigure(0, foreground="#9ba5b1")
                self._lb.configure(height=1)
                self._sb.pack_forget()
            else:
                for v in self._filtered:
                    self._lb.insert("end", "  " + v)
                n = len(self._filtered)
                vis = min(self._max_visible, n)
                self._lb.configure(height=vis)
                if n > vis:
                    self._sb.pack(side="right", fill="y")
                else:
                    self._sb.pack_forget()
        except tk.TclError:
            pass


# ═══════════════════════════════════════════════════════════════════════════════

class AmeliorationsFrame(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent, bg=C["bg"])
        self.app = app
        mk_header(self, "Amélioration continue",
                  "   Tickets de demande d'amélioration clients")

        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=8)
        tk.Label(sf, text="🔍 Recherche :", bg=C["bg"], font=("Arial", 10)).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(sf, textvariable=self.search_var, width=26).pack(side="left", padx=4)

        tk.Label(sf, text="  Statut :", bg=C["bg"], font=("Arial", 10)).pack(side="left", padx=(12, 4))
        self.statut_var = tk.StringVar(value="Tous")
        ttk.Combobox(sf, textvariable=self.statut_var,
                     values=["Tous"] + db.AMELIO_STATUTS, width=12,
                     state="readonly").pack(side="left")
        self.statut_var.trace_add("write", lambda *_: self.refresh())

        tk.Label(sf, text="  Priorité :", bg=C["bg"], font=("Arial", 10)).pack(side="left", padx=(12, 4))
        self.prio_var = tk.StringVar(value="Toutes")
        ttk.Combobox(sf, textvariable=self.prio_var,
                     values=["Toutes"] + db.AMELIO_PRIORITES, width=12,
                     state="readonly").pack(side="left")
        self.prio_var.trace_add("write", lambda *_: self.refresh())

        mk_btn(sf, "➕ Nouveau sujet",
               lambda: AmeliorationDialog(self, self.app, on_save=self.refresh)
               ).pack(side="right")

        cols = ("num", "titre", "client", "prio", "statut", "maj")
        col_defs = [
            ("num",    "N° Ticket",   130),
            ("titre",  "Sujet",       320),
            ("client", "Client",      180),
            ("prio",   "Priorité",    100, "center"),
            ("statut", "Statut",      110, "center"),
            ("maj",    "Modifié",     120),
        ]
        tf, self.tree = mk_tree(self, cols, col_defs, height=20)
        tf.pack(fill="both", expand=True, padx=20, pady=4)
        # Tags couleur priorité
        self.tree.tag_configure("prio_crit", background="#fef2f2",
                                 foreground=C["urg_critique"])
        self.tree.tag_configure("prio_haute", background="#fff7ed",
                                 foreground=C["urg_urgente"])

        af = tk.Frame(self, bg=C["bg"])
        af.pack(fill="x", padx=20, pady=8)
        mk_btn(af, "✏️ Modifier", self._modifier).pack(side="left", padx=3)
        mk_btn(af, "📄 Générer fiche", self._fiche).pack(side="left", padx=3)
        mk_btn(af, "📁 Dossier", self._dossier).pack(side="left", padx=3)
        mk_btn(af, "🗑️ Supprimer", self._supprimer,
               color=C["danger"]).pack(side="left", padx=3)
        self.tree.bind("<Double-1>", lambda e: self._modifier())
        self._cache = []

    def refresh(self):
        items = db.get_ameliorations(statut=self.statut_var.get(),
                                      search=self.search_var.get(),
                                      priorite=self.prio_var.get())
        self._cache = list(items)
        self.tree.delete(*self.tree.get_children())
        for i, a in enumerate(self._cache):
            tags = ["even" if i % 2 == 0 else "odd"]
            if a["priorite"] == "Critique":
                tags.append("prio_crit")
            elif a["priorite"] == "Haute":
                tags.append("prio_haute")
            self.tree.insert("", "end", iid=str(i), values=(
                a["num_ticket"], a["titre"], a["client_nom"] or "",
                a["priorite"], a["statut"],
                db.fmt_paris_short(a["updated_at"]),
            ), tags=tuple(tags))

    def _sel(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionnez un sujet.")
            return None
        return self._cache[int(sel[0])]

    def _modifier(self):
        r = self._sel()
        if r:
            AmeliorationDialog(self, self.app, amelio_id=r["id"],
                               on_save=self.refresh)

    def _fiche(self):
        r = self._sel()
        if not r:
            return
        from amelioration_generator import sauvegarder_fiche
        a = db.get_amelioration(amelio_id=r["id"])
        path = sauvegarder_fiche(a)
        ouvrir_fichier(path)

    def _dossier(self):
        r = self._sel()
        if not r:
            return
        d = Path(__file__).parent / "ameliorations" / r["num_ticket"]
        d.mkdir(parents=True, exist_ok=True)
        ouvrir_fichier(d)

    def _supprimer(self):
        r = self._sel()
        if r and messagebox.askyesno(
                "Supprimer",
                f"Supprimer le ticket {r['num_ticket']} ?\n\n"
                "(Le dossier sur disque n'est pas supprimé.)"):
            db.delete_amelioration(r["id"])
            self.refresh()


class AmeliorationDialog(tk.Toplevel):
    def __init__(self, parent, app, amelio_id=None, on_save=None):
        super().__init__(parent)
        self.app = app
        self.amelio_id = amelio_id
        self.on_save = on_save
        self.is_edit = amelio_id is not None
        self.title("Modifier le sujet" if self.is_edit
                   else "Nouveau sujet d'amélioration")
        self.geometry("680x720")
        self.configure(bg=C["bg"])
        self.grab_set()

        self._clients = list(db.get_clients())
        self._techs = list(db.get_techniciens())

        mk_header(self, "Sujet d'amélioration",
                  "   Demande client / piste d'amélioration")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=14)

        # Titre
        tk.Label(body, text="Titre / Sujet *", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.titre_var = tk.StringVar()
        ttk.Entry(body, textvariable=self.titre_var, width=64).pack(
            fill="x", pady=(2, 10))

        # Client + Priorité (ligne)
        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x", pady=(0, 10))
        cl = tk.Frame(row, bg=C["bg"])
        cl.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(cl, text="Client demandeur", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.client_var = tk.StringVar()
        self.client_combo = SearchableCombobox(
            cl, textvariable=self.client_var,
            values=[c["nom"] for c in self._clients], width=30)
        self.client_combo.pack(fill="x", pady=(2, 0))
        pr = tk.Frame(row, bg=C["bg"])
        pr.pack(side="left")
        tk.Label(pr, text="Priorité", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.prio_var = tk.StringVar(value=db.AMELIO_PRIORITE_DEFAULT)
        ttk.Combobox(pr, textvariable=self.prio_var,
                     values=db.AMELIO_PRIORITES, width=14,
                     state="readonly").pack(pady=(2, 0))

        # Statut
        row2 = tk.Frame(body, bg=C["bg"])
        row2.pack(fill="x", pady=(0, 10))
        st = tk.Frame(row2, bg=C["bg"])
        st.pack(side="left")
        tk.Label(st, text="Statut", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.statut_var = tk.StringVar(value=db.AMELIO_STATUT_DEFAULT)
        ttk.Combobox(st, textvariable=self.statut_var,
                     values=db.AMELIO_STATUTS, width=16,
                     state="readonly").pack(pady=(2, 0))

        # Description
        tk.Label(body, text="Description de la demande *", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.txt_desc = tk.Text(body, height=6, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", bd=1,
                                 padx=6, pady=4)
        self.txt_desc.pack(fill="x", pady=(2, 10))

        # Commentaires
        tk.Label(body, text="Commentaires / Suivi", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.txt_comm = tk.Text(body, height=5, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", bd=1,
                                 padx=6, pady=4)
        self.txt_comm.pack(fill="x", pady=(2, 4))

        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(side="bottom", pady=12)
        mk_btn(bf, "💾 Enregistrer", lambda: self._save(False)).pack(
            side="left", padx=6)
        mk_btn(bf, "📄 Enregistrer + Fiche", lambda: self._save(True)).pack(
            side="left", padx=6)
        mk_btn(bf, "Annuler", self.destroy, color=C["btn3"]).pack(
            side="left", padx=6)

        if self.is_edit:
            self.after(50, self._load)

    def _load(self):
        a = db.get_amelioration(amelio_id=self.amelio_id)
        if not a:
            return
        self.titre_var.set(row_get(a, "titre"))
        c = next((x for x in self._clients
                  if x["id"] == row_get(a, "client_id")), None)
        if c:
            self.client_combo.set(c["nom"])
        self.prio_var.set(row_get(a, "priorite", db.AMELIO_PRIORITE_DEFAULT))
        self.statut_var.set(row_get(a, "statut", db.AMELIO_STATUT_DEFAULT))
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", row_get(a, "description"))
        self.txt_comm.delete("1.0", "end")
        self.txt_comm.insert("1.0", row_get(a, "commentaires"))

    def _save(self, generer=False):
        titre = self.titre_var.get().strip()
        desc = self.txt_desc.get("1.0", "end").strip()
        if not titre or not desc:
            messagebox.showwarning(
                "Champs manquants",
                "Le titre et la description sont obligatoires.")
            return
        client = next((c for c in self._clients
                       if c["nom"] == self.client_var.get()), None)
        data = {
            "titre": titre,
            "client_id": client["id"] if client else "",
            "description": desc,
            "priorite": self.prio_var.get(),
            "statut": self.statut_var.get(),
            "commentaires": self.txt_comm.get("1.0", "end").strip(),
        }
        if self.is_edit:
            db.update_amelioration(self.amelio_id, data)
            num = db.get_amelioration(amelio_id=self.amelio_id)["num_ticket"]
        else:
            aid, num = db.create_amelioration(data)
            self.amelio_id = aid
            self.is_edit = True

        if self.on_save:
            self.on_save()

        if generer:
            from amelioration_generator import sauvegarder_fiche
            a = db.get_amelioration(amelio_id=self.amelio_id)
            path = sauvegarder_fiche(a)
            messagebox.showinfo(
                "Fiche générée",
                f"✅ {num}\nFiche enregistrée dans :\n{path}")
            ouvrir_fichier(path)
            self.destroy()
        else:
            messagebox.showinfo("Enregistré",
                                f"✅ Sujet {num} enregistré.")
            self.destroy()




# ═══════════════════════════════════════════════════════════════════════════════
#  FENÊTRE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════
class AmeliorationApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.state("zoomed")
        self.title("EMS – Amélioration continue")
        self.geometry("1100x720")
        self.minsize(880, 540)
        self.configure(bg=C["bg"])
        self._init_styles()
        db.init_db()
        # Le frame attend (parent, app) ; on se passe nous-mêmes comme 'app'
        self.frame = AmeliorationsFrame(self, self)
        self.frame.pack(fill="both", expand=True)
        self.frame.refresh()

    def _init_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("EMS.Treeview", background=C["surface"],
                    foreground=C["text"], fieldbackground=C["surface"],
                    borderwidth=0, rowheight=28, font=F["body"])
        s.configure("EMS.Treeview.Heading", background=C["bg_alt"],
                    foreground=C["header"], relief="flat", borderwidth=0,
                    font=F["small_bold"], padding=(8, 6))
        s.map("EMS.Treeview", background=[("selected", C["nav_sel"])],
              foreground=[("selected", "white")])
        s.configure("TEntry", fieldbackground=C["surface"],
                    bordercolor=C["border"], padding=4)
        s.configure("TCombobox", fieldbackground=C["surface"],
                    bordercolor=C["border"], arrowcolor=C["header"], padding=4)
        s.map("TCombobox", fieldbackground=[("readonly", C["surface"])])


# ─── Lancement ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = AmeliorationApp()
    app.mainloop()

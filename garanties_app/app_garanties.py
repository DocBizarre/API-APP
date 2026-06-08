#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
  EMS – GESTION DES GARANTIES  (application autonome)
═══════════════════════════════════════════════════════════════════════════════

Application séparée et indépendante du logiciel principal de suivi des
interventions. Elle se concentre uniquement sur la gestion des dossiers de
garantie moteur.

• Lancement :  python app_garanties.py
• Base de données : PARTAGÉE avec l'application principale (data/ems.db),
  ce qui permet de réutiliser les moteurs et clients déjà saisis.
• Dépendances : les fichiers  database.py  et  garantie_generator.py  doivent
  être présents (soit à côté de ce script, soit dans le projet EMS principal —
  voir la résolution de chemin ci-dessous).

Auteur : Paul MARTINEAU — Emeraude Moteurs Systèmes
═══════════════════════════════════════════════════════════════════════════════
"""

import sys
import os
from pathlib import Path

# Resolution des chemins pour PyInstaller (.exe) et dev
_HERE = Path(__file__).resolve().parent

# En .exe, _MEIPASS est le dossier temporaire d'extraction
if getattr(sys, "frozen", False):
    _ROOT = Path(sys.executable).parent
else:
    _ROOT = _HERE.parent  # ../ depuis garanties_app/ vers projet racine

# Ajouter les chemins necessaires pour les imports
for p in (_ROOT, _HERE):
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Imports principaux
try:
    from ems_client import api as db
    from shared import garantie_generator as gargen
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
    "bg":         "#fdf6f5",   # blanc cassé légèrement rosé
    "bg_alt":     "#f8e8e6",   # gris-rosé pour zones secondaires
    "surface":    "#ffffff",
    "header":     "#92177e",   # ROUGE EMS profond (header, titres)
    "header_alt": "#9e12b1",   # rouge intermédiaire (hover)
    "nav_sel":    "#a767a7",   # rouge sélection
    "accent":     "#6a067e",   # rouge très foncé (liseré d'accent)
    "text":       "#2a1a1a",   # presque noir légèrement chaud
    "text_muted": "#8a6f6f",   # gris-rouge moyen
    "text_light": "#b39e9e",   # gris-rosé clair
    "btn":        "#c62828",   # bouton primaire rouge
    "btn_hover":  "#a31515",
    "btn2":       "#1e7e3e",   # vert action positive (conservé pour lisibilité)
    "btn2_hover": "#155a2c",
    "btn3":       "#8a6f6f",   # gris-rouge neutre (annuler)
    "btn3_hover": "#6e5757",
    "danger":     "#7a0f0f",   # rouge très foncé pour suppression
    "danger_hover":"#5c0b0b",
    "warn":       "#e67e22",   # orange chaud
    "row_even":   "#fcf2f1",   # bandes très discrètes rosées
    "row_odd":    "#ffffff",
    "border":     "#e6cfcd",   # bordures douces rosées
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
#  FENÊTRE PRINCIPALE
# ═══════════════════════════════════════════════════════════════════════════════
class GarantiesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("EMS – Gestion des Garanties")
        self.geometry("1180x760")
        self.minsize(900, 560)
        self.configure(bg=C["bg"])
        self._init_styles()
        db.init_db()  # garantit que les tables existent (base partagée)
        self._build()
        self.refresh()

    def _init_styles(self):
        s = ttk.Style(self)
        self.state("zoomed")
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

    def _build(self):
        mk_header(self, "Gestion des Garanties",
                  f"   {_BASE_INFO}")

        # Bandeau de statistiques
        self.stats_bar = tk.Frame(self, bg=C["bg"])
        self.stats_bar.pack(fill="x", padx=20, pady=(12, 4))

        # Barre de filtres
        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=8)
        tk.Label(sf, text="🔍 Recherche :", bg=C["bg"],
                 font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh())
        ttk.Entry(sf, textvariable=self.search_var, width=24).pack(
            side="left", padx=4)

        tk.Label(sf, text="  Statut :", bg=C["bg"],
                 font=F["body"]).pack(side="left", padx=(12, 4))
        self.statut_var = tk.StringVar(value="Tous")
        self.statut_cb = ttk.Combobox(
            sf, textvariable=self.statut_var,
            values=["Tous"] + db.get_statuts_garantie(), width=22,
            state="readonly")
        self.statut_cb.pack(side="left")
        self.statut_var.trace_add("write", lambda *_: self.refresh())

        tk.Label(sf, text="  Attribution :", bg=C["bg"],
                 font=F["body"]).pack(side="left", padx=(12, 4))
        self.attr_var = tk.StringVar(value="Toutes")
        self.attr_filter_cb = ttk.Combobox(
            sf, textvariable=self.attr_var,
            values=["Toutes"] + db.get_attributions_garantie(),
            width=18, state="readonly")
        self.attr_filter_cb.pack(side="left")
        self.attr_var.trace_add("write", lambda *_: self.refresh())

        mk_btn(sf, "➕ Nouvelle garantie",
               lambda: GarantieDialog(self, on_save=self.refresh)
               ).pack(side="right")
        mk_btn(sf, "⚙ Statuts",
               lambda: StatutsDialog(self, on_save=self._reload_statuts),
               color=C["btn2"]).pack(side="right", padx=(0, 6))

        # Tableau
        cols = ("ems", "constr", "client", "moteur", "attr",
                "statut", "ouv", "maj")
        col_defs = [
            ("ems",    "N° EMS",          130),
            ("constr", "N° Constructeur", 140),
            ("client", "Client",          150),
            ("moteur", "Moteur",          150),
            ("attr",   "Attribution",     110, "center"),
            ("statut", "Statut",          180),
            ("ouv",    "Ouverture",        95, "center"),
            ("maj",    "Modifié",         100),
        ]
        tf, self.tree = mk_tree(self, cols, col_defs, height=18)
        tf.pack(fill="both", expand=True, padx=20, pady=4)
        self.tree.bind("<Double-1>", lambda e: self._modifier())

        af = tk.Frame(self, bg=C["bg"])
        af.pack(fill="x", padx=20, pady=10)
        mk_btn(af, "✏️ Modifier", self._modifier).pack(side="left", padx=3)
        mk_btn(af, "📄 Générer fiche", self._fiche).pack(side="left", padx=3)
        mk_btn(af, "📁 Dossier", self._dossier).pack(side="left", padx=3)
        mk_btn(af, "🗑️ Supprimer", self._supprimer,
               color=C["danger"]).pack(side="left", padx=3)
        mk_btn(af, "🔄 Rafraîchir", self.refresh,
               color=C["btn3"]).pack(side="right", padx=3)

        self._cache = []

    def _reload_statuts(self):
        self.statut_cb["values"] = ["Tous"] + db.get_statuts_garantie()
        self.refresh()

    def _render_stats(self):
        for w in self.stats_bar.winfo_children():
            w.destroy()
        s = db.get_stats_garanties()
        cards = [
            ("Total", s["Total"], C["header"]),
            ("Ouvertes", s["Ouvertes"], C["warn"]),
            ("Clôturées", s["Clôturées"], C["btn2"]),
        ]
        for attr, n in s["par_attribution"].items():
            cards.append((attr, n, C["nav_sel"]))
        for label, n, col in cards:
            outer = tk.Frame(self.stats_bar, bg=C["border"])
            outer.pack(side="left", padx=5)
            card = tk.Frame(outer, bg=C["surface"])
            card.pack(padx=1, pady=1)
            tk.Frame(card, bg=col, width=3).pack(side="left", fill="y")
            ct = tk.Frame(card, bg=C["surface"])
            ct.pack(side="left", padx=14, pady=6)
            tk.Label(ct, text=str(n), font=F["stat_value"],
                     bg=C["surface"], fg=col).pack(anchor="w")
            tk.Label(ct, text=label, font=F["stat_label"],
                     bg=C["surface"], fg=C["text_muted"]).pack(anchor="w")

    def refresh(self):
        self._render_stats()
        items = db.get_garanties(statut=self.statut_var.get(),
                                  search=self.search_var.get(),
                                  attribution=self.attr_var.get())
        self._cache = list(items)
        rows = []
        for g in self._cache:
            moteur = g["num_serie"] or ""
            if g["marque"]:
                moteur = f"{g['num_serie']} ({g['marque']})"
            rows.append((
                g["num_ems"], g["num_constructeur"] or "—",
                g["client_nom"] or "", moteur,
                g["attribution"], g["statut"],
                g["date_ouverture"] or "—",
                db.fmt_paris_short(g["updated_at"]),
            ))
        fill_tree(self.tree, rows)

    def _sel(self):
        s = self.tree.selection()
        if not s:
            messagebox.showwarning("Sélection",
                                    "Sélectionnez une garantie.")
            return None
        return self._cache[int(s[0])]

    def _modifier(self):
        r = self._sel()
        if r:
            GarantieDialog(self, garantie_id=r["id"], on_save=self.refresh)

    def _fiche(self):
        r = self._sel()
        if not r:
            return
        g = db.get_garantie(garantie_id=r["id"])
        path = gargen.sauvegarder_fiche(g)
        self._ouvrir(path)

    def _dossier(self):
        r = self._sel()
        if not r:
            return
        d = db.GARANTIE_DIR / r["num_ems"]
        d.mkdir(parents=True, exist_ok=True)
        self._ouvrir(d)

    def _supprimer(self):
        r = self._sel()
        if r and messagebox.askyesno(
                "Supprimer",
                f"Supprimer la garantie {r['num_ems']} ?\n\n"
                "(Le dossier sur disque n'est pas supprimé.)"):
            db.delete_garantie(r["id"])
            self.refresh()

    @staticmethod
    def _ouvrir(path):
        path = str(path)
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # noqa
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except OSError as e:
            messagebox.showinfo("Ouvrir", f"Fichier : {path}\n\n{e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOGUE — création / édition d'une garantie
# ═══════════════════════════════════════════════════════════════════════════════
class GarantieDialog(tk.Toplevel):
    def __init__(self, parent, garantie_id=None, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.garantie_id = garantie_id
        self.is_edit = garantie_id is not None
        self.title("Modifier la garantie" if self.is_edit
                   else "Nouvelle garantie moteur")
        self.geometry("700x760")
        self.configure(bg=C["bg"])
        self.grab_set()

        self._moteurs = list(db.get_moteurs())
        self._clients = list(db.get_clients())
        self._moteur_by_ns = {m["num_serie"]: m for m in self._moteurs}
        self._client_by_id = {c["id"]: c for c in self._clients}

        mk_header(self, "Garantie moteur",
                  "   Dossier de garantie constructeur / interne")

        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=24, pady=12)

        tk.Label(body, text="Moteur (N° série) *", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        mrow = tk.Frame(body, bg=C["bg"])
        mrow.pack(fill="x", pady=(2, 2))
        self.moteur_var = tk.StringVar()
        self.moteur_cb = SearchableCombobox(
            mrow, textvariable=self.moteur_var,
            values=[m["num_serie"] for m in self._moteurs], width=40)
        self.moteur_cb.pack(side="left", fill="x", expand=True)
        self.moteur_cb.bind_selected(self._on_moteur)
        mk_btn(mrow, "➕ Moteur", self._nouveau_moteur,
               color=C["btn2"]).pack(side="left", padx=(6, 0))
        self.moteur_info = tk.Label(body, text="", bg=C["bg"],
                                     fg=C["text_muted"], font=F["small"],
                                     anchor="w")
        self.moteur_info.pack(anchor="w", pady=(0, 10))

        row = tk.Frame(body, bg=C["bg"])
        row.pack(fill="x", pady=(0, 10))
        nc = tk.Frame(row, bg=C["bg"])
        nc.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(nc, text="N° garantie constructeur", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.num_constr_var = tk.StringVar()
        ttk.Entry(nc, textvariable=self.num_constr_var, width=28).pack(
            fill="x", pady=(2, 0))
        ne = tk.Frame(row, bg=C["bg"])
        ne.pack(side="left")
        tk.Label(ne, text="N° garantie EMS", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.num_ems_lbl = tk.Label(
            ne, text="(auto à la création)", bg=C["bg_alt"],
            font=F["body_bold"], fg=C["header"], anchor="w",
            relief="groove", width=20, padx=6)
        self.num_ems_lbl.pack(pady=(2, 0), ipady=3)

        row2 = tk.Frame(body, bg=C["bg"])
        row2.pack(fill="x", pady=(0, 10))
        at = tk.Frame(row2, bg=C["bg"])
        at.pack(side="left", padx=(0, 16))
        tk.Label(at, text="Attribution", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.attr_var = tk.StringVar(value=db.GARANTIE_ATTRIBUTION_DEFAULT)
        self.attr_combo = ttk.Combobox(
            at, textvariable=self.attr_var,
            values=db.get_attributions_garantie(), width=18)
        self.attr_combo.pack(pady=(2, 0))
        st = tk.Frame(row2, bg=C["bg"])
        st.pack(side="left", fill="x", expand=True)
        tk.Label(st, text="Statut", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.statut_var = tk.StringVar(value=db.GARANTIE_STATUT_DEFAULT)
        ttk.Combobox(st, textvariable=self.statut_var,
                     values=db.get_statuts_garantie(), width=30,
                     state="readonly").pack(fill="x", pady=(2, 0))

        row3 = tk.Frame(body, bg=C["bg"])
        row3.pack(fill="x", pady=(0, 10))
        do = tk.Frame(row3, bg=C["bg"])
        do.pack(side="left", padx=(0, 12))
        tk.Label(do, text="Date ouverture", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.d_ouv_var = tk.StringVar()
        DateEntry(do, textvariable=self.d_ouv_var, width=14).pack(pady=(2, 0))
        dc = tk.Frame(row3, bg=C["bg"])
        dc.pack(side="left", padx=(0, 12))
        tk.Label(dc, text="Date clôture", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.d_clo_var = tk.StringVar()
        DateEntry(dc, textvariable=self.d_clo_var, width=14).pack(pady=(2, 0))
        mt = tk.Frame(row3, bg=C["bg"])
        mt.pack(side="left")
        tk.Label(mt, text="Montant (€)", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.montant_var = tk.StringVar()
        ttk.Entry(mt, textvariable=self.montant_var, width=12).pack(pady=(2, 0))

        tk.Label(body, text="Description du dossier *", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.txt_desc = tk.Text(body, height=5, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", bd=1,
                                 padx=6, pady=4)
        self.txt_desc.pack(fill="x", pady=(2, 10))

        tk.Label(body, text="Commentaires / Suivi", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w")
        self.txt_comm = tk.Text(body, height=4, font=("Segoe UI", 10),
                                 wrap="word", relief="solid", bd=1,
                                 padx=6, pady=4)
        self.txt_comm.pack(fill="x", pady=(2, 4))

        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(side="bottom", pady=12)
        mk_btn(bf, "💾 Enregistrer",
               lambda: self._save(False)).pack(side="left", padx=6)
        mk_btn(bf, "📄 Enregistrer + Fiche",
               lambda: self._save(True)).pack(side="left", padx=6)
        mk_btn(bf, "Annuler", self.destroy,
               color=C["btn3"]).pack(side="left", padx=6)

        if self.is_edit:
            self.after(50, self._load)

    def _on_moteur(self, _e=None):
        m = self._moteur_by_ns.get(self.moteur_var.get())
        if m:
            c = self._client_by_id.get(m["client_id"])
            cl = c["nom"] if c else "—"
            mk = (f"{m['marque']} {m['ref_constructeur']}".strip()
                  if m["marque"] else (m["ref_constructeur"]
                                       or m["type_moteur"]))
            self.moteur_info.config(
                text=f"→ Client : {cl}   |   {mk}   |   "
                     f"Navire : {m['navire'] or '—'}")
            # Pré-remplir l'attribution avec la marque du moteur
            marque = (m["marque"] or "").strip()
            if marque and self.attr_var.get() in (
                    "", db.GARANTIE_ATTRIBUTION_DEFAULT):
                self.attr_var.set(marque)

    def _nouveau_moteur(self):
        """Ouvre le formulaire moteur (même forme que l'app principale)."""
        def _after(num_serie=None):
            # Recharger les listes moteurs/clients
            self._moteurs = list(db.get_moteurs())
            self._clients = list(db.get_clients())
            self._moteur_by_ns = {m["num_serie"]: m for m in self._moteurs}
            self._client_by_id = {c["id"]: c for c in self._clients}
            self.moteur_cb.set_values([m["num_serie"]
                                       for m in self._moteurs])
            # La nouvelle marque éventuelle enrichit la liste d'attributions
            self.attr_combo["values"] = db.get_attributions_garantie()
            # Auto-sélectionner le moteur fraîchement créé
            if num_serie and num_serie in self._moteur_by_ns:
                self.moteur_cb.set(num_serie)
                self._on_moteur()
        MoteurDialog(self, on_save=_after)

    def _load(self):
        g = db.get_garantie(garantie_id=self.garantie_id)
        if not g:
            return
        self.num_ems_lbl.config(text=row_get(g, "num_ems"))
        self.num_constr_var.set(row_get(g, "num_constructeur"))
        m = next((x for x in self._moteurs
                  if x["id"] == row_get(g, "moteur_id")), None)
        if m:
            self.moteur_cb.set(m["num_serie"])
            self._on_moteur()
        self.attr_var.set(row_get(g, "attribution",
                                   db.GARANTIE_ATTRIBUTION_DEFAULT))
        self.statut_var.set(row_get(g, "statut",
                                     db.GARANTIE_STATUT_DEFAULT))
        self.d_ouv_var.set(row_get(g, "date_ouverture"))
        self.d_clo_var.set(row_get(g, "date_cloture"))
        self.montant_var.set(row_get(g, "montant"))
        self.txt_desc.delete("1.0", "end")
        self.txt_desc.insert("1.0", row_get(g, "description"))
        self.txt_comm.delete("1.0", "end")
        self.txt_comm.insert("1.0", row_get(g, "commentaires"))

    def _save(self, generer=False):
        ns = self.moteur_var.get().strip()
        desc = self.txt_desc.get("1.0", "end").strip()
        if not ns or not desc:
            messagebox.showwarning(
                "Champs manquants",
                "Le moteur (N° série) et la description sont obligatoires.")
            return
        m = self._moteur_by_ns.get(ns)
        if not m:
            messagebox.showwarning(
                "Moteur inconnu",
                f"'{ns}' ne correspond à aucun moteur enregistré.\n\n"
                "Saisissez les moteurs depuis l'application principale.")
            return
        for lbl, v in [("ouverture", self.d_ouv_var.get().strip()),
                       ("clôture", self.d_clo_var.get().strip())]:
            if v and not DateEntry.is_valid(v):
                messagebox.showwarning(
                    "Date invalide",
                    f"Date de {lbl} invalide : '{v}'\nFormat : JJ/MM/AAAA")
                return
        data = {
            "num_constructeur": self.num_constr_var.get().strip(),
            "moteur_id": m["id"],
            "client_id": m["client_id"],
            "attribution": self.attr_var.get(),
            "statut": self.statut_var.get(),
            "date_ouverture": self.d_ouv_var.get().strip(),
            "date_cloture": self.d_clo_var.get().strip(),
            "montant": self.montant_var.get().strip(),
            "description": desc,
            "commentaires": self.txt_comm.get("1.0", "end").strip(),
        }
        if self.is_edit:
            db.update_garantie(self.garantie_id, data)
            num = db.get_garantie(garantie_id=self.garantie_id)["num_ems"]
        else:
            gid, num = db.create_garantie(data)
            self.garantie_id = gid
            self.is_edit = True

        if self.on_save:
            self.on_save()

        if generer:
            g = db.get_garantie(garantie_id=self.garantie_id)
            path = gargen.sauvegarder_fiche(g)
            messagebox.showinfo("Fiche générée",
                                f"✅ {num}\nFiche enregistrée :\n{path}")
            GarantiesApp._ouvrir(path)
            self.destroy()
        else:
            messagebox.showinfo("Enregistré",
                                f"✅ Garantie {num} enregistrée.")
            self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOGUE — client (même forme que l'app principale)
# ═══════════════════════════════════════════════════════════════════════════════
class ClientDialog(tk.Toplevel):
    def __init__(self, parent, client=None, on_save=None):
        super().__init__(parent)
        self.client = client
        self.on_save = on_save
        self.title("Nouveau client" if not client
                   else f"Modifier – {client['nom']}")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.grab_set()
        self.v = {k: tk.StringVar(value=client.get(k, "") if client else "")
                  for k in ["nom", "contact", "email", "telephone", "adresse"]}
        f = tk.Frame(self, bg=C["bg"])
        f.pack(padx=24, pady=18)
        for i, (key, lbl) in enumerate([
                ("nom", "Nom *"), ("contact", "Contact"),
                ("email", "Email"), ("telephone", "Téléphone"),
                ("adresse", "Adresse")]):
            tk.Label(f, text=lbl, bg=C["bg"], font=F["body"],
                     anchor="e", width=14).grid(
                row=i, column=0, sticky="e", padx=(0, 6), pady=4)
            ttk.Entry(f, textvariable=self.v[key], width=36).grid(
                row=i, column=1, pady=4)
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=12)
        mk_btn(bf, "💾 Enregistrer", self._save).pack(side="left", padx=8)
        mk_btn(bf, "Annuler", self.destroy,
               color=C["btn3"]).pack(side="left", padx=8)

    def _save(self):
        nom = self.v["nom"].get().strip()
        if not nom:
            messagebox.showwarning("Champ requis",
                                    "Le nom est obligatoire.")
            return
        email = self.v["email"].get().strip()
        if (email and hasattr(db, "email_looks_valid")
                and not db.email_looks_valid(email)):
            if not messagebox.askyesno(
                    "Format email douteux",
                    f"L'email '{email}' semble mal formé.\n\n"
                    "Voulez-vous quand même l'enregistrer tel quel ?"):
                return
        new_id = db.upsert_client(
            {k: self.v[k].get().strip() for k in self.v},
            client_id=self.client["id"] if self.client else None)
        if self.on_save:
            try:
                self.on_save(nom)
            except TypeError:
                self.on_save()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOGUE — moteur (même forme que l'app principale, 14 champs)
# ═══════════════════════════════════════════════════════════════════════════════
class MoteurDialog(tk.Toplevel):
    FIELDS = [
        ("num_serie",         "N° Série *"),
        ("navire",            "Navire / Site"),
        ("machine",           "Machine"),
        ("type_moteur",       "Type moteur / inverseur"),
        ("marque",            "Marque"),
        ("ref_constructeur",  "Réf. Constructeur"),
        ("cylindree",         "Cylindrée"),
        ("famille",           "Famille"),
        ("application",       "Application"),
        ("typologie",         "Typologie"),
        ("collection",        "Collection"),
        ("code_affaire",      "Code Affaire"),
        ("date_mise_service", "Mise en service"),
        ("duree_garantie",    "Garantie (mois)"),
    ]

    def __init__(self, parent, moteur=None, on_save=None):
        super().__init__(parent)
        self.moteur = moteur
        self.on_save = on_save
        self.title("Nouveau moteur" if not moteur
                   else f"Modifier – {moteur['num_serie']}")
        self.resizable(False, False)
        self.configure(bg=C["bg"])
        self.grab_set()
        self._clients = list(db.get_clients())
        self.client_var = tk.StringVar()
        if moteur and moteur.get("client_id"):
            c = next((x for x in self._clients
                      if x["id"] == moteur["client_id"]), None)
            if c:
                self.client_var.set(c["nom"])

        mk_header(self, "Moteur",
                  "   Création / modification d'un moteur du parc")

        f = tk.Frame(self, bg=C["bg"])
        f.pack(padx=24, pady=18)

        # Ligne client + bouton "+ Client"
        tk.Label(f, text="Client *", bg=C["bg"], font=F["body"],
                 anchor="e", width=22).grid(
            row=0, column=0, sticky="e", padx=(0, 6), pady=4)
        crow = tk.Frame(f, bg=C["bg"])
        crow.grid(row=0, column=1, pady=4, sticky="w")
        self.client_cb = ttk.Combobox(
            crow, textvariable=self.client_var,
            values=[c["nom"] for c in self._clients],
            width=26, state="readonly")
        self.client_cb.pack(side="left")
        mk_btn(crow, "➕", self._nouveau_client,
               color=C["btn2"]).pack(side="left", padx=(6, 0))

        self.v = {k: tk.StringVar(
            value=(moteur.get(k, "") if moteur else ""))
            for k, _ in self.FIELDS}
        for i, (key, lbl) in enumerate(self.FIELDS, start=1):
            tk.Label(f, text=lbl, bg=C["bg"], font=F["body"],
                     anchor="e", width=22).grid(
                row=i, column=0, sticky="e", padx=(0, 6), pady=4)
            if key == "date_mise_service":
                DateEntry(f, textvariable=self.v[key], width=32).grid(
                    row=i, column=1, pady=4, sticky="w")
            else:
                ttk.Entry(f, textvariable=self.v[key], width=34).grid(
                    row=i, column=1, pady=4, sticky="w")
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=12)
        mk_btn(bf, "💾 Enregistrer", self._save).pack(side="left", padx=8)
        mk_btn(bf, "Annuler", self.destroy,
               color=C["btn3"]).pack(side="left", padx=8)

    def _nouveau_client(self):
        def _after(nom=None):
            self._clients = list(db.get_clients())
            self.client_cb["values"] = [c["nom"] for c in self._clients]
            if nom:
                self.client_var.set(nom)
        ClientDialog(self, on_save=_after)

    def _save(self):
        ns = self.v["num_serie"].get().strip()
        cn = self.client_var.get()
        if not ns or not cn:
            messagebox.showwarning(
                "Champs requis",
                "N° de série et client sont obligatoires.")
            return
        d_svc = self.v["date_mise_service"].get().strip()
        if d_svc and not DateEntry.is_valid(d_svc):
            messagebox.showwarning(
                "Date invalide",
                f"Date de mise en service invalide : '{d_svc}'\n"
                "Format attendu : JJ/MM/AAAA")
            return
        client = next((c for c in self._clients
                       if c["nom"] == cn), None)
        db.upsert_moteur(
            {"client_id": client["id"] if client else "",
             **{k: self.v[k].get().strip() for k in self.v}},
            moteur_id=self.moteur["id"] if self.moteur else None)
        if self.on_save:
            try:
                self.on_save(ns)
            except TypeError:
                self.on_save()
        self.destroy()


# ═══════════════════════════════════════════════════════════════════════════════
#  DIALOGUE — configuration des statuts
# ═══════════════════════════════════════════════════════════════════════════════
class StatutsDialog(tk.Toplevel):
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Statuts de garantie")
        self.geometry("420x500")
        self.configure(bg=C["bg"])
        self.grab_set()

        tk.Label(self, text="Statuts de garantie configurables",
                 bg=C["bg"], font=F["h2"], fg=C["header"]).pack(pady=(14, 4))
        tk.Label(self,
                 text="Ces statuts apparaissent dans le suivi des garanties.",
                 bg=C["bg"], font=F["small"],
                 fg=C["text_muted"]).pack()

        lf = tk.Frame(self, bg=C["bg"])
        lf.pack(fill="both", expand=True, padx=16, pady=10)
        self.lst = tk.Listbox(lf, font=("Segoe UI", 10), height=12,
                              selectbackground=C["nav_sel"],
                              selectforeground="white")
        self.lst.pack(fill="both", expand=True)

        af = tk.Frame(self, bg=C["bg"])
        af.pack(fill="x", padx=16, pady=(0, 6))
        self.input_var = tk.StringVar()
        ttk.Entry(af, textvariable=self.input_var, width=28).pack(
            side="left", padx=(0, 4))
        mk_btn(af, "➕ Ajouter", self._add).pack(side="left")

        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=10)
        mk_btn(bf, "✏️ Renommer", self._rename).pack(side="left", padx=4)
        mk_btn(bf, "🗑️ Supprimer", self._del,
               color=C["danger"]).pack(side="left", padx=4)
        mk_btn(bf, "Fermer", self._close,
               color=C["btn3"]).pack(side="left", padx=4)
        self._refresh()

    def _refresh(self):
        self.lst.delete(0, "end")
        for s in db.get_statuts_garantie():
            self.lst.insert("end", s)

    def _add(self):
        v = self.input_var.get().strip()
        if not v:
            return
        if not db.add_statut_garantie(v):
            messagebox.showwarning("Doublon",
                                    f"Le statut '{v}' existe déjà.")
            return
        self.input_var.set("")
        self._refresh()

    def _selected(self):
        s = self.lst.curselection()
        if not s:
            messagebox.showwarning("Sélection",
                                    "Sélectionnez un statut.")
            return None
        return self.lst.get(s[0])

    def _rename(self):
        cur = self._selected()
        if not cur:
            return
        new = simpledialog.askstring(
            "Renommer", f"Nouveau nom pour '{cur}' :",
            parent=self, initialvalue=cur)
        if new and new.strip() and new != cur:
            if db.update_statut_garantie(cur, new.strip()):
                self._refresh()
            else:
                messagebox.showwarning("Erreur",
                                        "Ce nom existe déjà.")

    def _del(self):
        cur = self._selected()
        if not cur:
            return
        if messagebox.askyesno(
                "Supprimer",
                f"Supprimer le statut '{cur}' ?\n\n"
                "(Les garanties existantes gardent leur libellé.)"):
            db.delete_statut_garantie(cur)
            self._refresh()

    def _close(self):
        if self.on_save:
            self.on_save()
        self.destroy()


# ─── Lancement ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = GarantiesApp()
    app.mainloop()

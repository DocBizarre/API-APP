#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
  EMS — Gestion des pièces détachées (stock)
═══════════════════════════════════════════════════════════════════════════════
 
Application autonome de gestion du catalogue des pièces détachées.
Calquée sur l'app Gestion de parc des moteurs.
 
Fonctionnalités :
  • Listing avec recherche temps réel (ref + libellé + marque)
  • Création / Modification / Suppression
  • Import CSV / Excel avec aperçu et gestion des doublons
  • Pagination implicite : limite à 500 résultats max (suffisant pour l'UI)
 
Peut être lancée :
  • via ems_launcher.py (automatique)
  • directement : python app_pieces.py
═══════════════════════════════════════════════════════════════════════════════
"""
import csv
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox
 
# ─── Résolution des dépendances ──────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
# Ajouter la racine du projet au PYTHONPATH pour importer ems_client
for parent in (_HERE, _HERE.parent):
    if (parent / "ems_client").is_dir():
        if str(parent) not in sys.path:
            sys.path.insert(0, str(parent))
        break
 
try:
    from ems_client import api as db
    from shared.bon_generator import apply_icon
    from shared.version import __version__
except ImportError as e:
    _r = tk.Tk(); _r.withdraw()
    messagebox.showerror("Dépendance manquante",
        "Impossible de trouver 'ems_client'.\n\n"
        "Placez ce script à côté du dossier 'ems_client' du projet EMS.\n\n"
        f"Détail : {e}")
    sys.exit(1)

# Vérification connexion API avant d'afficher l'UI
_ok, _msg = db.check_api()
if not _ok:
    _r = tk.Tk(); _r.withdraw()
    if not messagebox.askokcancel(
        "Serveur introuvable",
        f"{_msg}\n\nVérifiez que le serveur EMS est démarré.\n\n"
        "Continuer quand même ?"):
        sys.exit(0)
 
 
# ─── Constantes UI ───────────────────────────────────────────────────────────
C = {
    "bg":        "#f5f7fa",
    "surface":   "#ffffff",
    "header":    "#353a41",
    "accent":    "#c62828",
    "text":      "#1a2332",
    "muted":     "#6b7785",
    "border":    "#d0d7de",
    "btn":       "#53595F",
    "btn_hover": "#404449",
    "btn2":      "#1e7e3e",
    "btn3":      "#6b7785",
    "danger":    "#c62828",
    "warn":      "#f9a825",
}
F = {
    "header":     ("Segoe UI", 14, "bold"),
    "subheader":  ("Segoe UI", 10),
    "body":       ("Segoe UI", 10),
    "body_bold":  ("Segoe UI", 10, "bold"),
    "small":      ("Segoe UI", 9),
    "btn":        ("Segoe UI", 10, "bold"),
}
 
 
# ─── Helpers UI ──────────────────────────────────────────────────────────────
def mk_header(parent, title, subtitle=""):
    head = tk.Frame(parent, bg=C["header"], height=64)
    head.pack(fill="x")
    head.pack_propagate(False)
    tk.Frame(head, bg=C["accent"], width=5).pack(side="left", fill="y")
    inner = tk.Frame(head, bg=C["header"])
    inner.pack(side="left", fill="both", expand=True, padx=18)
    tk.Label(inner, text=title, font=("Segoe UI", 16, "bold"),
             bg=C["header"], fg="white").pack(anchor="w", pady=(10, 0))
    if subtitle:
        tk.Label(inner, text=subtitle, font=("Segoe UI", 10),
                 bg=C["header"], fg="#aac4e8").pack(anchor="w")
 
 
def mk_btn(parent, text, cmd, color=None, **kw):
    bg = color or C["btn"]
    btn = tk.Button(parent, text=text, command=cmd,
                     bg=bg, fg="white", font=F["btn"],
                     relief="flat", bd=0, padx=12, pady=6,
                     cursor="hand2",
                     activebackground=C["btn_hover"],
                     activeforeground="white", **kw)
    return btn
 
 
def mk_tree(parent, cols, col_defs, height=18):
    tf = tk.Frame(parent, bg=C["bg"])
    vsb = ttk.Scrollbar(tf, orient="vertical")
    tree = ttk.Treeview(tf, columns=cols, show="headings",
                         height=height, yscrollcommand=vsb.set,
                         selectmode="extended")
    vsb.config(command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    for cd in col_defs:
        cid, lbl, width = cd[0], cd[1], cd[2]
        anchor = cd[3] if len(cd) > 3 else "w"
        tree.heading(cid, text=lbl)
        tree.column(cid, width=width, anchor=anchor)
    return tf, tree


def _parse_prix(val) -> float:
    """Convertit une valeur (str Excel/CSV ou nombre) en prix float. 0 si vide/invalide.

    Gère les formats FR/BE courants : "1234.56", "1234,56", "1 234,56 €"
    (espace normal ou insécable comme séparateur de milliers) et
    "1.234,56" (point comme séparateur de milliers, virgule décimale)."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = (str(val).strip().replace("€", "")
         .replace("\xa0", "").replace(" ", "").replace(" ", ""))
    if not s:
        return 0.0
    if "," in s and "." in s:
        # Les deux séparateurs présents : le dernier rencontré est la
        # décimale, l'autre est un séparateur de milliers à supprimer.
        if s.rindex(",") > s.rindex("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def _fmt_prix(val) -> str:
    """Formate un prix pour l'affichage (ex: 12.5 -> '12.50 €')."""
    try:
        v = float(val or 0)
    except (TypeError, ValueError):
        v = 0.0
    if not v:
        return ""
    return f"{v:.2f} €"


# ═════════════════════════════════════════════════════════════════════════════
#   PiecesApp — App principale
# ═════════════════════════════════════════════════════════════════════════════
class PiecesApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.withdraw()
        apply_icon(self)
        self.title(f"EMS — Pièces détachées  v{__version__}")
        self.geometry("1100x650")
        self.configure(bg=C["bg"])
        self._init_styles()
        self._build()
        self._refresh_count()
        self.update_idletasks()
        self.deiconify()

    def _init_styles(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Treeview", font=F["body"], rowheight=24,
                    background=C["surface"], fieldbackground=C["surface"])
        s.configure("Treeview.Heading", font=F["body_bold"],
                    background=C["header"], foreground="white",
                    relief="flat")
        s.map("Treeview.Heading",
              background=[("active", C["header"])],
              foreground=[("active", "white")])
 
    def _build(self):
        mk_header(self, "Pièces détachées",
                   "Catalogue : recherche, ajout, modification, import")
 
        # ── Barre de recherche ────────────────────────────────────────────────
        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=10)
 
        tk.Label(sf, text="🔍 Recherche :", bg=C["bg"],
                 font=F["body"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._on_search_change())
        ttk.Entry(sf, textvariable=self.search_var, width=30,
                   font=F["body"]).pack(side="left", padx=6)
 
        self.ref_only_var = tk.IntVar(value=0)
        tk.Checkbutton(sf, text="Référence uniquement",
                       variable=self.ref_only_var,
                       bg=C["bg"], font=F["small"], fg=C["muted"],
                       command=self._do_search).pack(side="left", padx=(8, 0))
 
        # Compteur à droite
        self.count_lbl = tk.Label(sf, text="", bg=C["bg"],
                                    font=F["small"], fg=C["muted"])
        self.count_lbl.pack(side="right")
 
        # Boutons à droite
        mk_btn(sf, "➕ Nouvelle pièce",
               lambda: PieceDialog(self, on_save=self._do_search)).pack(
            side="right", padx=(6, 12))
        mk_btn(sf, "📥 Importer CSV/Excel",
               lambda: ImportPiecesDialog(self, on_save=self._do_search),
               color=C["btn2"]).pack(side="right", padx=6)
 
        # ── Tableau ───────────────────────────────────────────────────────────
        cols = ("reference", "libelle", "marque", "prix_vente", "notes")
        col_defs = [
            ("reference",  "Référence",   140),
            ("libelle",    "Libellé",     380),
            ("marque",     "Marque",      120),
            ("prix_vente", "Prix vente",  90, "e"),
            ("notes",      "Notes",       200),
        ]
        tf, self.tree = mk_tree(self, cols, col_defs, height=22)
        tf.pack(fill="both", expand=True, padx=20, pady=4)
        self.tree.bind("<Double-1>", lambda e: self._modifier())

        # Message d'aide quand vide
        self._show_help_message()

        # ── Boutons d'action ──────────────────────────────────────────────────
        af = tk.Frame(self, bg=C["bg"])
        af.pack(fill="x", padx=20, pady=10)
        mk_btn(af, "✏️ Modifier", self._modifier).pack(side="left", padx=4)
        mk_btn(af, "🗑️ Supprimer", self._supprimer,
               color=C["danger"]).pack(side="left", padx=4)
        self.sel_info = tk.Label(af, text="", bg=C["bg"],
                                   fg=C["muted"], font=F["small"])
        self.sel_info.pack(side="left", padx=(12, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_select_change)

        self._cache = []           # liste de pieces actuellement affichees
        self._search_after_id = None
 
    # ── Recherche temps réel (avec debounce 250ms) ───────────────────────────
    def _on_search_change(self):
        if self._search_after_id:
            self.after_cancel(self._search_after_id)
        # Attendre 250ms après la dernière frappe avant de lancer la recherche
        self._search_after_id = self.after(250, self._do_search)
 
    def _do_search(self):
        self._search_after_id = None
        q = self.search_var.get().strip()
        if len(q) < 2 and not q:
            self._show_help_message()
            return
        if len(q) < 2:
            self._show_help_message(f"Tapez au moins 2 caractères "
                                     f"(actuel : {len(q)})")
            return
        try:
            pieces = db.get_pieces(search=q,
                                    ref_only=bool(self.ref_only_var.get()),
                                    limit=500)
        except Exception as e:
            messagebox.showerror("Erreur", f"Recherche impossible :\n{e}")
            return
 
        self._cache = list(pieces)
        self._fill_tree()
        self._refresh_count()
 
    def _show_help_message(self, msg=None):
        """Affiche un message d'aide dans le tableau."""
        self.tree.delete(*self.tree.get_children())
        self._cache = []
        if msg is None:
            msg = "💡 Tapez au moins 2 caractères pour rechercher dans le catalogue"
        self.tree.insert("", "end", iid="help",
                          values=("—", msg, "", "", ""), tags=("help",))
        self.tree.tag_configure("help", foreground=C["muted"])
 
    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self._cache:
            self.tree.insert("", "end",
                              values=("—", "(aucun résultat)", "", "", ""))
            return
        for i, p in enumerate(self._cache):
            self.tree.insert("", "end", iid=str(i),
                              values=(p["reference"],
                                      p["libelle"],
                                      p.get("marque", ""),
                                      _fmt_prix(p.get("prix_vente", 0)),
                                      p.get("notes", "")))
        # Si on a 500 résultats, prévenir l'utilisateur qu'il y en a peut-être plus
        if len(self._cache) >= 500:
            self.count_lbl.config(
                text=f"⚠ {len(self._cache)}+ résultats (affinez la recherche)",
                fg=C["warn"])
        else:
            self.count_lbl.config(text=f"{len(self._cache)} résultat(s)",
                                    fg=C["muted"])
 
    def _refresh_count(self):
        """Met à jour le compteur total en base."""
        try:
            total = db.count_pieces()
            self.count_lbl.config(text=f"{total:,} pièces en base".replace(",", " "),
                                   fg=C["muted"])
        except Exception:
            self.count_lbl.config(text="(connexion API impossible)",
                                   fg=C["danger"])
 
    def _on_select_change(self, _ev=None):
        sel = self.tree.selection()
        if not sel or "help" in sel:
            self.sel_info.config(text="")
            return
        n = len(sel)
        if n == 1:
            self.sel_info.config(text="")
        else:
            self.sel_info.config(
                text=f"{n} pièces sélectionnées "
                     "(Ctrl/Maj-clic pour ajuster)")
 
    def _sel(self):
        sel = self.tree.selection()
        if not sel or "help" in sel:
            messagebox.showwarning("Sélection",
                                    "Sélectionnez une pièce.")
            return None
        try:
            return self._cache[int(sel[0])]
        except (ValueError, IndexError):
            return None
 
    def _sel_multi(self):
        sel = self.tree.selection()
        if not sel or "help" in sel:
            messagebox.showwarning(
                "Sélection",
                "Sélectionnez une ou plusieurs pièces.\n"
                "(Ctrl-clic ou Maj-clic pour en sélectionner plusieurs)")
            return []
        out = []
        for s in sel:
            try:
                out.append(self._cache[int(s)])
            except (ValueError, IndexError):
                continue
        return out
 
    def _modifier(self):
        p = self._sel()
        if p:
            PieceDialog(self, piece=dict(p), on_save=self._do_search)
 
    def _supprimer(self):
        pieces = self._sel_multi()
        if not pieces:
            return
        n = len(pieces)
        if n == 1:
            msg = (f"Supprimer la pièce « {pieces[0]['reference']} » ?\n\n"
                   "Cette action est irréversible.")
        else:
            apercu = "\n".join(f"  • {p['reference']}" for p in pieces[:8])
            if n > 8:
                apercu += f"\n  … et {n - 8} autre(s)"
            msg = (f"⚠ Vous allez supprimer {n} pièces :\n\n"
                   f"{apercu}\n\n"
                   "Cette action est IRRÉVERSIBLE. Continuer ?")
        if not messagebox.askyesno("Confirmer la suppression", msg,
                                    icon="warning"):
            return
        echecs = []
        for p in pieces:
            try:
                db.delete_piece(p["id"])
            except Exception as e:
                echecs.append(f"{p['reference']} : {e}")
        self._do_search()
        if echecs:
            messagebox.showerror(
                "Suppression partielle",
                f"{n - len(echecs)}/{n} pièces supprimées.\n\n"
                "Échecs :\n" + "\n".join(echecs[:10]))
        else:
            messagebox.showinfo(
                "Suppression effectuée",
                f"✅ {n} pièce(s) supprimée(s).")
 
 
# ═════════════════════════════════════════════════════════════════════════════
#   PieceDialog — Création / Modification
# ═════════════════════════════════════════════════════════════════════════════
class PieceDialog(tk.Toplevel):
    def __init__(self, parent, piece=None, on_save=None):
        super().__init__(parent)
        self.piece = piece
        self.on_save = on_save
        self.title("Modifier la pièce" if piece else "Nouvelle pièce")
        self.configure(bg=C["bg"])
        self.geometry("520x460")
        self.resizable(False, True)
        self.grab_set()

        mk_header(self, "Pièce détachée",
                   "Catalogue de stock")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=24, pady=18)

        tab_general = tk.Frame(nb, bg=C["bg"], padx=16, pady=14)
        tab_prix = tk.Frame(nb, bg=C["bg"], padx=16, pady=14)
        nb.add(tab_general, text="Général")
        nb.add(tab_prix, text="Prix")

        self.v = {}
        champs = [
            ("reference", "Référence *", 30),
            ("libelle",   "Libellé",     50),
            ("marque",    "Marque",      30),
            ("notes",     "Notes",       50),
        ]
        for key, label, width in champs:
            tk.Label(tab_general, text=label, bg=C["bg"], font=F["body_bold"],
                     anchor="w").pack(anchor="w", pady=(6, 2))
            v = tk.StringVar(value=(piece or {}).get(key, ""))
            ttk.Entry(tab_general, textvariable=v, width=width,
                       font=F["body"]).pack(fill="x")
            self.v[key] = v

        tk.Label(tab_prix, text="Prix de vente (€)", bg=C["bg"],
                 font=F["body_bold"], anchor="w").pack(anchor="w", pady=(6, 2))
        prix_val = (piece or {}).get("prix_vente", 0) or ""
        v_prix = tk.StringVar(value=str(prix_val) if prix_val else "")
        ttk.Entry(tab_prix, textvariable=v_prix, width=20,
                   font=F["body"]).pack(anchor="w")
        self.v["prix_vente"] = v_prix

        # Boutons
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=14)
        mk_btn(bf, "💾 Enregistrer", self._save).pack(side="left", padx=6)
        mk_btn(bf, "Annuler", self.destroy,
               color=C["btn3"]).pack(side="left", padx=6)

    def _save(self):
        ref = self.v["reference"].get().strip()
        if not ref:
            messagebox.showwarning("Référence requise",
                                    "La référence est obligatoire.",
                                    parent=self)
            return
        data = {k: v.get().strip() for k, v in self.v.items()
                 if k != "prix_vente"}
        data["prix_vente"] = _parse_prix(self.v["prix_vente"].get())
        try:
            db.upsert_piece(data,
                             piece_id=self.piece["id"] if self.piece else None)
        except Exception as e:
            messagebox.showerror("Erreur",
                                  f"Impossible d'enregistrer :\n{e}",
                                  parent=self)
            return
        if self.on_save:
            if not self.piece:
                try:
                    self.master.search_var.set(data["reference"])
                except AttributeError:
                    pass
            self.on_save()
        self.destroy()


# ═════════════════════════════════════════════════════════════════════════════
#   ImportPiecesDialog — Import CSV/Excel
# ═════════════════════════════════════════════════════════════════════════════
class ImportPiecesDialog(tk.Toplevel):
    # Mots-clés pour deviner automatiquement la correspondance des colonnes
    _KEYWORDS = {
        "reference": ["référence", "reference", "ref", "code", "code article",
                      "code produit", "codearticle", "sku", "id"],
        "libelle":   ["libellé", "libelle", "désignation", "designation",
                      "description", "nom", "produit", "article"],
        "marque":    ["marque", "brand", "fabricant", "fournisseur"],
        "prix_achat": ["prix achat", "prix d'achat", "prix d achat",
                       "cout", "coût", "prix fournisseur", "pa"],
        "prix_vente": ["prix vente", "prix de vente", "pv", "tarif",
                       "montant", "prix ttc", "prix ht", "prix"],
    }
    # Ordre de devinette : du plus spécifique au plus générique, pour éviter
    # qu'une colonne "Prix d'achat" soit devinée comme "Prix de vente" (le
    # mot-clé générique "prix" ne doit s'appliquer qu'en dernier recours).
    _ORDRE_DEVINETTE = ["reference", "libelle", "marque",
                        "prix_achat", "prix_vente"]
    _CHAMPS = [
        ("reference",  "Référence *",   True),
        ("libelle",    "Libellé",       False),
        ("marque",     "Marque",        False),
        ("prix_achat", "Prix d'achat",  False),
        ("prix_vente", "Prix de vente", False),
    ]
    _IGNORER = "(ignorer)"

    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Importer des pièces depuis CSV/Excel")
        self.configure(bg=C["bg"])
        self.geometry("820x700")
        self.grab_set()

        mk_header(self, "Import en masse",
                   "Fait correspondre les colonnes du fichier, quel que "
                   "soit leur ordre")

        # ── Sélection du fichier ──────────────────────────────────────────────
        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=10)
        tk.Label(sf, text="Fichier :", bg=C["bg"],
                 font=F["body_bold"]).pack(side="left")
        self.path_var = tk.StringVar(value="(aucun fichier sélectionné)")
        tk.Label(sf, textvariable=self.path_var, bg=C["bg"],
                 font=F["body"], fg=C["muted"]).pack(side="left", padx=6)
        mk_btn(sf, "📁 Choisir...", self._choose_file).pack(side="right")

        # ── Ligne d'en-tête ? ─────────────────────────────────────────────────
        hf = tk.Frame(self, bg=C["bg"])
        hf.pack(fill="x", padx=20, pady=(0, 4))
        self.has_header_var = tk.IntVar(value=1)
        tk.Checkbutton(hf, text="La 1ère ligne du fichier contient les "
                                 "en-têtes de colonnes",
                       variable=self.has_header_var,
                       command=self._on_mapping_changed,
                       bg=C["bg"], font=F["small"]).pack(anchor="w")

        # ── Correspondance des colonnes ──────────────────────────────────────
        tk.Label(self, text="Correspondance des colonnes :", bg=C["bg"],
                 font=F["body_bold"]).pack(anchor="w", padx=20, pady=(6, 2))
        self.map_frame = tk.Frame(self, bg=C["bg"])
        self.map_frame.pack(fill="x", padx=20, pady=(0, 6))
        self.map_vars = {}
        self._display_to_index = {}
        self._no_mapping_lbl = tk.Label(
            self.map_frame,
            text="Choisissez d'abord un fichier pour configurer la "
                 "correspondance des colonnes.",
            bg=C["bg"], font=F["small"], fg=C["muted"])
        self._no_mapping_lbl.pack(anchor="w")

        # ── Options ───────────────────────────────────────────────────────────
        of = tk.Frame(self, bg=C["bg"])
        of.pack(fill="x", padx=20, pady=4)
        self.skip_doublons_var = tk.IntVar(value=1)
        tk.Checkbutton(of, text="Ignorer les références déjà en base "
                                 "(complète les champs vides sans écraser "
                                 "les existants — sinon mise à jour complète)",
                       variable=self.skip_doublons_var,
                       bg=C["bg"], font=F["small"]).pack(anchor="w")

        # ── Aperçu ────────────────────────────────────────────────────────────
        tk.Label(self, text="Aperçu (10 premières lignes) :",
                 bg=C["bg"], font=F["body_bold"]).pack(anchor="w", padx=20,
                                                        pady=(10, 4))
        cols = ("ref", "lib", "marque", "prix_achat", "prix")
        col_defs = [("ref", "Référence", 140), ("lib", "Libellé", 290),
                    ("marque", "Marque", 110),
                    ("prix_achat", "Prix achat", 90, "e"),
                    ("prix", "Prix vente", 90, "e")]
        tf, self.preview_tree = mk_tree(self, cols, col_defs, height=8)
        tf.pack(fill="both", expand=True, padx=20)

        self.info_lbl = tk.Label(self, text="", bg=C["bg"],
                                   font=F["small"], fg=C["muted"], wraplength=760)
        self.info_lbl.pack(anchor="w", padx=20, pady=4)

        # ── Boutons ───────────────────────────────────────────────────────────
        bf = tk.Frame(self, bg=C["bg"])
        bf.pack(pady=14)
        self.btn_import = mk_btn(bf, "✓ Lancer l'import",
                                   self._do_import, color=C["btn2"])
        self.btn_import.pack(side="left", padx=6)
        self.btn_import.config(state="disabled")
        mk_btn(bf, "Annuler", self.destroy,
               color=C["btn3"]).pack(side="left", padx=6)

        self._raw_rows = []          # toutes les lignes du fichier, brutes
        self._pieces_to_import = []

    # ── Lecture brute (sans supposer l'ordre des colonnes) ───────────────────
    def _choose_file(self):
        path = filedialog.askopenfilename(
            title="Choisir un fichier CSV ou Excel",
            filetypes=[("Excel / CSV", "*.xlsx *.xls *.csv *.tsv"),
                       ("Tous les fichiers", "*.*")],
            parent=self)
        if not path:
            return
        self.path_var.set(Path(path).name)
        try:
            self._raw_rows = self._lire_brut(Path(path))
        except Exception as e:
            messagebox.showerror("Lecture impossible",
                                  f"Erreur lors de la lecture :\n{e}",
                                  parent=self)
            return
        if not self._raw_rows:
            messagebox.showwarning("Fichier vide",
                                    "Aucune ligne exploitable dans ce fichier.",
                                    parent=self)
            return
        self._build_mapping_ui()
        self._recompute_preview()

    def _lire_brut(self, path: Path) -> list[tuple]:
        """Lit toutes les lignes non vides du fichier, sans interpréter les
        colonnes (chaque cellule est renvoyée telle quelle, en texte)."""
        suf = path.suffix.lower()
        if suf in (".xlsx", ".xlsm", ".xls"):
            return self._lire_brut_xlsx(path)
        elif suf in (".csv", ".tsv"):
            return self._lire_brut_csv(path)
        else:
            raise ValueError(f"Format non supporté : {suf}")

    def _lire_brut_xlsx(self, path: Path) -> list[tuple]:
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl non installé : "
                               "pip install openpyxl")
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active
        rows = []
        for row in ws.iter_rows(values_only=True):
            if not row or all(c is None or str(c).strip() == "" for c in row):
                continue
            rows.append(tuple("" if c is None else str(c).strip() for c in row))
        return rows

    def _lire_brut_csv(self, path: Path) -> list[tuple]:
        with open(path, encoding="utf-8-sig", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(f, dialect)
            rows = []
            for row in reader:
                if not row or all(not str(c).strip() for c in row):
                    continue
                rows.append(tuple(str(c).strip() for c in row))
            return rows

    # ── Correspondance des colonnes ───────────────────────────────────────────
    def _guess_column(self, key, col_labels, used=frozenset()):
        kws = self._KEYWORDS.get(key, [])
        for i, lbl in enumerate(col_labels):
            if i in used:
                continue
            if lbl.strip().lower() in kws:
                return i
        for i, lbl in enumerate(col_labels):
            if i in used:
                continue
            norm = lbl.strip().lower()
            if any(k in norm for k in kws):
                return i
        return None

    def _guess_all_columns(self, col_labels):
        """Devine la colonne de chaque champ, du plus spécifique au plus
        générique, en évitant qu'une même colonne soit assignée deux fois
        (ex : "Prix d'achat" ne doit pas aussi être devinée comme le prix
        de vente)."""
        guesses = {}
        used = set()
        for key in self._ORDRE_DEVINETTE:
            g = self._guess_column(key, col_labels, used)
            if g is not None:
                guesses[key] = g
                used.add(g)
        return guesses

    def _build_mapping_ui(self):
        for w in self.map_frame.winfo_children():
            w.destroy()
        self.map_vars = {}
        if not self._raw_rows:
            return

        ncols = max(len(r) for r in self._raw_rows)
        if self.has_header_var.get() and len(self._raw_rows) >= 1:
            header_row = self._raw_rows[0]
            col_labels = [(header_row[i] if i < len(header_row)
                            and header_row[i] else f"Colonne {i + 1}")
                          for i in range(ncols)]
        else:
            col_labels = [f"Colonne {i + 1}" for i in range(ncols)]

        display_values = [f"{lbl}  (col. {i + 1})"
                           for i, lbl in enumerate(col_labels)]
        self._display_to_index = {dv: i for i, dv in enumerate(display_values)}
        guesses = self._guess_all_columns(col_labels)

        for row_i, (key, label, required) in enumerate(self._CHAMPS):
            tk.Label(self.map_frame, text=label, bg=C["bg"], font=F["small"],
                     width=14, anchor="w").grid(row=row_i, column=0,
                                                  sticky="w", pady=2)
            options = list(display_values) if required else \
                [self._IGNORER] + list(display_values)
            var = tk.StringVar()
            guess = guesses.get(key)
            if guess is not None:
                var.set(display_values[guess])
            elif required and display_values:
                var.set(display_values[0])
            else:
                var.set(self._IGNORER)
            cb = ttk.Combobox(self.map_frame, textvariable=var, values=options,
                               state="readonly", width=30, font=F["small"])
            cb.grid(row=row_i, column=1, sticky="w", padx=6, pady=2)
            cb.bind("<<ComboboxSelected>>", lambda _e: self._recompute_preview())
            self.map_vars[key] = var

    def _on_mapping_changed(self):
        if self._raw_rows:
            self._build_mapping_ui()
            self._recompute_preview()

    def _recompute_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        if not self._raw_rows or not self.map_vars:
            self._pieces_to_import = []
            self.btn_import.config(state="disabled")
            return

        idx = {}
        for key, var in self.map_vars.items():
            val = var.get()
            idx[key] = self._display_to_index.get(val) if val != self._IGNORER else None

        if idx.get("reference") is None:
            self.info_lbl.config(
                text="⚠ Sélectionnez la colonne à utiliser pour la Référence.")
            self._pieces_to_import = []
            self.btn_import.config(state="disabled")
            return

        data_rows = self._raw_rows[1:] if self.has_header_var.get() else self._raw_rows

        def cell(row, i):
            return str(row[i]).strip() if i is not None and i < len(row) else ""

        pieces = []
        for row in data_rows:
            ref = cell(row, idx["reference"])
            if not ref:
                continue
            pieces.append({
                "reference": ref,
                "libelle": cell(row, idx.get("libelle")),
                "marque": cell(row, idx.get("marque")),
                "prix_achat": _parse_prix(cell(row, idx.get("prix_achat"))),
                "prix_vente": _parse_prix(cell(row, idx.get("prix_vente"))),
            })

        self._pieces_to_import = pieces
        for p in pieces[:10]:
            self.preview_tree.insert("", "end",
                                      values=(p["reference"], p["libelle"],
                                              p.get("marque", ""),
                                              _fmt_prix(p.get("prix_achat", 0)),
                                              _fmt_prix(p.get("prix_vente", 0))))
        self.info_lbl.config(
            text=f"📋 {len(pieces)} ligne(s) prête(s) à l'import "
                 f"(sur {len(data_rows)} ligne(s) lue(s)).")
        self.btn_import.config(state="normal" if pieces else "disabled")

    def _do_import(self):
        if not self._pieces_to_import:
            return
        n = len(self._pieces_to_import)
        if not messagebox.askyesno(
                "Confirmer l'import",
                f"Importer {n} pièce(s) ?\n\n"
                f"Doublons : {'ignorés' if self.skip_doublons_var.get() else 'mis à jour'}",
                parent=self):
            return
        self.btn_import.config(state="disabled", text="⏳ Import en cours...")
        self.update_idletasks()
        try:
            res = db.bulk_import_pieces(
                self._pieces_to_import,
                skip_doublons=bool(self.skip_doublons_var.get()))
        except Exception as e:
            messagebox.showerror("Erreur",
                                  f"Import impossible :\n{e}",
                                  parent=self)
            self.btn_import.config(state="normal",
                                     text="✓ Lancer l'import")
            return
        ignorees = res.get('ignorees', 0)
        completees = res.get('completees', 0)
        doublons_ligne = f"  • {ignorees} doublon(s) ignoré(s)"
        if completees:
            doublons_ligne += f" (dont {completees} complété(s) avec les infos manquantes)"
        msg = (f"✅ Import terminé !\n\n"
               f"  • {res.get('importees', 0)} nouvelle(s) pièce(s)\n"
               f"  • {res.get('mises_a_jour', 0)} mise(s) à jour\n"
               f"{doublons_ligne}\n"
               f"  • {res.get('erreurs', 0)} erreur(s)")
        if res.get("details_erreurs"):
            msg += "\n\nQuelques erreurs :\n" + \
                   "\n".join(res["details_erreurs"][:5])
        messagebox.showinfo("Import terminé", msg, parent=self)
        if self.on_save:
            self.on_save()
        self.destroy()
 
 
# ─── Point d'entrée ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    PiecesApp().mainloop()
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
 
 
# ═════════════════════════════════════════════════════════════════════════════
#   PiecesApp — App principale
# ═════════════════════════════════════════════════════════════════════════════
class PiecesApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.withdraw()
        apply_icon(self)
        self.title("EMS — Pièces détachées")
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
        cols = ("reference", "libelle", "marque", "notes")
        col_defs = [
            ("reference",  "Référence",   140),
            ("libelle",    "Libellé",     420),
            ("marque",     "Marque",      120),
            ("notes",      "Notes",       240),
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
                          values=("—", msg, "", ""), tags=("help",))
        self.tree.tag_configure("help", foreground=C["muted"])
 
    def _fill_tree(self):
        self.tree.delete(*self.tree.get_children())
        if not self._cache:
            self.tree.insert("", "end",
                              values=("—", "(aucun résultat)", "", ""))
            return
        for i, p in enumerate(self._cache):
            self.tree.insert("", "end", iid=str(i),
                              values=(p["reference"],
                                      p["libelle"],
                                      p.get("marque", ""),
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
        self.geometry("520x420")
        self.resizable(False, True)
        self.grab_set()
 
        mk_header(self, "Pièce détachée",
                   "Catalogue de stock")
 
        frm = tk.Frame(self, bg=C["bg"])
        frm.pack(fill="both", expand=True, padx=24, pady=18)
 
        self.v = {}
        champs = [
            ("reference", "Référence *", 30),
            ("libelle",   "Libellé",     50),
            ("marque",    "Marque",      30),
            ("notes",     "Notes",       50),
        ]
        for key, label, width in champs:
            tk.Label(frm, text=label, bg=C["bg"], font=F["body_bold"],
                     anchor="w").pack(anchor="w", pady=(6, 2))
            v = tk.StringVar(value=(piece or {}).get(key, ""))
            ttk.Entry(frm, textvariable=v, width=width,
                       font=F["body"]).pack(fill="x")
            self.v[key] = v
 
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
        data = {k: v.get().strip() for k, v in self.v.items()}
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
    def __init__(self, parent, on_save=None):
        super().__init__(parent)
        self.on_save = on_save
        self.title("Importer des pièces depuis CSV/Excel")
        self.configure(bg=C["bg"])
        self.geometry("780x560")
        self.grab_set()
 
        mk_header(self, "Import en masse",
                   "Référence + Libellé (+ Marque optionnel)")
 
        # ── Sélection du fichier ──────────────────────────────────────────────
        sf = tk.Frame(self, bg=C["bg"])
        sf.pack(fill="x", padx=20, pady=10)
        tk.Label(sf, text="Fichier :", bg=C["bg"],
                 font=F["body_bold"]).pack(side="left")
        self.path_var = tk.StringVar(value="(aucun fichier sélectionné)")
        tk.Label(sf, textvariable=self.path_var, bg=C["bg"],
                 font=F["body"], fg=C["muted"]).pack(side="left", padx=6)
        mk_btn(sf, "📁 Choisir...", self._choose_file).pack(side="right")
 
        # ── Options ───────────────────────────────────────────────────────────
        of = tk.Frame(self, bg=C["bg"])
        of.pack(fill="x", padx=20, pady=4)
        self.skip_doublons_var = tk.IntVar(value=1)
        tk.Checkbutton(of, text="Ignorer les références déjà en base "
                                 "(sinon mise à jour)",
                       variable=self.skip_doublons_var,
                       bg=C["bg"], font=F["small"]).pack(anchor="w")
 
        # ── Aperçu ────────────────────────────────────────────────────────────
        tk.Label(self, text="Aperçu (10 premières lignes) :",
                 bg=C["bg"], font=F["body_bold"]).pack(anchor="w", padx=20,
                                                        pady=(10, 4))
        cols = ("ref", "lib", "marque")
        col_defs = [("ref", "Référence", 140), ("lib", "Libellé", 380),
                    ("marque", "Marque", 140)]
        tf, self.preview_tree = mk_tree(self, cols, col_defs, height=10)
        tf.pack(fill="both", expand=True, padx=20)
 
        self.info_lbl = tk.Label(self, text="", bg=C["bg"],
                                   font=F["small"], fg=C["muted"], wraplength=720)
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
 
        self._pieces_to_import = []
 
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
            lignes = self._lire_fichier(Path(path))
        except Exception as e:
            messagebox.showerror("Lecture impossible",
                                  f"Erreur lors de la lecture :\n{e}",
                                  parent=self)
            return
        self._pieces_to_import = lignes
        # Aperçu
        self.preview_tree.delete(*self.preview_tree.get_children())
        for i, p in enumerate(lignes[:10]):
            self.preview_tree.insert("", "end",
                                      values=(p["reference"], p["libelle"],
                                              p.get("marque", "")))
        self.info_lbl.config(
            text=f"📋 {len(lignes)} ligne(s) prête(s) à l'import. "
                 "Le fichier doit avoir 2 ou 3 colonnes : "
                 "Référence, Libellé, (Marque). "
                 "La 1ère ligne sera ignorée si c'est un en-tête.")
        self.btn_import.config(state="normal")
 
    def _lire_fichier(self, path: Path) -> list[dict]:
        suf = path.suffix.lower()
        if suf in (".xlsx", ".xlsm", ".xls"):
            return self._lire_xlsx(path)
        elif suf in (".csv", ".tsv"):
            return self._lire_csv(path)
        else:
            raise ValueError(f"Format non supporté : {suf}")
 
    def _lire_xlsx(self, path: Path) -> list[dict]:
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("openpyxl non installé : "
                               "pip install openpyxl")
        wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
        ws = wb.active
        lignes = []
        first = True
        for row in ws.iter_rows(values_only=True):
            if first:
                first = False
                cell = str(row[0] or "").strip().lower()
                if cell in ("référence", "reference", "ref"):
                    continue
            if not row or not row[0]:
                continue
            ref = str(row[0]).strip()
            lib = str(row[1] or "").strip() if len(row) > 1 else ""
            marq = str(row[2] or "").strip() if len(row) > 2 else ""
            if ref:
                lignes.append({"reference": ref, "libelle": lib,
                                "marque": marq})
        return lignes
 
    def _lire_csv(self, path: Path) -> list[dict]:
        with open(path, encoding="utf-8-sig", newline="") as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
            except csv.Error:
                dialect = csv.excel
            reader = csv.reader(f, dialect)
            lignes = []
            first = True
            for row in reader:
                if first:
                    first = False
                    if (row and str(row[0]).strip().lower()
                            in ("référence", "reference", "ref")):
                        continue
                if not row or not row[0]:
                    continue
                ref = str(row[0]).strip()
                lib = str(row[1]).strip() if len(row) > 1 else ""
                marq = str(row[2]).strip() if len(row) > 2 else ""
                if ref:
                    lignes.append({"reference": ref, "libelle": lib,
                                    "marque": marq})
            return lignes
 
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
        msg = (f"✅ Import terminé !\n\n"
               f"  • {res.get('importees', 0)} nouvelle(s) pièce(s)\n"
               f"  • {res.get('mises_a_jour', 0)} mise(s) à jour\n"
               f"  • {res.get('ignorees', 0)} doublon(s) ignoré(s)\n"
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
"""
EMS Installer – déploiement local des applications EMS.
Placer ce .exe dans le dossier EMS_Distribution et le lancer.
"""

import os
import sys
import shutil
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


def _is_accessible(path: Path) -> bool:
    """True si le fichier existe et est lisible par l'utilisateur courant.
    Les fichiers cachés sont inclus ; les fichiers sans permission sont exclus."""
    if not path.is_file():
        return False
    return os.access(path, os.R_OK)

# ---------------------------------------------------------------------------
# Catalogue – ordre d'affichage et descriptions
# ---------------------------------------------------------------------------
APPS = [
    ("EMS_Launcher",     "Lanceur principal EMS"),
    ("EMS_Bons",         "Bons d'intervention"),
    ("EMS_Parc",         "Gestion du parc machines"),
    ("EMS_Garanties",    "Suivi des garanties"),
    ("EMS_Amelioration", "Suivi des améliorations"),
    ("EMS_Pieces",       "Gestion des pièces"),
    ("EMS_BI",           "Business Intelligence / Rapports"),
    ("EMS_Affaire",      "Gestion des affaires"),
]

DEFAULT_DIR = r"C:\EMS"

BLUE       = "#002b5c"
LIGHT_BLUE = "#eef2f7"
RED_LINE   = "#c62828"
WHITE      = "#ffffff"
TEXT_COL   = "#1a2332"
GREY_COL   = "#aab0bb"


def _source_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def _create_shortcut(target: Path, link: Path) -> None:
    ps = (
        f'$s=(New-Object -COM WScript.Shell).CreateShortcut("{link}");'
        f'$s.TargetPath="{target}";'
        f'$s.WorkingDirectory="{target.parent}";'
        f'$s.IconLocation="{target}";'
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
        capture_output=True, timeout=10,
    )


# ---------------------------------------------------------------------------

class InstallerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("EMS – Installeur d'applications")
        self.resizable(False, False)
        self.configure(bg=WHITE)

        self._source = _source_dir()
        self._dest   = tk.StringVar(value=DEFAULT_DIR)
        self._shortcut_desktop   = tk.BooleanVar(value=True)
        self._shortcut_startmenu = tk.BooleanVar(value=False)
        self._vars: dict[str, tk.BooleanVar] = {}

        self._build_ui()

        # Centrage après construction
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth()  - w) // 2
        y = (self.winfo_screenheight() - h) // 2
        self.geometry(f"+{x}+{y}")

    # ── Construction de l'interface ──────────────────────────────────────────

    def _build_ui(self):
        # En-tête
        hdr = tk.Frame(self, bg=BLUE, height=68)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="EMS  –  Installation des applications",
            bg=BLUE, fg=WHITE,
            font=("Segoe UI", 14, "bold"),
        ).pack(side="left", padx=22, pady=16)

        body = tk.Frame(self, bg=WHITE, padx=22, pady=16)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)

        row = 0

        # ── Dossier de destination ───────────────────────────────────────
        tk.Label(
            body, text="Dossier d'installation :",
            bg=WHITE, fg=BLUE, font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=0, sticky="w"); row += 1

        dest_f = tk.Frame(body, bg=WHITE)
        dest_f.grid(row=row, column=0, sticky="ew", pady=(4, 14)); row += 1
        dest_f.columnconfigure(0, weight=1)
        tk.Entry(dest_f, textvariable=self._dest,
                 font=("Segoe UI", 10)
                 ).grid(row=0, column=0, sticky="ew")
        tk.Button(
            dest_f, text="Parcourir…", command=self._browse,
            bg=LIGHT_BLUE, relief="flat", font=("Segoe UI", 9),
        ).grid(row=0, column=1, padx=(6, 0))

        tk.Frame(body, bg=RED_LINE, height=2
                 ).grid(row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── Liste des applications ───────────────────────────────────────
        lbl_f = tk.Frame(body, bg=WHITE)
        lbl_f.grid(row=row, column=0, sticky="ew", pady=(0, 6)); row += 1
        tk.Label(
            lbl_f, text="Applications à installer :",
            bg=WHITE, fg=BLUE, font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        tk.Button(
            lbl_f, text="Tout cocher", command=self._select_all,
            bg=LIGHT_BLUE, relief="flat", font=("Segoe UI", 8),
        ).pack(side="right", padx=(4, 0))
        tk.Button(
            lbl_f, text="Tout décocher", command=self._select_none,
            bg=LIGHT_BLUE, relief="flat", font=("Segoe UI", 8),
        ).pack(side="right")

        apps_f = tk.Frame(body, bg=WHITE, bd=1, relief="solid")
        apps_f.grid(row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        for name, desc in APPS:
            available = _is_accessible(self._source / f"{name}.exe")
            var = tk.BooleanVar(value=available)
            self._vars[name] = var

            rf = tk.Frame(apps_f, bg=WHITE)
            rf.pack(fill="x", padx=8, pady=3)

            tk.Checkbutton(
                rf, variable=var, bg=WHITE, activebackground=WHITE,
                state="normal" if available else "disabled",
            ).pack(side="left")

            fg = TEXT_COL if available else GREY_COL
            tk.Label(
                rf, text=name.replace("_", " "),
                bg=WHITE, fg=fg,
                font=("Segoe UI", 9, "bold"), width=18, anchor="w",
            ).pack(side="left")
            suffix = "" if available else "  [non disponible]"
            tk.Label(
                rf, text=desc + suffix,
                bg=WHITE, fg=fg, font=("Segoe UI", 9),
            ).pack(side="left")

        tk.Frame(body, bg=RED_LINE, height=2
                 ).grid(row=row, column=0, sticky="ew", pady=(0, 12)); row += 1

        # ── Raccourcis ───────────────────────────────────────────────────
        tk.Label(
            body, text="Raccourcis :",
            bg=WHITE, fg=BLUE, font=("Segoe UI", 10, "bold"),
        ).grid(row=row, column=0, sticky="w"); row += 1

        sc_f = tk.Frame(body, bg=WHITE)
        sc_f.grid(row=row, column=0, sticky="w", pady=(4, 14)); row += 1
        tk.Checkbutton(
            sc_f, text="Bureau",
            variable=self._shortcut_desktop,
            bg=WHITE, activebackground=WHITE, font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 20))
        tk.Checkbutton(
            sc_f, text="Menu Démarrer",
            variable=self._shortcut_startmenu,
            bg=WHITE, activebackground=WHITE, font=("Segoe UI", 9),
        ).pack(side="left")

        # ── Progression + log ────────────────────────────────────────────
        self._progress = ttk.Progressbar(body, mode="determinate", length=500)
        self._progress.grid(row=row, column=0, sticky="ew", pady=(0, 6)); row += 1

        self._log = tk.Text(
            body, height=5, state="disabled",
            font=("Consolas", 8), bg=LIGHT_BLUE, relief="flat", wrap="word",
        )
        self._log.grid(row=row, column=0, sticky="ew", pady=(0, 14)); row += 1

        # ── Bouton Installer ─────────────────────────────────────────────
        self._btn = tk.Button(
            body, text="   Installer   ",
            command=self._start_install,
            bg=BLUE, fg=WHITE,
            font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=8,
        )
        self._btn.grid(row=row, column=0, pady=(0, 4)); row += 1

    # ── Actions ─────────────────────────────────────────────────────────────

    def _browse(self):
        d = filedialog.askdirectory(title="Choisir le dossier d'installation")
        if d:
            self._dest.set(d)

    def _select_all(self):
        for name, var in self._vars.items():
            if _is_accessible(self._source / f"{name}.exe"):
                var.set(True)

    def _select_none(self):
        for var in self._vars.values():
            var.set(False)

    def _log_write(self, msg: str):
        self._log.config(state="normal")
        self._log.insert("end", msg + "\n")
        self._log.see("end")
        self._log.config(state="disabled")
        self.update_idletasks()

    def _start_install(self):
        selected = [n for n, v in self._vars.items() if v.get()]
        if not selected:
            messagebox.showwarning(
                "Aucune sélection",
                "Veuillez cocher au moins une application.",
            )
            return
        self._btn.config(state="disabled")
        threading.Thread(target=self._run_install, args=(selected,),
                         daemon=True).start()

    def _run_install(self, selected: list[str]):
        dest = Path(self._dest.get().strip())
        self._progress["maximum"] = len(selected)
        self._progress["value"]   = 0

        try:
            dest.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self._log_write(f"ERREUR : impossible de créer {dest}\n  {e}")
            self._btn.config(state="normal")
            return

        # config.ini
        cfg = self._source / "config.ini"
        if cfg.is_file():
            try:
                shutil.copy2(cfg, dest / "config.ini")
                self._log_write("config.ini copié.")
            except Exception as e:
                self._log_write(f"Avertissement config.ini : {e}")

        errors   = 0
        installed: list[Path] = []

        for name in selected:
            src = self._source / f"{name}.exe"
            dst = dest / f"{name}.exe"
            try:
                shutil.copy2(src, dst)
                self._log_write(f"✓  {name}.exe")
                installed.append(dst)
            except Exception as e:
                self._log_write(f"✗  {name}.exe  –  {e}")
                errors += 1
            self._progress["value"] += 1
            self.update_idletasks()

        # Raccourcis Bureau
        if self._shortcut_desktop.get():
            desktop = Path(os.path.expandvars(r"%USERPROFILE%\Desktop"))
            for exe in installed:
                try:
                    _create_shortcut(exe, desktop / (exe.stem + ".lnk"))
                    self._log_write(f"   Raccourci bureau : {exe.stem}")
                except Exception as e:
                    self._log_write(f"   Raccourci bureau échoué : {e}")

        # Raccourcis Menu Démarrer
        if self._shortcut_startmenu.get():
            sm = Path(os.path.expandvars(
                r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\EMS"))
            sm.mkdir(parents=True, exist_ok=True)
            for exe in installed:
                try:
                    _create_shortcut(exe, sm / (exe.stem + ".lnk"))
                    self._log_write(f"   Menu Démarrer : {exe.stem}")
                except Exception as e:
                    self._log_write(f"   Menu Démarrer échoué : {e}")

        if errors == 0:
            self._log_write(
                f"\nInstallation terminée – {len(installed)} application(s) dans {dest}")
            messagebox.showinfo(
                "Installation réussie",
                f"{len(installed)} application(s) installée(s) dans :\n{dest}",
            )
        else:
            self._log_write(f"\n{errors} erreur(s). Voir le journal ci-dessus.")
            messagebox.showwarning(
                "Terminé avec erreurs",
                f"{errors} erreur(s) lors de l'installation.\n"
                "Vérifiez le journal.",
            )
        self._btn.config(state="normal")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    InstallerApp().mainloop()

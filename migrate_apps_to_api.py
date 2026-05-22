#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
  Migration des apps Tkinter : utiliser l'API REST au lieu de la DB locale
═══════════════════════════════════════════════════════════════════════════════

Modifie en place les fichiers main.py / app_*.py des 4 apps pour qu'elles
utilisent `ems_client.api` au lieu de `database.py`.

Usage :
    python migrate_apps_to_api.py [--dry-run]

Le --dry-run affiche les changements sans modifier les fichiers.

L'opération est idempotente : relancer le script ne fait rien si les apps
sont déjà migrées.

Sauvegarde automatique des fichiers originaux en .bak avant modification.
═══════════════════════════════════════════════════════════════════════════════
"""
import sys
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent

APPS = [
    HERE / "ems_project" / "main.py",
    HERE / "garanties_app" / "app_garanties.py",
    HERE / "amelioration_app" / "app_amelioration.py",
]

# Remplacements à faire (avant → après)
REMPLACEMENTS = [
    # Import principal
    ("import database as db", "from ems_client import api as db"),
    # Imports parfois utilisés autrement
    ("from database import ", "from ems_client.api import "),
]


def patcher_fichier(path: Path, dry_run: bool) -> int:
    """Applique les remplacements. Retourne le nombre de modifs."""
    if not path.is_file():
        print(f"  ⚠ {path.relative_to(HERE)} : introuvable (ignoré)")
        return 0

    txt = path.read_text(encoding="utf-8")
    n = 0
    for old, new in REMPLACEMENTS:
        if old in txt:
            txt = txt.replace(old, new)
            n += txt.count(new) - txt.count(new)  # compte indicatif
            n += 1

    # Détecter si déjà migré
    if "from ems_client import api as db" in path.read_text(encoding="utf-8") \
       and n == 0:
        print(f"  ✓ {path.relative_to(HERE)} : déjà migré")
        return 0

    if n == 0:
        print(f"  • {path.relative_to(HERE)} : rien à changer")
        return 0

    if dry_run:
        print(f"  → {path.relative_to(HERE)} : {n} modif(s) "
              f"[DRY-RUN, non écrit]")
    else:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text(txt, encoding="utf-8")
        print(f"  ✓ {path.relative_to(HERE)} : migré "
              f"(sauvegarde : {backup.name})")
    return n


def main():
    dry_run = "--dry-run" in sys.argv
    print(f"Migration des apps EMS vers l'API REST"
          f"{' (DRY-RUN)' if dry_run else ''}\n")
    total = 0
    for app_path in APPS:
        total += patcher_fichier(app_path, dry_run)
    print(f"\n{total} modification(s) au total.")
    if not dry_run and total > 0:
        print("\nPour annuler, restaurer les fichiers .bak :")
        for app_path in APPS:
            bak = app_path.with_suffix(app_path.suffix + ".bak")
            if bak.exists():
                print(f"  copy {bak} {app_path}")

    if dry_run:
        print("\nLancez sans --dry-run pour appliquer les changements.")


if __name__ == "__main__":
    main()

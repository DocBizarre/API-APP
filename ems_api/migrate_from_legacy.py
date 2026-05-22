"""
Migration : ancienne ems.db (sqlite direct) → nouvelle base API.

Préserve :
  - les IDs (clés primaires)
  - les num_bon / num_ems / num_ticket (numéros officiels)
  - les types_intervention, statuts_garantie
  - la config (dashboard_widgets, dashboard_cards, etc.)

Usage :
    python -m ems_api.migrate_from_legacy [chemin/vers/ancienne/ems.db]
"""
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy import DateTime

from .config import settings
from .database import init_db, SessionLocal
from .models import (
    Client, Moteur, Intervention, Garantie, Amelioration, Technicien,
    TypeIntervention, StatutGarantie, Config,
)


def trouver_ancienne_db():
    here = Path(__file__).resolve().parent.parent
    for c in (
        here / "ems_project" / "data" / "ems.db",
        here.parent / "ems_project" / "data" / "ems.db",
        here / "data" / "ems.db",
    ):
        if c.is_file():
            return c
    return None


def _parse_datetime(s):
    """Convertit une string SQLite en datetime, ou retourne None."""
    if s is None or s == "":
        return None
    if isinstance(s, datetime):
        return s
    if not isinstance(s, str):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _copy_row(src_row, target_class, columns_target, datetime_cols):
    """Copie les colonnes communes entre src_row (sqlite3.Row) et target_class.
    Convertit les colonnes datetime de string vers datetime."""
    src_cols = set(src_row.keys())
    d = {}
    for col in columns_target:
        if col not in src_cols:
            continue
        v = src_row[col]
        if v is None:
            continue
        if col in datetime_cols:
            v = _parse_datetime(v)
            if v is None:
                continue
        d[col] = v
    return d


def _datetime_cols(model_class):
    """Retourne l'ensemble des noms de colonnes DateTime du modèle."""
    return {c.name for c in model_class.__table__.columns
            if isinstance(c.type, DateTime)}


def migrer(ancienne_db: Path):
    print(f"Source : {ancienne_db}")
    print(f"Cible  : {settings.DB_PATH}")
    print()
    init_db()

    src = sqlite3.connect(str(ancienne_db))
    src.row_factory = sqlite3.Row
    dst = SessionLocal()

    tables_src = {r[0] for r in src.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}

    def _migrer_table(table_sql, model_class, label):
        if table_sql not in tables_src:
            print(f"  • {label:14}: table absente")
            return
        cols = [c.name for c in model_class.__table__.columns]
        dt_cols = _datetime_cols(model_class)
        n = 0
        for r in src.execute(f"SELECT * FROM {table_sql}"):
            d = _copy_row(r, model_class, cols, dt_cols)
            dst.merge(model_class(**d))
            n += 1
        dst.commit()
        print(f"  ✓ {label:14}: {n}")

    _migrer_table("clients",       Client,       "clients")
    _migrer_table("moteurs",       Moteur,       "moteurs")
    _migrer_table("techniciens",   Technicien,   "techniciens")
    _migrer_table("interventions", Intervention, "interventions")
    _migrer_table("garanties",     Garantie,     "garanties")
    _migrer_table("ameliorations", Amelioration, "améliorations")
    _migrer_table("types_intervention", TypeIntervention, "types_interv")
    _migrer_table("statuts_garantie",   StatutGarantie,   "statuts_gar")

    # Config (clé/valeur) — pas de datetime
    if "config" in tables_src:
        n = 0
        for r in src.execute("SELECT * FROM config"):
            dst.merge(Config(cle=r["cle"], valeur=r["valeur"] or ""))
            n += 1
        dst.commit()
        print(f"  ✓ config        : {n}")

    src.close()
    dst.close()
    print("\n✅ Migration terminée.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        path = Path(sys.argv[1])
    else:
        path = trouver_ancienne_db()
        if not path:
            print("⚠ Ancienne base introuvable. Spécifiez le chemin en argument.")
            sys.exit(1)
    if not path.is_file():
        print(f"⚠ Fichier introuvable : {path}")
        sys.exit(1)
    migrer(path)

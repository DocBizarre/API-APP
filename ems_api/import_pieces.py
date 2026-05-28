"""
Import des pièces détachées depuis un fichier Excel ou CSV.

Usage :
    python -m ems_api.import_pieces chemin/vers/Produits_Mon_Stock_EMS.xlsx
    python -m ems_api.import_pieces fichier.csv
"""
import sys
import csv
from pathlib import Path
from uuid import uuid4

from .config import settings
from .database import init_db, SessionLocal
from .models import Piece


def importer_xlsx(path: Path) -> list[dict]:
    try:
        import openpyxl
    except ImportError:
        print("ERREUR : openpyxl non installé. Faire : pip install openpyxl")
        sys.exit(1)
    wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
    ws = wb.active
    lignes = []
    first = True
    for row in ws.iter_rows(values_only=True):
        if first:
            first = False
            # Détecte si la 1ère ligne est un header (texte non chiffre)
            cell = str(row[0] or "").strip().lower()
            if cell in ("référence", "reference", "ref"):
                continue   # skip header
            # Sinon c'est déjà une donnée, on continue
        if not row or not row[0]:
            continue
        ref = str(row[0]).strip()
        lib = str(row[1] or "").strip() if len(row) > 1 else ""
        marq = str(row[2] or "").strip() if len(row) > 2 else ""
        if ref:
            lignes.append({"reference": ref, "libelle": lib, "marque": marq})
    return lignes


def importer_csv(path: Path) -> list[dict]:
    lignes = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        # Détection automatique du séparateur
        sample = f.read(2048)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=";,\t|")
        except csv.Error:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        first = True
        for row in reader:
            if first:
                first = False
                if row and str(row[0]).strip().lower() in ("référence", "reference", "ref"):
                    continue
            if not row or not row[0]:
                continue
            ref = str(row[0]).strip()
            lib = str(row[1]).strip() if len(row) > 1 else ""
            marq = str(row[2]).strip() if len(row) > 2 else ""
            if ref:
                lignes.append({"reference": ref, "libelle": lib, "marque": marq})
    return lignes


def importer(path: Path):
    print(f"Source : {path}")
    print(f"Cible  : {settings.DB_PATH}")
    init_db()

    if path.suffix.lower() in (".xlsx", ".xlsm"):
        lignes = importer_xlsx(path)
    elif path.suffix.lower() in (".csv", ".tsv"):
        lignes = importer_csv(path)
    else:
        print(f"⚠ Format non supporté : {path.suffix}")
        sys.exit(1)

    print(f"  → {len(lignes)} lignes lues")

    db = SessionLocal()
    existing = {r[0] for r in db.query(Piece.reference).all()}
    print(f"  → {len(existing)} pièces déjà en base")

    importees = 0
    ignorees = 0
    erreurs = 0
    for i, d in enumerate(lignes, 1):
        ref = d["reference"]
        if ref in existing:
            ignorees += 1
            continue
        try:
            db.add(Piece(id=str(uuid4()),
                          reference=ref,
                          libelle=d.get("libelle", ""),
                          marque=d.get("marque", "")))
            existing.add(ref)
            importees += 1
            if (importees % 1000) == 0:
                db.commit()
                print(f"  → {importees} pièces importées...")
        except Exception as e:
            erreurs += 1
            if erreurs <= 10:
                print(f"  ⚠ Ligne {i} ({ref}) : {e}")
    db.commit()
    db.close()

    print()
    print(f"  ✓ {importees} pièces importées")
    print(f"  • {ignorees} pièces déjà présentes (ignorées)")
    if erreurs:
        print(f"  ⚠ {erreurs} erreurs")
    print("\n✅ Import terminé.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage : python -m ems_api.import_pieces <fichier.xlsx ou .csv>")
        sys.exit(1)
    p = Path(sys.argv[1])
    if not p.is_file():
        print(f"⚠ Fichier introuvable : {p}")
        sys.exit(1)
    importer(p)

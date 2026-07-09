"""
Router admin - Endpoints d'administration.

- Export de la base SQLite pour l'app BI (le BI a besoin de la DB complete
  pour faire ses analyses cote navigateur (SQL.js)).
- Diagnostic et correction des compteurs de numerotation (affaires / bons),
  pour reperer et corriger les incoherences (trous en fin de sequence)
  causees par des creations echouees apres reservation du numero.
"""
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import engine, get_db
from ..models.affaire import Affaire
from ..models.intervention import Intervention
from ..models.configurations import Config

router = APIRouter(prefix="/admin", tags=["admin"])


def _get_db_path() -> Path:
    """Extrait le chemin du fichier SQLite depuis l'URL SQLAlchemy."""
    url = str(engine.url)
    # Forme typique : sqlite:///C:/path/to/ems.db ou sqlite:///./data/ems.db
    if url.startswith("sqlite:///"):
        return Path(url.replace("sqlite:///", "", 1))
    if url.startswith("sqlite://"):
        return Path(url.replace("sqlite://", "", 1))
    raise RuntimeError(f"URL non SQLite : {url}")


@router.get("/export-db",
            summary="Telecharge la base SQLite complete",
            response_class=FileResponse)
def export_db():
    """
    Renvoie le fichier ems.db en binaire pour usage par l'app BI.
    A utiliser en lecture seule cote client.
    """
    try:
        db_file = _get_db_path()
    except RuntimeError as e:
        raise HTTPException(500, str(e))

    if not db_file.is_file():
        raise HTTPException(404, f"Base introuvable : {db_file}")
    return FileResponse(
        path=str(db_file),
        media_type="application/octet-stream",
        filename="ems.db",
        headers={"Cache-Control": "no-store"})


# ═══════════════════════════════════════════════════════════════════════════
# Diagnostic et correction des compteurs de numerotation
# ═══════════════════════════════════════════════════════════════════════════
# Rappel du fonctionnement (voir ems_api/services/numerotation.py) :
#   prochain numero = max(dernier numero reellement utilise, HWM stocke en
#   config) + 1. Le HWM est avance des qu'un numero est distribue, meme si la
#   creation echoue ensuite -> le numero est "brule" et un trou apparait a la
#   fin de la sequence. Comme le calcul prend toujours le max des deux
#   sources, ramener le HWM au niveau du dernier numero reellement utilise
#   est une operation sans risque : elle ne peut jamais faire re-emettre un
#   numero deja pris par un enregistrement existant.

_NUMEROTATION_TYPES = {
    "affaire": {
        "model": Affaire,
        "colonne": "num_affaire",
        "regex": re.compile(r"^(AMOT\d{4})(\d{4})$"),
        "hwm_prefix_test": lambda p: p.startswith("AMOT"),
    },
    "bon": {
        "model": Intervention,
        "colonne": "num_bon",
        "regex": re.compile(r"^(BON-(?:[^-]+-)?\d{4}-)(\d{4})$"),
        "hwm_prefix_test": lambda p: p.startswith("BON-"),
    },
}


def _type_config(type_key: str) -> dict:
    conf = _NUMEROTATION_TYPES.get(type_key)
    if not conf:
        raise HTTPException(404, f"Type de numerotation inconnu : {type_key} (attendu : affaire, bon)")
    return conf


def _diagnostiquer_groupe(db: Session, type_key: str, prefixe: str) -> dict:
    """Calcule l'etat (HWM, dernier numero reellement utilise, trous) pour un prefixe donne."""
    conf = _type_config(type_key)
    model, colonne = conf["model"], conf["colonne"]
    col = getattr(model, colonne)

    rows = db.query(getattr(model, "id"), col).filter(col.like(f"{prefixe}%")).all()
    utilises = {}
    for rec_id, num in rows:
        m = conf["regex"].match(num or "")
        if m and m.group(1) == prefixe:
            try:
                utilises[int(m.group(2))] = rec_id
            except ValueError:
                continue

    cfg = db.query(Config).filter(Config.cle == f"hwm:{prefixe}").first()
    hwm = int(cfg.valeur) if cfg and cfg.valeur and cfg.valeur.isdigit() else 0
    db_max = max(utilises.keys()) if utilises else 0
    plafond = max(db_max, hwm)
    manquants = [n for n in range(1, plafond + 1) if n not in utilises]

    return {
        "prefixe": prefixe,
        "hwm": hwm,
        "db_max": db_max,
        "nb_enregistrements": len(utilises),
        "numeros_manquants": manquants,
        "trou_en_fin": max(hwm - db_max, 0),
        "incoherent": len(manquants) > 0,
    }


@router.get("/numerotation/{type_key}",
            summary="Diagnostic des compteurs de numerotation (affaire ou bon)")
def diagnostic_numerotation(type_key: str, db: Session = Depends(get_db)):
    conf = _type_config(type_key)
    model, colonne = conf["model"], conf["colonne"]
    col = getattr(model, colonne)

    prefixes = set()
    for (num,) in db.query(col).all():
        m = conf["regex"].match(num or "")
        if m:
            prefixes.add(m.group(1))
    for (cle,) in db.query(Config.cle).filter(Config.cle.like("hwm:%")).all():
        p = cle[len("hwm:"):]
        if conf["hwm_prefix_test"](p):
            prefixes.add(p)

    groupes = [_diagnostiquer_groupe(db, type_key, p) for p in sorted(prefixes)]
    return {"type": type_key, "groupes": groupes}


@router.get("/numerotation/{type_key}/{prefixe}/dossiers",
            summary="Liste des dossiers (affaires/bons) existants pour un prefixe, numero par numero")
def dossiers_numerotation(type_key: str, prefixe: str, db: Session = Depends(get_db)):
    conf = _type_config(type_key)
    model, colonne = conf["model"], conf["colonne"]
    col = getattr(model, colonne)

    rows = db.query(model).filter(col.like(f"{prefixe}%")).all()
    dossiers = []
    for rec in rows:
        num = getattr(rec, colonne)
        m = conf["regex"].match(num or "")
        if not m or m.group(1) != prefixe:
            continue
        item = {"numero": int(m.group(2)), "id": rec.id, "num": num}
        if type_key == "affaire":
            item["libelle"] = rec.nom_projet or ""
            item["statut"] = rec.statut or ""
        else:
            item["libelle"] = rec.type_intervention or ""
            item["statut"] = rec.statut or ""
        dossiers.append(item)
    dossiers.sort(key=lambda d: d["numero"])
    return {"prefixe": prefixe, "dossiers": dossiers}


class CompteurUpdate(BaseModel):
    valeur: Optional[int] = None  # None = recalibrer automatiquement sur le dernier numero reellement utilise


@router.post("/numerotation/{type_key}/{prefixe}/compteur",
             summary="Corrige le compteur (HWM) d'un prefixe de numerotation")
def corriger_compteur(type_key: str, prefixe: str, body: CompteurUpdate,
                       db: Session = Depends(get_db)):
    _type_config(type_key)  # valide le type et 404 si inconnu
    etat = _diagnostiquer_groupe(db, type_key, prefixe)

    nouvelle_valeur = body.valeur if body.valeur is not None else etat["db_max"]
    if nouvelle_valeur < 0:
        raise HTTPException(400, "La valeur du compteur ne peut pas etre negative")

    hwm_key = f"hwm:{prefixe}"
    cfg = db.query(Config).filter(Config.cle == hwm_key).first()
    if cfg:
        cfg.valeur = str(nouvelle_valeur)
    else:
        db.add(Config(cle=hwm_key, valeur=str(nouvelle_valeur)))
    db.commit()

    return _diagnostiquer_groupe(db, type_key, prefixe)

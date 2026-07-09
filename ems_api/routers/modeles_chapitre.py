"""Endpoints REST pour les modèles de chapitres d'affaire (templates de champs
par type, verrou, types personnalisés et ordre d'affichage).

Remplace l'ancien stockage 100% côté navigateur (localStorage), propre à
chaque poste/navigateur et absent de toute sauvegarde : tout est désormais
en base, partagé entre postes et couvert par les sauvegardes de ems.db.
"""
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.configurations import Config, ModeleChapitre

router = APIRouter(prefix="/modeles-chapitre", tags=["modeles-chapitre"])

_CLE_LOCKED = "chapitre_templates_locked"
_CLE_CUSTOM_TYPES = "chapitre_types_personnalises"
_CLE_ORDER = "chapitre_types_ordre"


class ChampsPayload(BaseModel):
    fields: List[Dict]


class ConfigPayload(BaseModel):
    locked: Optional[bool] = None
    custom_types: Optional[List[str]] = None
    order: Optional[List[str]] = None


def _lire_json(db: Session, cle: str, defaut):
    row = db.query(Config).filter(Config.cle == cle).first()
    if not row or not row.valeur:
        return defaut
    try:
        return json.loads(row.valeur)
    except (json.JSONDecodeError, TypeError):
        return defaut


def _ecrire_config(db: Session, cle: str, valeur: str):
    row = db.query(Config).filter(Config.cle == cle).first()
    if row:
        row.valeur = valeur
    else:
        db.add(Config(cle=cle, valeur=valeur))


@router.get("")
def get_modeles(db: Session = Depends(get_db)):
    templates = {
        m.type_name: json.loads(m.champs_json)
        for m in db.query(ModeleChapitre).all()
    }
    locked_row = db.query(Config).filter(Config.cle == _CLE_LOCKED).first()
    return {
        "templates": templates,
        "locked": bool(locked_row and locked_row.valeur == "1"),
        "custom_types": _lire_json(db, _CLE_CUSTOM_TYPES, []),
        "order": _lire_json(db, _CLE_ORDER, []),
    }


@router.put("/config")
def set_config(p: ConfigPayload, db: Session = Depends(get_db)):
    if p.locked is not None:
        _ecrire_config(db, _CLE_LOCKED, "1" if p.locked else "0")
    if p.custom_types is not None:
        _ecrire_config(db, _CLE_CUSTOM_TYPES, json.dumps(p.custom_types, ensure_ascii=False))
    if p.order is not None:
        _ecrire_config(db, _CLE_ORDER, json.dumps(p.order, ensure_ascii=False))
    db.commit()
    return {"ok": True}


@router.put("/{type_name:path}")
def save_modele(type_name: str, p: ChampsPayload, db: Session = Depends(get_db)):
    m = db.query(ModeleChapitre).filter(ModeleChapitre.type_name == type_name).first()
    champs_json = json.dumps(p.fields, ensure_ascii=False)
    if m:
        m.champs_json = champs_json
    else:
        db.add(ModeleChapitre(type_name=type_name, champs_json=champs_json))
    db.commit()
    return {"type_name": type_name, "fields": p.fields}


@router.delete("/{type_name:path}", status_code=204)
def delete_modele(type_name: str, db: Session = Depends(get_db)):
    m = db.query(ModeleChapitre).filter(ModeleChapitre.type_name == type_name).first()
    if m:
        db.delete(m)
        db.commit()
    return None

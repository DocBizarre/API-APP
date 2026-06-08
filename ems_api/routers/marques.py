"""Endpoints REST pour les marques moteur (table de paramétrage)."""
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.configurations import MarqueMoteur

router = APIRouter(prefix="/marques-moteur", tags=["marques-moteur"])


class LibellePayload(BaseModel):
    libelle: str


class RenamePayload(BaseModel):
    old: str
    new: str


@router.get("", response_model=List[Dict])
def list_marques(db: Session = Depends(get_db)):
    return [{"id": m.id, "libelle": m.libelle, "ordre": m.ordre}
            for m in db.query(MarqueMoteur).order_by(MarqueMoteur.ordre).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_marque(p: LibellePayload, db: Session = Depends(get_db)):
    if db.query(MarqueMoteur).filter(MarqueMoteur.libelle == p.libelle).first():
        raise HTTPException(409, f"Marque '{p.libelle}' existe déjà")
    ordre = db.query(MarqueMoteur).count()
    m = MarqueMoteur(libelle=p.libelle, ordre=ordre)
    db.add(m)
    db.commit()
    return {"id": m.id, "libelle": m.libelle, "ordre": m.ordre}


@router.put("")
def rename_marque(p: RenamePayload, db: Session = Depends(get_db)):
    m = db.query(MarqueMoteur).filter(MarqueMoteur.libelle == p.old).first()
    if not m:
        raise HTTPException(404, f"Marque '{p.old}' introuvable")
    m.libelle = p.new
    db.commit()
    return {"id": m.id, "libelle": m.libelle}


@router.delete("/{libelle}", status_code=status.HTTP_204_NO_CONTENT)
def delete_marque(libelle: str, db: Session = Depends(get_db)):
    m = db.query(MarqueMoteur).filter(MarqueMoteur.libelle == libelle).first()
    if not m:
        raise HTTPException(404, f"Marque '{libelle}' introuvable")
    db.delete(m)
    db.commit()
    return None

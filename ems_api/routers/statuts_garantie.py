"""Endpoints REST pour les statuts de garantie (table de paramétrage)."""
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.configurations import StatutGarantie

router = APIRouter(prefix="/statuts-garantie", tags=["statuts-garantie"])


class LibellePayload(BaseModel):
    libelle: str


class RenamePayload(BaseModel):
    old: str
    new: str


@router.get("", response_model=List[Dict])
def list_statuts(db: Session = Depends(get_db)):
    return [{"id": s.id, "libelle": s.libelle, "ordre": s.ordre}
            for s in db.query(StatutGarantie)
                       .order_by(StatutGarantie.ordre).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_statut(p: LibellePayload, db: Session = Depends(get_db)):
    if db.query(StatutGarantie).filter(
            StatutGarantie.libelle == p.libelle).first():
        raise HTTPException(409, f"Statut '{p.libelle}' existe déjà")
    ordre = db.query(StatutGarantie).count()
    s = StatutGarantie(libelle=p.libelle, ordre=ordre)
    db.add(s)
    db.commit()
    return {"id": s.id, "libelle": s.libelle, "ordre": s.ordre}


@router.put("")
def rename_statut(p: RenamePayload, db: Session = Depends(get_db)):
    s = db.query(StatutGarantie).filter(
        StatutGarantie.libelle == p.old).first()
    if not s:
        raise HTTPException(404, f"Statut '{p.old}' introuvable")
    s.libelle = p.new
    db.commit()
    return {"id": s.id, "libelle": s.libelle}


@router.delete("/{libelle}", status_code=status.HTTP_204_NO_CONTENT)
def delete_statut(libelle: str, db: Session = Depends(get_db)):
    s = db.query(StatutGarantie).filter(
        StatutGarantie.libelle == libelle).first()
    if not s:
        raise HTTPException(404, f"Statut '{libelle}' introuvable")
    db.delete(s)
    db.commit()
    return None


@router.post("/reorder")
def reorder_statuts(libelles: List[str], db: Session = Depends(get_db)):
    for i, lib in enumerate(libelles):
        s = db.query(StatutGarantie).filter(
            StatutGarantie.libelle == lib).first()
        if s:
            s.ordre = i
    db.commit()
    return {"ok": True}

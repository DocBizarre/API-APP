"""Endpoints REST pour les types d'intervention (table de paramétrage)."""
from typing import List, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.configurations import TypeIntervention

router = APIRouter(prefix="/types-intervention", tags=["types-intervention"])


class LibellePayload(BaseModel):
    libelle: str


class RenamePayload(BaseModel):
    old: str
    new: str


@router.get("", response_model=List[Dict])
def list_types(db: Session = Depends(get_db)):
    return [{"id": t.id, "libelle": t.libelle, "ordre": t.ordre}
            for t in db.query(TypeIntervention)
                       .order_by(TypeIntervention.ordre).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_type(p: LibellePayload, db: Session = Depends(get_db)):
    if db.query(TypeIntervention).filter(
            TypeIntervention.libelle == p.libelle).first():
        raise HTTPException(409, f"Type '{p.libelle}' existe déjà")
    ordre = (db.query(TypeIntervention).count())
    t = TypeIntervention(libelle=p.libelle, ordre=ordre)
    db.add(t)
    db.commit()
    return {"id": t.id, "libelle": t.libelle, "ordre": t.ordre}


@router.put("")
def rename_type(p: RenamePayload, db: Session = Depends(get_db)):
    t = db.query(TypeIntervention).filter(
        TypeIntervention.libelle == p.old).first()
    if not t:
        raise HTTPException(404, f"Type '{p.old}' introuvable")
    t.libelle = p.new
    db.commit()
    return {"id": t.id, "libelle": t.libelle}


@router.delete("/{libelle}", status_code=status.HTTP_204_NO_CONTENT)
def delete_type(libelle: str, db: Session = Depends(get_db)):
    t = db.query(TypeIntervention).filter(
        TypeIntervention.libelle == libelle).first()
    if not t:
        raise HTTPException(404, f"Type '{libelle}' introuvable")
    db.delete(t)
    db.commit()
    return None


@router.post("/reorder")
def reorder_types(libelles: List[str], db: Session = Depends(get_db)):
    """Réordonne selon la liste fournie."""
    for i, lib in enumerate(libelles):
        t = db.query(TypeIntervention).filter(
            TypeIntervention.libelle == lib).first()
        if t:
            t.ordre = i
    db.commit()
    return {"ok": True}

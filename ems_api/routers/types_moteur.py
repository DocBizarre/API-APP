"""Endpoints REST pour les types de moteur (table de paramétrage)."""
from typing import List, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.configurations import TypeMoteur

router = APIRouter(prefix="/types-moteur", tags=["types-moteur"])


class LibellePayload(BaseModel):
    libelle: str
    marque: str = ""


class RenamePayload(BaseModel):
    old: str
    new: str
    marque: Optional[str] = None


@router.get("", response_model=List[Dict])
def list_types(db: Session = Depends(get_db)):
    return [{"id": t.id, "libelle": t.libelle, "ordre": t.ordre, "marque": t.marque or ""}
            for t in db.query(TypeMoteur).order_by(TypeMoteur.ordre).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def add_type(p: LibellePayload, db: Session = Depends(get_db)):
    if db.query(TypeMoteur).filter(TypeMoteur.libelle == p.libelle).first():
        raise HTTPException(409, f"Type '{p.libelle}' existe déjà")
    ordre = db.query(TypeMoteur).count()
    t = TypeMoteur(libelle=p.libelle, ordre=ordre, marque=p.marque)
    db.add(t)
    db.commit()
    return {"id": t.id, "libelle": t.libelle, "ordre": t.ordre, "marque": t.marque or ""}


@router.put("")
def rename_type(p: RenamePayload, db: Session = Depends(get_db)):
    t = db.query(TypeMoteur).filter(TypeMoteur.libelle == p.old).first()
    if not t:
        raise HTTPException(404, f"Type '{p.old}' introuvable")
    t.libelle = p.new
    if p.marque is not None:
        t.marque = p.marque
    db.commit()
    return {"id": t.id, "libelle": t.libelle, "marque": t.marque or ""}


@router.delete("/{libelle}", status_code=status.HTTP_204_NO_CONTENT)
def delete_type(libelle: str, db: Session = Depends(get_db)):
    t = db.query(TypeMoteur).filter(TypeMoteur.libelle == libelle).first()
    if not t:
        raise HTTPException(404, f"Type '{libelle}' introuvable")
    db.delete(t)
    db.commit()
    return None


@router.post("/reorder")
def reorder_types(libelles: List[str], db: Session = Depends(get_db)):
    """Réordonne selon la liste fournie."""
    for i, lib in enumerate(libelles):
        t = db.query(TypeMoteur).filter(TypeMoteur.libelle == lib).first()
        if t:
            t.ordre = i
    db.commit()
    return {"ok": True}

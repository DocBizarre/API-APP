"""Endpoints REST pour la ressource Technicien."""
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Technicien
from ..schemas.technicien import TechnicienCreate, TechnicienUpdate, TechnicienOut

router = APIRouter(prefix="/techniciens", tags=["techniciens"])


@router.get("", response_model=List[TechnicienOut])
def list_techniciens(db: Session = Depends(get_db)):
    return db.query(Technicien).order_by(Technicien.nom).all()


@router.get("/{tech_id}", response_model=TechnicienOut)
def get_technicien(tech_id: str, db: Session = Depends(get_db)):
    t = db.query(Technicien).filter(Technicien.id == tech_id).first()
    if not t:
        raise HTTPException(404, f"Technicien {tech_id} introuvable")
    return t


@router.post("", response_model=TechnicienOut,
             status_code=status.HTTP_201_CREATED)
def create_technicien(data: TechnicienCreate, db: Session = Depends(get_db)):
    """Crée ou met à jour un technicien (upsert par nom)."""
    existing = db.query(Technicien).filter(Technicien.nom == data.nom).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing
    t = Technicien(id=str(uuid4()), **data.model_dump())
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.put("/{tech_id}", response_model=TechnicienOut)
def update_technicien(tech_id: str, data: TechnicienUpdate,
                      db: Session = Depends(get_db)):
    t = db.query(Technicien).filter(Technicien.id == tech_id).first()
    if not t:
        raise HTTPException(404, f"Technicien {tech_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(t, field, value)
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{tech_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_technicien(tech_id: str, db: Session = Depends(get_db)):
    t = db.query(Technicien).filter(Technicien.id == tech_id).first()
    if not t:
        raise HTTPException(404, f"Technicien {tech_id} introuvable")
    db.delete(t)
    db.commit()
    return None

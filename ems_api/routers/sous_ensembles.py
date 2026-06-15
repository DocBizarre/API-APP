"""Endpoints REST pour les sous-ensembles d'un moteur."""
from typing import List, Optional
from uuid import uuid4
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from ..database import get_db
from ..models import Moteur
from ..models.sous_ensemble import SousEnsemble

router = APIRouter(prefix="/moteurs", tags=["sous-ensembles"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SousEnsembleCreate(BaseModel):
    libelle:    str
    reference:  str = ""
    marque:     str = ""
    num_serie:  str = ""
    etat:       str = ""
    notes:      str = ""


class SousEnsembleUpdate(BaseModel):
    libelle:    Optional[str] = None
    reference:  Optional[str] = None
    marque:     Optional[str] = None
    num_serie:  Optional[str] = None
    etat:       Optional[str] = None
    notes:      Optional[str] = None


class SousEnsembleOut(BaseModel):
    id:         str
    moteur_id:  str
    libelle:    str
    reference:  str
    marque:     str
    num_serie:  str
    etat:       str
    notes:      str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


def _to_out(se: SousEnsemble) -> dict:
    return {
        "id":         se.id,
        "moteur_id":  se.moteur_id,
        "libelle":    se.libelle or "",
        "reference":  se.reference or "",
        "marque":     se.marque or "",
        "num_serie":  se.num_serie or "",
        "etat":       se.etat or "",
        "notes":      se.notes or "",
        "created_at": se.created_at,
        "updated_at": se.updated_at,
    }


def _get_moteur_or_404(moteur_id: str, db: Session) -> Moteur:
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    return m


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/{moteur_id}/sous-ensembles", response_model=List[SousEnsembleOut])
def list_sous_ensembles(moteur_id: str, db: Session = Depends(get_db)):
    _get_moteur_or_404(moteur_id, db)
    items = (db.query(SousEnsemble)
               .filter(SousEnsemble.moteur_id == moteur_id)
               .order_by(SousEnsemble.libelle)
               .all())
    return [_to_out(se) for se in items]


@router.post("/{moteur_id}/sous-ensembles",
             response_model=SousEnsembleOut,
             status_code=status.HTTP_201_CREATED)
def create_sous_ensemble(moteur_id: str, data: SousEnsembleCreate,
                         db: Session = Depends(get_db)):
    _get_moteur_or_404(moteur_id, db)
    se = SousEnsemble(id=str(uuid4()), moteur_id=moteur_id, **data.model_dump())
    db.add(se)
    db.commit()
    db.refresh(se)
    return _to_out(se)


@router.put("/{moteur_id}/sous-ensembles/{se_id}", response_model=SousEnsembleOut)
def update_sous_ensemble(moteur_id: str, se_id: str, data: SousEnsembleUpdate,
                         db: Session = Depends(get_db)):
    _get_moteur_or_404(moteur_id, db)
    se = db.query(SousEnsemble).filter(
        SousEnsemble.id == se_id,
        SousEnsemble.moteur_id == moteur_id,
    ).first()
    if not se:
        raise HTTPException(404, f"Sous-ensemble {se_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(se, field, value)
    db.commit()
    db.refresh(se)
    return _to_out(se)


@router.delete("/{moteur_id}/sous-ensembles/{se_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_sous_ensemble(moteur_id: str, se_id: str, db: Session = Depends(get_db)):
    _get_moteur_or_404(moteur_id, db)
    se = db.query(SousEnsemble).filter(
        SousEnsemble.id == se_id,
        SousEnsemble.moteur_id == moteur_id,
    ).first()
    if not se:
        raise HTTPException(404, f"Sous-ensemble {se_id} introuvable")
    db.delete(se)
    db.commit()
    return None

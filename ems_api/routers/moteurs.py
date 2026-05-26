"""Endpoints REST pour la ressource Moteur."""
from typing import List, Optional
from uuid import uuid4
from sqlalchemy.orm import joinedload
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Moteur, Client
from ..schemas.moteur import MoteurCreate, MoteurUpdate, MoteurOut

router = APIRouter(prefix="/moteurs", tags=["moteurs"])


def _to_out(m: Moteur) -> dict:
    """Sérialise un moteur en garantissant TOUS les champs (jamais None)."""
    d = {}
    for c in m.__table__.columns:
        val = getattr(m, c.name)
        # Convertir None en "" pour les colonnes string
        if val is None and not c.name.endswith("_at"):
            val = ""
        d[c.name] = val
    d["client_nom"] = m.client.nom if m.client else ""
    return d


@router.get("", response_model=List[MoteurOut])
def list_moteurs(
    search: Optional[str] = Query(None),
    serie_only: bool = Query(False, description="Recherche uniquement par N° série"),
    db: Session = Depends(get_db),
):
    q = db.query(Moteur).options(joinedload(Moteur.client))
    if search:
        like = f"%{search}%"
        if serie_only:
            q = q.filter(Moteur.num_serie.ilike(like))
        else:
            # outerjoin Client pour pouvoir chercher par nom client
            q = q.outerjoin(Client).filter(
                or_(Moteur.num_serie.ilike(like),
                    Moteur.marque.ilike(like),
                    Moteur.navire.ilike(like),
                    Moteur.machine.ilike(like),
                    Moteur.ref_constructeur.ilike(like),
                    Moteur.code_affaire.ilike(like),
                    Client.nom.ilike(like)))
    return [_to_out(m) for m in q.order_by(Moteur.num_serie).all()]


@router.get("/garantie-expirante", response_model=List[MoteurOut])
def list_moteurs_garantie_expirante(
    jours_max: int = Query(90, description="Jours avant expiration"),
    db: Session = Depends(get_db),
):
    """Moteurs dont la garantie (date + durée) expire dans les N jours."""
    from datetime import datetime, timedelta
    moteurs = db.query(Moteur).all()
    res = []
    seuil = datetime.now() + timedelta(days=jours_max)
    for m in moteurs:
        if not m.date_mise_service or not m.duree_garantie:
            continue
        try:
            d = datetime.strptime(m.date_mise_service, "%d/%m/%Y")
            mois = int(str(m.duree_garantie).strip())
            fin = d + timedelta(days=mois * 30)
            if datetime.now() <= fin <= seuil:
                res.append(_to_out(m))
        except (ValueError, TypeError):
            continue
    return res


@router.get("/by-serie/{num_serie}", response_model=Optional[MoteurOut])
def find_by_serie(num_serie: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.num_serie == num_serie).first()
    return _to_out(m) if m else None


@router.get("/{moteur_id}", response_model=MoteurOut)
def get_moteur(moteur_id: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    return _to_out(m)


@router.post("", response_model=MoteurOut, status_code=status.HTTP_201_CREATED)
def create_moteur(data: MoteurCreate, db: Session = Depends(get_db)):
    """Crée ou met à jour un moteur (upsert sur num_serie)."""
    if not db.query(Client).filter(Client.id == data.client_id).first():
        raise HTTPException(400, f"Client {data.client_id} introuvable")
    existing = db.query(Moteur).filter(Moteur.num_serie == data.num_serie).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    m = Moteur(id=str(uuid4()), **data.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.put("/{moteur_id}", response_model=MoteurOut)
def update_moteur(moteur_id: str, data: MoteurUpdate,
                  db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(m, field, value)
    db.commit()
    db.refresh(m)
    return _to_out(m)


@router.delete("/{moteur_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_moteur(moteur_id: str, db: Session = Depends(get_db)):
    m = db.query(Moteur).filter(Moteur.id == moteur_id).first()
    if not m:
        raise HTTPException(404, f"Moteur {moteur_id} introuvable")
    db.delete(m)
    db.commit()
    return None

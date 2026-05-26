"""Endpoints REST pour l'Amélioration continue."""
from typing import List, Optional, Dict
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Amelioration, Client
from ..schemas.amelioration import (
    AmeliorationCreate, AmeliorationUpdate, AmeliorationOut,
)
from ..services.numerotation import next_num_amelioration


router = APIRouter(prefix="/ameliorations", tags=["ameliorations"])


def _to_out(a: Amelioration) -> dict:
    d = {}
    for c in a.__table__.columns:
        val = getattr(a, c.name)
        if val is None and not c.name.endswith("_at"):
            val = ""
        d[c.name] = val
    d["client_nom"] = a.client.nom if a.client else ""
    return d


@router.get("", response_model=List[AmeliorationOut])
def list_ameliorations(
    statut: Optional[str] = None,
    priorite: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Amelioration)
    if statut and statut != "Tous":
        q = q.filter(Amelioration.statut == statut)
    if priorite:
        q = q.filter(Amelioration.priorite == priorite)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Client).filter(
            or_(Amelioration.num_ticket.ilike(like),
                Amelioration.titre.ilike(like),
                Amelioration.description.ilike(like),
                Client.nom.ilike(like))
        )
    q = q.order_by(Amelioration.created_at.desc())
    return [_to_out(a) for a in q.all()]


@router.get("/stats", response_model=Dict[str, int])
def stats(db: Session = Depends(get_db)):
    """Statistiques par statut + total."""
    res = {"Nouveau": 0, "À étudier": 0, "En cours": 0,
            "Résolu": 0, "Refusé": 0, "Total": 0}
    for a in db.query(Amelioration).all():
        res["Total"] += 1
        if a.statut in res:
            res[a.statut] += 1
        else:
            res[a.statut] = res.get(a.statut, 0) + 1
    return res


@router.get("/by-num/{num_ticket}", response_model=AmeliorationOut)
def get_by_num(num_ticket: str, db: Session = Depends(get_db)):
    a = db.query(Amelioration).filter(
        Amelioration.num_ticket == num_ticket).first()
    if not a:
        raise HTTPException(404, f"Ticket {num_ticket} introuvable")
    return _to_out(a)


@router.get("/{amelio_id}", response_model=AmeliorationOut)
def get_amelioration(amelio_id: str, db: Session = Depends(get_db)):
    a = db.query(Amelioration).filter(Amelioration.id == amelio_id).first()
    if not a:
        raise HTTPException(404, f"Amélioration {amelio_id} introuvable")
    return _to_out(a)


@router.post("", response_model=AmeliorationOut,
             status_code=status.HTTP_201_CREATED)
def create_amelioration(data: AmeliorationCreate,
                        db: Session = Depends(get_db)):
    payload = data.model_dump()
    if not payload.get("num_ticket"):
        payload["num_ticket"] = next_num_amelioration(db)
    a = Amelioration(id=str(uuid4()), **payload)
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.put("/{amelio_id}", response_model=AmeliorationOut)
def update_amelioration(amelio_id: str, data: AmeliorationUpdate,
                        db: Session = Depends(get_db)):
    a = db.query(Amelioration).filter(Amelioration.id == amelio_id).first()
    if not a:
        raise HTTPException(404, f"Amélioration {amelio_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(a, field, value)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{amelio_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_amelioration(amelio_id: str, db: Session = Depends(get_db)):
    a = db.query(Amelioration).filter(Amelioration.id == amelio_id).first()
    if not a:
        raise HTTPException(404, f"Amélioration {amelio_id} introuvable")
    db.delete(a)
    db.commit()
    return None

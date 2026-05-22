"""Endpoints REST pour les Interventions (+ signatures + notifications)."""
from typing import List, Optional
from uuid import uuid4
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Intervention, Client, Moteur
from ..schemas.intervention import (
    InterventionCreate, InterventionUpdate, InterventionOut, SignatureIn,
)
from ..services.numerotation import next_num_bon


# Heure Paris (sans dépendance externe)
PARIS = timezone(timedelta(hours=1))   # UTC+1 (CET) — ajuster si besoin DST


router = APIRouter(prefix="/interventions", tags=["interventions"])


def _to_out(inv: Intervention) -> dict:
    d = {c.name: getattr(inv, c.name) for c in inv.__table__.columns}
    d["client_nom"] = inv.client.nom if inv.client else None
    d["moteur_serie"] = inv.moteur.num_serie if inv.moteur else None
    return d


@router.get("", response_model=List[InterventionOut])
def list_interventions(
    statut: Optional[str] = None,
    urgence: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Intervention)
    if statut and statut != "Tous":
        q = q.filter(Intervention.statut == statut)
    if urgence:
        q = q.filter(Intervention.urgence == urgence)
    if search:
        like = f"%{search}%"
        # Recherche dans num_bon + technicien + (via jointure) client.nom + moteur.num_serie
        q = q.outerjoin(Client).outerjoin(Moteur).filter(
            or_(Intervention.num_bon.ilike(like),
                Intervention.technicien.ilike(like),
                Client.nom.ilike(like),
                Moteur.num_serie.ilike(like))
        )
    q = q.order_by(Intervention.created_at.desc())
    return [_to_out(i) for i in q.all()]


@router.get("/urgentes", response_model=List[InterventionOut])
def list_urgentes(limit: int = Query(10, ge=1, le=100),
                  db: Session = Depends(get_db)):
    """Interventions urgentes/critiques en cours."""
    q = (db.query(Intervention)
         .filter(Intervention.urgence.in_(("Urgente", "Critique")))
         .filter(Intervention.statut == "En cours")
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/non-notifies", response_model=List[InterventionOut])
def list_non_notifies(limit: int = Query(50, ge=1, le=500),
                       db: Session = Depends(get_db)):
    """Interventions en cours dont client OU technicien n'est pas notifié."""
    q = (db.query(Intervention)
         .filter(Intervention.statut == "En cours")
         .filter((Intervention.client_notifie == 0) |
                 (Intervention.tech_notifie == 0))
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/by-moteur/{moteur_id}", response_model=List[InterventionOut])
def list_for_moteur(moteur_id: str, db: Session = Depends(get_db)):
    q = (db.query(Intervention)
         .filter(Intervention.moteur_id == moteur_id)
         .order_by(Intervention.created_at.desc()))
    return [_to_out(i) for i in q.all()]


@router.get("/by-num/{num_bon}", response_model=InterventionOut)
def get_by_num(num_bon: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.num_bon == num_bon).first()
    if not inv:
        raise HTTPException(404, f"Bon {num_bon} introuvable")
    return _to_out(inv)


@router.get("/{inv_id}", response_model=InterventionOut)
def get_intervention(inv_id: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    return _to_out(inv)


@router.post("", response_model=InterventionOut,
             status_code=status.HTTP_201_CREATED)
def create_intervention(data: InterventionCreate, db: Session = Depends(get_db)):
    num_bon = next_num_bon(db)
    inv = Intervention(id=str(uuid4()), num_bon=num_bon, **data.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


@router.put("/{inv_id}", response_model=InterventionOut)
def update_intervention(inv_id: str, data: InterventionUpdate,
                        db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(inv, field, value)
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


@router.delete("/{inv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intervention(inv_id: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    db.delete(inv)
    db.commit()
    return None


# ─── Signatures ──────────────────────────────────────────────────────────────
@router.post("/{inv_id}/signature", response_model=InterventionOut)
def enregistrer_signature(inv_id: str, payload: SignatureIn,
                          db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    horod = datetime.now(PARIS).strftime("%d/%m/%Y %H:%M")
    if payload.role == "technicien":
        inv.signature_tech_b64 = payload.signature_b64
        inv.signature_tech_nom = payload.signature_nom
        inv.signature_tech_date = horod
    else:
        inv.signature_b64 = payload.signature_b64
        inv.signature_nom = payload.signature_nom
        inv.signature_date = horod
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


# ─── Notifications ───────────────────────────────────────────────────────────
@router.post("/{inv_id}/notifie/{kind}", response_model=InterventionOut)
def mark_notifie(inv_id: str, kind: str, db: Session = Depends(get_db)):
    """kind = 'client' ou 'tech'."""
    if kind not in ("client", "tech"):
        raise HTTPException(400, "kind doit être 'client' ou 'tech'")
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    if kind == "client":
        inv.client_notifie = 1
    else:
        inv.tech_notifie = 1
    db.commit()
    db.refresh(inv)
    return _to_out(inv)

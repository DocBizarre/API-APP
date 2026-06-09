"""Endpoints REST pour les Affaires et leurs items."""
from typing import List, Optional
from uuid import uuid4
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.affaire import Affaire, AffaireItem
from ..models.client import Client
from ..schemas.affaire import (
    AffaireCreate, AffaireUpdate, AffaireOut,
    AffaireItemCreate, AffaireItemUpdate, AffaireItemOut,
)
from ..services.numerotation import next_num_affaire
from ..config import settings

router = APIRouter(prefix="/affaires", tags=["affaires"])

STATUTS = ["En cours", "En attente", "Clos", "Annulé"]


def _to_out(a: Affaire) -> dict:
    d = {c.name: (getattr(a, c.name) or "") for c in a.__table__.columns}
    d["client_nom"] = a.client.nom if a.client else ""
    d["nb_items"] = len(a.items)
    return d


def _item_to_out(it: AffaireItem) -> dict:
    d = {}
    for c in it.__table__.columns:
        val = getattr(it, c.name)
        if val is None:
            d[c.name] = 0 if str(c.type) == "INTEGER" else ""
        else:
            d[c.name] = val
    return d


def _create_dossier(num_affaire: str) -> str:
    """Crée le dossier racine de l'affaire et retourne son chemin."""
    try:
        base = Path(settings.DOSSIERS_DIR) / "affaires" / num_affaire
        base.mkdir(parents=True, exist_ok=True)
        return str(base)
    except Exception:
        return ""


# ─── Affaires ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AffaireOut])
def list_affaires(
    statut: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Affaire)
    if statut and statut not in ("Tous", "Toutes"):
        q = q.filter(Affaire.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Client).filter(
            or_(Affaire.num_affaire.ilike(like),
                Affaire.nom_projet.ilike(like),
                Affaire.navire_machine.ilike(like),
                Affaire.ref_interne.ilike(like),
                Affaire.charge_affaire.ilike(like),
                Client.nom.ilike(like))
        )
    q = q.order_by(Affaire.created_at.desc())
    return [_to_out(a) for a in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/{affaire_id}", response_model=AffaireOut)
def get_affaire(affaire_id: str, db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    return _to_out(a)


@router.post("", response_model=AffaireOut, status_code=201)
def create_affaire(body: AffaireCreate, db: Session = Depends(get_db)):
    num = body.num_affaire or next_num_affaire(db)
    dossier = _create_dossier(num)
    a = Affaire(
        id=str(uuid4()),
        num_affaire=num,
        client_id=body.client_id or None,
        nom_projet=body.nom_projet,
        navire_machine=body.navire_machine,
        ref_interne=body.ref_interne,
        charge_affaire=body.charge_affaire,
        date_debut=body.date_debut,
        date_fin_prevue=body.date_fin_prevue,
        date_cloture=body.date_cloture,
        statut=body.statut,
        description=body.description,
        commentaires=body.commentaires,
        dossier_path=dossier,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.put("/{affaire_id}", response_model=AffaireOut)
def update_affaire(affaire_id: str, body: AffaireUpdate,
                   db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(a, field, val)
    a.version = (a.version or 1) + 1
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{affaire_id}", status_code=204)
def delete_affaire(affaire_id: str, db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    db.delete(a)
    db.commit()


# ─── Items d'une affaire ─────────────────────────────────────────────────────

@router.get("/{affaire_id}/items", response_model=List[AffaireItemOut])
def list_items(affaire_id: str, db: Session = Depends(get_db)):
    return [_item_to_out(it) for it in
            db.query(AffaireItem)
              .filter(AffaireItem.affaire_id == affaire_id)
              .order_by(AffaireItem.ordre)
              .all()]


@router.post("/{affaire_id}/items", response_model=AffaireItemOut, status_code=201)
def add_item(affaire_id: str, body: AffaireItemCreate,
             db: Session = Depends(get_db)):
    if not db.query(Affaire).filter(Affaire.id == affaire_id).first():
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    it = AffaireItem(
        id=str(uuid4()),
        affaire_id=affaire_id,
        **body.model_dump(),
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return _item_to_out(it)


@router.put("/{affaire_id}/items/{item_id}", response_model=AffaireItemOut)
def update_item(affaire_id: str, item_id: str, body: AffaireItemUpdate,
                db: Session = Depends(get_db)):
    it = db.query(AffaireItem).filter(
        AffaireItem.id == item_id,
        AffaireItem.affaire_id == affaire_id,
    ).first()
    if not it:
        raise HTTPException(404, "Item introuvable")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(it, field, val)
    it.version = (it.version or 1) + 1
    db.commit()
    db.refresh(it)
    return _item_to_out(it)


@router.delete("/{affaire_id}/items/{item_id}", status_code=204)
def delete_item(affaire_id: str, item_id: str, db: Session = Depends(get_db)):
    it = db.query(AffaireItem).filter(
        AffaireItem.id == item_id,
        AffaireItem.affaire_id == affaire_id,
    ).first()
    if not it:
        raise HTTPException(404, "Item introuvable")
    db.delete(it)
    db.commit()

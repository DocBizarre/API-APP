"""Endpoints REST pour les Garanties."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Garantie, Moteur, Client
from ..schemas.garantie import GarantieCreate, GarantieUpdate, GarantieOut
from ..services.numerotation import next_num_garantie


router = APIRouter(prefix="/garanties", tags=["garanties"])


def _to_out(g: Garantie) -> dict:
    """Sérialise une garantie en garantissant TOUS les champs (jamais None)."""
    d = {}
    for c in g.__table__.columns:
        val = getattr(g, c.name)
        if val is None and not c.name.endswith("_at"):
            val = ""
        d[c.name] = val
    d["client_nom"]    = g.client.nom if g.client else ""
    d["moteur_serie"]  = g.moteur.num_serie if g.moteur else ""
    # Alias pour le code Tkinter qui utilise num_serie directement
    d["num_serie"]     = g.moteur.num_serie if g.moteur else ""
    d["marque"]        = g.moteur.marque if g.moteur else ""
    d["moteur_marque"] = g.moteur.marque if g.moteur else ""
    return d


@router.get("", response_model=List[GarantieOut])
def list_garanties(
    statut: Optional[str] = None,
    search: Optional[str] = None,
    attribution: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Garantie)
    if statut and statut != "Tous":
        q = q.filter(Garantie.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Client).outerjoin(Moteur).filter(
            or_(Garantie.num_ems.ilike(like),
                Garantie.num_constructeur.ilike(like),
                Garantie.attribution.ilike(like),
                Client.nom.ilike(like),
                Moteur.num_serie.ilike(like))
        )
    if attribution and attribution not in ("Toutes", "Tous"):
        q = q.filter(Garantie.attribution == attribution)
    q = q.order_by(Garantie.created_at.desc())
    return [_to_out(g) for g in q.all()]


@router.get("/attributions", response_model=List[str])
def list_attributions(db: Session = Depends(get_db)):
    """Liste des attributions (marques moteurs + options internes)."""
    marques = (db.query(Moteur.marque).distinct()
               .filter(Moteur.marque != "").all())
    res = sorted({m[0] for m in marques if m[0]})
    res.extend(["Constructeur", "Interne EMS", "Mixte"])
    # dédoublonner en préservant ordre
    seen = set()
    out = []
    for x in res:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


@router.get("/by-moteur/{moteur_id}", response_model=List[GarantieOut])
def list_for_moteur(moteur_id: str, db: Session = Depends(get_db)):
    q = (db.query(Garantie).filter(Garantie.moteur_id == moteur_id)
         .order_by(Garantie.created_at.desc()))
    return [_to_out(g) for g in q.all()]


@router.get("/by-num/{num_ems}", response_model=GarantieOut)
def get_by_num(num_ems: str, db: Session = Depends(get_db)):
    g = db.query(Garantie).filter(Garantie.num_ems == num_ems).first()
    if not g:
        raise HTTPException(404, f"Garantie {num_ems} introuvable")
    return _to_out(g)


@router.get("/{garantie_id}", response_model=GarantieOut)
def get_garantie(garantie_id: str, db: Session = Depends(get_db)):
    g = db.query(Garantie).filter(Garantie.id == garantie_id).first()
    if not g:
        raise HTTPException(404, f"Garantie {garantie_id} introuvable")
    return _to_out(g)


@router.post("", response_model=GarantieOut,
             status_code=status.HTTP_201_CREATED)
def create_garantie(data: GarantieCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    if not payload.get("num_ems"):
        payload["num_ems"] = next_num_garantie(db)
    g = Garantie(id=str(uuid4()), **payload)
    db.add(g)
    db.commit()
    db.refresh(g)
    return _to_out(g)


@router.put("/{garantie_id}", response_model=GarantieOut)
def update_garantie(garantie_id: str, data: GarantieUpdate,
                    db: Session = Depends(get_db)):
    g = db.query(Garantie).filter(Garantie.id == garantie_id).first()
    if not g:
        raise HTTPException(404, f"Garantie {garantie_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(g, field, value)
    db.commit()
    db.refresh(g)
    return _to_out(g)


@router.delete("/{garantie_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_garantie(garantie_id: str, db: Session = Depends(get_db)):
    g = db.query(Garantie).filter(Garantie.id == garantie_id).first()
    if not g:
        raise HTTPException(404, f"Garantie {garantie_id} introuvable")
    db.delete(g)
    db.commit()
    return None

"""Endpoints REST pour la ressource Navire (registre auto-alimenté, cf. fournisseurs.py)."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_

from ..database import get_db
from ..models import Navire
from ..schemas.navire import NavireCreate, NavireUpdate, NavireOut

router = APIRouter(prefix="/navires", tags=["navires"])


def _to_out(n: Navire) -> dict:
    d = {}
    for col in n.__table__.columns:
        val = getattr(n, col.name)
        if val is None and not col.name.endswith("_at") and col.name != "proprietaire_id":
            val = ""
        d[col.name] = val
    d["proprietaire_nom"] = n.proprietaire.nom if n.proprietaire else ""
    return d


def _upsert_navire(db: Session, nom: str, immatriculation: str = "",
                   port_attache: str = "", proprietaire_id: Optional[str] = None) -> None:
    """Mémorise ou met à jour un navire dans la table navires
    (fail-safe, savepoint pour ne pas annuler la transaction parente)."""
    nom = (nom or "").strip()
    if not nom:
        return
    try:
        with db.begin_nested():
            existing = db.query(Navire).filter(Navire.nom == nom).first()
            if existing:
                existing.usage_count = (existing.usage_count or 0) + 1
                # Immatriculation / port d'attache : une saisie explicite corrige
                # la valeur connue (donnée factuelle du navire, pas une supposition).
                if immatriculation:
                    existing.immatriculation = immatriculation
                if port_attache:
                    existing.port_attache = port_attache
                # Propriétaire : ne complète que si inconnu (le client d'un moteur
                # n'est pas forcément le propriétaire du navire — ex. exploitant).
                if proprietaire_id and not existing.proprietaire_id:
                    existing.proprietaire_id = proprietaire_id
            else:
                db.add(Navire(
                    id=str(uuid4()),
                    nom=nom,
                    immatriculation=(immatriculation or "").strip(),
                    port_attache=(port_attache or "").strip(),
                    proprietaire_id=proprietaire_id,
                    usage_count=1,
                ))
    except Exception:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Impossible d'upsert le navire %r (table absente ou erreur schema).", nom
        )


@router.get("", response_model=List[NavireOut])
def list_navires(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Navire).options(joinedload(Navire.proprietaire))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Navire.nom.ilike(like),
                         Navire.immatriculation.ilike(like)))
    navires = q.order_by(Navire.usage_count.desc(), Navire.nom).all()
    return [_to_out(n) for n in navires]


@router.get("/by-nom/{nom}", response_model=Optional[NavireOut])
def find_by_nom(nom: str, db: Session = Depends(get_db)):
    n = db.query(Navire).filter(Navire.nom == nom).first()
    return _to_out(n) if n else None


@router.get("/{navire_id}", response_model=NavireOut)
def get_navire(navire_id: str, db: Session = Depends(get_db)):
    n = db.query(Navire).filter(Navire.id == navire_id).first()
    if not n:
        raise HTTPException(404, f"Navire {navire_id} introuvable")
    return _to_out(n)


@router.post("", response_model=NavireOut, status_code=status.HTTP_201_CREATED)
def create_navire(data: NavireCreate, db: Session = Depends(get_db)):
    """Crée ou met à jour un navire (upsert sur nom)."""
    existing = db.query(Navire).filter(Navire.nom == data.nom).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    n = Navire(id=str(uuid4()), **data.model_dump())
    db.add(n)
    db.commit()
    db.refresh(n)
    return _to_out(n)


@router.put("/{navire_id}", response_model=NavireOut)
def update_navire(navire_id: str, data: NavireUpdate,
                  db: Session = Depends(get_db)):
    n = db.query(Navire).filter(Navire.id == navire_id).first()
    if not n:
        raise HTTPException(404, f"Navire {navire_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(n, field, value)
    n.version = (n.version or 0) + 1
    db.commit()
    db.refresh(n)
    return _to_out(n)


@router.delete("/{navire_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_navire(navire_id: str, db: Session = Depends(get_db)):
    n = db.query(Navire).filter(Navire.id == navire_id).first()
    if not n:
        raise HTTPException(404, f"Navire {navire_id} introuvable")
    db.delete(n)
    db.commit()
    return None

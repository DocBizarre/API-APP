"""Endpoints REST pour les commerciaux EMS (commercial en charge d'une affaire).

La table est alimentée automatiquement à chaque enregistrement d'une affaire
(cf. `_upsert_commercial`), sert à la précomplétion dans l'app Affaire (nom →
email / téléphone) et se gère depuis l'app Affaire via le CRUD ci-dessous.
Les affaires stockent leurs propres champs (commercial, commercial_email,
commercial_tel) : modifier ou supprimer un commercial ne les change pas.
"""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.commercial import Commercial
from ..models.affaire import Affaire
from ..schemas.commercial import CommercialCreate, CommercialUpdate, CommercialOut

router = APIRouter(prefix="/commerciaux", tags=["commerciaux"])


def _find_by_nom(db: Session, nom: str, exclude_id: Optional[str] = None):
    """Recherche par nom, insensible à la casse et aux espaces de bord."""
    q = db.query(Commercial).filter(func.lower(func.trim(Commercial.nom)) == nom.strip().lower())
    if exclude_id:
        q = q.filter(Commercial.id != exclude_id)
    return q.first()


def _upsert_commercial(db: Session, nom: str, email: str = "", telephone: str = "") -> None:
    """Mémorise ou complète un commercial (fail-safe, savepoint pour ne pas
    annuler la transaction parente). Comme pour les fournisseurs : un
    commercial existant voit seulement ses champs vides complétés (les
    corrections se font dans la gestion des commerciaux)."""
    nom = (nom or "").strip()
    if not nom:
        return
    valeurs = {"email": (email or "").strip(), "telephone": (telephone or "").strip()}
    try:
        with db.begin_nested():
            existing = _find_by_nom(db, nom)
            if existing:
                existing.usage_count = (existing.usage_count or 0) + 1
                for field, val in valeurs.items():
                    if val and not getattr(existing, field):
                        setattr(existing, field, val)
            else:
                db.add(Commercial(id=str(uuid4()), nom=nom, usage_count=1, **valeurs))
    except Exception:
        import logging as _log
        _log.getLogger(__name__).warning("Impossible d'upsert le commercial %r.", nom, exc_info=True)


def _to_out(c: Commercial, nb_affaires: int = 0) -> dict:
    return {
        "id": c.id,
        "nom": c.nom or "",
        "email": c.email or "",
        "telephone": c.telephone or "",
        "usage_count": c.usage_count or 0,
        "nb_affaires": nb_affaires,
    }


def _nb_affaires(db: Session) -> dict:
    rows = (db.query(func.lower(func.trim(Affaire.commercial)), func.count(Affaire.id))
              .filter(Affaire.commercial.isnot(None), Affaire.commercial != "")
              .group_by(func.lower(func.trim(Affaire.commercial))).all())
    return dict(rows)


def _get(db: Session, commercial_id: str) -> Commercial:
    c = db.query(Commercial).filter(Commercial.id == commercial_id).first()
    if not c:
        raise HTTPException(404, f"Commercial {commercial_id} introuvable")
    return c


@router.get("", response_model=List[CommercialOut])
def list_commerciaux(search: Optional[str] = Query(None), db: Session = Depends(get_db)):
    q = db.query(Commercial)
    if search:
        like = f"%{search}%"
        q = q.filter(Commercial.nom.ilike(like) | Commercial.email.ilike(like))
    nb = _nb_affaires(db)
    return [_to_out(c, nb.get((c.nom or "").strip().lower(), 0))
            for c in q.order_by(Commercial.usage_count.desc(), Commercial.nom).all()]


@router.get("/{commercial_id}", response_model=CommercialOut)
def get_commercial(commercial_id: str, db: Session = Depends(get_db)):
    c = _get(db, commercial_id)
    return _to_out(c, _nb_affaires(db).get((c.nom or "").strip().lower(), 0))


@router.post("", response_model=CommercialOut, status_code=status.HTTP_201_CREATED)
def create_commercial(data: CommercialCreate, db: Session = Depends(get_db)):
    """Crée un commercial ; si le nom existe déjà (casse ignorée), le met à jour."""
    if not data.nom:
        raise HTTPException(422, "Le nom du commercial est obligatoire")
    existing = _find_by_nom(db, data.nom)
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    c = Commercial(id=str(uuid4()), usage_count=0, **data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.put("/{commercial_id}", response_model=CommercialOut)
def update_commercial(commercial_id: str, data: CommercialUpdate, db: Session = Depends(get_db)):
    c = _get(db, commercial_id)
    values = data.model_dump(exclude_unset=True)
    if "nom" in values:
        if not values["nom"]:
            raise HTTPException(422, "Le nom du commercial est obligatoire")
        if _find_by_nom(db, values["nom"], exclude_id=c.id):
            raise HTTPException(409, f"Un commercial nommé « {values['nom']} » existe déjà")
    for field, value in values.items():
        if value is not None:
            setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _to_out(c)


@router.delete("/{commercial_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_commercial(commercial_id: str, db: Session = Depends(get_db)):
    """Retire le commercial de la liste de précomplétion (les affaires qui le
    citent gardent leurs propres champs)."""
    db.delete(_get(db, commercial_id))
    db.commit()
    return None

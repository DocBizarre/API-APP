"""Endpoints REST pour les fournisseurs (autocomplétion achats)."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Fournisseur

router = APIRouter(prefix="/fournisseurs", tags=["fournisseurs"])


def _upsert_fournisseur(db: Session, nom: str, contact: str = "", email: str = "",
                        telephone: str = "", rue: str = "", code_postal: str = "",
                        ville: str = "", pays: str = "") -> None:
    """Mémorise ou met à jour un fournisseur dans la table fournisseurs
    (fail-safe, savepoint pour ne pas annuler la transaction parente)."""
    nom = (nom or "").strip()
    if not nom:
        return
    try:
        with db.begin_nested():
            existing = db.query(Fournisseur).filter(Fournisseur.nom == nom).first()
            if existing:
                existing.usage_count = (existing.usage_count or 0) + 1
                for field, val in (
                    ("contact", contact), ("email", email), ("telephone", telephone),
                    ("rue", rue), ("code_postal", code_postal),
                    ("ville", ville), ("pays", pays),
                ):
                    if val and not getattr(existing, field):
                        setattr(existing, field, val)
            else:
                db.add(Fournisseur(
                    id=str(uuid4()),
                    nom=nom,
                    contact=(contact or "").strip(),
                    email=(email or "").strip(),
                    telephone=(telephone or "").strip(),
                    rue=(rue or "").strip(),
                    code_postal=(code_postal or "").strip(),
                    ville=(ville or "").strip(),
                    pays=(pays or "").strip(),
                    usage_count=1,
                ))
    except Exception:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Impossible d'upsert le fournisseur %r (table absente ou erreur schema).", nom
        )


@router.get("", response_model=List[dict])
def list_fournisseurs(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Fournisseur)
    if search:
        q = q.filter(Fournisseur.nom.ilike(f"%{search}%"))
    fournisseurs = q.order_by(Fournisseur.usage_count.desc(), Fournisseur.nom).all()
    return [
        {
            "nom": f.nom,
            "contact": f.contact,
            "email": f.email,
            "telephone": f.telephone,
            "rue": f.rue,
            "code_postal": f.code_postal,
            "ville": f.ville,
            "pays": f.pays,
        }
        for f in fournisseurs
    ]

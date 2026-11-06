"""Endpoints REST pour les fournisseurs (base fournisseurs des achats).

La table est alimentée automatiquement à chaque enregistrement d'un bon de
commande / d'une intention d'achat / d'une affaire (cf. `_upsert_fournisseur`),
sert à la précomplétion dans l'app Affaire, et se gère dans l'app Parc
(onglet « Fournisseurs ») via le CRUD ci-dessous.
"""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Fournisseur, Piece, PieceFournisseur
from ..schemas.fournisseur import FournisseurCreate, FournisseurUpdate, FournisseurOut

router = APIRouter(prefix="/fournisseurs", tags=["fournisseurs"])

_CHAMPS = ("contact", "email", "telephone", "rue", "code_postal", "ville", "pays")


def _find_by_nom(db: Session, nom: str, exclude_id: Optional[str] = None):
    """Recherche par nom, insensible à la casse et aux espaces de bord."""
    q = db.query(Fournisseur).filter(func.lower(func.trim(Fournisseur.nom)) == nom.strip().lower())
    if exclude_id:
        q = q.filter(Fournisseur.id != exclude_id)
    return q.first()


def _upsert_fournisseur(db: Session, nom: str, contact: str = "", email: str = "",
                        telephone: str = "", rue: str = "", code_postal: str = "",
                        ville: str = "", pays: str = "") -> None:
    """Mémorise ou met à jour un fournisseur dans la table fournisseurs
    (fail-safe, savepoint pour ne pas annuler la transaction parente).
    Comme pour les contacts : un fournisseur existant voit seulement ses champs
    vides complétés (les corrections se font dans l'app Parc)."""
    nom = (nom or "").strip()
    if not nom:
        return
    valeurs = dict(zip(_CHAMPS, (contact, email, telephone, rue, code_postal, ville, pays)))
    valeurs = {k: (v or "").strip() for k, v in valeurs.items()}
    try:
        with db.begin_nested():
            existing = _find_by_nom(db, nom)
            if existing:
                existing.usage_count = (existing.usage_count or 0) + 1
                for field, val in valeurs.items():
                    if val and not getattr(existing, field):
                        setattr(existing, field, val)
            else:
                db.add(Fournisseur(id=str(uuid4()), nom=nom, usage_count=1, **valeurs))
    except Exception:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Impossible d'upsert le fournisseur %r (table absente ou erreur schema).", nom
        )


def _to_out(f: Fournisseur, nb_references: int = 0) -> dict:
    d = {"nb_references": nb_references}
    for col in f.__table__.columns:
        val = getattr(f, col.name)
        if val is None:
            val = 0 if col.name == "usage_count" else ""
        d[col.name] = val
    return d


def _get(db: Session, fournisseur_id: str) -> Fournisseur:
    f = db.query(Fournisseur).filter(Fournisseur.id == fournisseur_id).first()
    if not f:
        raise HTTPException(404, f"Fournisseur {fournisseur_id} introuvable")
    return f


@router.get("", response_model=List[FournisseurOut])
def list_fournisseurs(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Fournisseur)
    if search:
        like = f"%{search}%"
        q = q.filter(Fournisseur.nom.ilike(like) | Fournisseur.contact.ilike(like)
                     | Fournisseur.ville.ilike(like) | Fournisseur.email.ilike(like))
    fournisseurs = q.order_by(Fournisseur.usage_count.desc(), Fournisseur.nom).all()
    nb = dict(db.query(PieceFournisseur.fournisseur_id, func.count(PieceFournisseur.id))
                .group_by(PieceFournisseur.fournisseur_id).all())
    return [_to_out(f, nb.get(f.id, 0)) for f in fournisseurs]


@router.get("/{fournisseur_id}/pieces", response_model=List[dict])
def list_fournisseur_pieces(fournisseur_id: str, db: Session = Depends(get_db)):
    """Références produits liées à ce fournisseur (avec sa référence et son prix)."""
    _get(db, fournisseur_id)
    rows = (db.query(Piece, PieceFournisseur)
              .join(PieceFournisseur, PieceFournisseur.piece_id == Piece.id)
              .filter(PieceFournisseur.fournisseur_id == fournisseur_id)
              .order_by(Piece.reference).all())
    return [{"piece_id": p.id, "reference": p.reference, "libelle": p.libelle or "",
             "marque": p.marque or "", "ref_fournisseur": lk.ref_fournisseur or "",
             "prix_achat": lk.prix_achat or 0.0, "date_dernier_achat": lk.date_dernier_achat or ""}
            for p, lk in rows]


@router.get("/{fournisseur_id}", response_model=FournisseurOut)
def get_fournisseur(fournisseur_id: str, db: Session = Depends(get_db)):
    return _to_out(_get(db, fournisseur_id))


@router.post("", response_model=FournisseurOut, status_code=status.HTTP_201_CREATED)
def create_fournisseur(data: FournisseurCreate, db: Session = Depends(get_db)):
    """Crée un fournisseur ; si le nom existe déjà (casse ignorée), le met à jour."""
    if not data.nom:
        raise HTTPException(422, "Le nom du fournisseur est obligatoire")
    existing = _find_by_nom(db, data.nom)
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    f = Fournisseur(id=str(uuid4()), usage_count=0, **data.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return _to_out(f)


@router.put("/{fournisseur_id}", response_model=FournisseurOut)
def update_fournisseur(fournisseur_id: str, data: FournisseurUpdate,
                       db: Session = Depends(get_db)):
    f = _get(db, fournisseur_id)
    values = data.model_dump(exclude_unset=True)
    if "nom" in values:
        if not values["nom"]:
            raise HTTPException(422, "Le nom du fournisseur est obligatoire")
        if _find_by_nom(db, values["nom"], exclude_id=f.id):
            raise HTTPException(409, f"Un fournisseur nommé « {values['nom']} » existe déjà")
    for field, value in values.items():
        if value is not None:
            setattr(f, field, value)
    db.commit()
    db.refresh(f)
    return _to_out(f)


@router.delete("/{fournisseur_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fournisseur(fournisseur_id: str, db: Session = Depends(get_db)):
    """Supprime l'entrée de la base fournisseurs (n'affecte pas les bons de
    commande / intentions d'achat existants, qui stockent leurs propres champs)."""
    f = _get(db, fournisseur_id)
    db.query(PieceFournisseur).filter(PieceFournisseur.fournisseur_id == fournisseur_id).delete()
    db.delete(f)
    db.commit()
    return None

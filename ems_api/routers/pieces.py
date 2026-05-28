"""Endpoints REST pour les pièces détachées."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models import Piece
from ..schemas.piece import (
    PieceCreate, PieceUpdate, PieceOut,
    PieceBulkImport, PieceImportResult,
)


router = APIRouter(prefix="/pieces", tags=["pieces"])


def _to_out(p: Piece) -> dict:
    """Sérialise une pièce en garantissant tous les champs."""
    d = {}
    for c in p.__table__.columns:
        val = getattr(p, c.name)
        if val is None and not c.name.endswith("_at"):
            val = ""
        d[c.name] = val
    return d


@router.get("", response_model=List[PieceOut])
def list_pieces(
    search: Optional[str] = Query(None),
    ref_only: bool = Query(False, description="Recherche uniquement par référence"),
    limit: int = Query(500, ge=1, le=5000,
                        description="Nombre max de résultats (cap par défaut "
                                    "pour éviter de transférer 55k lignes)"),
    db: Session = Depends(get_db),
):
    """
    Liste les pièces, avec recherche optionnelle.
    Par défaut, limite à 500 résultats (suffisant pour l'UI).
    Pour récupérer tout : passer limit=5000 (ou plusieurs appels).
    """
    q = db.query(Piece)
    if search:
        like = f"%{search}%"
        if ref_only:
            q = q.filter(Piece.reference.ilike(like))
        else:
            q = q.filter(or_(Piece.reference.ilike(like),
                             Piece.libelle.ilike(like),
                             Piece.marque.ilike(like)))
    q = q.order_by(Piece.reference).limit(limit)
    return [_to_out(p) for p in q.all()]


@router.get("/count")
def count_pieces(db: Session = Depends(get_db)) -> dict:
    """Compte total des pièces en base (utile pour le tableau de bord)."""
    return {"total": db.query(Piece).count()}


@router.get("/by-reference/{reference}", response_model=Optional[PieceOut])
def find_by_reference(reference: str, db: Session = Depends(get_db)):
    """Recherche une pièce par sa référence exacte."""
    p = db.query(Piece).filter(Piece.reference == reference).first()
    return _to_out(p) if p else None


@router.get("/{piece_id}", response_model=PieceOut)
def get_piece(piece_id: str, db: Session = Depends(get_db)):
    p = db.query(Piece).filter(Piece.id == piece_id).first()
    if not p:
        raise HTTPException(404, f"Pièce {piece_id} introuvable")
    return _to_out(p)


@router.post("", response_model=PieceOut, status_code=status.HTTP_201_CREATED)
def create_piece(data: PieceCreate, db: Session = Depends(get_db)):
    """Crée ou met à jour une pièce (upsert sur reference)."""
    if not data.reference.strip():
        raise HTTPException(400, "La référence ne peut pas être vide")
    existing = db.query(Piece).filter(Piece.reference == data.reference).first()
    if existing:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return _to_out(existing)
    p = Piece(id=str(uuid4()), **data.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.put("/{piece_id}", response_model=PieceOut)
def update_piece(piece_id: str, data: PieceUpdate,
                  db: Session = Depends(get_db)):
    p = db.query(Piece).filter(Piece.id == piece_id).first()
    if not p:
        raise HTTPException(404, f"Pièce {piece_id} introuvable")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    p.version = (p.version or 0) + 1
    db.commit()
    db.refresh(p)
    return _to_out(p)


@router.delete("/{piece_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_piece(piece_id: str, db: Session = Depends(get_db)):
    p = db.query(Piece).filter(Piece.id == piece_id).first()
    if not p:
        raise HTTPException(404, f"Pièce {piece_id} introuvable")
    db.delete(p)
    db.commit()
    return None


@router.post("/bulk", response_model=PieceImportResult)
def bulk_import(data: PieceBulkImport, db: Session = Depends(get_db)):
    """
    Import en masse de pièces (depuis CSV ou Excel côté client).
    Gère les doublons : par défaut ignore (skip_doublons=True),
    sinon met à jour les références existantes.
    """
    res = PieceImportResult(importees=0, mises_a_jour=0,
                              ignorees=0, erreurs=0, details_erreurs=[])

    # Précharger toutes les références existantes pour gain de perf
    existing_refs = {r[0] for r in db.query(Piece.reference).all()}

    for i, piece_data in enumerate(data.pieces, 1):
        ref = (piece_data.reference or "").strip()
        if not ref:
            res.erreurs += 1
            if len(res.details_erreurs) < 20:
                res.details_erreurs.append(f"Ligne {i} : référence vide")
            continue

        if ref in existing_refs:
            if data.skip_doublons:
                res.ignorees += 1
            else:
                # Mise à jour
                p = db.query(Piece).filter(Piece.reference == ref).first()
                p.libelle = piece_data.libelle or p.libelle
                p.marque  = piece_data.marque  or p.marque
                p.notes   = piece_data.notes   or p.notes
                res.mises_a_jour += 1
        else:
            p = Piece(id=str(uuid4()),
                       reference=ref,
                       libelle=piece_data.libelle or "",
                       marque=piece_data.marque or "",
                       notes=piece_data.notes or "")
            db.add(p)
            existing_refs.add(ref)
            res.importees += 1

        # Commit par lots pour ne pas exploser la mémoire
        if (i % 500) == 0:
            db.commit()

    db.commit()
    return res

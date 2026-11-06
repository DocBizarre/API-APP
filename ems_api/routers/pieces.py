"""Endpoints REST pour les pièces détachées."""
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, case

from ..database import get_db
from ..models import Piece, PieceFournisseur
from ..schemas.piece import (
    PieceCreate, PieceUpdate, PieceOut,
    PieceBulkImport, PieceImportResult,
    PieceFournisseurIn, PIECE_LINK_FIELDS,
)
from ..services import piece_fournisseurs as pf


router = APIRouter(prefix="/pieces", tags=["pieces"])


def _to_out(p: Piece) -> dict:
    """Sérialise une pièce en garantissant tous les champs."""
    d = {}
    for c in p.__table__.columns:
        val = getattr(p, c.name)
        if val is None and not c.name.endswith("_at"):
            val = 0 if str(c.type).startswith(("FLOAT", "INTEGER")) else ""
        d[c.name] = val
    return d


@router.get("", response_model=List[PieceOut])
def list_pieces(
    search: Optional[str] = Query(None),
    ref_only: bool = Query(False, description="Recherche uniquement par référence"),
    limit: int = Query(500, ge=1, le=5000,
                        description="Nombre max de résultats (cap par défaut "
                                    "pour éviter de transférer 55k lignes)"),
    fournisseur: Optional[str] = Query(None, description="Nom du fournisseur : ses "
                                       "références passent en tête, avec son prix"),
    only_fournisseur: bool = Query(False, description="Seulement les références de ce fournisseur"),
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
        # La référence chez un fournisseur est aussi cherchée
        par_ref_fourn = Piece.id.in_(db.query(PieceFournisseur.piece_id)
                                       .filter(PieceFournisseur.ref_fournisseur.ilike(like)))
        if ref_only:
            q = q.filter(or_(Piece.reference.ilike(like), par_ref_fourn))
        else:
            q = q.filter(or_(Piece.reference.ilike(like),
                             Piece.libelle.ilike(like),
                             Piece.marque.ilike(like),
                             par_ref_fourn))
    f = pf.find_fournisseur(db, fournisseur) if fournisseur else None
    if only_fournisseur:
        if f is None:
            return []
        q = q.filter(Piece.id.in_(db.query(PieceFournisseur.piece_id)
                                    .filter(PieceFournisseur.fournisseur_id == f.id)))
        q = q.order_by(Piece.reference)
    elif f is not None:
        chez_f = Piece.id.in_(db.query(PieceFournisseur.piece_id)
                                .filter(PieceFournisseur.fournisseur_id == f.id))
        q = q.order_by(case((chez_f, 0), else_=1), Piece.reference)
    else:
        q = q.order_by(Piece.reference)
    pieces = q.limit(limit).all()
    liens = pf.fournisseurs_par_piece(db, (p.id for p in pieces))
    out = []
    for p in pieces:
        d = _to_out(p)
        d["fournisseurs"] = liens.get(p.id, [])
        if f is not None:
            lk = next((x for x in d["fournisseurs"] if x["fournisseur_id"] == f.id), None)
            if lk:
                d["chez_fournisseur"] = True
                d["prix_fournisseur"] = lk["prix_achat"] or None
                d["ref_fournisseur"] = lk["ref_fournisseur"]
        out.append(d)
    return out


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
        for field, value in data.model_dump(exclude_unset=True,
                                            exclude=PIECE_LINK_FIELDS).items():
            setattr(existing, field, value)
        p = existing
    else:
        p = Piece(id=str(uuid4()), **data.model_dump(exclude=PIECE_LINK_FIELDS))
        db.add(p)
        db.flush()
    if data.fournisseur.strip():
        f = pf.get_or_create_fournisseur(db, data.fournisseur)
        pf.link(db, p.id, f.id, data.ref_fournisseur, data.prix_achat)
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
    db.query(PieceFournisseur).filter(PieceFournisseur.piece_id == piece_id).delete()
    db.delete(p)
    db.commit()
    return None


# ─── Fournisseurs d'une pièce ─────────────────────────────────────────────────
def _get_piece_or_404(db: Session, piece_id: str) -> Piece:
    p = db.query(Piece).filter(Piece.id == piece_id).first()
    if not p:
        raise HTTPException(404, f"Pièce {piece_id} introuvable")
    return p


@router.get("/{piece_id}/fournisseurs", response_model=List[dict])
def list_piece_fournisseurs(piece_id: str, db: Session = Depends(get_db)):
    _get_piece_or_404(db, piece_id)
    return pf.fournisseurs_par_piece(db, [piece_id]).get(piece_id, [])


@router.put("/{piece_id}/fournisseurs", response_model=dict)
def set_piece_fournisseur(piece_id: str, data: PieceFournisseurIn,
                          db: Session = Depends(get_db)):
    """Crée ou modifie le lien avec un fournisseur (créé dans la base
    fournisseurs s'il n'existe pas encore)."""
    _get_piece_or_404(db, piece_id)
    if not data.fournisseur_nom.strip():
        raise HTTPException(422, "Le nom du fournisseur est obligatoire")
    f = pf.get_or_create_fournisseur(db, data.fournisseur_nom)
    lk = pf.link(db, piece_id, f.id, data.ref_fournisseur, data.prix_achat)
    # Saisie manuelle : une référence / un prix vidés volontairement sont pris en compte
    lk.ref_fournisseur = data.ref_fournisseur.strip()
    lk.prix_achat = data.prix_achat or 0.0
    db.commit()
    return pf.link_out(lk, f.nom)


@router.delete("/{piece_id}/fournisseurs/{fournisseur_id}",
               status_code=status.HTTP_204_NO_CONTENT)
def delete_piece_fournisseur(piece_id: str, fournisseur_id: str,
                             db: Session = Depends(get_db)):
    n = (db.query(PieceFournisseur)
           .filter(PieceFournisseur.piece_id == piece_id,
                   PieceFournisseur.fournisseur_id == fournisseur_id)
           .delete())
    if not n:
        raise HTTPException(404, "Lien pièce / fournisseur introuvable")
    db.commit()
    return None


@router.post("/bulk", response_model=PieceImportResult)
def bulk_import(data: PieceBulkImport, db: Session = Depends(get_db)):
    """
    Import en masse de pièces (depuis CSV ou Excel côté client).
    Gère les doublons : par défaut ignore (skip_doublons=True) — dans ce
    mode, les champs déjà remplis ne sont jamais écrasés mais les champs
    restés vides (libellé, marque, notes, prix d'achat, prix de vente) sont complétés
    à partir du fichier si une valeur y est présente.
    Si skip_doublons=False, les références existantes sont mises à jour
    (le fichier importé l'emporte quand une valeur est fournie).
    """
    res = PieceImportResult(importees=0, mises_a_jour=0,
                              ignorees=0, completees=0,
                              erreurs=0, details_erreurs=[])

    # Précharger toutes les pièces existantes (par référence) pour gain de
    # perf et pour pouvoir retrouver, sans requêter la DB, les pièces créées
    # plus tôt dans cette même importation (cas des doublons intra-fichier,
    # pas encore flush/committées).
    pieces_by_ref = {p.reference: p for p in db.query(Piece).all()}
    fournisseurs_cache: dict = {}

    for i, piece_data in enumerate(data.pieces, 1):
        ref = (piece_data.reference or "").strip()
        if not ref:
            res.erreurs += 1
            if len(res.details_erreurs) < 20:
                res.details_erreurs.append(f"Ligne {i} : référence vide")
            continue

        if ref in pieces_by_ref:
            p = pieces_by_ref[ref]
            if data.skip_doublons:
                # Doublon ignoré : on ne l'écrase pas, mais on complète les
                # champs restés vides avec les infos du fichier importé.
                completee = False
                if not p.libelle and piece_data.libelle:
                    p.libelle = piece_data.libelle
                    completee = True
                if not p.marque and piece_data.marque:
                    p.marque = piece_data.marque
                    completee = True
                if not p.notes and piece_data.notes:
                    p.notes = piece_data.notes
                    completee = True
                if not p.prix_vente and piece_data.prix_vente:
                    p.prix_vente = piece_data.prix_vente
                    completee = True
                if not p.prix_achat and piece_data.prix_achat:
                    p.prix_achat = piece_data.prix_achat
                    completee = True
                res.ignorees += 1
                if completee:
                    res.completees += 1
            else:
                # Mise à jour
                p.libelle    = piece_data.libelle    or p.libelle
                p.marque     = piece_data.marque     or p.marque
                p.notes      = piece_data.notes      or p.notes
                p.prix_vente = piece_data.prix_vente or p.prix_vente
                p.prix_achat = piece_data.prix_achat or p.prix_achat
                res.mises_a_jour += 1
        else:
            p = Piece(id=str(uuid4()),
                       reference=ref,
                       libelle=piece_data.libelle or "",
                       marque=piece_data.marque or "",
                       notes=piece_data.notes or "",
                       prix_vente=piece_data.prix_vente or 0,
                       prix_achat=piece_data.prix_achat or 0)
            db.add(p)
            pieces_by_ref[ref] = p
            res.importees += 1

        # Lien avec le fournisseur de la ligne (ou celui choisi pour tout le fichier)
        nom_f = (piece_data.fournisseur or data.fournisseur or "").strip()
        if nom_f:
            f = pf.get_or_create_fournisseur(db, nom_f, fournisseurs_cache)
            pf.link(db, p.id, f.id, piece_data.ref_fournisseur, piece_data.prix_achat,
                    overwrite=not data.skip_doublons)

        # Commit par lots pour ne pas exploser la mémoire (pas en simulation)
        if (i % 500) == 0 and not data.dry_run:
            db.commit()

    if data.dry_run:
        db.rollback()   # simulation : aucune écriture
    else:
        db.commit()
    return res

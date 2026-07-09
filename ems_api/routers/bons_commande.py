"""Endpoints REST pour les bons de commande (achats), liés ou non à une affaire."""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.affaire import Affaire
from ..models.piece import Piece
from ..models.bon_commande import BonCommande, BonCommandeLigne
from ..schemas.bon_commande import (
    BonCommandeCreate, BonCommandeUpdate, BonCommandeOut,
)
from ..services.numerotation import next_num_bon_commande
from .affaires import _get_dossier, _create_arborescence

router = APIRouter(prefix="/bons-commande", tags=["bons-commande"])

STATUTS = ["Brouillon", "Envoyé", "Confirmé", "Reçu", "Annulé"]


def _coerce(c, val):
    if val is not None:
        return val
    type_str = str(c.type)
    if type_str.startswith(("FLOAT", "INTEGER")):
        return 0
    if type_str.startswith(("DATETIME", "DATE")):
        return None
    return ""


def _ligne_to_out(l: BonCommandeLigne) -> dict:
    d = {}
    for c in l.__table__.columns:
        d[c.name] = _coerce(c, getattr(l, c.name))
    d["piece_id"] = l.piece_id  # préserver None (pas de piece cataloguée)
    return d


def _to_out(bc: BonCommande) -> dict:
    d = {}
    for c in bc.__table__.columns:
        d[c.name] = _coerce(c, getattr(bc, c.name))
    d["affaire_id"] = bc.affaire_id  # préserver None (non-lié), pas de coercition en ""
    d["lignes"] = [_ligne_to_out(l) for l in bc.lignes]
    total_ht = sum(l.montant_ligne or 0 for l in bc.lignes)
    d["total_ht"] = total_ht
    d["total_ttc"] = total_ht if bc.exonere_tva else round(total_ht * 1.20, 2)
    d["affaire_num"] = bc.affaire.num_affaire if bc.affaire else None
    d["affaire_nom"] = bc.affaire.nom_projet if bc.affaire else None
    return d


def _get_bon(bc_id: str, db: Session) -> BonCommande:
    bc = db.query(BonCommande).filter(BonCommande.id == bc_id).first()
    if not bc:
        raise HTTPException(404, "Bon de commande introuvable")
    return bc


def _check_affaire(affaire_id: Optional[str], db: Session) -> None:
    if affaire_id and not db.query(Affaire).filter(Affaire.id == affaire_id).first():
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")


def _recalc_lignes(bc: BonCommande, lignes_in: list, db: Session) -> None:
    """Remplace intégralement les lignes du bon de commande."""
    for l in list(bc.lignes):
        db.delete(l)
    for i, ligne in enumerate(lignes_in):
        piece_id = ligne.piece_id or None
        if piece_id and not db.query(Piece).filter(Piece.id == piece_id).first():
            piece_id = None
        montant = round((ligne.quantite or 0) * (ligne.prix_unitaire or 0), 2)
        db.add(BonCommandeLigne(
            id=str(uuid4()),
            bon_commande_id=bc.id,
            piece_id=piece_id,
            reference=ligne.reference,
            libelle=ligne.libelle,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            montant_ligne=montant,
            ordre=ligne.ordre or i,
        ))


@router.get("", response_model=List[BonCommandeOut])
def list_bons_commande(
    affaire_id: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(BonCommande)
    if affaire_id:
        q = q.filter(BonCommande.affaire_id == affaire_id)
    if statut:
        q = q.filter(BonCommande.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(BonCommande.num_bc.ilike(like),
                         BonCommande.fournisseur_nom.ilike(like)))
    q = q.order_by(BonCommande.created_at.desc())
    return [_to_out(bc) for bc in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/{bc_id}", response_model=BonCommandeOut)
def get_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    return _to_out(_get_bon(bc_id, db))


@router.post("", response_model=BonCommandeOut, status_code=201)
def create_bon_commande(body: BonCommandeCreate, db: Session = Depends(get_db)):
    _check_affaire(body.affaire_id, db)
    bc = BonCommande(
        id=str(uuid4()),
        affaire_id=body.affaire_id or None,
        num_bc=next_num_bon_commande(db),
        fournisseur_nom=body.fournisseur_nom,
        fournisseur_adresse=body.fournisseur_adresse,
        fournisseur_contact=body.fournisseur_contact,
        fournisseur_email=body.fournisseur_email,
        fournisseur_tel=body.fournisseur_tel,
        date_commande=body.date_commande,
        date_livraison_prevue=body.date_livraison_prevue,
        date_livraison_reelle=body.date_livraison_reelle,
        date_reglement=body.date_reglement,
        statut=body.statut,
        conditions=body.conditions,
        notes=body.notes,
        exonere_tva=body.exonere_tva,
    )
    db.add(bc)
    db.flush()
    _recalc_lignes(bc, body.lignes, db)
    db.commit()
    db.refresh(bc)
    return _to_out(bc)


@router.put("/{bc_id}", response_model=BonCommandeOut)
def update_bon_commande(bc_id: str, body: BonCommandeUpdate,
                        db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    data = body.model_dump(exclude_unset=True)
    lignes = data.pop("lignes", None)
    if "affaire_id" in data:
        aid = data.pop("affaire_id")
        _check_affaire(aid, db)
        bc.affaire_id = aid or None
    for field, val in data.items():
        if val is not None:
            setattr(bc, field, val)
    if lignes is not None:
        _recalc_lignes(bc, body.lignes, db)
    bc.version = (bc.version or 1) + 1
    db.commit()
    db.refresh(bc)
    return _to_out(bc)


@router.delete("/{bc_id}", status_code=204)
def delete_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    bc = _get_bon(bc_id, db)
    db.delete(bc)
    db.commit()


@router.get("/{bc_id}/pdf",
            summary="Génère, archive (si lié à une affaire) et renvoie le bon de commande en PDF",
            response_class=Response)
def generer_pdf_bon_commande(bc_id: str, db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_bon_commande_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    bc = _get_bon(bc_id, db)
    a = db.query(Affaire).filter(Affaire.id == bc.affaire_id).first() if bc.affaire_id else None

    a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns} if a else None
    bc_dict = {c.name: getattr(bc, c.name) for c in bc.__table__.columns}
    lignes = [
        {c.name: getattr(l, c.name) for c in l.__table__.columns}
        for l in bc.lignes
    ]

    html_str = build_bon_commande_html(bc_dict, lignes, affaire=a_dict)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = bc.num_bc.replace("/", "-").replace(" ", "_")

    if a:
        try:
            dossier = _get_dossier(a.id, db)
            _create_arborescence(dossier)
            dest = dossier / "ACHAT" / "FOURNISSEURS" / f"BC_{safe_num}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pdf_bytes)
            bc.pdf_path = str(dest)
        except Exception:
            pass  # l'archivage disque est un plus, ne doit pas bloquer le téléchargement

    bc.date_generation = datetime.now()
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="BC_{safe_num}.pdf"',
            "Cache-Control": "no-store",
        },
    )

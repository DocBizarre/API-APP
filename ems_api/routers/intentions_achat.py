"""Endpoints REST pour les intentions d'achat (confirmations préliminaires envoyées à
un fournisseur), liées ou non à une affaire. Document informel, sans lien avec le
bilan de coûts de l'affaire (contrairement aux bons de commande)."""
from datetime import datetime
from typing import List, Optional
from uuid import uuid4
import json as _json_mod

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.affaire import Affaire
from ..models.piece import Piece
from ..models.intention_achat import IntentionAchat, IntentionAchatLigne
from ..schemas.intention_achat import (
    IntentionAchatCreate, IntentionAchatUpdate, IntentionAchatOut,
)
from ..services.numerotation import next_num_intention_achat
from .affaires import _get_dossier, _create_arborescence
from .interventions import _upsert_contact
from .fournisseurs import _upsert_fournisseur

router = APIRouter(prefix="/intentions-achat", tags=["intentions-achat"])

STATUTS = ["Brouillon", "Envoyée", "Confirmée", "Annulée"]


def _coerce(c, val):
    if val is not None:
        return val
    type_str = str(c.type)
    if type_str.startswith(("FLOAT", "INTEGER")):
        return 0
    if type_str.startswith(("DATETIME", "DATE")):
        return None
    return ""


def _ligne_to_out(l: IntentionAchatLigne) -> dict:
    d = {}
    for c in l.__table__.columns:
        d[c.name] = _coerce(c, getattr(l, c.name))
    d["piece_id"] = l.piece_id  # préserver None (pas de piece cataloguée)
    return d


def _to_out(ia: IntentionAchat) -> dict:
    d = {}
    for c in ia.__table__.columns:
        d[c.name] = _coerce(c, getattr(ia, c.name))
    d["affaire_id"] = ia.affaire_id  # préserver None (non-lié), pas de coercition en ""
    d["lignes"] = [_ligne_to_out(l) for l in ia.lignes]
    total_lignes_ht = sum(l.montant_ligne or 0 for l in ia.lignes)
    total_ht = total_lignes_ht + (ia.frais_port or 0)
    d["total_lignes_ht"] = total_lignes_ht
    d["total_ht"] = total_ht
    d["total_ttc"] = total_ht if ia.exonere_tva else round(total_ht * 1.20, 2)
    d["affaire_num"] = ia.affaire.num_affaire if ia.affaire else None
    d["affaire_nom"] = ia.affaire.nom_projet if ia.affaire else None
    return d


def _get_intention(ia_id: str, db: Session) -> IntentionAchat:
    ia = db.query(IntentionAchat).filter(IntentionAchat.id == ia_id).first()
    if not ia:
        raise HTTPException(404, "Intention d'achat introuvable")
    return ia


def _upsert_interlocuteurs_fournisseur(db: Session, interlocuteurs_json: str) -> None:
    """Mémorise chaque interlocuteur fournisseur dans la table contacts (autocomplétion)."""
    try:
        interlocuteurs = _json_mod.loads(interlocuteurs_json or "[]")
    except Exception:
        interlocuteurs = []
    for it in interlocuteurs:
        _upsert_contact(db, it.get("nom", ""), it.get("email", ""), it.get("telephone", ""))


def _check_affaire(affaire_id: Optional[str], db: Session) -> None:
    if affaire_id and not db.query(Affaire).filter(Affaire.id == affaire_id).first():
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")


def _recalc_lignes(ia: IntentionAchat, lignes_in: list, db: Session) -> None:
    """Remplace intégralement les lignes de l'intention d'achat."""
    for l in list(ia.lignes):
        db.delete(l)
    for i, ligne in enumerate(lignes_in):
        piece_id = ligne.piece_id or None
        if piece_id and not db.query(Piece).filter(Piece.id == piece_id).first():
            piece_id = None
        montant = round((ligne.quantite or 0) * (ligne.prix_unitaire or 0), 2)
        db.add(IntentionAchatLigne(
            id=str(uuid4()),
            intention_achat_id=ia.id,
            piece_id=piece_id,
            reference=ligne.reference,
            drawing_no=ligne.drawing_no,
            libelle=ligne.libelle,
            ratio_notes=ligne.ratio_notes,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            montant_ligne=montant,
            ordre=ligne.ordre or i,
        ))


@router.get("", response_model=List[IntentionAchatOut])
def list_intentions_achat(
    affaire_id: Optional[str] = Query(None),
    statut: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(IntentionAchat)
    if affaire_id:
        q = q.filter(IntentionAchat.affaire_id == affaire_id)
    if statut:
        q = q.filter(IntentionAchat.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(IntentionAchat.num_ia.ilike(like),
                         IntentionAchat.fournisseur_nom.ilike(like),
                         IntentionAchat.reference_client.ilike(like)))
    q = q.order_by(IntentionAchat.created_at.desc())
    return [_to_out(ia) for ia in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/{ia_id}", response_model=IntentionAchatOut)
def get_intention_achat(ia_id: str, db: Session = Depends(get_db)):
    return _to_out(_get_intention(ia_id, db))


@router.post("", response_model=IntentionAchatOut, status_code=201)
def create_intention_achat(body: IntentionAchatCreate, db: Session = Depends(get_db)):
    _check_affaire(body.affaire_id, db)
    ia = IntentionAchat(
        id=str(uuid4()),
        affaire_id=body.affaire_id or None,
        num_ia=next_num_intention_achat(db),
        langue=body.langue or "fr",
        reference_devis=body.reference_devis,
        reference_client=body.reference_client,
        fournisseur_nom=body.fournisseur_nom,
        reference_fournisseur=body.reference_fournisseur,
        reference_monstock=body.reference_monstock,
        lien_monstock=body.lien_monstock,
        fournisseur_rue=body.fournisseur_rue,
        fournisseur_code_postal=body.fournisseur_code_postal,
        fournisseur_ville=body.fournisseur_ville,
        fournisseur_pays=body.fournisseur_pays,
        fournisseur_contact=body.fournisseur_contact,
        fournisseur_email=body.fournisseur_email,
        fournisseur_tel=body.fournisseur_tel,
        interlocuteurs_fournisseur=body.interlocuteurs_fournisseur,
        livraison_nom=body.livraison_nom,
        livraison_rue=body.livraison_rue,
        livraison_code_postal=body.livraison_code_postal,
        livraison_ville=body.livraison_ville,
        livraison_pays=body.livraison_pays,
        incoterm=body.incoterm,
        lieu_livraison_texte=body.lieu_livraison_texte,
        delai_livraison_texte=body.delai_livraison_texte,
        conditions_paiement_texte=body.conditions_paiement_texte,
        garantie_texte=body.garantie_texte,
        charge_commande_nom=body.charge_commande_nom,
        charge_commande_email=body.charge_commande_email,
        charge_commande_tel=body.charge_commande_tel,
        date_commande=body.date_commande,
        date_livraison_prevue=body.date_livraison_prevue,
        date_livraison_reelle=body.date_livraison_reelle,
        date_reglement=body.date_reglement,
        statut=body.statut,
        conditions=body.conditions,
        notes=body.notes,
        exonere_tva=body.exonere_tva,
        frais_port=body.frais_port,
    )
    db.add(ia)
    db.flush()
    _recalc_lignes(ia, body.lignes, db)
    _upsert_fournisseur(db, ia.fournisseur_nom, ia.fournisseur_contact, ia.fournisseur_email,
                       ia.fournisseur_tel, ia.fournisseur_rue, ia.fournisseur_code_postal,
                       ia.fournisseur_ville, ia.fournisseur_pays)
    _upsert_interlocuteurs_fournisseur(db, ia.interlocuteurs_fournisseur)
    db.commit()
    db.refresh(ia)
    return _to_out(ia)


@router.put("/{ia_id}", response_model=IntentionAchatOut)
def update_intention_achat(ia_id: str, body: IntentionAchatUpdate,
                           db: Session = Depends(get_db)):
    ia = _get_intention(ia_id, db)
    data = body.model_dump(exclude_unset=True)
    lignes = data.pop("lignes", None)
    if "affaire_id" in data:
        aid = data.pop("affaire_id")
        _check_affaire(aid, db)
        ia.affaire_id = aid or None
    for field, val in data.items():
        if val is not None:
            setattr(ia, field, val)
    if lignes is not None:
        _recalc_lignes(ia, body.lignes, db)
    _upsert_fournisseur(db, ia.fournisseur_nom, ia.fournisseur_contact, ia.fournisseur_email,
                       ia.fournisseur_tel, ia.fournisseur_rue, ia.fournisseur_code_postal,
                       ia.fournisseur_ville, ia.fournisseur_pays)
    _upsert_interlocuteurs_fournisseur(db, ia.interlocuteurs_fournisseur)
    ia.version = (ia.version or 1) + 1
    db.commit()
    db.refresh(ia)
    return _to_out(ia)


@router.delete("/{ia_id}", status_code=204)
def delete_intention_achat(ia_id: str, db: Session = Depends(get_db)):
    ia = _get_intention(ia_id, db)
    db.delete(ia)
    db.commit()


@router.get("/{ia_id}/pdf",
            summary="Génère, archive (si liée à une affaire) et renvoie l'intention d'achat en PDF",
            response_class=Response)
def generer_pdf_intention_achat(ia_id: str, lang: str = Query("fr", pattern="^(fr|en)$"),
                                db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_intention_achat_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    ia = _get_intention(ia_id, db)
    a = db.query(Affaire).filter(Affaire.id == ia.affaire_id).first() if ia.affaire_id else None

    a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns} if a else None
    ia_dict = {c.name: getattr(ia, c.name) for c in ia.__table__.columns}
    lignes = [
        {c.name: getattr(l, c.name) for c in l.__table__.columns}
        for l in ia.lignes
    ]

    html_str = build_intention_achat_html(ia_dict, lignes, affaire=a_dict, lang=lang)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = ia.num_ia.replace("/", "-").replace(" ", "_")

    if a:
        try:
            dossier = _get_dossier(a.id, db)
            _create_arborescence(dossier)
            dest = dossier / "ACHAT" / "INTENTIONS" / f"IA_{safe_num}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(pdf_bytes)
            ia.pdf_path = str(dest)
        except Exception:
            pass  # l'archivage disque est un plus, ne doit pas bloquer le téléchargement

    ia.date_generation = datetime.now()
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="IA_{safe_num}.pdf"',
            "Cache-Control": "no-store",
        },
    )

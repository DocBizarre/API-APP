"""Endpoints REST pour les Devis (chiffrés, transformables en bon d'intervention)."""
import json
from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from ..database import get_db
from ..config import settings
from ..models.client import Client
from ..models.moteur import Moteur
from ..models.piece import Piece
from ..models.intervention import Intervention
from ..models.devis import Devis, DevisLigne
from ..schemas.devis import (
    DevisCreate, DevisUpdate, DevisOut, DevisTransformOut,
)
from ..services.numerotation import next_num_devis, next_num_bon

router = APIRouter(prefix="/devis", tags=["devis"])

STATUTS = ["Brouillon", "Envoyé", "Accepté", "Refusé", "Transformé"]

_EAGER = (
    selectinload(Devis.client),
    selectinload(Devis.moteur),
    selectinload(Devis.intervention),
)


def _coerce(c, val):
    if val is not None:
        return val
    type_str = str(c.type)
    if type_str.startswith(("FLOAT", "INTEGER")):
        return 0
    if type_str.startswith(("DATETIME", "DATE")):
        return None
    return ""


def _ligne_to_out(l: DevisLigne) -> dict:
    d = {}
    for c in l.__table__.columns:
        d[c.name] = _coerce(c, getattr(l, c.name))
    d["piece_id"] = l.piece_id
    return d


def _to_out(d: Devis) -> dict:
    out = {}
    for c in d.__table__.columns:
        out[c.name] = _coerce(c, getattr(d, c.name))
    out["moteur_id"] = d.moteur_id  # préserver None (pas de moteur)
    out["lignes"] = [_ligne_to_out(l) for l in d.lignes]
    total_lignes_ht = sum(l.montant_ligne or 0 for l in d.lignes)
    out["total_lignes_ht"] = total_lignes_ht
    out["total_ht"] = total_lignes_ht
    out["total_ttc"] = total_lignes_ht if d.exonere_tva else round(total_lignes_ht * 1.20, 2)
    out["client_nom"] = d.client.nom if d.client else None
    out["moteur_num_serie"] = d.moteur.num_serie if d.moteur else None
    out["intervention_id"] = d.intervention_id
    out["intervention_num_bon"] = d.intervention.num_bon if d.intervention else None
    return out


def _get_devis(devis_id: str, db: Session) -> Devis:
    d = db.query(Devis).options(*_EAGER).filter(Devis.id == devis_id).first()
    if not d:
        raise HTTPException(404, "Devis introuvable")
    return d


def _check_client(client_id: str, db: Session) -> None:
    if not client_id or not db.query(Client).filter(Client.id == client_id).first():
        raise HTTPException(404, f"Client {client_id!r} introuvable")


def _recalc_lignes(d: Devis, lignes_in: list, db: Session) -> None:
    """Remplace intégralement les lignes du devis."""
    for l in list(d.lignes):
        db.delete(l)
    for i, ligne in enumerate(lignes_in):
        piece_id = ligne.piece_id or None
        if piece_id and not db.query(Piece).filter(Piece.id == piece_id).first():
            piece_id = None
        montant = round((ligne.quantite or 0) * (ligne.prix_unitaire or 0)
                        * (1 - (ligne.remise_pct or 0) / 100), 2)
        db.add(DevisLigne(
            id=str(uuid4()),
            devis_id=d.id,
            piece_id=piece_id,
            reference=ligne.reference,
            libelle=ligne.libelle,
            quantite=ligne.quantite,
            prix_unitaire=ligne.prix_unitaire,
            remise_pct=ligne.remise_pct,
            montant_ligne=montant,
            ordre=ligne.ordre or i,
        ))


@router.get("", response_model=List[DevisOut])
def list_devis(
    statut: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Devis).options(*_EAGER)
    if statut:
        q = q.filter(Devis.statut == statut)
    if client_id:
        q = q.filter(Devis.client_id == client_id)
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Devis.num_devis.ilike(like), Devis.objet.ilike(like)))
    q = q.order_by(Devis.created_at.desc())
    return [_to_out(d) for d in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/{devis_id}", response_model=DevisOut)
def get_devis(devis_id: str, db: Session = Depends(get_db)):
    return _to_out(_get_devis(devis_id, db))


@router.post("", response_model=DevisOut, status_code=201)
def create_devis(body: DevisCreate, db: Session = Depends(get_db)):
    _check_client(body.client_id, db)
    if body.moteur_id and not db.query(Moteur).filter(Moteur.id == body.moteur_id).first():
        raise HTTPException(404, f"Moteur {body.moteur_id!r} introuvable")
    d = Devis(
        id=str(uuid4()),
        client_id=body.client_id,
        moteur_id=body.moteur_id or None,
        num_devis=next_num_devis(db, settings.DEVICE_PREFIX),
        objet=body.objet,
        description=body.description,
        demande_client=body.demande_client,
        date_devis=body.date_devis,
        date_validite=body.date_validite,
        statut=body.statut,
        navire_nom=body.navire_nom,
        navire_immatriculation=body.navire_immatriculation,
        navire_pavillon=body.navire_pavillon,
        navire_port_attache=body.navire_port_attache,
        navire_type_usage=body.navire_type_usage,
        lieu_intervention=body.lieu_intervention,
        destinataire_nom=body.destinataire_nom,
        destinataire_email=body.destinataire_email,
        destinataire_telephone=body.destinataire_telephone,
        acompte_pct=body.acompte_pct,
        delai_paiement_jours=body.delai_paiement_jours,
        conditions=body.conditions,
        notes=body.notes,
        exonere_tva=body.exonere_tva,
        moteurs_supplementaires_json=body.moteurs_supplementaires_json,
    )
    db.add(d)
    db.flush()
    _recalc_lignes(d, body.lignes, db)
    db.commit()
    db.refresh(d)
    return _to_out(d)


@router.put("/{devis_id}", response_model=DevisOut)
def update_devis(devis_id: str, body: DevisUpdate, db: Session = Depends(get_db)):
    d = _get_devis(devis_id, db)
    data = body.model_dump(exclude_unset=True)
    lignes = data.pop("lignes", None)

    if d.statut == "Transformé":
        # Devis déjà transformé en bon : seuls notes/conditions restent modifiables,
        # pour ne pas faire diverger le devis du bon d'intervention déjà créé.
        interdits = set(data.keys()) - {"notes", "conditions"}
        if interdits or lignes is not None:
            raise HTTPException(
                409,
                f"Devis déjà transformé en bon {d.intervention.num_bon if d.intervention else ''} "
                "— seules les notes et conditions restent modifiables.",
            )

    if "client_id" in data:
        cid = data.pop("client_id")
        _check_client(cid, db)
        d.client_id = cid
    if "moteur_id" in data:
        mid = data.pop("moteur_id")
        if mid and not db.query(Moteur).filter(Moteur.id == mid).first():
            raise HTTPException(404, f"Moteur {mid!r} introuvable")
        d.moteur_id = mid or None

    for field, val in data.items():
        if val is not None:
            setattr(d, field, val)

    if lignes is not None:
        _recalc_lignes(d, body.lignes, db)

    d.version = (d.version or 1) + 1
    db.commit()
    db.refresh(d)
    return _to_out(d)


@router.delete("/{devis_id}", status_code=204)
def delete_devis(devis_id: str, db: Session = Depends(get_db)):
    d = _get_devis(devis_id, db)
    db.delete(d)
    db.commit()


@router.post("/{devis_id}/transformer", response_model=DevisTransformOut)
def transformer_devis(devis_id: str, db: Session = Depends(get_db)):
    """Transforme un devis 'Accepté' en bon d'intervention (Intervention brouillon)."""
    d = _get_devis(devis_id, db)
    if d.statut != "Accepté":
        raise HTTPException(409, "Seul un devis au statut 'Accepté' peut être transformé en bon.")
    if d.intervention_id:
        num_bon = d.intervention.num_bon if d.intervention else d.intervention_id
        raise HTTPException(409, f"Ce devis a déjà été transformé (bon {num_bon}).")

    demande_client = d.demande_client or d.description or d.objet
    # Format attendu par MaterielsTable (ems_project) et bon_generator.py :
    # une liste de {"qte", "ref", "designation"}, et non un texte à plat —
    # sinon le bon d'intervention affiche tout dans une seule ligne "désignation"
    # sans référence ni quantité (cf. fallback legacy sur `pieces`).
    materiels = [
        {
            "qte": (f"{l.quantite:g}" if l.quantite is not None else ""),
            "ref": l.reference or "",
            "designation": l.libelle or "",
        }
        for l in d.lignes
    ]
    num_bon = next_num_bon(db, settings.DEVICE_PREFIX)
    inv = Intervention(
        id=str(uuid4()),
        num_bon=num_bon,
        client_id=d.client_id,
        moteur_id=d.moteur_id,
        statut="En cours",
        date_creation=datetime.now().strftime("%d/%m/%Y"),
        demande_client=demande_client,
        description=demande_client,
        materiels_json=json.dumps(materiels, ensure_ascii=False),
        moteurs_supplementaires_json=d.moteurs_supplementaires_json or "[]",
    )
    db.add(inv)
    db.flush()

    d.statut = "Transformé"
    d.intervention_id = inv.id
    d.version = (d.version or 1) + 1

    db.commit()
    db.refresh(d)
    db.refresh(inv)

    return DevisTransformOut(devis=_to_out(d), intervention_id=inv.id, num_bon=inv.num_bon)


@router.get("/{devis_id}/pdf",
            summary="Génère et renvoie le devis en PDF",
            response_class=Response)
def generer_pdf_devis(devis_id: str, db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_devis_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    d = _get_devis(devis_id, db)
    client_dict = {c.name: getattr(d.client, c.name) for c in d.client.__table__.columns} if d.client else None
    moteur_dict = {c.name: getattr(d.moteur, c.name) for c in d.moteur.__table__.columns} if d.moteur else None
    devis_dict = {c.name: getattr(d, c.name) for c in d.__table__.columns}
    lignes = [
        {c.name: getattr(l, c.name) for c in l.__table__.columns}
        for l in d.lignes
    ]
    try:
        moteurs_supp = json.loads(d.moteurs_supplementaires_json or "[]")
    except (json.JSONDecodeError, TypeError):
        moteurs_supp = []

    html_str = build_devis_html(devis_dict, lignes, client=client_dict, moteur=moteur_dict,
                                 moteurs_supplementaires=moteurs_supp)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = d.num_devis.replace("/", "-").replace(" ", "_")
    d.date_generation = datetime.now()
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_num}.pdf"',
            "Cache-Control": "no-store",
        },
    )

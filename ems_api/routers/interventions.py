"""Endpoints REST pour les Interventions (+ signatures + notifications).

MODIFICATIONS (perf) :
- selectinload(client, moteur) sur tous les endpoints de liste : supprime
  le N+1 (avant : 2 requetes SQL supplementaires PAR intervention a cause
  des acces lazy inv.client / inv.moteur dans _to_out).
- Fuseau Europe/Paris via zoneinfo (gere automatiquement heure d'ete/hiver,
  l'ancien timezone(timedelta(hours=1)) etait faux 6 mois par an).
  Sous Windows : `pip install tzdata` (a ajouter au requirements.txt).
"""
from typing import List, Optional
from uuid import uuid4
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import or_

from ..database import get_db
from ..models import Intervention, Client, Moteur, Contact
from ..schemas.intervention import (
    InterventionCreate, InterventionUpdate, InterventionOut, SignatureIn,
)
from ..services.numerotation import next_num_bon


# Heure Paris — zoneinfo gere l'heure d'ete/hiver. Necessite le paquet
# `tzdata` sous Windows. Fallback UTC+1 fixe si tzdata absent.
try:
    from zoneinfo import ZoneInfo
    PARIS = ZoneInfo("Europe/Paris")
except Exception:
    from datetime import timezone, timedelta
    PARIS = timezone(timedelta(hours=1))


router = APIRouter(prefix="/interventions", tags=["interventions"])


def _upsert_contact(db: Session, nom: str, email: str, telephone: str):
    """Mémorise ou met à jour un contact dans la table contacts (fail-safe).
    Utilise un savepoint pour ne pas annuler la transaction parente en cas d'erreur."""
    nom = (nom or "").strip()
    if not nom:
        return
    try:
        with db.begin_nested():
            existing = db.query(Contact).filter(Contact.nom == nom).first()
            if existing:
                existing.usage_count = (existing.usage_count or 0) + 1
                if email and not existing.email:
                    existing.email = email
                if telephone and not existing.telephone:
                    existing.telephone = telephone
            else:
                db.add(Contact(
                    id=str(uuid4()),
                    nom=nom,
                    email=(email or "").strip(),
                    telephone=(telephone or "").strip(),
                    usage_count=1,
                ))
    except Exception:
        import logging as _log
        _log.getLogger(__name__).warning(
            "Impossible d'upsert le contact %r (table absente ou erreur schema).", nom
        )


# Chargement anticipe des relations utilisees par _to_out : evite le N+1.
_EAGER = (
    selectinload(Intervention.client),
    selectinload(Intervention.moteur),
)


def _to_out(inv: Intervention) -> dict:
    """Sérialise une intervention en garantissant TOUS les champs."""
    d = {}
    for c in inv.__table__.columns:
        val = getattr(inv, c.name)
        if val is None and not c.name.endswith("_at"):
            # Type par défaut selon la colonne
            if c.name in ("garantie_intervention", "facturable", "interne",
                           "outil_diagnostic", "memoriser_avant", "memoriser_apres",
                           "photos_avant", "photos_apres", "pour_information",
                           "preconisation", "client_notifie", "tech_notifie"):
                val = 0
            else:
                val = ""
        d[c.name] = val
    # Jointures pour les vues Tkinter
    d["client_nom"] = inv.client.nom if inv.client else ""
    d["moteur_serie"] = inv.moteur.num_serie if inv.moteur else ""
    # Champs additionnels attendus par le code Tkinter
    d["navire"] = inv.moteur.navire if inv.moteur else ""
    d["num_serie"] = inv.moteur.num_serie if inv.moteur else ""
    d["marque"] = inv.moteur.marque if inv.moteur else ""
    d["machine"] = inv.moteur.machine if inv.moteur else ""
    d["type_moteur"] = inv.moteur.type_moteur if inv.moteur else ""
    d["date_mise_service"] = inv.moteur.date_mise_service if inv.moteur else ""
    d["ref_constructeur"] = inv.moteur.ref_constructeur if inv.moteur else ""
    return d


@router.get("", response_model=List[InterventionOut])
def list_interventions(
    statut: Optional[str] = None,
    urgence: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Intervention).options(*_EAGER)
    if statut and statut != "Tous":
        q = q.filter(Intervention.statut == statut)
    if urgence and urgence != "Toutes":
        q = q.filter(Intervention.urgence == urgence)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Client).outerjoin(Moteur).filter(
            or_(
                # Intervention – identifiants
                Intervention.num_bon.ilike(like),
                Intervention.num_commande_client.ilike(like),
                Intervention.type_intervention.ilike(like),
                Intervention.date_creation.ilike(like),
                # Intervention – personnes
                Intervention.technicien.ilike(like),
                Intervention.nom_signataire.ilike(like),
                Intervention.email_signataire.ilike(like),
                Intervention.telephone_signataire.ilike(like),
                Intervention.nom_demandeur.ilike(like),
                Intervention.email_demandeur.ilike(like),
                Intervention.telephone_demandeur.ilike(like),
                # Intervention – localisation & textes
                Intervention.lieu_intervention.ilike(like),
                Intervention.demande_client.ilike(like),
                Intervention.constat.ilike(like),
                Intervention.travaux.ilike(like),
                Intervention.informations.ilike(like),
                Intervention.preconisation_text.ilike(like),
                Intervention.commentaire.ilike(like),
                Intervention.marque.ilike(like),
                Intervention.description.ilike(like),
                # Client
                Client.nom.ilike(like),
                Client.contact.ilike(like),
                Client.adresse.ilike(like),
                # Moteur
                Moteur.num_serie.ilike(like),
                Moteur.navire.ilike(like),
                Moteur.machine.ilike(like),
                Moteur.type_moteur.ilike(like),
                Moteur.marque.ilike(like),
                Moteur.ref_constructeur.ilike(like),
            )
        )
    q = q.order_by(Intervention.created_at.desc())
    return [_to_out(i) for i in q.all()]


@router.get("/urgentes", response_model=List[InterventionOut])
def list_urgentes(limit: int = Query(10, ge=1, le=100),
                  db: Session = Depends(get_db)):
    """Interventions urgentes/critiques en cours."""
    q = (db.query(Intervention)
         .options(*_EAGER)
         .filter(Intervention.urgence.in_(("Urgente", "Critique")))
         .filter(Intervention.statut == "En cours")
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/a-programmer", response_model=List[InterventionOut])
def list_a_programmer(limit: int = Query(10, ge=1, le=100),
                       db: Session = Depends(get_db)):
    """Interventions au statut 'Date à programmer'."""
    q = (db.query(Intervention)
         .options(*_EAGER)
         .filter(Intervention.statut == "Date à programmer")
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/a-facturer", response_model=List[InterventionOut])
def list_a_facturer(limit: int = Query(10, ge=1, le=100),
                    db: Session = Depends(get_db)):
    """Interventions au statut 'À facturer'."""
    q = (db.query(Intervention)
         .options(*_EAGER)
         .filter(Intervention.statut == "À facturer")
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/non-notifies", response_model=List[InterventionOut])
def list_non_notifies(limit: int = Query(50, ge=1, le=500),
                       db: Session = Depends(get_db)):
    """Interventions en cours dont client OU technicien n'est pas notifié."""
    q = (db.query(Intervention)
         .options(*_EAGER)
         .filter(Intervention.statut == "En cours")
         .filter((Intervention.client_notifie == 0) |
                 (Intervention.tech_notifie == 0))
         .order_by(Intervention.created_at.desc())
         .limit(limit))
    return [_to_out(i) for i in q.all()]


@router.get("/by-moteur/{moteur_id}", response_model=List[InterventionOut])
def list_for_moteur(moteur_id: str, db: Session = Depends(get_db)):
    q = (db.query(Intervention)
         .options(*_EAGER)
         .filter(or_(
             Intervention.moteur_id == moteur_id,
             Intervention.moteurs_supplementaires_json.like(f'%"id": "{moteur_id}"%'),
         ))
         .order_by(Intervention.created_at.desc()))
    return [_to_out(i) for i in q.all()]


@router.get("/by-num/{num_bon}", response_model=InterventionOut)
def get_by_num(num_bon: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.num_bon == num_bon).first()
    if not inv:
        raise HTTPException(404, f"Bon {num_bon} introuvable")
    return _to_out(inv)


@router.get("/{inv_id}", response_model=InterventionOut)
def get_intervention(inv_id: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    return _to_out(inv)


@router.post("", response_model=InterventionOut,
             status_code=status.HTTP_201_CREATED)
def create_intervention(data: InterventionCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    # Si num_bon non fourni → génération auto
    if not payload.get("num_bon"):
        from ..config import settings
        payload["num_bon"] = next_num_bon(db, settings.DEVICE_PREFIX)
    inv = Intervention(id=str(uuid4()), **payload)
    db.add(inv)
    _upsert_contact(db, payload.get("nom_signataire", ""),
                    payload.get("email_signataire", ""),
                    payload.get("telephone_signataire", ""))
    _upsert_contact(db, payload.get("nom_demandeur", ""),
                    payload.get("email_demandeur", ""),
                    payload.get("telephone_demandeur", ""))
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


@router.put("/{inv_id}", response_model=InterventionOut)
def update_intervention(inv_id: str, data: InterventionUpdate,
                        db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    updated = data.model_dump(exclude_unset=True)
    for field, value in updated.items():
        setattr(inv, field, value)
    # Incrémenter la version pour la détection de conflit lors de la synchro
    inv.version = (inv.version or 0) + 1
    _upsert_contact(db, updated.get("nom_signataire", inv.nom_signataire),
                    updated.get("email_signataire", inv.email_signataire),
                    updated.get("telephone_signataire", inv.telephone_signataire))
    _upsert_contact(db, updated.get("nom_demandeur", inv.nom_demandeur),
                    updated.get("email_demandeur", inv.email_demandeur),
                    updated.get("telephone_demandeur", inv.telephone_demandeur))
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


@router.delete("/{inv_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_intervention(inv_id: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    db.delete(inv)
    db.commit()
    return None


# ─── Signatures ──────────────────────────────────────────────────────────────
@router.post("/{inv_id}/signature", response_model=InterventionOut)
def enregistrer_signature(inv_id: str, payload: SignatureIn,
                          db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    horod = datetime.now(PARIS).strftime("%d/%m/%Y %H:%M")
    if payload.role == "technicien":
        inv.signature_tech_b64 = payload.signature_b64
        inv.signature_tech_nom = payload.signature_nom
        inv.signature_tech_date = horod
    else:
        inv.signature_b64 = payload.signature_b64
        inv.signature_nom = payload.signature_nom
        inv.signature_date = horod

    # Bascule automatique : si client ET technicien ont signe, et que le bon
    # est encore "En cours", on passe a "A facturer". Sans ecraser un statut
    # deja modifie manuellement (Facture, Clos, etc.)
    has_client_sig = bool(inv.signature_b64)
    has_tech_sig   = bool(inv.signature_tech_b64)
    if has_client_sig and has_tech_sig and inv.statut == "En cours" and inv.facturable:
        inv.statut = "À facturer"

    inv.version = (inv.version or 0) + 1
    db.commit()
    db.refresh(inv)
    return _to_out(inv)


# ─── Notifications ───────────────────────────────────────────────────────────
@router.post("/{inv_id}/notifie/{kind}", response_model=InterventionOut)
def mark_notifie(inv_id: str, kind: str, db: Session = Depends(get_db)):
    """kind = 'client' ou 'tech'."""
    if kind not in ("client", "tech"):
        raise HTTPException(400, "kind doit être 'client' ou 'tech'")
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    if kind == "client":
        inv.client_notifie = 1
    else:
        inv.tech_notifie = 1
    db.commit()
    db.refresh(inv)
    return _to_out(inv)

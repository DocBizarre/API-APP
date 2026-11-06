"""Liens références produits ↔ fournisseurs (table piece_fournisseurs).

Fonctions partagées par les routers pièces, bons de commande et intentions
d'achat. Tout est « fail-safe » côté achats : un problème de liaison ne doit
jamais empêcher l'enregistrement d'un bon de commande.
"""
import logging
from datetime import date
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import Fournisseur, Piece, PieceFournisseur

_log = logging.getLogger(__name__)


def find_fournisseur(db: Session, nom: str):
    nom = (nom or "").strip()
    if not nom:
        return None
    return (db.query(Fournisseur)
              .filter(func.lower(func.trim(Fournisseur.nom)) == nom.lower())
              .first())


def get_or_create_fournisseur(db: Session, nom: str, cache: dict | None = None):
    """Fournisseur par nom (casse ignorée) ; créé s'il n'existe pas encore."""
    nom = (nom or "").strip()
    if not nom:
        return None
    key = nom.lower()
    if cache is not None and key in cache:
        return cache[key]
    f = find_fournisseur(db, nom)
    if f is None:
        f = Fournisseur(id=str(uuid4()), nom=nom, usage_count=0)
        db.add(f)
        db.flush()
    if cache is not None:
        cache[key] = f
    return f


def link(db: Session, piece_id: str, fournisseur_id: str, ref_fournisseur: str = "",
         prix_achat: float | None = None, date_achat: str = "",
         overwrite: bool = True) -> PieceFournisseur:
    """Crée ou met à jour le lien pièce ↔ fournisseur. Les valeurs vides ne
    remplacent jamais une valeur existante ; overwrite=False ne fait que
    compléter les champs vides du lien."""
    lk = (db.query(PieceFournisseur)
            .filter(PieceFournisseur.piece_id == piece_id,
                    PieceFournisseur.fournisseur_id == fournisseur_id)
            .first())
    if lk is None:
        lk = PieceFournisseur(id=str(uuid4()), piece_id=piece_id,
                              fournisseur_id=fournisseur_id,
                              ref_fournisseur="", prix_achat=0.0, date_dernier_achat="")
        db.add(lk)
    ref_fournisseur = (ref_fournisseur or "").strip()
    if ref_fournisseur and (overwrite or not lk.ref_fournisseur):
        lk.ref_fournisseur = ref_fournisseur
    if prix_achat and prix_achat > 0 and (overwrite or not lk.prix_achat):
        lk.prix_achat = prix_achat
    if date_achat and (overwrite or not lk.date_dernier_achat):
        lk.date_dernier_achat = date_achat
    return lk


def lier_lignes_achat(db: Session, fournisseur_nom: str, lignes, date_achat: str = "") -> None:
    """Lie au fournisseur du bon chaque ligne correspondant à une référence du
    catalogue (par piece_id, sinon par référence exacte) et mémorise le prix
    unitaire comme dernier prix d'achat. `lignes` : objets avec piece_id,
    reference, prix_unitaire."""
    if not (fournisseur_nom or "").strip() or not lignes:
        return
    date_achat = date_achat or date.today().strftime("%d/%m/%Y")
    try:
        with db.begin_nested():
            f = get_or_create_fournisseur(db, fournisseur_nom)
            for l in lignes:
                piece = None
                pid = getattr(l, "piece_id", None)
                if pid:
                    piece = db.query(Piece).filter(Piece.id == pid).first()
                ref = (getattr(l, "reference", "") or "").strip()
                if piece is None and ref:
                    piece = db.query(Piece).filter(Piece.reference == ref).first()
                if piece is None:
                    continue
                link(db, piece.id, f.id, prix_achat=getattr(l, "prix_unitaire", 0) or 0,
                     date_achat=date_achat)
    except Exception:
        _log.warning("Liaison références ↔ fournisseur %r impossible.", fournisseur_nom,
                     exc_info=True)


def fournisseurs_par_piece(db: Session, piece_ids) -> dict:
    """{piece_id: [ {fournisseur_id, nom, ref_fournisseur, prix_achat, date_dernier_achat}, … ]}"""
    piece_ids = list(piece_ids)
    if not piece_ids:
        return {}
    rows = (db.query(PieceFournisseur, Fournisseur.nom)
              .join(Fournisseur, Fournisseur.id == PieceFournisseur.fournisseur_id)
              .filter(PieceFournisseur.piece_id.in_(piece_ids))
              .order_by(Fournisseur.nom)
              .all())
    out: dict = {}
    for lk, nom in rows:
        out.setdefault(lk.piece_id, []).append(link_out(lk, nom))
    return out


def link_out(lk: PieceFournisseur, nom: str) -> dict:
    return {
        "fournisseur_id": lk.fournisseur_id,
        "nom": nom,
        "ref_fournisseur": lk.ref_fournisseur or "",
        "prix_achat": lk.prix_achat or 0.0,
        "date_dernier_achat": lk.date_dernier_achat or "",
    }


def _date_key(d: str):
    """« JJ/MM/AAAA » → (AAAA, MM, JJ) pour trier ; date illisible → en premier."""
    try:
        j, m, a = (int(x) for x in (d or "").split("/"))
        return (a, m, j)
    except ValueError:
        return (0, 0, 0)


def backfill_depuis_achats(db: Session) -> int:
    """Crée les liens à partir de tous les bons de commande et intentions
    d'achat existants, du plus ancien au plus récent (le dernier prix gagne).
    Retourne le nombre de liens présents à la fin."""
    from ..models.bon_commande import BonCommande
    from ..models.intention_achat import IntentionAchat
    achats = [b for b in db.query(BonCommande).all() if (b.fournisseur_nom or "").strip()]
    achats += [i for i in db.query(IntentionAchat).all() if (i.fournisseur_nom or "").strip()]
    achats.sort(key=lambda a: _date_key(a.date_commande))
    pieces_by_id = {p.id: p for p in db.query(Piece).all()}
    pieces_by_ref = {p.reference: p for p in pieces_by_id.values()}
    cache: dict = {}
    for a in achats:
        f = get_or_create_fournisseur(db, a.fournisseur_nom, cache)
        for l in a.lignes:
            piece = pieces_by_id.get(l.piece_id) if l.piece_id else None
            if piece is None and (l.reference or "").strip():
                piece = pieces_by_ref.get(l.reference.strip())
            if piece is None:
                continue
            link(db, piece.id, f.id, prix_achat=l.prix_unitaire or 0,
                 date_achat=a.date_commande or "")
            db.flush()
    return db.query(PieceFournisseur).count()

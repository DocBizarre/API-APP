"""Endpoints REST pour les Affaires et leurs items."""
from typing import List, Optional
from uuid import uuid4
from pathlib import Path
import json as _json_mod
import logging
import subprocess, sys, os, time, re, unicodedata, mimetypes
from datetime import date as _date

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Form
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, object_session, joinedload
from sqlalchemy import or_, func as _func

from ..database import get_db
from ..models.affaire import Affaire, AffaireItem, AffaireCoutLigne
from ..models.client import Client
from ..models.bon_commande import BonCommande, BonCommandeLigne
from ..schemas.affaire import (
    AffaireCreate, AffaireUpdate, AffaireOut,
    AffaireItemCreate, AffaireItemUpdate, AffaireItemOut,
    AffaireCoutLigneCreate, AffaireCoutLigneUpdate, AffaireCoutLigneOut,
)
from ..services.numerotation import next_num_affaire
from ..config import settings
from .interventions import _upsert_contact
from .fournisseurs import _upsert_fournisseur
from .navires import _upsert_navire

router = APIRouter(prefix="/affaires", tags=["affaires"])

STATUTS = ["En cours", "En attente", "À facturer", "Clos", "Annulé"]
COMPLEXITES = ["A", "B", "C"]


def _upsert_interlocuteurs(db: Session, interlocuteurs_json: str, entreprise: str = "") -> None:
    """Mémorise chaque interlocuteur client dans la table contacts (autocomplétion)."""
    try:
        interlocuteurs = _json_mod.loads(interlocuteurs_json or "[]")
    except Exception:
        interlocuteurs = []
    for it in interlocuteurs:
        _upsert_contact(db, it.get("nom", ""), it.get("email", ""), it.get("telephone", ""),
                         entreprise=entreprise)


def _to_out(a: Affaire) -> dict:
    d = {}
    for c in a.__table__.columns:
        val = getattr(a, c.name)
        # Les colonnes entières gardent leur valeur numérique (0 est valide)
        if val is None:
            d[c.name] = 0 if str(c.type).startswith("INTEGER") else ""
        else:
            d[c.name] = val
    d["client_nom"] = a.client.nom if a.client else ""
    d["nb_items"] = len(a.items)
    # Total achats HT (cf. décision plan §8.2) des bons de commande liés à l'affaire.
    db = object_session(a)
    total_achats = 0.0
    if db is not None:
        total_lignes = (
            db.query(_func.sum(BonCommandeLigne.montant_ligne))
            .join(BonCommande, BonCommandeLigne.bon_commande_id == BonCommande.id)
            .filter(BonCommande.affaire_id == a.id)
            .scalar()
        ) or 0.0
        total_frais_port = (
            db.query(_func.sum(BonCommande.frais_port))
            .filter(BonCommande.affaire_id == a.id)
            .scalar()
        ) or 0.0
        total_achats = total_lignes + total_frais_port
    d["total_achats"] = total_achats
    return d


def _to_out_bulk(affaires: List[Affaire], db: Session) -> List[dict]:
    """Équivalent de _to_out() pour une liste, sans requête N+1 : les compteurs
    d'items et totaux d'achats sont calculés en une requête agrégée chacun,
    plutôt qu'en 2 requêtes par affaire."""
    ids = [a.id for a in affaires]
    if not ids:
        return []
    nb_items_map = dict(
        db.query(AffaireItem.affaire_id, _func.count(AffaireItem.id))
          .filter(AffaireItem.affaire_id.in_(ids))
          .group_by(AffaireItem.affaire_id)
          .all()
    )
    lignes_map = dict(
        db.query(BonCommande.affaire_id, _func.sum(BonCommandeLigne.montant_ligne))
          .join(BonCommandeLigne, BonCommandeLigne.bon_commande_id == BonCommande.id)
          .filter(BonCommande.affaire_id.in_(ids))
          .group_by(BonCommande.affaire_id)
          .all()
    )
    frais_map = dict(
        db.query(BonCommande.affaire_id, _func.sum(BonCommande.frais_port))
          .filter(BonCommande.affaire_id.in_(ids))
          .group_by(BonCommande.affaire_id)
          .all()
    )
    out = []
    for a in affaires:
        d = {}
        for c in a.__table__.columns:
            val = getattr(a, c.name)
            if val is None:
                d[c.name] = 0 if str(c.type).startswith("INTEGER") else ""
            else:
                d[c.name] = val
        d["client_nom"] = a.client.nom if a.client else ""
        d["nb_items"] = nb_items_map.get(a.id, 0)
        d["total_achats"] = (lignes_map.get(a.id) or 0.0) + (frais_map.get(a.id) or 0.0)
        out.append(d)
    return out


def _item_to_out(it: AffaireItem) -> dict:
    d = {}
    for c in it.__table__.columns:
        val = getattr(it, c.name)
        if val is None:
            d[c.name] = 0 if str(c.type) == "INTEGER" else ""
        else:
            d[c.name] = val
    return d


def _cout_to_out(c: AffaireCoutLigne) -> dict:
    d = {}
    for col in c.__table__.columns:
        val = getattr(c, col.name)
        if val is None:
            t = str(col.type)
            d[col.name] = 0 if (t.startswith("INTEGER") or t.startswith("FLOAT")) else ""
        else:
            d[col.name] = val
    return d


def _slug(s: str) -> str:
    """Convertit une chaîne en nom de dossier sûr (ASCII, sans espaces)."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^\w\s-]", "", s).strip()
    s = re.sub(r"[\s_]+", "_", s)
    return s[:30] or "chapitre"


def _sanitize_folder(s: str, maxlen: int = 60) -> str:
    """Sanitise un composant de nom de dossier Windows (garde les accents et caractères spéciaux, retire '/ \\ : * ? " < > |')."""
    s = re.sub(r'[<>:"/\\|?*]', '', s or '').strip()
    s = s.replace('/', ' - ')
    s = re.sub(r'\s+', ' ', s)
    return s[:maxlen].strip()


def _restrict_commercial_access(folder: Path) -> None:
    """Casse l'héritage NTFS sur COMMERCIAL et le restreint au groupe AD configuré.

    Sans groupe configuré (settings.COMMERCIAL_GROUP vide), ne fait rien : le
    dossier reste ouvert comme le reste de l'arborescence.
    """
    if sys.platform != "win32" or not settings.COMMERCIAL_GROUP:
        return
    try:
        subprocess.run(["icacls", str(folder), "/inheritance:r"],
                        capture_output=True, timeout=10, check=False)
        grants = [f"{settings.COMMERCIAL_GROUP}:(OI)(CI)M"]
        grants += [f"{a.strip()}:(OI)(CI)F" for a in settings.COMMERCIAL_ADMINS.split(",") if a.strip()]
        args = ["icacls", str(folder)]
        for g in grants:
            args += ["/grant:r", g]
        subprocess.run(args, capture_output=True, timeout=10, check=False)
    except Exception:
        pass


def _create_arborescence(base: Path) -> None:
    """Crée l'arborescence standard dans le dossier affaire."""
    structure = {
        "COMMERCIAL": [],
        "ACHAT": ["FOURNISSEURS", "NOMENCLATURES"],
        "TECHNIQUE": [
            "SPECIFICATIONS",
            "ETUDE ET PLANS",
            "FABRICATION - MONTAGE",
            "ESSAI USINE",
            "PHOTO ATELIER",
        ],
        "QUALITE - CERTIFICATION": [],
    }
    for folder, subfolders in structure.items():
        d = base / folder
        is_new = not d.exists()
        d.mkdir(parents=True, exist_ok=True)
        for sub in subfolders:
            (d / sub).mkdir(parents=True, exist_ok=True)
        if folder == "COMMERCIAL" and is_new:
            _restrict_commercial_access(d)


def _create_dossier(num_affaire: str, client_nom: str = "", navire_machine: str = "", nom_projet: str = "") -> str:
    """Crée le dossier racine de l'affaire et retourne son chemin.

    Format : «AMOTYYYYNNNN   00_ClientNom_NavireMachine - NomProjet»
    """
    try:
        parts = []
        if client_nom:
            parts.append(_sanitize_folder(client_nom))
        if navire_machine:
            parts.append(_sanitize_folder(navire_machine))
        main_part = "_".join(parts)

        if nom_projet:
            proj_part = _sanitize_folder(nom_projet)
            full_suffix = f"{main_part} - {proj_part}" if main_part else proj_part
        else:
            full_suffix = main_part

        folder_name = f"{num_affaire}   00_{full_suffix}" if full_suffix else num_affaire
        base = Path(settings.AFFAIRES_DIR) / folder_name
        base.mkdir(parents=True, exist_ok=True)
        _create_arborescence(base)
        return str(base)
    except Exception:
        logger.exception("Echec creation dossier affaire (num=%s, AFFAIRES_DIR=%s)",
                          num_affaire, settings.AFFAIRES_DIR)
        return ""


def _create_item_dossier(affaire_dossier: str, libelle: str, type_item: str) -> str:
    """Crée le sous-dossier du chapitre (nom = slug du libellé) et retourne son chemin."""
    try:
        if not affaire_dossier:
            return ""
        folder_name = _slug(libelle or type_item or "chapitre")
        p = Path(affaire_dossier) / folder_name
        p.mkdir(parents=True, exist_ok=True)
        return str(p)
    except Exception:
        logger.exception("Echec creation dossier chapitre (affaire_dossier=%s, libelle=%s)",
                          affaire_dossier, libelle)
        return ""


# ─── Affaires ────────────────────────────────────────────────────────────────

_SORT_COLUMNS = {
    "num_affaire":     Affaire.num_affaire,
    "nom_projet":      Affaire.nom_projet,
    "client_nom":      Client.nom,
    "navire_machine":  Affaire.navire_machine,
    "charge_affaire":  Affaire.charge_affaire,
    "date_debut":      Affaire.date_debut,
    "date_fin_prevue": Affaire.date_fin_prevue,
    "statut":          Affaire.statut,
    "complexite":      Affaire.complexite,
}


@router.get("")
def list_affaires(
    statut: Optional[str] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
    sort: Optional[str] = None,
    dir: str = "desc",
    db: Session = Depends(get_db),
):
    """Sans `limit` : renvoie la liste complète (comportement historique, utilisé
    par le tableau de bord / planning / facturation qui ont besoin de tout le
    jeu de données). Avec `limit` : pagine côté serveur et renvoie
    {"items": [...], "total": N} pour la vue "Affaires" (recherche)."""
    base = db.query(Affaire)
    needs_client_join = bool(search) or sort == "client_nom"
    if needs_client_join:
        base = base.outerjoin(Client)
    if statut and statut not in ("Tous", "Toutes"):
        base = base.filter(Affaire.statut == statut)
    if search:
        like = f"%{search}%"
        base = base.filter(
            or_(Affaire.num_affaire.ilike(like),
                Affaire.nom_projet.ilike(like),
                Affaire.navire_machine.ilike(like),
                Affaire.ref_interne.ilike(like),
                Affaire.charge_affaire.ilike(like),
                Client.nom.ilike(like))
        )

    total = base.with_entities(_func.count(Affaire.id.distinct())).scalar() if limit is not None else None

    order_col = _SORT_COLUMNS.get(sort, Affaire.created_at)
    order_by = order_col.asc() if dir == "asc" else order_col.desc()
    q = base.options(joinedload(Affaire.client)).order_by(order_by)
    if limit is not None:
        q = q.offset(offset).limit(limit)

    items = _to_out_bulk(q.all(), db)
    if limit is not None:
        return {"items": items, "total": total}
    return items


@router.get("/statuts")
def get_statuts():
    return STATUTS


@router.get("/complexites")
def get_complexites():
    return COMPLEXITES


_COMPLEXITE_RANK = {"C": 3, "B": 2, "A": 1}


@router.get("/planning/pdf",
            summary="Génère le planning atelier (Gantt hebdomadaire) en PDF",
            response_class=Response)
def generer_planning_pdf(annee: Optional[int] = None, sans_prix: bool = False,
                         statut: Optional[str] = None,
                         db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")
    try:
        from shared.affaire_pdf import build_planning_pdf
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    def _parse_fr(s):
        try:
            j, m, a = str(s).split("/")
            return _date(int(a), int(m), int(j))
        except (ValueError, TypeError, AttributeError):
            return None

    # Collecte de toutes les affaires valides (dates cohérentes) avec, pour
    # chacune, la plage d'années réellement couverte par sa barre (livraison,
    # ou visite applicative / commissioning si elles s'étendent au-delà).
    affaires = []
    for a in db.query(Affaire).options(joinedload(Affaire.client)).all():
        if statut and statut != "all" and a.statut != statut:
            continue
        ds, de = _parse_fr(a.date_debut), _parse_fr(a.date_fin_prevue)
        if not ds or not de or de < ds:
            continue
        effective_end = de
        for field in ("date_visite_appli_debut", "date_visite_appli_fin",
                      "date_commissioning_debut", "date_commissioning_fin"):
            d = _parse_fr(getattr(a, field))
            if d and d > effective_end:
                effective_end = d
        row = {
            "num_affaire":     a.num_affaire,
            "client_nom":      a.client.nom if a.client else "",
            "nom_projet":      a.nom_projet,
            "navire_machine":  a.navire_machine,
            "statut":          a.statut,
            "complexite":      a.complexite,
            "prix_ht":         a.prix_ht,
            "date_debut":      a.date_debut,
            "date_fat":        a.date_fat,
            "date_fin_fat":    a.date_fin_fat,
            "date_fin_prevue": a.date_fin_prevue,
            "date_visite_appli_debut":  a.date_visite_appli_debut,
            "date_visite_appli_fin":    a.date_visite_appli_fin,
            "date_commissioning_debut": a.date_commissioning_debut,
            "date_commissioning_fin":   a.date_commissioning_fin,
        }
        affaires.append((ds, effective_end, row))

    if annee is not None:
        # Compat / usage API direct : une seule année explicitement demandée.
        years_to_generate = [annee]
    else:
        # Par défaut : toutes les années touchées par une affaire, à partir de
        # l'année en cours (les années passées ne sont plus pertinentes pour
        # un planning atelier), sauf en fin d'année (décembre) où l'année en
        # cours qui se termine reste encore incluse — on ne l'exclut donc pas
        # rétroactivement dès le 1er décembre.
        today = _date.today()
        min_year = today.year - 1 if today.month == 12 else today.year
        touched_years = set()
        for ds, effective_end, _row in affaires:
            for y in range(ds.year, effective_end.year + 1):
                touched_years.add(y)
        years_to_generate = sorted(y for y in touched_years if y >= min_year)
        if not years_to_generate:
            years_to_generate = [today.year]

    rows_by_year = {}
    for year in years_to_generate:
        year_start, year_end = _date(year, 1, 1), _date(year, 12, 31)
        year_entries = [(ds, row) for ds, effective_end, row in affaires
                         if effective_end >= year_start and ds <= year_end]
        year_entries.sort(key=lambda e: (-_COMPLEXITE_RANK.get(e[1]["complexite"], 0), e[0]))
        rows_by_year[year] = [row for _ds, row in year_entries]

    html_str = build_planning_pdf(rows_by_year, sans_prix=sans_prix)
    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    suffix = "_SansPrix" if sans_prix else ""
    year_label = str(years_to_generate[0]) if len(years_to_generate) == 1 \
        else f"{years_to_generate[0]}-{years_to_generate[-1]}"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Planning_Atelier_{year_label}{suffix}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{affaire_id}", response_model=AffaireOut)
def get_affaire(affaire_id: str, db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    return _to_out(a)


@router.post("", response_model=AffaireOut, status_code=201)
def create_affaire(body: AffaireCreate, db: Session = Depends(get_db)):
    num = body.num_affaire or next_num_affaire(db)
    client_nom = ""
    if body.client_id:
        c = db.query(Client).filter(Client.id == body.client_id).first()
        if c:
            client_nom = c.nom or ""
    dossier = _create_dossier(num, client_nom, body.navire_machine, body.nom_projet)
    a = Affaire(
        id=str(uuid4()),
        num_affaire=num,
        complexite=body.complexite,
        client_id=body.client_id or None,
        nom_projet=body.nom_projet,
        navire_machine=body.navire_machine,
        navire_immatriculation=body.navire_immatriculation,
        navire_port_attache=body.navire_port_attache,
        ref_interne=body.ref_interne,
        num_commande_client=body.num_commande_client,
        charge_affaire=body.charge_affaire,
        resp_technique=body.resp_technique,
        date_debut=body.date_debut,
        date_fat=body.date_fat,
        date_fin_fat=body.date_fin_fat,
        date_fin_prevue=body.date_fin_prevue,
        date_cloture=body.date_cloture,
        date_visite_appli_debut=body.date_visite_appli_debut,
        date_visite_appli_fin=body.date_visite_appli_fin,
        date_commissioning_debut=body.date_commissioning_debut,
        date_commissioning_fin=body.date_commissioning_fin,
        statut=body.statut,
        description=body.description,
        commentaires=body.commentaires,
        dossier_path=dossier,
        prix_ht=body.prix_ht,
        exonere_tva=body.exonere_tva,
        date_achat=body.date_achat,
        fournisseur=body.fournisseur,
        reference_fournisseur=body.reference_fournisseur,
        etablissement_financier=body.etablissement_financier,
        echeances_facturation=body.echeances_facturation,
        lots_vendus=body.lots_vendus,
        whiteboard=body.whiteboard,
        transporteur=body.transporteur,
        contact_transport=body.contact_transport,
        prix_transport=body.prix_transport,
        num_suivi_transport=body.num_suivi_transport,
        instructions_transport=body.instructions_transport,
        livraison_nom=body.livraison_nom,
        livraison_rue=body.livraison_rue,
        livraison_code_postal=body.livraison_code_postal,
        livraison_ville=body.livraison_ville,
        livraison_pays=body.livraison_pays,
        conditions_reglement=body.conditions_reglement,
        garanties=body.garanties,
        interlocuteurs_client=body.interlocuteurs_client,
    )
    db.add(a)
    _upsert_fournisseur(db, a.fournisseur)
    _client_nom = ""
    if a.client_id:
        _client = db.query(Client).filter(Client.id == a.client_id).first()
        _client_nom = _client.nom if _client else ""
    _upsert_interlocuteurs(db, a.interlocuteurs_client, entreprise=_client_nom)
    _upsert_navire(db, a.navire_machine, a.navire_immatriculation,
                  a.navire_port_attache, a.client_id)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.put("/{affaire_id}", response_model=AffaireOut)
def update_affaire(affaire_id: str, body: AffaireUpdate,
                   db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(a, field, val)
    if body.interlocuteurs_client is not None:
        _client_nom = ""
        if a.client_id:
            _client = db.query(Client).filter(Client.id == a.client_id).first()
            _client_nom = _client.nom if _client else ""
        _upsert_interlocuteurs(db, body.interlocuteurs_client, entreprise=_client_nom)
    if body.fournisseur is not None:
        _upsert_fournisseur(db, a.fournisseur)
    if body.navire_machine is not None:
        _upsert_navire(db, a.navire_machine, a.navire_immatriculation,
                      a.navire_port_attache, a.client_id)
    a.version = (a.version or 1) + 1
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{affaire_id}", status_code=204)
def delete_affaire(affaire_id: str, db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    db.delete(a)
    db.commit()


# ─── PDF ─────────────────────────────────────────────────────────────────────

@router.get("/{affaire_id}/pdf",
            summary="Génère et renvoie la fiche affaire en PDF",
            response_class=Response)
def generer_pdf_affaire(affaire_id: str, pdf_type: str = "complet",
                        db: Session = Depends(get_db)):
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_affaire_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")

    client = db.query(Client).filter(Client.id == a.client_id).first() if a.client_id else None

    a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    a_dict["client_nom"] = client.nom if client else ""

    if a.navire_machine:
        from ..models.navire import Navire
        nav = db.query(Navire).filter(Navire.nom == a.navire_machine).first()
        a_dict["navire_proprietaire"] = nav.proprietaire.nom if nav and nav.proprietaire else ""
    else:
        a_dict["navire_proprietaire"] = ""

    c_dict = {c.name: getattr(client, c.name) for c in client.__table__.columns} if client else None

    items = [
        {c.name: getattr(it, c.name) for c in it.__table__.columns}
        for it in db.query(AffaireItem)
                    .filter(AffaireItem.affaire_id == affaire_id)
                    .order_by(AffaireItem.ordre)
                    .all()
    ]

    from ..models.moteur import Moteur
    from ..services.numerotation import code_from_num_affaire
    moteurs = [
        {c.name: getattr(m, c.name) for c in m.__table__.columns}
        for m in db.query(Moteur)
                   .filter(Moteur.code_affaire == code_from_num_affaire(a.num_affaire))
                   .order_by(Moteur.num_serie)
                   .all()
    ] if a.num_affaire else []

    _pdf_type = pdf_type if pdf_type in ("complet", "technique") else "complet"
    html_str = build_affaire_html(a_dict, items, client=c_dict, for_pdf=True,
                                  pdf_type=_pdf_type, moteurs=moteurs)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = a.num_affaire.replace("/", "-").replace(" ", "_")
    suffix = "_TECHNIQUE" if _pdf_type == "technique" else ""
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Affaire_{safe_num}{suffix}.pdf"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/{affaire_id}/echeances/{echelon_idx}/bon-facturation",
            summary="Génère le bon de facturation PDF pour un échelon",
            response_class=Response)
def generer_bon_facturation_echelon(affaire_id: str, echelon_idx: int,
                                    lot_id: Optional[str] = None,
                                    db: Session = Depends(get_db)):
    import json as _json

    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    try:
        from shared.affaire_pdf import build_bon_facturation_html
    except ImportError as e:
        raise HTTPException(500, f"shared.affaire_pdf indisponible : {e}")

    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")

    lot = None
    if lot_id:
        try:
            lots = _json.loads(a.lots_vendus or "[]")
        except Exception:
            lots = []
        lot = next((l for l in lots if l.get("id") == lot_id), None)
        if not lot:
            raise HTTPException(404, f"Lot {lot_id} introuvable")
        echeances = lot.get("echeances") or []
    else:
        try:
            echeances = _json.loads(a.echeances_facturation or "[]")
        except Exception:
            echeances = []

    if echelon_idx < 0 or echelon_idx >= len(echeances):
        raise HTTPException(404, f"Échelon {echelon_idx} introuvable")

    echelon = echeances[echelon_idx]
    client = db.query(Client).filter(Client.id == a.client_id).first() if a.client_id else None

    a_dict = {c.name: getattr(a, c.name) for c in a.__table__.columns}
    a_dict["client_nom"] = client.nom if client else ""
    c_dict = {c.name: getattr(client, c.name) for c in client.__table__.columns} if client else None

    html_str = build_bon_facturation_html(a_dict, echelon, echelon_idx, client=c_dict, lot=lot)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num   = a.num_affaire.replace("/", "-").replace(" ", "_")
    safe_stade = (echelon.get("stade") or f"echelon_{echelon_idx+1}").replace("/", "-").replace(" ", "_")
    safe_lot   = (lot.get("libelle") or "lot").replace("/", "-").replace(" ", "_") + "_" if lot else ""
    prefix     = "DemandeAcompte" if "acompte" in (echelon.get("stade") or "").lower() else "BonFacturation"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{prefix}_{safe_num}_{safe_lot}{safe_stade}.pdf"',
            "Cache-Control": "no-store",
        },
    )


# ─── Items d'une affaire ─────────────────────────────────────────────────────

@router.get("/{affaire_id}/items", response_model=List[AffaireItemOut])
def list_items(affaire_id: str, db: Session = Depends(get_db)):
    return [_item_to_out(it) for it in
            db.query(AffaireItem)
              .filter(AffaireItem.affaire_id == affaire_id)
              .order_by(AffaireItem.ordre)
              .all()]


@router.post("/{affaire_id}/items", response_model=AffaireItemOut, status_code=201)
def add_item(affaire_id: str, body: AffaireItemCreate,
             db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    # Crée le dossier affaire si absent (affaires antérieures à la feature)
    if not a.dossier_path:
        _cn = a.client.nom if a.client else ""
        a.dossier_path = _create_dossier(a.num_affaire, _cn, a.navire_machine, a.nom_projet)
        db.commit()
    # Interdit les noms de chapitres identiques (slug insensible à la casse)
    new_slug = _slug(body.libelle or body.type_item or "chapitre").lower()
    for existing in db.query(AffaireItem).filter(AffaireItem.affaire_id == affaire_id).all():
        if _slug(existing.libelle or existing.type_item or "chapitre").lower() == new_slug:
            raise HTTPException(409, f"Un chapitre nommé « {existing.libelle or existing.type_item} » existe déjà dans cette affaire")
    item_id = str(uuid4())
    dossier = _create_item_dossier(a.dossier_path, body.libelle, body.type_item)
    it = AffaireItem(
        id=item_id,
        affaire_id=affaire_id,
        dossier_path=dossier,
        **body.model_dump(),
    )
    db.add(it)
    db.commit()
    db.refresh(it)
    return _item_to_out(it)


@router.put("/{affaire_id}/items/{item_id}", response_model=AffaireItemOut)
def update_item(affaire_id: str, item_id: str, body: AffaireItemUpdate,
                db: Session = Depends(get_db)):
    it = db.query(AffaireItem).filter(
        AffaireItem.id == item_id,
        AffaireItem.affaire_id == affaire_id,
    ).first()
    if not it:
        raise HTTPException(404, "Item introuvable")
    for field, val in body.model_dump(exclude_unset=True).items():
        if val is not None:
            setattr(it, field, val)
    it.version = (it.version or 1) + 1
    db.commit()
    db.refresh(it)
    return _item_to_out(it)


@router.delete("/{affaire_id}/items/{item_id}", status_code=204)
def delete_item(affaire_id: str, item_id: str, db: Session = Depends(get_db)):
    it = db.query(AffaireItem).filter(
        AffaireItem.id == item_id,
        AffaireItem.affaire_id == affaire_id,
    ).first()
    if not it:
        raise HTTPException(404, "Item introuvable")
    db.delete(it)
    db.commit()


# ─── Bilan (coûts prévus / réels) d'une affaire ─────────────────────────────

def _validate_poste_lie(db: Session, affaire_id: str, own_id: Optional[str],
                        target_id: Optional[str], own_stade: str) -> None:
    """Un poste P2 (réel) peut être associé à un poste P1 (prévisionnel) non
    déjà associé, pour que les deux apparaissent sur la même ligne du bilan."""
    if not target_id:
        return
    if own_stade != "P2":
        raise HTTPException(400, "Seul un poste réel (P2) peut être associé à un prévisionnel (P1).")
    target = db.query(AffaireCoutLigne).filter(
        AffaireCoutLigne.id == target_id,
        AffaireCoutLigne.affaire_id == affaire_id,
    ).first()
    if not target:
        raise HTTPException(404, "Poste prévisionnel à associer introuvable.")
    if (target.stade or "P1") != "P1":
        raise HTTPException(400, "Le poste associé doit être un prévisionnel (P1).")
    already = db.query(AffaireCoutLigne).filter(
        AffaireCoutLigne.poste_lie_id == target_id,
        AffaireCoutLigne.id != (own_id or ""),
    ).first()
    if already:
        raise HTTPException(400, "Ce poste prévisionnel est déjà associé à un autre poste réel.")


@router.get("/{affaire_id}/couts", response_model=List[AffaireCoutLigneOut])
def list_couts(affaire_id: str, db: Session = Depends(get_db)):
    return [_cout_to_out(c) for c in
            db.query(AffaireCoutLigne)
              .filter(AffaireCoutLigne.affaire_id == affaire_id)
              .order_by(AffaireCoutLigne.ordre)
              .all()]


@router.post("/{affaire_id}/couts", response_model=AffaireCoutLigneOut, status_code=201)
def add_cout(affaire_id: str, body: AffaireCoutLigneCreate, db: Session = Depends(get_db)):
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, f"Affaire {affaire_id} introuvable")
    _validate_poste_lie(db, affaire_id, None, body.poste_lie_id, body.stade)
    c = AffaireCoutLigne(id=str(uuid4()), affaire_id=affaire_id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return _cout_to_out(c)


@router.put("/{affaire_id}/couts/{cout_id}", response_model=AffaireCoutLigneOut)
def update_cout(affaire_id: str, cout_id: str, body: AffaireCoutLigneUpdate,
                db: Session = Depends(get_db)):
    c = db.query(AffaireCoutLigne).filter(
        AffaireCoutLigne.id == cout_id,
        AffaireCoutLigne.affaire_id == affaire_id,
    ).first()
    if not c:
        raise HTTPException(404, "Ligne de coût introuvable")
    fields = body.model_dump(exclude_unset=True)
    if c.bon_commande_id and (set(fields.keys()) - {"poste_lie_id"}):
        raise HTTPException(400, "Ce poste est lié à un bon de commande — modifiez-le depuis le bon de commande.")
    if "poste_lie_id" in fields:
        target_id = fields.pop("poste_lie_id")
        _validate_poste_lie(db, affaire_id, cout_id, target_id, fields.get("stade") or c.stade or "P1")
        c.poste_lie_id = target_id
    for field, val in fields.items():
        if val is not None:
            setattr(c, field, val)
    db.commit()
    db.refresh(c)
    return _cout_to_out(c)


@router.delete("/{affaire_id}/couts/{cout_id}", status_code=204)
def delete_cout(affaire_id: str, cout_id: str, db: Session = Depends(get_db)):
    c = db.query(AffaireCoutLigne).filter(
        AffaireCoutLigne.id == cout_id,
        AffaireCoutLigne.affaire_id == affaire_id,
    ).first()
    if not c:
        raise HTTPException(404, "Ligne de coût introuvable")
    if c.bon_commande_id:
        raise HTTPException(400, "Ce poste est lié à un bon de commande — modifiez-le depuis le bon de commande.")
    db.query(AffaireCoutLigne).filter(AffaireCoutLigne.poste_lie_id == cout_id).update({"poste_lie_id": None})
    db.delete(c)
    db.commit()


# ─── Fichiers d'un item (chapitre) ───────────────────────────────────────────

def _get_item_dossier(affaire_id: str, item_id: str, db: Session) -> Path:
    it = db.query(AffaireItem).filter(
        AffaireItem.id == item_id,
        AffaireItem.affaire_id == affaire_id,
    ).first()
    if not it:
        raise HTTPException(404, "Item introuvable")
    # Crée le sous-dossier à la volée si absent (chapitres antérieurs)
    if not it.dossier_path:
        a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
        if not a:
            raise HTTPException(404, "Affaire introuvable")
        if not a.dossier_path:
            _cn = a.client.nom if a.client else ""
            a.dossier_path = _create_dossier(a.num_affaire, _cn, a.navire_machine, a.nom_projet)
            db.commit()
        if not a.dossier_path:
            raise HTTPException(500, "Impossible de créer le dossier affaire (accès O:\\ ?)")
        p_str = _create_item_dossier(a.dossier_path, it.libelle, it.type_item)
        if not p_str:
            raise HTTPException(500, "Impossible de créer le dossier du chapitre (accès O:\\ ?)")
        it.dossier_path = p_str
        db.commit()
    if not it.dossier_path:
        raise HTTPException(500, "Dossier du chapitre introuvable (accès O:\\ ?)")
    p = Path(it.dossier_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("/{affaire_id}/items/{item_id}/files")
def list_item_files(affaire_id: str, item_id: str, db: Session = Depends(get_db)):
    p = _get_item_dossier(affaire_id, item_id, db)
    files = []
    for f in sorted(p.iterdir()):
        if f.is_file():
            st = f.stat()
            files.append({"name": f.name, "size": st.st_size, "modified": st.st_mtime})
    return files


@router.post("/{affaire_id}/items/{item_id}/files", status_code=201)
async def upload_item_file(
    affaire_id: str, item_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    p = _get_item_dossier(affaire_id, item_id, db)
    data = await file.read()
    dest = p / (file.filename or "upload")
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = p / f"{stem}_{int(time.time())}{suffix}"
    dest.write_bytes(data)
    return {"name": dest.name, "size": len(data)}


@router.get("/{affaire_id}/items/{item_id}/files/{filename}")
def download_item_file(affaire_id: str, item_id: str, filename: str,
                       db: Session = Depends(get_db)):
    p = _get_item_dossier(affaire_id, item_id, db)
    fp = p / filename
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(str(fp), filename=filename)


@router.delete("/{affaire_id}/items/{item_id}/files/{filename}", status_code=204)
def delete_item_file(affaire_id: str, item_id: str, filename: str,
                     db: Session = Depends(get_db)):
    p = _get_item_dossier(affaire_id, item_id, db)
    fp = p / filename
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "Fichier introuvable")
    fp.unlink()


@router.post("/{affaire_id}/items/{item_id}/files/{filename}/rename")
async def rename_item_file(
    affaire_id: str, item_id: str, filename: str,
    new_name: str = Body(..., embed=True),
    db: Session = Depends(get_db),
):
    """Renomme un fichier dans le dossier du chapitre."""
    p = _get_item_dossier(affaire_id, item_id, db)
    src = p / filename
    if not src.exists() or not src.is_file():
        raise HTTPException(404, "Fichier introuvable")
    new_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', new_name.strip())
    if not new_name:
        raise HTTPException(400, "Nouveau nom invalide")
    dst = p / new_name
    if dst.exists():
        raise HTTPException(409, f"Un fichier nommé « {new_name} » existe déjà")
    src.rename(dst)
    return {"name": new_name}


@router.get("/{affaire_id}/items/{item_id}/open-dossier")
def open_item_dossier(affaire_id: str, item_id: str, db: Session = Depends(get_db)):
    p = _get_item_dossier(affaire_id, item_id, db)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(p)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"opened": True, "path": str(p)}


# ─── Dossier & fichiers ──────────────────────────────────────────────────────

def _get_dossier(affaire_id: str, db: Session) -> Path:
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, "Affaire introuvable")
    if not a.dossier_path:
        _cn = a.client.nom if a.client else ""
        dossier = _create_dossier(a.num_affaire, _cn, a.navire_machine, a.nom_projet)
        if not dossier:
            raise HTTPException(500, "Impossible de créer le dossier affaire")
        a.dossier_path = dossier
        db.commit()
    p = Path(a.dossier_path)
    # Si le chemin stocké n'existe pas (ex: ancienne install C:\EMS\...),
    # chercher dans AFFAIRES_DIR un dossier commençant par le num_affaire
    if not p.exists():
        affaires_dir = Path(settings.AFFAIRES_DIR)
        found = None
        if affaires_dir.exists():
            for d in affaires_dir.iterdir():
                if d.is_dir() and d.name.startswith(a.num_affaire):
                    found = d
                    break
        if found:
            p = found
        else:
            # Créer un nouveau dossier avec le bon chemin
            _cn = a.client.nom if a.client else ""
            dossier = _create_dossier(a.num_affaire, _cn, a.navire_machine or "", a.nom_projet or "")
            if dossier:
                p = Path(dossier)
            else:
                p.mkdir(parents=True, exist_ok=True)
        # Mettre à jour le chemin en base
        a.dossier_path = str(p)
        db.commit()
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("/debug-affaires-dir")
def debug_affaires_dir():
    """Diagnostic : teste l'accès à AFFAIRES_DIR."""
    d = Path(settings.AFFAIRES_DIR)
    try:
        exists = d.exists()
        items = [x.name for x in d.iterdir()] if exists else []
        return {"affaires_dir": str(d), "exists": exists, "items": items[:10], "error": None}
    except Exception as e:
        return {"affaires_dir": str(d), "exists": False, "items": [], "error": str(e)}


def _compute_dossier_path(a) -> str:
    """Calcule le chemin attendu du dossier affaire sans rien créer sur le disque."""
    _cn = a.client.nom if a.client else ""
    parts = []
    if _cn:
        parts.append(_sanitize_folder(_cn))
    if a.navire_machine:
        parts.append(_sanitize_folder(a.navire_machine))
    main_part = "_".join(parts)
    if a.nom_projet:
        proj = _sanitize_folder(a.nom_projet)
        suffix = f"{main_part} - {proj}" if main_part else proj
    else:
        suffix = main_part
    folder_name = f"{a.num_affaire}   00_{suffix}" if suffix else a.num_affaire
    return str(Path(settings.AFFAIRES_DIR) / folder_name)


@router.get("/{affaire_id}/ensure-dossier")
def ensure_dossier(affaire_id: str, db: Session = Depends(get_db)):
    """Retourne le chemin du dossier affaire (création côté client via local server)."""
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, "Affaire introuvable")

    affaires_dir = str(settings.AFFAIRES_DIR)
    needs_update = (
        not a.dossier_path
        or not a.dossier_path.startswith(affaires_dir)
    )
    if needs_update:
        a.dossier_path = _compute_dossier_path(a)
        db.commit()

    return {"path": a.dossier_path}


@router.get("/{affaire_id}/open-dossier")
def open_dossier(affaire_id: str, db: Session = Depends(get_db)):
    """Ouvre le dossier de l'affaire dans l'explorateur Windows (côté serveur)."""
    p = _get_dossier(affaire_id, db)
    _create_arborescence(p)
    if sys.platform == "win32":
        subprocess.Popen(["explorer", str(p)])
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(p)])
    else:
        subprocess.Popen(["xdg-open", str(p)])
    return {"opened": True, "path": str(p)}


@router.get("/{affaire_id}/files")
def list_files(affaire_id: str, db: Session = Depends(get_db)):
    """Liste les fichiers du dossier de l'affaire."""
    p = _get_dossier(affaire_id, db)
    files = []
    for f in sorted(p.iterdir()):
        if f.is_file():
            st = f.stat()
            files.append({
                "name": f.name,
                "size": st.st_size,
                "modified": st.st_mtime,
            })
    return files


@router.post("/{affaire_id}/files", status_code=201)
async def upload_file(
    affaire_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Dépose un fichier dans le dossier de l'affaire."""
    p = _get_dossier(affaire_id, db)
    data = await file.read()
    dest = p / (file.filename or "upload")
    # Évite d'écraser un fichier existant
    if dest.exists():
        stem, suffix = dest.stem, dest.suffix
        dest = p / f"{stem}_{int(time.time())}{suffix}"
    dest.write_bytes(data)
    return {"name": dest.name, "size": len(data)}


@router.get("/{affaire_id}/files/{filename}")
def download_file(affaire_id: str, filename: str, db: Session = Depends(get_db)):
    """Télécharge un fichier du dossier."""
    p = _get_dossier(affaire_id, db)
    fp = p / filename
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "Fichier introuvable")
    return FileResponse(str(fp), filename=filename)


@router.delete("/{affaire_id}/files/{filename}", status_code=204)
def delete_file(affaire_id: str, filename: str, db: Session = Depends(get_db)):
    """Supprime un fichier du dossier."""
    p = _get_dossier(affaire_id, db)
    fp = p / filename
    if not fp.exists() or not fp.is_file():
        raise HTTPException(404, "Fichier introuvable")
    fp.unlink()


# ─── Arborescence (ACHAT / TECHNIQUE / QUALITE…) ────────────────────────────

def _safe_rel(base: Path, rel: str) -> Optional[Path]:
    """Retourne le chemin absolu si rel reste dans base, sinon None."""
    try:
        target = (base / rel).resolve()
        base_r = base.resolve()
        if target == base_r or str(target).startswith(str(base_r) + os.sep):
            return target
        return None
    except Exception:
        return None


def _build_tree(folder: Path, base: Path) -> dict:
    """Construit l'arbre dossiers/fichiers récursif pour l'arborescence affaire."""
    try:
        rel = folder.relative_to(base).as_posix()
    except ValueError:
        rel = ""
    result: dict = {"name": folder.name, "rel": rel, "files": [], "folders": []}
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
        for item in entries:
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                result["folders"].append(_build_tree(item, base))
            elif item.is_file():
                st = item.stat()
                result["files"].append({
                    "name": item.name,
                    "size": st.st_size,
                    "modified": st.st_mtime,
                    "rel": item.relative_to(base).as_posix(),
                })
    except PermissionError:
        pass
    return result


@router.get("/{affaire_id}/folder-tree")
def get_folder_tree(affaire_id: str, db: Session = Depends(get_db)):
    """Retourne l'arborescence complète du dossier affaire.
    Retourne un arbre vide si le dossier n'est pas encore accessible côté serveur
    (la création est déléguée au client via /open-folder).
    """
    a = db.query(Affaire).filter(Affaire.id == affaire_id).first()
    if not a:
        raise HTTPException(404, "Affaire introuvable")

    if not a.dossier_path:
        a.dossier_path = _compute_dossier_path(a)
        db.commit()

    p = Path(a.dossier_path)

    try:
        exists = p.exists()
    except Exception:
        exists = False

    if not exists:
        return {"name": p.name, "rel": "", "files": [], "folders": []}

    try:
        _create_arborescence(p)
    except Exception:
        pass

    return _build_tree(p, p)


@router.get("/{affaire_id}/file")
def serve_file(affaire_id: str, rel: str, db: Session = Depends(get_db)):
    """Sert un fichier de l'arborescence (inline pour PDF/images, attachment sinon)."""
    p = _get_dossier(affaire_id, db)
    target = _safe_rel(p, rel)
    if not target or not target.is_file():
        raise HTTPException(404, "Fichier introuvable")
    mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    disp = "inline" if mime == "application/pdf" or mime.startswith("image/") else "attachment"
    return FileResponse(str(target), media_type=mime,
                        headers={"Content-Disposition": f'{disp}; filename="{target.name}"'})


@router.post("/{affaire_id}/folder-upload", status_code=201)
async def upload_to_folder(
    affaire_id: str,
    file: UploadFile = File(...),
    folder: str = Form(""),
    db: Session = Depends(get_db),
):
    """Dépose un fichier dans un sous-dossier de l'arborescence affaire."""
    p = _get_dossier(affaire_id, db)
    dest_dir = _safe_rel(p, folder) if folder else p
    if not dest_dir or not dest_dir.is_dir():
        raise HTTPException(400, "Dossier invalide")
    data = await file.read()
    dest = dest_dir / (file.filename or "upload")
    if dest.exists():
        stem = Path(dest.name).stem
        suffix = Path(dest.name).suffix
        dest = dest_dir / f"{stem}_{int(time.time())}{suffix}"
    dest.write_bytes(data)
    return {"name": dest.name, "rel": dest.relative_to(p).as_posix()}


@router.delete("/{affaire_id}/folder-file", status_code=204)
def delete_folder_file(affaire_id: str, rel: str, db: Session = Depends(get_db)):
    """Supprime un fichier dans l'arborescence de l'affaire."""
    p = _get_dossier(affaire_id, db)
    target = _safe_rel(p, rel)
    if not target or not target.is_file():
        raise HTTPException(404, "Fichier introuvable")
    target.unlink()


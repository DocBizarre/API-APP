"""Endpoints REST pour les Affaires et leurs items."""
from typing import List, Optional
from uuid import uuid4
from pathlib import Path
import json as _json_mod
import subprocess, sys, os, time, re, unicodedata, mimetypes

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body, Form
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session, object_session
from sqlalchemy import or_, func as _func

from ..database import get_db
from ..models.affaire import Affaire, AffaireItem
from ..models.client import Client
from ..models.bon_commande import BonCommande, BonCommandeLigne
from ..schemas.affaire import (
    AffaireCreate, AffaireUpdate, AffaireOut,
    AffaireItemCreate, AffaireItemUpdate, AffaireItemOut,
)
from ..services.numerotation import next_num_affaire
from ..config import settings
from .interventions import _upsert_contact

router = APIRouter(prefix="/affaires", tags=["affaires"])

STATUTS = ["En cours", "En attente", "À facturer", "Clos", "Annulé"]


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
        total_achats = (
            db.query(_func.sum(BonCommandeLigne.montant_ligne))
            .join(BonCommande, BonCommandeLigne.bon_commande_id == BonCommande.id)
            .filter(BonCommande.affaire_id == a.id)
            .scalar()
        ) or 0.0
    d["total_achats"] = total_achats
    return d


def _item_to_out(it: AffaireItem) -> dict:
    d = {}
    for c in it.__table__.columns:
        val = getattr(it, c.name)
        if val is None:
            d[c.name] = 0 if str(c.type) == "INTEGER" else ""
        else:
            d[c.name] = val
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
        return ""


# ─── Affaires ────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AffaireOut])
def list_affaires(
    statut: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Affaire)
    if statut and statut not in ("Tous", "Toutes"):
        q = q.filter(Affaire.statut == statut)
    if search:
        like = f"%{search}%"
        q = q.outerjoin(Client).filter(
            or_(Affaire.num_affaire.ilike(like),
                Affaire.nom_projet.ilike(like),
                Affaire.navire_machine.ilike(like),
                Affaire.ref_interne.ilike(like),
                Affaire.charge_affaire.ilike(like),
                Client.nom.ilike(like))
        )
    q = q.order_by(Affaire.created_at.desc())
    return [_to_out(a) for a in q.all()]


@router.get("/statuts")
def get_statuts():
    return STATUTS


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
        client_id=body.client_id or None,
        nom_projet=body.nom_projet,
        navire_machine=body.navire_machine,
        ref_interne=body.ref_interne,
        num_commande_client=body.num_commande_client,
        charge_affaire=body.charge_affaire,
        resp_technique=body.resp_technique,
        date_debut=body.date_debut,
        date_fin_prevue=body.date_fin_prevue,
        date_cloture=body.date_cloture,
        statut=body.statut,
        description=body.description,
        commentaires=body.commentaires,
        dossier_path=dossier,
        prix_ht=body.prix_ht,
        exonere_tva=body.exonere_tva,
        date_achat=body.date_achat,
        fournisseur=body.fournisseur,
        etablissement_financier=body.etablissement_financier,
        echeances_facturation=body.echeances_facturation,
        whiteboard=body.whiteboard,
        transporteur=body.transporteur,
        contact_transport=body.contact_transport,
        prix_transport=body.prix_transport,
        num_suivi_transport=body.num_suivi_transport,
        instructions_transport=body.instructions_transport,
        conditions_reglement=body.conditions_reglement,
        garanties=body.garanties,
        interlocuteurs_client=body.interlocuteurs_client,
    )
    db.add(a)
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
        try:
            interlocuteurs = _json_mod.loads(body.interlocuteurs_client or "[]")
        except Exception:
            interlocuteurs = []
        for it in interlocuteurs:
            nom_complet = f"{(it.get('prenom') or '').strip()} {(it.get('nom') or '').strip()}".strip()
            _upsert_contact(db, nom_complet, it.get("email", ""), it.get("telephone", ""))
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

    c_dict = {c.name: getattr(client, c.name) for c in client.__table__.columns} if client else None

    items = [
        {c.name: getattr(it, c.name) for c in it.__table__.columns}
        for it in db.query(AffaireItem)
                    .filter(AffaireItem.affaire_id == affaire_id)
                    .order_by(AffaireItem.ordre)
                    .all()
    ]

    _pdf_type = pdf_type if pdf_type in ("complet", "technique") else "complet"
    html_str = build_affaire_html(a_dict, items, client=c_dict, for_pdf=True,
                                  pdf_type=_pdf_type)

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

    html_str = build_bon_facturation_html(a_dict, echelon, echelon_idx, client=c_dict)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num   = a.num_affaire.replace("/", "-").replace(" ", "_")
    safe_stade = (echelon.get("stade") or f"echelon_{echelon_idx+1}").replace("/", "-").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="BonFacturation_{safe_num}_{safe_stade}.pdf"',
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
            raise HTTPException(500, "Impossible de créer le dossier affaire")
        p_str = _create_item_dossier(a.dossier_path, it.libelle, it.type_item)
        it.dossier_path = p_str
        db.commit()
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


"""Endpoints REST pour les Affaires et leurs items."""
from typing import List, Optional
from uuid import uuid4
from pathlib import Path
import subprocess, sys, os, time, re, unicodedata

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Body
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import or_

from ..database import get_db
from ..models.affaire import Affaire, AffaireItem
from ..models.client import Client
from ..schemas.affaire import (
    AffaireCreate, AffaireUpdate, AffaireOut,
    AffaireItemCreate, AffaireItemUpdate, AffaireItemOut,
)
from ..services.numerotation import next_num_affaire
from ..config import settings

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


def _create_dossier(num_affaire: str) -> str:
    """Crée le dossier racine de l'affaire et retourne son chemin."""
    try:
        base = Path(settings.DOSSIERS_DIR) / "affaires" / num_affaire
        base.mkdir(parents=True, exist_ok=True)
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
    dossier = _create_dossier(num)
    a = Affaire(
        id=str(uuid4()),
        num_affaire=num,
        client_id=body.client_id or None,
        nom_projet=body.nom_projet,
        navire_machine=body.navire_machine,
        ref_interne=body.ref_interne,
        charge_affaire=body.charge_affaire,
        date_debut=body.date_debut,
        date_fin_prevue=body.date_fin_prevue,
        date_cloture=body.date_cloture,
        statut=body.statut,
        description=body.description,
        commentaires=body.commentaires,
        dossier_path=dossier,
        prix_ht=body.prix_ht,
        date_achat=body.date_achat,
        fournisseur=body.fournisseur,
        etablissement_financier=body.etablissement_financier,
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
def generer_pdf_affaire(affaire_id: str, db: Session = Depends(get_db)):
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

    html_str = build_affaire_html(a_dict, items, client=c_dict, for_pdf=True)

    try:
        pdf_bytes = HTML(string=html_str).write_pdf()
    except Exception as e:
        raise HTTPException(500, f"Échec génération PDF (WeasyPrint) : {e}")

    safe_num = a.num_affaire.replace("/", "-").replace(" ", "_")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="Affaire_{safe_num}.pdf"',
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
        a.dossier_path = _create_dossier(a.num_affaire)
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
            a.dossier_path = _create_dossier(a.num_affaire)
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
        dossier = _create_dossier(a.num_affaire)
        if not dossier:
            raise HTTPException(500, "Impossible de créer le dossier affaire")
        a.dossier_path = dossier
        db.commit()
    p = Path(a.dossier_path)
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("/{affaire_id}/open-dossier")
def open_dossier(affaire_id: str, db: Session = Depends(get_db)):
    """Ouvre le dossier de l'affaire dans l'explorateur Windows."""
    p = _get_dossier(affaire_id, db)
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


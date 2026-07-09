"""
Router PDF - Generation de bons d'intervention en PDF cote serveur.

WeasyPrint est installe sur le serveur (avec GTK3). Les clients .exe n'ont
donc pas besoin de l'installer eux-memes : ils appellent juste cet endpoint
pour recuperer le PDF deja genere.

MODIFICATIONS (perf/stabilite) :
- /pdf/render : le rendu WeasyPrint passe par run_in_threadpool pour ne
  plus bloquer l'event loop uvicorn (cause des "API indisponible").
- Plus de fichiers temporaires : write_pdf() sans argument retourne
  directement les bytes du PDF.
"""
import os
import re
import tempfile

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models.intervention import Intervention
from ..models.client import Client
from ..models.moteur import Moteur

router = APIRouter(prefix="/interventions", tags=["pdf"])
router_render = APIRouter(prefix="/pdf", tags=["pdf"])


@router_render.post("/render",
                    summary="Rendu PDF depuis HTML brut (photos incluses)",
                    response_class=Response)
async def render_pdf_from_html(request: Request):
    """
    Accepte le HTML complet en bytes bruts (Content-Type: text/html; charset=utf-8).
    Les photos sont embarquees en data-URI base64 dans le HTML.
    Retourne le PDF binaire genere par WeasyPrint.

    IMPORTANT : l'appel WeasyPrint (CPU-bound, plusieurs secondes) est
    delegue au threadpool via run_in_threadpool. Sans cela, un endpoint
    `async def` qui appelle write_pdf() directement gele l'event loop :
    plus AUCUNE requete n'est traitee pendant la generation.
    """
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installe sur le serveur : {e}")

    html_bytes = await request.body()
    if not html_bytes:
        raise HTTPException(400, "Corps de requete vide")
    try:
        html_str = html_bytes.decode("utf-8")
    except Exception as e:
        raise HTTPException(400, f"Lecture du corps impossible : {e}")

    try:
        data = await run_in_threadpool(lambda: HTML(string=html_str).write_pdf())
    except Exception as e:
        raise HTTPException(500, f"Echec generation PDF (WeasyPrint) : {e}")

    return Response(content=data, media_type="application/pdf")


async def _convert_document(file: UploadFile, doc_type: "str | None", include_cgv: bool) -> Response:
    """Logique commune aux endpoints de conversion PDF (CC / CF / DE).

    doc_type=None => auto-détection côté serveur (via convertisseurpdf.detect_doc_type).
    Le client (exe allégé, sans pdfplumber) ne peut pas détecter le type
    lui-même : c'est pour ça que l'endpoint générique /pdf/convert existe.
    """
    try:
        import convertisseurpdf as _conv
    except ImportError as e:
        raise HTTPException(500, f"convertisseurpdf indisponible : {e}")

    try:
        from weasyprint import HTML  # noqa: F401 — vérifie la dispo avant de lire le fichier
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installé sur le serveur : {e}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Fichier PDF vide")

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        if doc_type is None:
            doc_type = _conv.detect_doc_type(tmp_path)

        logo = _conv.extract_logo_datauri(tmp_path)

        if doc_type == "CF":
            data = _conv.parse_bon_fournisseur(tmp_path)
            html_str = _conv.build_html_bon_fournisseur(data, logo)
            num = _conv._clean(data["entete"].get("N° Cde EMS", ""))
            suffix = "_commande_fournisseur_EMS.pdf"
        elif doc_type == "DE":
            data = _conv.parse_devis(tmp_path)
            html_str = _conv.build_html_devis(data, logo)
            num = _conv._clean(data["entete"].get("N° Devis EMS", ""))
            suffix = "_devis_EMS.pdf"
        else:
            data = _conv.parse_commande(tmp_path)
            html_str = _conv.build_html(data, logo)
            num = _conv._clean(data["entete"].get("N° Cde EMS", ""))
            suffix = "_accuse_EMS.pdf"

        safe = re.sub(r"[^\w\-]+", "_", num).strip("_") or "document"
        out_name = safe + suffix

        issues = _conv._validate_data(data, doc_type)
        if issues:
            import logging as _log
            _log.getLogger("convertisseurpdf").warning(
                "[%s] %s : %s", doc_type, file.filename, " | ".join(issues)
            )

        pdf_bytes = await run_in_threadpool(
            lambda: _conv._render_to_bytes(data, html_str, tmp_path, include_cgv)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Echec conversion PDF : {e}")
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{out_name}"'},
    )


@router_render.post("/accuse-reception",
                    summary="Remise en page d'un accusé de réception de commande",
                    response_class=Response)
async def convert_accuse_reception(
    file: UploadFile = File(...),
    include_cgv: bool = Query(default=True),
):
    return await _convert_document(file, "CC", include_cgv)


@router_render.post("/bon-fournisseur",
                    summary="Remise en page d'un bon de commande fournisseur",
                    response_class=Response)
async def convert_bon_fournisseur(
    file: UploadFile = File(...),
    include_cgv: bool = Query(default=True),
):
    return await _convert_document(file, "CF", include_cgv)


@router_render.post("/devis",
                    summary="Remise en page d'un devis client",
                    response_class=Response)
async def convert_devis(
    file: UploadFile = File(...),
    include_cgv: bool = Query(default=True),
):
    return await _convert_document(file, "DE", include_cgv)


@router_render.post("/convert",
                    summary="Remise en page avec auto-détection du type (CC/CF/DE)",
                    response_class=Response)
async def convert_auto(
    file: UploadFile = File(...),
    include_cgv: bool = Query(default=True),
):
    """À utiliser par les clients qui n'embarquent pas pdfplumber (exe allégé) :
    le type de document (accusé / bon fournisseur / devis) est détecté ici,
    côté serveur, plutôt que par le client."""
    return await _convert_document(file, None, include_cgv)


def _to_dict(orm_obj):
    if orm_obj is None:
        return None
    return {c.name: getattr(orm_obj, c.name) for c in orm_obj.__table__.columns}


@router.get("/{inv_id}/pdf",
            summary="Genere et renvoie le PDF d'un bon d'intervention",
            response_class=Response)
def generer_pdf_bon(inv_id: str):
    """
    Genere le PDF du bon d'intervention via WeasyPrint cote serveur.
    Le client recoit le PDF binaire pret a sauvegarder.

    NOTE : on appelle directement _build_html + WeasyPrint pour eviter
    la boucle infinie qui se produirait si on utilisait generer_bon_pdf()
    (celle-ci rappelle l'API serveur pour obtenir le PDF).

    Cet endpoint est un `def` synchrone : FastAPI l'execute deja dans le
    threadpool, il ne bloque donc pas l'event loop. On a simplement
    supprime le tempfile + BackgroundTasks au profit des bytes directs.
    """
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installe sur le serveur : {e}")

    try:
        from shared.bon_generator import _build_html
    except ImportError as e:
        raise HTTPException(500, f"shared.bon_generator indisponible : {e}")

    db: Session = SessionLocal()
    try:
        inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
        if not inv:
            raise HTTPException(404, f"Intervention {inv_id} introuvable")

        client = db.query(Client).filter(Client.id == inv.client_id).first() if inv.client_id else None
        moteur = db.query(Moteur).filter(Moteur.id == inv.moteur_id).first() if inv.moteur_id else None

        inv_dict    = _to_dict(inv)
        client_dict = _to_dict(client)
        moteur_dict = _to_dict(moteur)

        html_str = _build_html(inv_dict, client=client_dict, moteur=moteur_dict,
                               photos_annexe=None, for_pdf=True)

        try:
            pdf_bytes = HTML(string=html_str).write_pdf()
        except Exception as e:
            raise HTTPException(500, f"Echec generation PDF (WeasyPrint) : {e}")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{inv.num_bon}.pdf"',
                "Cache-Control": "no-store",
            })
    finally:
        db.close()

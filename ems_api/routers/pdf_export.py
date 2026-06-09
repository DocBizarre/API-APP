"""
Router PDF - Generation de bons d'intervention en PDF cote serveur.

WeasyPrint est installe sur le serveur (avec GTK3). Les clients .exe n'ont
donc pas besoin de l'installer eux-memes : ils appellent juste cet endpoint
pour recuperer le PDF deja genere.
"""
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import FileResponse, Response
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
    """
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise HTTPException(500, f"WeasyPrint non installe sur le serveur : {e}")

    try:
        html_bytes = await request.body()
        if not html_bytes:
            raise HTTPException(400, "Corps de requete vide")
        html_str = html_bytes.decode("utf-8")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(400, f"Lecture du corps impossible : {e}")

    tmp_path = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".pdf")
        tmp_path = Path(tmp)
        os.close(fd)
        HTML(string=html_str).write_pdf(str(tmp_path))
        data = tmp_path.read_bytes()
    except Exception as e:
        raise HTTPException(500, f"Echec generation PDF (WeasyPrint) : {e}")
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    return Response(content=data, media_type="application/pdf")


def _to_dict(orm_obj):
    if orm_obj is None:
        return None
    return {c.name: getattr(orm_obj, c.name) for c in orm_obj.__table__.columns}


@router.get("/{inv_id}/pdf",
            summary="Genere et renvoie le PDF d'un bon d'intervention",
            response_class=FileResponse)
def generer_pdf_bon(inv_id: str, background: BackgroundTasks):
    """
    Genere le PDF du bon d'intervention via WeasyPrint cote serveur.
    Le client recoit le PDF binaire pret a sauvegarder.

    NOTE : on appelle directement _build_html + WeasyPrint pour eviter
    la boucle infinie qui se produirait si on utilisait generer_bon_pdf()
    (celle-ci rappelle l'API serveur pour obtenir le PDF).
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

        fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix=f"ems_{inv.num_bon}_")
        pdf_path = Path(tmp)
        os.close(fd)
        try:
            HTML(string=html_str).write_pdf(str(pdf_path))
        except Exception as e:
            pdf_path.unlink(missing_ok=True)
            raise HTTPException(500, f"Echec generation PDF (WeasyPrint) : {e}")

        if not pdf_path.is_file():
            raise HTTPException(500, "PDF non genere")

        background.add_task(pdf_path.unlink, missing_ok=True)
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"{inv.num_bon}.pdf",
            headers={"Cache-Control": "no-store"})
    finally:
        db.close()

"""
Endpoints de génération de documents :
    GET /interventions/{id}/document.html   → bon HTML
    GET /interventions/{id}/document.pdf    → bon PDF (si playwright dispo)
    GET /garanties/{id}/document.html       → fiche garantie HTML
    GET /ameliorations/{id}/document.html   → ticket amélioration HTML

Le HTML est généré par `shared/bon_generator.py`.
Le PDF est généré à la volée via Playwright (optionnel : si non installé,
l'endpoint PDF renvoie 501 Not Implemented).
"""
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Intervention, Garantie, Amelioration


router = APIRouter(tags=["documents"])


def _intervention_to_dict(inv: Intervention) -> dict:
    """Convertit en dict pour passer au générateur (qui attend du dict-like)."""
    d = {c.name: getattr(inv, c.name) for c in inv.__table__.columns}
    if inv.client:
        d.update({
            "client_nom":     inv.client.nom,
            "client_contact": inv.client.contact,
            "client_email":   inv.client.email,
            "client_tel":     inv.client.telephone,
            "client_adresse": inv.client.adresse,
        })
    if inv.moteur:
        d.update({
            "moteur_num_serie":    inv.moteur.num_serie,
            "moteur_marque":       inv.moteur.marque,
            "moteur_ref":          inv.moteur.ref_constructeur,
            "moteur_navire":       inv.moteur.navire,
            "moteur_machine":      inv.moteur.machine,
            "moteur_date_service": inv.moteur.date_mise_service,
            "moteur_garantie_mois": inv.moteur.duree_garantie,
        })
    return d


# ─── HTML ────────────────────────────────────────────────────────────────────
@router.get("/interventions/{inv_id}/document.html",
            response_class=HTMLResponse)
def bon_html(inv_id: str, db: Session = Depends(get_db)):
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    try:
        from shared.bon_generator import generer_bon_html
    except ImportError as e:
        raise HTTPException(501,
                            f"Générateur indisponible : {e}. "
                            f"Vérifiez que shared/ est accessible.")
    return generer_bon_html(_intervention_to_dict(inv))


@router.get("/interventions/{inv_id}/document.pdf")
def bon_pdf(inv_id: str, db: Session = Depends(get_db)):
    """Génère un PDF via Playwright (à installer : pip install playwright + playwright install chromium)."""
    inv = db.query(Intervention).filter(Intervention.id == inv_id).first()
    if not inv:
        raise HTTPException(404, f"Intervention {inv_id} introuvable")
    try:
        from shared.bon_generator import generer_bon_html
    except ImportError as e:
        raise HTTPException(501, f"Générateur indisponible : {e}")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise HTTPException(501,
                            "Playwright n'est pas installé sur le serveur. "
                            "Installer : pip install playwright "
                            "&& playwright install chromium")
    html = generer_bon_html(_intervention_to_dict(inv))
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False,
                                      mode="w", encoding="utf-8") as f:
        f.write(html)
        html_path = f.name
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page()
            page.goto(f"file://{html_path}")
            pdf_bytes = page.pdf(format="A4", print_background=True,
                                  prefer_css_page_size=True)
            browser.close()
    finally:
        Path(html_path).unlink(missing_ok=True)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition":
                  f'inline; filename="{inv.num_bon}.pdf"'},
    )

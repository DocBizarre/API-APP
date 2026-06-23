#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
  EMS — Génération de fiches Garantie en HTML
═══════════════════════════════════════════════════════════════════════════════

Génère une fiche HTML propre depuis un dict garantie (tel que retourné par
l'API EMS) et l'enregistre dans le dossier du dossier garantie.

API publique :
    sauvegarder_fiche(g: dict) -> Path
        Génère la fiche HTML et retourne son chemin sur disque.

    generer_html(g: dict) -> str
        Retourne juste le HTML (sans écrire de fichier).
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import html
from datetime import datetime
from pathlib import Path
from typing import Dict


# ─── Configuration ───────────────────────────────────────────────────────────
import sys as _sys

def _get_garanties_root() -> Path:
    from configparser import ConfigParser
    base = (Path(_sys.executable).parent if getattr(_sys, "frozen", False)
            else Path(__file__).resolve().parent.parent)
    for cfg in (base / "config.ini",
                Path(__file__).resolve().parent.parent / "config.ini"):
        if cfg.is_file():
            cp = ConfigParser()
            cp.read(cfg, encoding="utf-8")
            v = cp.get("files", "garanties_root", fallback="").strip()
            if v:
                p = Path(v); p.mkdir(parents=True, exist_ok=True); return p
            v = cp.get("files", "dossiers_root", fallback="").strip()
            if v:
                p = Path(v).parent / "garanties"
                p.mkdir(parents=True, exist_ok=True); return p
            break
    p = base / "garanties"
    p.mkdir(parents=True, exist_ok=True)
    return p

_DOSSIERS_BASE = _get_garanties_root()


# ─── Logo ────────────────────────────────────────────────────────────────────
def _logo_data_uri() -> str:
    logo_path = Path(__file__).parent / "assets" / "logo_ems.png"
    if logo_path.is_file():
        try:
            import base64
            b = logo_path.read_bytes()
            return f"data:image/png;base64,{base64.b64encode(b).decode()}"
        except Exception:
            pass
    try:
        from .logo_data import LOGO_EMS_B64
        return f"data:image/png;base64,{LOGO_EMS_B64}"
    except ImportError:
        try:
            from shared.logo_data import LOGO_EMS_B64
            return f"data:image/png;base64,{LOGO_EMS_B64}"
        except ImportError:
            return ""


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _esc(v) -> str:
    """Echappe un texte pour le HTML, gere les None."""
    if v is None:
        return ""
    return html.escape(str(v))


def _safe(g: Dict, key: str, default: str = "") -> str:
    """Recupere une cle d'un dict en retournant default si absente ou None."""
    v = g.get(key) if isinstance(g, dict) else None
    return v if v not in (None, "") else default


def _format_date_iso(s: str) -> str:
    """Convertit un timestamp ISO en JJ/MM/AAAA HH:MM, ou renvoie tel quel."""
    if not s:
        return ""
    if isinstance(s, datetime):
        return s.strftime("%d/%m/%Y %H:%M")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(s).replace("Z", ""), fmt)
            return dt.strftime("%d/%m/%Y %H:%M")
        except ValueError:
            continue
    return str(s)


# ─── Generation HTML ─────────────────────────────────────────────────────────
def generer_html(g: Dict) -> str:
    """Genere le contenu HTML de la fiche garantie."""
    if not isinstance(g, dict):
        raise TypeError(f"sauvegarder_fiche attend un dict, recu : {type(g)}")

    num_ems         = _safe(g, "num_ems")
    num_constr      = _safe(g, "num_constructeur")
    client_nom      = _safe(g, "client_nom")
    num_serie       = _safe(g, "num_serie") or _safe(g, "moteur_serie")
    moteur_marque   = _safe(g, "marque") or _safe(g, "moteur_marque")
    attribution     = _safe(g, "attribution")
    statut          = _safe(g, "statut")
    date_ouverture  = _safe(g, "date_ouverture")
    date_cloture    = _safe(g, "date_cloture")
    montant         = _safe(g, "montant")
    description     = _safe(g, "description")
    commentaires    = _safe(g, "commentaires")
    updated         = _format_date_iso(_safe(g, "updated_at"))
    created         = _format_date_iso(_safe(g, "created_at"))

    titre = f"Fiche Garantie - {num_ems}" if num_ems else "Fiche Garantie"

    def ligne(label, value, color=None):
        v = _esc(value) if value else "<span class='vide'>—</span>"
        style = f" style='color:{color};font-weight:600'" if color else ""
        return (f"<tr><th>{_esc(label)}</th>"
                f"<td{style}>{v}</td></tr>")

    def bloc(label, value):
        v = _esc(value).replace("\n", "<br>") if value else "<em class='vide'>(aucun)</em>"
        return (f"<div class='bloc'>"
                f"<div class='bloc-label'>{_esc(label)}</div>"
                f"<div class='bloc-content'>{v}</div></div>")

    couleurs_statut = {
        "Suivi EMS": "#5a3090",
        "Envoyée":   "#c67c00",
        "Acceptée":  "#1e7e3e",
        "Refusée":   "#c62828",
        "Clôturée":  "#555a64",
        "Cloturée":  "#555a64",
    }
    statut_color = couleurs_statut.get(statut, "#92177e")

    logo_uri = _logo_data_uri()
    if logo_uri:
        logo_html = (f'<img src="{logo_uri}" alt="EMS – Emeraude Moteurs Systemes" '
                     f'style="max-height:54px;max-width:150px;">')
    else:
        logo_html = '<span class="logo-text">EMS</span>'

    date_line = ""
    if date_ouverture:
        date_line += f"Ouverture&nbsp;: {_esc(date_ouverture)}"
    if date_cloture:
        if date_line:
            date_line += "&nbsp;&nbsp;·&nbsp;&nbsp;"
        date_line += f"Clôture&nbsp;: {_esc(date_cloture)}"

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{_esc(titre)}</title>
<style>
  @page {{ size: A4; margin: 1.2cm 1.4cm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #1a1a2e;
    background: #fff;
    font-size: 10.5pt;
    line-height: 1.45;
  }}

  /* ── Header ── */
  .doc-header {{
    background: linear-gradient(135deg, #92177e 0%, #5c0670 100%);
    color: white;
    padding: 18px 26px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-height: 78px;
  }}
  .header-logo .logo-text {{
    font-size: 24pt;
    font-weight: 900;
    letter-spacing: 4px;
    color: white;
  }}
  .header-right {{
    text-align: right;
  }}
  .header-right h1 {{
    font-size: 17pt;
    font-weight: 700;
    color: white;
    margin-bottom: 3px;
  }}
  .header-right .num-ems {{
    font-size: 11pt;
    color: rgba(255,255,255,0.82);
    letter-spacing: 0.5px;
  }}

  /* ── Corps ── */
  .doc-body {{
    padding: 20px 26px 10px;
  }}

  /* ── Bandeau statut ── */
  .status-bar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #faf5fb;
    border-left: 4px solid #92177e;
    padding: 9px 14px;
    margin-bottom: 18px;
    border-radius: 0 4px 4px 0;
  }}
  .badge {{
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    background: {statut_color};
    color: #fff;
    font-size: 9.5pt;
    font-weight: 700;
    letter-spacing: 0.2px;
  }}
  .status-dates {{
    font-size: 9pt;
    color: #7a6080;
  }}

  /* ── Sections ── */
  h2 {{
    color: #92177e;
    font-size: 9.5pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.9px;
    margin: 18px 0 7px 0;
    padding-bottom: 4px;
    border-bottom: 2px solid #f0d0ec;
  }}

  /* ── Tableaux ── */
  table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 2px;
  }}
  th, td {{
    text-align: left;
    padding: 6px 12px;
    border-bottom: 1px solid #f0e8ee;
    vertical-align: top;
  }}
  th {{
    color: #9a6090;
    font-weight: 600;
    width: 32%;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  td {{ color: #1a1a2e; font-size: 10pt; }}
  tr:last-child th, tr:last-child td {{ border-bottom: none; }}
  .vide {{ color: #b8b8c8; font-style: italic; }}

  /* ── Blocs texte ── */
  .bloc {{
    margin: 8px 0;
    padding: 11px 15px;
    background: #faf5fb;
    border-left: 3px solid #92177e;
    border-radius: 0 4px 4px 0;
  }}
  .bloc-label {{
    font-weight: 700;
    color: #92177e;
    font-size: 8.5pt;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 5px;
  }}
  .bloc-content {{
    color: #1a1a2e;
    line-height: 1.55;
    font-size: 10pt;
  }}

  /* ── Footer ── */
  .footer {{
    margin-top: 24px;
    padding-top: 9px;
    border-top: 1px solid #e8d0e8;
    color: #8a7090;
    font-size: 8.5pt;
    text-align: center;
    line-height: 1.6;
  }}
  .footer strong {{ color: #92177e; }}
</style>
</head>
<body>

<div class="doc-header">
  <div class="header-logo">
    {logo_html}
  </div>
  <div class="header-right">
    <h1>Fiche de Garantie</h1>
    <div class="num-ems">{_esc(num_ems) or "—"}</div>
  </div>
</div>

<div class="doc-body">

<div class="status-bar">
  <div>Statut&nbsp;: <span class="badge">{_esc(statut) or "—"}</span></div>
  <div class="status-dates">{date_line}</div>
</div>

<h2>Identification</h2>
<table>
  {ligne("N° EMS",            num_ems)}
  {ligne("N° constructeur",   num_constr)}
  {ligne("Client",            client_nom)}
  {ligne("Moteur — n° série", num_serie)}
  {ligne("Marque",            moteur_marque)}
  {ligne("Attribution",       attribution)}
</table>

<h2>Suivi financier</h2>
<table>
  {ligne("Statut",          statut, color=statut_color)}
  {ligne("Date ouverture",  date_ouverture)}
  {ligne("Date clôture",    date_cloture)}
  {ligne("Montant",         (montant + " €") if montant else "")}
</table>

<h2>Description</h2>
{bloc("Description de la garantie", description)}
{bloc("Commentaires / Suivi",        commentaires)}

</div>

<div class="footer">
  Fiche générée le {datetime.now().strftime("%d/%m/%Y à %H:%M")}
  &nbsp;·&nbsp; Création&nbsp;: {created or "—"}
  &nbsp;·&nbsp; Modifié&nbsp;: {updated or "—"}
  <br>
  <strong>Emeraude Moteurs Systèmes</strong>
</div>

</body>
</html>"""


# ─── Sauvegarde ──────────────────────────────────────────────────────────────
def sauvegarder_fiche(g: Dict) -> Path:
    """
    Genere et enregistre la fiche garantie en HTML.

    Le fichier est place dans :
        garanties_app/dossiers/<num_ems>/fiche_garantie.html

    Si num_ems est manquant, utilise l'id ou un timestamp.

    Retourne le chemin du fichier ecrit.
    """
    if not isinstance(g, dict):
        raise TypeError(f"sauvegarder_fiche attend un dict, recu : {type(g)}")

    # Determine un identifiant pour le sous-dossier
    nom_dossier = (_safe(g, "num_ems") or
                    _safe(g, "id") or
                    datetime.now().strftime("garantie_%Y%m%d_%H%M%S"))
    # Nettoyer le nom (pas de caracteres interdits sous Windows)
    nom_dossier = "".join(c for c in nom_dossier
                            if c.isalnum() or c in "-_")

    dossier = _DOSSIERS_BASE / nom_dossier
    dossier.mkdir(parents=True, exist_ok=True)

    fichier = dossier / "fiche_garantie.html"
    fichier.write_text(generer_html(g), encoding="utf-8")
    return fichier


# ─── Test direct ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test rapide
    exemple = {
        "num_ems": "GAR-2026-0099",
        "num_constructeur": "BD-12345",
        "client_nom": "OCEA",
        "num_serie": "2M263-0529",
        "marque": "BAUDOUIN",
        "attribution": "Constructeur",
        "statut": "Suivi EMS",
        "date_ouverture": "20/05/2026",
        "date_cloture": "",
        "montant": "1500 EUR",
        "description": "Casse turbo apres 800h\nDemande d'expertise en cours.",
        "commentaires": "Pieces commandees le 21/05/2026.",
    }
    p = sauvegarder_fiche(exemple)
    print(f"Fiche generee : {p}")

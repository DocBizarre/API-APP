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
_HERE = Path(__file__).resolve().parent
if getattr(_sys, "frozen", False):
    _DOSSIERS_BASE = Path(_sys.executable).parent / "garanties"
else:
    _DOSSIERS_BASE = _HERE / "dossiers"


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
        v = _esc(value) if value else "<span class='vide'>-</span>"
        style = f" style='color:{color}'" if color else ""
        return (f"<tr><th>{_esc(label)}</th>"
                f"<td{style}>{v}</td></tr>")

    def bloc(label, value):
        v = _esc(value) if value else "<em class='vide'>(aucun)</em>"
        return (f"<div class='bloc'>"
                f"<div class='bloc-label'>{_esc(label)}</div>"
                f"<div class='bloc-content'>{v}</div></div>")

    # Couleur du statut
    couleurs_statut = {
        "Suivi EMS": "#0056b3",
        "Envoyée":   "#1e7e3e",
        "Acceptée":  "#1e7e3e",
        "Refusée":   "#c62828",
        "Cloturée":  "#6b7785",
    }
    statut_color = couleurs_statut.get(statut, "#1a2332")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{_esc(titre)}</title>
<style>
  @page {{ size: A4; margin: 1.5cm; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    color: #1a2332;
    background: #fff;
    margin: 0;
    padding: 20px 30px;
    font-size: 11pt;
  }}
  h1 {{
    color: #002b5c;
    border-bottom: 3px solid #c62828;
    padding-bottom: 8px;
    margin: 0 0 6px 0;
    font-size: 22pt;
  }}
  h2 {{
    color: #002b5c;
    font-size: 13pt;
    margin: 24px 0 8px 0;
    border-bottom: 1px solid #d0d7de;
    padding-bottom: 4px;
  }}
  .header-info {{
    display: flex;
    justify-content: space-between;
    color: #6b7785;
    font-size: 10pt;
    margin-bottom: 18px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 4px 0;
  }}
  th, td {{
    text-align: left;
    padding: 7px 12px;
    border-bottom: 1px solid #e5e9ee;
    vertical-align: top;
  }}
  th {{
    background: #f5f7fa;
    color: #6b7785;
    font-weight: 600;
    width: 30%;
    font-size: 10pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
  }}
  td {{ color: #1a2332; }}
  .vide {{ color: #b0b7be; font-style: italic; }}
  .badge {{
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    background: {statut_color};
    color: #fff;
    font-size: 9pt;
    font-weight: 600;
  }}
  .bloc {{
    margin: 10px 0;
    padding: 12px 14px;
    background: #f5f7fa;
    border-left: 3px solid #0056b3;
    border-radius: 3px;
  }}
  .bloc-label {{
    font-weight: 600;
    color: #6b7785;
    font-size: 9pt;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    margin-bottom: 6px;
  }}
  .bloc-content {{
    white-space: pre-wrap;
    color: #1a2332;
    line-height: 1.5;
  }}
  .footer {{
    margin-top: 30px;
    padding-top: 10px;
    border-top: 1px solid #d0d7de;
    color: #6b7785;
    font-size: 9pt;
    text-align: center;
  }}
</style>
</head>
<body>

<h1>Fiche de Garantie</h1>
<div class="header-info">
  <div><strong>N° EMS :</strong> {_esc(num_ems) or "-"}</div>
  <div>Statut : <span class="badge">{_esc(statut) or "-"}</span></div>
</div>

<h2>Identification</h2>
<table>
  {ligne("N° EMS",            num_ems)}
  {ligne("N° constructeur",   num_constr)}
  {ligne("Client",            client_nom)}
  {ligne("Moteur (n° série)", num_serie)}
  {ligne("Marque moteur",     moteur_marque)}
  {ligne("Attribution",       attribution)}
</table>

<h2>Suivi</h2>
<table>
  {ligne("Statut",         statut, color=statut_color)}
  {ligne("Date ouverture", date_ouverture)}
  {ligne("Date clôture",   date_cloture)}
  {ligne("Montant",        montant)}
</table>

<h2>Description</h2>
{bloc("Description de la garantie", description)}
{bloc("Commentaires",                commentaires)}

<div class="footer">
  Fiche générée le {datetime.now().strftime("%d/%m/%Y à %H:%M")}
  &nbsp;·&nbsp; Création : {created or "-"}
  &nbsp;·&nbsp; Dernière modification : {updated or "-"}
  <br><br>
  Emeraude Moteurs Systèmes
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

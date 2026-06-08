"""
EMS - Generation des bons d'intervention HTML + PDF (v3)
Layout fidele au modele papier officiel EMS.

Deux fonctions de sortie :
  - generer_bon_html()  : HTML pour consultation rapide en navigateur
  - generer_bon_pdf()   : PDF via WeasyPrint avec header repete + pagination
                          (necessite WeasyPrint installe cote API serveur)
"""

import base64
import json
import logging
import os
import platform
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def _get_dossiers_root() -> Path:
    """Recupere le chemin du dossier racine exactement comme main.py."""
    import sys
    from configparser import ConfigParser

    if getattr(sys, "frozen", False):
        base_default = Path(sys.executable).parent
    else:
        base_default = Path(__file__).resolve().parent

    candidats_cfg = [
        base_default / "config.ini",
        Path(__file__).resolve().parent.parent / "config.ini",
    ]

    for cfg_path in candidats_cfg:
        if cfg_path.is_file():
            try:
                cp = ConfigParser()
                cp.read(cfg_path, encoding="utf-8")
                custom = cp.get("files", "dossiers_root", fallback="").strip()
                if custom:
                    p = Path(custom)
                    p.mkdir(parents=True, exist_ok=True)
                    return p
            except Exception:
                pass
            break

    p = base_default / "dossiers"
    p.mkdir(parents=True, exist_ok=True)
    return p


DOSSIERS_PATH = _get_dossiers_root()
LOGO_PATH = Path(__file__).parent / "assets" / "logo_ems.png"

# Logo embarque (fallback si assets/logo_ems.png absent)
try:
    from .logo_data import LOGO_EMS_B64
except ImportError:
    LOGO_EMS_B64 = ""

# Les 4 types officiels qui apparaissent comme cases a cocher dans l'en-tete
TYPES_HEADER = ["Entretien", "Depannage", "Diagnostic", "Garantie"]


def _g(obj, key, default=""):
    """Acces tolerant a un sqlite3.Row, dict ou None."""
    if obj is None:
        return default
    try:
        v = obj[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def _esc(s):
    """Echappement HTML minimaliste pour valeurs utilisateur."""
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _logo_data_uri():
    """Retourne le logo en data:URI."""
    if LOGO_PATH.is_file():
        try:
            b = LOGO_PATH.read_bytes()
            return "data:image/png;base64," + base64.b64encode(b).decode("ascii")
        except OSError:
            pass
    if LOGO_EMS_B64:
        return "data:image/png;base64," + LOGO_EMS_B64
    return ""


def _check(cond):
    """Case a cocher : coche ou vide."""
    try:
        return "&#9746;" if int(cond) else "&#9744;"
    except (ValueError, TypeError):
        return "&#9746;" if bool(cond) else "&#9744;"


def _bloc_signature_client(inv):
    b64 = _g(inv, "signature_b64")
    nom = _g(inv, "signature_nom")
    dte = _g(inv, "signature_date")
    if nom == "Client absent":
        return ('<div class="lab" style="color:#856404;font-weight:bold;'
                'background:#fff3cd;padding:6px 10px;border-radius:3px;">'
                '⚠ CLIENT ABSENT</div>')
    if b64:
        return (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="max-width:100%;max-height:70px;display:block;'
            f'margin:2px 0;" alt="signature">'
            f'<div class="lab" style="margin-top:6px;">'
            f'Signe par <strong>{_esc(nom)}</strong> le {_esc(dte)}<br>'
            f'Bon pour accord des travaux realises</div>')
    return '<div class="lab">Bon pour accord des travaux realises</div>'


def _bloc_signature_tech(inv, technicien_nom_par_defaut=""):
    b64 = _g(inv, "signature_tech_b64")
    nom = _g(inv, "signature_tech_nom") or technicien_nom_par_defaut
    dte = _g(inv, "signature_tech_date")
    if b64:
        return (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="max-width:100%;max-height:70px;display:block;'
            f'margin:2px 0;" alt="signature technicien">'
            f'<div class="lab" style="margin-top:6px;">'
            f'<strong>{_esc(nom)}</strong> - le {_esc(dte)}<br>'
            f'Atteste la realisation des travaux</div>')
    return f'<div class="lab">{_esc(nom)}</div>'


def _bloc_annexe_photos(photos_paths):
    """Genere les pages annexes avec les photos selectionnees."""
    if not photos_paths:
        return ""
    import mimetypes
    cartes = []
    for p in photos_paths:
        p = Path(p)
        if not p.is_file():
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        mime, _ = mimetypes.guess_type(str(p))
        if not mime or not mime.startswith("image"):
            mapping = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                       ".png": "image/png", ".gif": "image/gif",
                       ".bmp": "image/bmp", ".webp": "image/webp"}
            mime = mapping.get(p.suffix.lower())
            if not mime:
                continue
        b64 = base64.b64encode(data).decode("ascii")
        cartes.append(
            f'<div class="photo-card">'
            f'<img src="data:{mime};base64,{b64}" alt="{_esc(p.name)}">'
            f'<div class="photo-legend">{_esc(p.name)}</div>'
            f'</div>')
    if not cartes:
        return ""
    return ('<div class="annexe-photos">'
            '<div class="annexe-title">ANNEXE - PHOTOS</div>'
            '<div class="photo-grid">' + "\n".join(cartes) + '</div></div>')


def _build_html(inv, client=None, moteur=None, photos_annexe=None,
                for_pdf=False):
    """
    Construit le HTML complet. Si for_pdf=True, ajoute les regles CSS
    avancees compatibles WeasyPrint (header repete, pagination).
    """
    # Identification
    num_bon = _g(inv, "num_bon")
    num_cmd = _g(inv, "num_commande_client")
    date_i = _g(inv, "date_creation")
    technicien = _g(inv, "technicien")
    statut = _g(inv, "statut", "En cours")
    urgence = _g(inv, "urgence", "Normale")
    type_inv = _g(inv, "type_intervention")

    cls_factur = _g(inv, "facturable", 0)
    cls_interne = _g(inv, "interne", 0)

    # Client / signataire
    c_nom = _g(client, "nom") or _g(inv, "client_nom")
    c_contact = _g(client, "contact") or _g(inv, "client_contact")
    c_email = _g(client, "email") or _g(inv, "client_email")
    c_tel = _g(client, "telephone") or _g(inv, "client_tel")
    c_adresse = _g(client, "adresse") or _g(inv, "client_adresse")

    lieu = _g(inv, "lieu_intervention")
    nom_signataire = _g(inv, "nom_signataire") or c_contact
    email_signataire = _g(inv, "email_signataire") or c_email
    tel_signataire = _g(inv, "telephone_signataire") or c_tel
    nom_demandeur = _g(inv, "nom_demandeur")
    email_demandeur = _g(inv, "email_demandeur")
    tel_demandeur = _g(inv, "telephone_demandeur")

    # Equipement (moteur principal)
    navire = _g(moteur, "navire") or _g(inv, "navire")
    machine = _g(moteur, "machine") or _g(inv, "machine")
    type_mot = _g(moteur, "type_moteur") or _g(inv, "type_moteur")
    num_serie = _g(moteur, "num_serie") or _g(inv, "num_serie")
    date_svc = _g(moteur, "date_mise_service") or _g(inv, "date_mise_service")
    nb_heures = _g(inv, "nb_heures_fct")
    marque = _g(moteur, "marque") or _g(inv, "marque")
    ref_const = _g(moteur, "ref_constructeur") or _g(inv, "ref_constructeur")
    tech_ref = ref_const or type_mot or machine
    type_complet = f"{marque} {tech_ref}".strip() if marque else tech_ref

    # Moteurs supplémentaires : parsing JSON avant utilisation
    try:
        extra_moteurs = json.loads(_g(inv, "moteurs_supplementaires_json", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        extra_moteurs = []

    # Moteurs supplémentaires → bloc HTML inséré après le tableau principal
    _extra_moteurs_html = ""
    for _i, _em in enumerate(extra_moteurs, 2):
        _ns   = _g(_em, "num_serie")
        _nav  = _g(_em, "navire")
        _mac  = _g(_em, "machine")
        _mar  = _g(_em, "marque")
        _ref  = _g(_em, "ref_constructeur") or _g(_em, "type_moteur")
        _type = f"{_mar} {_ref}".strip() if _mar else _ref
        _svc  = _g(_em, "date_mise_service")
        if not _ns:
            continue
        _extra_moteurs_html += f"""
<table class="bloc-info" style="margin-top:3px;">
  <tr>
    <td colspan="4" style="background:#eef2f7;font-weight:700;font-size:9.5px;
        color:#002b5c;padding:3px 8px;letter-spacing:.3px;">
      MOTEUR {_i}
    </td>
  </tr>
  <tr>
    <td class="lbl">N&deg; de serie</td>
    <td><strong>{_esc(_ns)}</strong></td>
    <td class="lbl">Navire / Site</td>
    <td>{_esc(_nav)}</td>
  </tr>
  <tr>
    <td class="lbl">Marque / Modele</td>
    <td>{_esc(_type)}</td>
    <td class="lbl">Mise en service</td>
    <td>{_esc(_svc)}</td>
  </tr>
  <tr>
    <td class="lbl">Type machine</td>
    <td colspan="3">{_esc(_mac)}</td>
  </tr>
</table>"""

    # Options
    opt_diag = _g(inv, "outil_diagnostic", 0)
    mem_avant = _g(inv, "memoriser_avant", 0)
    mem_apres = _g(inv, "memoriser_apres", 0)
    ph_avant = _g(inv, "photos_avant", 0)
    ph_apres = _g(inv, "photos_apres", 0)
    pour_info = _g(inv, "pour_information", 0)
    preco = _g(inv, "preconisation", 0)

    # Zones de texte
    demande_client = _g(inv, "demande_client") or _g(inv, "description")
    constat = _g(inv, "constat")
    travaux = _g(inv, "travaux")
    informations = _g(inv, "informations")
    preco_text = _g(inv, "preconisation_text")

    # Tableaux JSON
    try:
        materiels = json.loads(_g(inv, "materiels_json", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        materiels = []
    try:
        depl = json.loads(_g(inv, "deplacements_json", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        depl = {}

    legacy_pieces = _g(inv, "pieces")
    if legacy_pieces and not materiels:
        materiels = [{"qte": "", "ref": "", "designation": legacy_pieces}]

    n_min_mat = 5
    mat_rows = []
    for m in materiels:
        mat_rows.append((
            _esc(m.get("qte", "")),
            _esc(m.get("ref", "")),
            _esc(m.get("designation", ""))
        ))
    while len(mat_rows) < n_min_mat:
        mat_rows.append(("", "", ""))

    mat_html = "\n".join(
        f"      <tr><td class='ref'>{r}</td><td>{d}</td><td class='qte'>{q}</td></tr>"
        for q, r, d in mat_rows
    )

    def d(k):
        return _esc(depl.get(k, ""))

    statut_cls = {"En cours": "ec", "A facturer": "afact",
                  "Facture": "fact", "Clos": "clos"}.get(statut, "ec")
    urg_cls = {"Critique": "crit", "Urgente": "urg",
               "Normale": "norm"}.get(urgence, "norm")

    type_cases = ""
    for t in TYPES_HEADER:
        coche = "&#9746;" if t.lower() == (type_inv or "").lower() else "&#9744;"
        type_cases += f'<div class="type-row"><span class="cb">{coche}</span> {t}</div>\n'

    type_other = ""
    if type_inv and type_inv not in TYPES_HEADER:
        type_other = f'<div class="type-row"><span class="cb">&#9746;</span> {_esc(type_inv)}</div>'

    logo_uri = _logo_data_uri()
    logo_html = f'<img src="{logo_uri}" alt="EMS">' if logo_uri else '<div class="logo-fallback">EMS</div>'

    # ===== CSS de base + bloc PDF (header repete + pagination) =====
    # Pour le PDF (WeasyPrint) : on injecte le num_bon/cmd directement dans
    # le CSS content (evite les problemes de string-set sur elements absolus).
    css_pdf_extra = ""
    body_padding  = "60px 20px 16px 20px"   # HTML web (avec bouton imprimer)
    base_page_css = "@page { size: A4; margin: 10mm 10mm 10mm 10mm; }"

    if for_pdf:
        body_padding  = "6mm 6mm 10mm 6mm"  # WeasyPrint : @page gere les marges
        base_page_css = ""                   # remplace par la regle ci-dessous
        # Contenu pied de page : texte brut, pas de string-set
        _safe = lambda s: str(s).replace('"', "'").replace("\\", "")
        _footer_left = _safe(num_bon)
        if num_cmd:
            _footer_left += f"  –  N° cmd : {_safe(num_cmd)}"
        css_pdf_extra = f"""
/* === WeasyPrint : regle @page unique avec pieds de page === */
@page {{
  size: A4;
  margin: 10mm 5mm 18mm 5mm;
  @bottom-left {{
    content: "{_footer_left}";
    font-size: 8pt;
    color: #6b7785;
  }}
  @bottom-right {{
    content: "Page " counter(page) " / " counter(pages);
    font-size: 8pt;
    color: #6b7785;
    font-weight: 600;
  }}
}}
"""

    # ===== HTML =====
    # Le n de commande dans le header de page 1 :
    num_cmd_header_html = (
        f'<div class="num-cmd-box">N&deg; commande client : '
        f'<strong>{_esc(num_cmd)}</strong></div>'
        if num_cmd else ""
    )

    page_header_html = ""   # plus besoin des spans string-set

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Bon d'intervention {num_bon}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
       font-size: 10.5px; color: #1a2332; background: #fff;
       padding: {body_padding};
       -webkit-font-smoothing: antialiased; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #b8c0c9; padding: 4px 6px; vertical-align: top; }}

/* En-tete page 1 (3 colonnes) */
.header-wrap {{ width: 100%; margin-bottom: 14px; padding-bottom: 4px; }}
.header {{ display: grid;
           grid-template-columns: 1fr 1.6fr 1fr;
           gap: 16px;
           align-items: center;
           width: 100%; }}
.header-left {{ display: flex; flex-direction: column; align-items: center;
                justify-content: center; padding: 4px; }}
.header-left img {{ max-width: 200px; max-height: 110px; }}
.header-left .logo-fallback {{ font-size: 28px; font-weight: bold; color: #002b5c;
                                letter-spacing: 3px; }}
.header-mid {{ text-align: center; padding: 4px; }}
.header-mid h1 {{ font-size: 18px; font-weight: 700; color: #002b5c;
                   margin: 0 0 6px 0; letter-spacing: 0.5px; }}
.header-mid .info {{ font-size: 9.5px; line-height: 1.5; color: #4a5560; }}
.header-right {{ padding: 4px 0 4px 8px; }}
.header-right .titre {{ font-weight: bold; font-size: 11px; margin-bottom: 4px;
                         color: #002b5c; }}
.type-row {{ font-size: 10.5px; padding: 1px 0; color: #1a2332;
             white-space: nowrap; }}
.type-row .cb {{ font-family: "Segoe UI Symbol", Arial, sans-serif;
                 font-size: 13px; margin-right: 4px; }}

/* Referenece du bon */
.ref-box {{ display: inline-block;
            background: #002b5c; color: #fff; padding: 5px 12px;
            font-size: 11px; font-weight: bold; border-radius: 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.15);
            margin-bottom: 6px; }}

/* N de commande dans le header */
.num-cmd-box {{ display: inline-block; margin-left: 8px;
                background: #fffbe6; color: #6b4400; padding: 5px 10px;
                font-size: 10px; border: 1px solid #f5cf6d;
                border-radius: 4px; margin-bottom: 6px; }}
.num-cmd-box strong {{ color: #6b4400; }}

.classif {{ font-size: 9.5px; margin-top: 6px; }}
.classif .cb {{ font-family: "Segoe UI Symbol", Arial, sans-serif; font-size: 12px; }}
.classif .pill {{ display: inline-block; padding: 2px 8px; margin-right: 4px;
                   background: #f0f0f0; color: #6b7785; border-radius: 10px;
                   font-weight: 600; font-size: 9px; }}
.classif .pill.on {{ background: #002b5c; color: #fff; }}

/* Bandeaux de section dans le bloc info */
.section-header {{ display: block; padding: 4px 10px; font-size: 10px;
                   font-weight: 700; color: #fff; margin: 10px 0 0 0;
                   border-radius: 4px 4px 0 0; letter-spacing: 0.5px; }}
.section-header-blue   {{ background: #002b5c; }}
.section-header-orange {{ background: #002b5c; }}
.section-header-green  {{ background: #002b5c; }}
.lbl-section {{ background: #eef2f7; font-style: italic; font-size: 9.5px;
                color: #4a5560; font-weight: 600;
                padding: 3px 8px !important; }}


/* Bloc info client/equipement */
.bloc-info {{ width: 100%; margin-top: 4px; border-radius: 4px; overflow: hidden; }}
.bloc-info td {{ font-size: 10px; height: 20px; }}
.bloc-info .lbl {{ background: #f5f7fa; font-weight: 600; width: 28%;
                    color: #002b5c; }}

/* Sections texte */
.section-title {{ font-weight: 700; font-size: 11px; color: #002b5c;
                  margin: 14px 0 4px; padding-bottom: 3px;
                  border-bottom: 2px solid #c62828;
                  display: inline-block; padding-right: 12px;
                  letter-spacing: 0.3px; }}
.zone-texte {{ border: 1px solid #b8c0c9; min-height: 50px; padding: 6px 8px;
               white-space: pre-wrap; font-size: 10px; line-height: 1.5;
               border-radius: 3px; background: #fafbfc;
               page-break-inside: avoid; break-inside: avoid; }}
.zone-grande {{ min-height: 70px; }}
.section-bloc {{ page-break-inside: avoid; break-inside: avoid; }}

/* Options */
.options {{ margin: 6px 0; font-size: 10.5px; }}
.options .opt {{ display: inline-block; margin-right: 18px; }}
.options .cb {{ font-family: "Segoe UI Symbol", Arial, sans-serif;
                font-size: 13px; margin-right: 4px; }}
.options strong {{ font-size: 10.5px; color: #002b5c; }}

/* === MODIFS PHASE A : MATERIEL / PRECO / INFO PLEINE LARGEUR === */
.materiels {{ width: 100%; margin-top: 4px; border-radius: 3px; overflow: hidden; }}
.materiels th {{ background: #002b5c; color: #fff !important; font-size: 10px;
                 font-weight: 600; text-align: left; padding: 6px 8px;
                 letter-spacing: 0.3px; }}
.materiels td {{ height: 24px; font-size: 10px; }}
.materiels th.ref {{ width: 35%; }}
.materiels th.des {{ width: 55%; }}
.materiels th.qte {{ width: 10%; text-align: center; }}
.materiels td.ref {{ color: #4a5560; font-family: 'Consolas', monospace; }}
.materiels td.qte {{ text-align: center; font-weight: 600; }}

/* Pour info et Preconisation : pleine largeur, l'une sous l'autre */
.info-fullrow {{ width: 100%; border: 1px solid #b8c0c9; padding: 8px 10px;
                 margin-top: 8px; font-size: 10px; line-height: 1.4;
                 border-radius: 3px; background: #fafbfc;
                 page-break-inside: avoid; break-inside: avoid; }}
.info-fullrow .head {{ font-size: 10.5px; margin-bottom: 4px;
                       font-weight: 700; color: #002b5c; }}
.info-fullrow .head .cb {{ font-family: "Segoe UI Symbol", Arial, sans-serif;
                           font-size: 13px; margin-right: 4px; }}
.info-fullrow .body {{ white-space: pre-wrap; color: #1a2332;
                       min-height: 40px; }}

/* Tableau deplacements */
.depl {{ width: 100%; margin-top: 4px; border-radius: 3px; overflow: hidden; }}
.depl th {{ background: #002b5c; color: #fff; font-size: 10px;
            padding: 6px 8px; text-align: left; font-weight: 600;
            letter-spacing: 0.3px; }}
.depl td {{ height: 20px; font-size: 10px; }}
.depl .lbl {{ background: #f5f7fa; font-weight: 600; width: 25%;
               color: #002b5c; }}
.depl .val {{ width: 25%; }}

/* Signatures */
.sign-footer-wrap {{
  page-break-inside: avoid; break-inside: avoid;
  margin-top: 18px;
}}
.signatures {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
               page-break-inside: avoid; break-inside: avoid; }}
.sign-box {{ border: 1px solid #b8c0c9; padding: 10px; min-height: 80px;
             font-size: 10px; border-radius: 3px; background: #fafbfc;
             page-break-inside: avoid; break-inside: avoid; }}
.sign-box .head {{ font-weight: 700; margin-bottom: 4px; color: #002b5c; }}
.sign-box .lab  {{ font-size: 9px; color: #6b7785; margin-top: 36px;
                   padding-top: 4px; }}

/* Pied de page */
.footer {{ border-top: 2px solid #002b5c; margin-top: 16px; padding-top: 8px;
           font-size: 8.5px; color: #6b7785; text-align: center; line-height: 1.7;
           page-break-inside: avoid; break-inside: avoid; }}
.footer strong {{ color: #002b5c; }}

/* Insecabilite */
table, .depl, .signatures, .classif {{ page-break-inside: auto; break-inside: auto; }}
tr, .sign-box {{ page-break-inside: avoid; break-inside: avoid; }}
.section-title {{ page-break-after: avoid; break-after: avoid; }}

/* ANNEXE PHOTOS */
.annexe-photos {{ page-break-before: always; break-before: page; margin-top: 10px; }}
.annexe-title {{ font-weight: 700; font-size: 13px; color: #002b5c;
                 margin: 0 0 10px; padding-bottom: 4px;
                 border-bottom: 2px solid #c62828; display: inline-block;
                 padding-right: 14px; letter-spacing: 0.3px; }}
.photo-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
.photo-card {{ border: 1px solid #b8c0c9; border-radius: 4px; padding: 6px;
               background: #fafbfc; page-break-inside: avoid;
               break-inside: avoid; text-align: center; }}
.photo-card img {{ max-width: 100%; max-height: 360px; object-fit: contain;
                   border-radius: 2px; }}
.photo-legend {{ font-size: 9px; color: #6b7785; margin-top: 4px;
                 word-break: break-all; }}

/* Bouton imprimer (HTML web uniquement) */
.print-btn {{ position: fixed; top: 14px; right: 14px;
              background: #002b5c; color: #fff; border: 2px solid #fff;
              padding: 10px 18px; border-radius: 6px;
              font-size: 12px; font-weight: 700; cursor: pointer;
              font-family: 'Segoe UI', Arial, sans-serif;
              box-shadow: 0 3px 10px rgba(0,0,0,0.35),
                          0 0 0 1px rgba(0,0,0,0.1);
              z-index: 9999; }}
.print-btn:hover {{ background: #003d7a; }}

/* Regle @page : remplacee par css_pdf_extra pour le PDF */
{base_page_css}
@media print {{
  .print-btn {{ display: none !important; }}
  html, body {{ background: #fff !important; }}
  body {{ margin: 0 !important;
          padding: 6mm 6mm 8mm 6mm !important;
          font-size: 9.5pt; }}
  .header-wrap, .bloc-info, .classif, .options,
  .info-fullrow, .sign-box,
  .footer, table.depl, .ref-box, .section-bloc,
  .zone-texte {{
      page-break-inside: avoid !important;
      break-inside: avoid !important;
  }}
  tr {{ page-break-inside: avoid !important; break-inside: avoid !important; }}
  .section-title {{ page-break-after: avoid !important;
                     break-after: avoid !important; }}
  .section-title + * {{ page-break-before: avoid !important;
                         break-before: avoid !important; }}
  table {{ orphans: 4; widows: 4; }}
  thead {{ display: table-header-group; }}
  tfoot {{ display: table-footer-group; }}
  .sign-footer-wrap {{
    page-break-inside: avoid !important;
    break-inside: avoid !important;
  }}
}}

{css_pdf_extra}
</style>
</head>
<body>
{"" if for_pdf else '<button class="print-btn" onclick="window.print()">Imprimer / PDF</button>'}

{page_header_html}

<div class="ref-box">{_esc(num_bon)}</div>
{num_cmd_header_html}

<!-- EN-TETE PAGE 1 -->
<div class="header-wrap">
<div class="header">
  <div class="header-left">
    {logo_html}
  </div>
  <div class="header-mid">
    <h1>BON D'INTERVENTION</h1>
    <div class="info">
      Tel : 02.99.19.01.99<br>
      Courriel : service.technique@emeraudemoteurs.com<br>
      Siret 431 976 729 00027 &nbsp;|&nbsp; TVA intra FR 14 431 976 729
    </div>
  </div>
  <div class="header-right">
    <div class="titre">Type d'intervention :</div>
    {type_cases}
    {type_other}
  </div>
</div>
</div>

<!-- BLOC CLIENT / EQUIPEMENT -->
<!-- ═══ SECTION 1 : CLIENT & LIEU ═══ -->
<div class="section-header section-header-blue">CLIENT &amp; LIEU D'INTERVENTION</div>
<table class="bloc-info">
  <tr>
    <td class="lbl">Societe</td>
    <td>{_esc(c_nom)}<br><small>{_esc(c_adresse)}</small></td>
    <td class="lbl">Lieu de l'intervention</td>
    <td>{_esc(lieu)}</td>
  </tr>
  <tr>
    <td class="lbl">Date intervention</td>
    <td>{_esc(date_i)}</td>
    <td class="lbl">Technicien EMS</td>
    <td><strong>{_esc(technicien)}</strong></td>
  </tr>
</table>

<!-- ═══ SECTION 2 : CONTACTS ═══ -->
<div class="section-header section-header-orange">CONTACTS</div>
<table class="bloc-info">
  <tr>
    <td class="lbl-section" colspan="4">Demandeur (personne ayant appele)</td>
  </tr>
  <tr>
    <td class="lbl">Nom</td>
    <td>{_esc(nom_demandeur)}</td>
    <td class="lbl">Telephone</td>
    <td>{_esc(tel_demandeur)}</td>
  </tr>
  <tr>
    <td class="lbl">Email</td>
    <td colspan="3">{_esc(email_demandeur)}</td>
  </tr>
  <tr>
    <td class="lbl-section" colspan="4">Signataire (personne signant le bon)</td>
  </tr>
  <tr>
    <td class="lbl">Nom</td>
    <td>{_esc(nom_signataire)}</td>
    <td class="lbl">Telephone</td>
    <td>{_esc(tel_signataire)}</td>
  </tr>
  <tr>
    <td class="lbl">Email</td>
    <td colspan="3">{_esc(email_signataire)}</td>
  </tr>
</table>

<!-- ═══ SECTION 3 : EQUIPEMENT ═══ -->
<div class="section-header section-header-green">EQUIPEMENT</div>
<table class="bloc-info">
  <tr>
    <td class="lbl">Navire / Site</td>
    <td>{_esc(navire)}</td>
    <td class="lbl">Type machine</td>
    <td>{_esc(machine)}</td>
  </tr>
  <tr>
    <td class="lbl">Marque / Modele moteur</td>
    <td>{_esc(type_complet)}</td>
    <td class="lbl">N&deg; de serie</td>
    <td><strong>{_esc(num_serie)}</strong></td>
  </tr>
  <tr>
    <td class="lbl">Nb heures de fonctionnement</td>
    <td>{_esc(nb_heures)}</td>
    <td class="lbl">Date mise en service</td>
    <td>{_esc(date_svc)}</td>
  </tr>
</table>
{_extra_moteurs_html}
<!-- Classifications -->
<div class="classif">
  <span class="pill {'on' if cls_factur else ''}">{_check(cls_factur)} Facturable</span>
  <span class="pill {'on' if cls_interne else ''}">{_check(cls_interne)} Interne</span>
</div>

<!-- DEMANDE DU CLIENT -->
<div class="section-bloc">
<div class="section-title">DEMANDE DU CLIENT :</div>
<div class="zone-texte">{_esc(demande_client)}</div>
</div>

<!-- OPTIONS -->
<div class="options">
  <span class="opt"><span class="cb">{_check(opt_diag)}</span> Utilisation de l'Outil de diagnostic</span>
  <span class="opt"><strong>Memoriser les donnees :</strong>
    <span class="cb">{_check(mem_avant)}</span> avant
    <span class="cb">{_check(mem_apres)}</span> apres</span>
  <span class="opt"><strong>PHOTOS :</strong>
    <span class="cb">{_check(ph_avant)}</span> avant
    <span class="cb">{_check(ph_apres)}</span> apres</span>
</div>

<!-- CONSTAT -->
<div class="section-bloc">
<div class="section-title">CONSTAT AVANT INTERVENTION :</div>
<div class="zone-texte zone-grande">{_esc(constat)}</div>
</div>

<!-- TRAVAUX -->
<div class="section-bloc">
<div class="section-title">TRAVAUX :</div>
<div class="zone-texte zone-grande">{_esc(travaux)}</div>
</div>

<!-- === PHASE A : MATERIELS PLEINE LARGEUR === -->
<div class="section-bloc">
<div class="section-title">MATERIELS UTILISES</div>
<table class="materiels">
  <thead>
    <tr>
      <th class="ref">REFERENCE</th>
      <th class="des">DESIGNATION</th>
      <th class="qte">QTE</th>
    </tr>
  </thead>
  <tbody>
{mat_html}
  </tbody>
</table>
</div>

<!-- === PHASE A : POUR INFO PLEINE LARGEUR === -->
<div class="section-bloc">
<div class="info-fullrow">
  <div class="head"><span class="cb">{_check(pour_info)}</span> Pour information</div>
  <div class="body">{_esc(informations)}</div>
</div>
</div>

<!-- === PHASE A : PRECONISATION PLEINE LARGEUR === -->
<div class="section-bloc">
<div class="info-fullrow">
  <div class="head"><span class="cb">{_check(preco)}</span> Preconisation</div>
  <div class="body">{_esc(preco_text)}</div>
</div>
</div>

<!-- DEPLACEMENTS / TEMPS / FRAIS -->
<div class="section-bloc">
<div class="section-title">TEMPS &amp; FRAIS</div>
<table class="depl">
  <tr>
    <td class="lbl">Trajet aller-retour</td>
    <td class="val">{d("trajet_aller_retour")}</td>
    <td class="lbl">Frais de repas</td>
    <td class="val">{_check(depl.get("frais_repas", 0))}</td>
  </tr>
  <tr>
    <td class="lbl">Duree de l'intervention</td>
    <td class="val">{d("duree_intervention")}</td>
    <td class="lbl">Frais d'hotel</td>
    <td class="val">{_check(depl.get("frais_hotel", 0))}</td>
  </tr>
  <tr>
    <td class="lbl">Temps de preparation</td>
    <td class="val">{d("temps_preparation")}</td>
    <td class="lbl">Frais de peages</td>
    <td class="val">{_check(depl.get("frais_peages", 0))}</td>
  </tr>
  <tr>
    <td class="lbl">Temps de rangement</td>
    <td class="val">{d("temps_rangement")}</td>
    <td class="lbl"></td>
    <td class="val"></td>
  </tr>
</table>
</div>

<!-- COMMENTAIRE -->
{f'''<div class="section-bloc" style="margin-top:14px;">
<div class="section-title">COMMENTAIRE :</div>
<div class="zone-texte zone-grande">{_esc(_g(inv, "commentaire"))}</div>
</div>''' if _g(inv, "commentaire") else ""}

<!-- SIGNATURES + PIED -->
<div class="sign-footer-wrap">
<div class="signatures">
  <div class="sign-box">
    <div class="head">Signature Client :</div>
    {_bloc_signature_client(inv)}
  </div>
  <div class="sign-box">
    <div class="head">Signature Technicien EMS :</div>
    {_bloc_signature_tech(inv, technicien)}
  </div>
</div>

<div class="footer">
  <strong>Emeraude Moteurs Systemes</strong> - Constructeur de groupe de puissance<br>
  9 Rue d'Armorique - 35540 Miniac Morvan<br>
  Tel : 02.99.19.01.99 &nbsp;|&nbsp;
  <strong>www.emeraudemoteurs.com</strong><br>
  <em style="color:#888;">Document genere le {datetime.now().strftime('%d/%m/%Y a %H:%M')}</em>
</div>
</div>
{_bloc_annexe_photos(photos_annexe)}
</body>
</html>"""
    return html


def generer_bon_html(inv, client=None, moteur=None, photos_annexe=None):
    """Genere le HTML pour consultation rapide en navigateur."""
    return _build_html(inv, client=client, moteur=moteur,
                       photos_annexe=photos_annexe, for_pdf=False)


def _unlock_file(path: Path) -> None:
    """
    Retire l'attribut lecture-seule ET ajuste les droits NTFS (Windows).
    Cas couverts :
      - fichier marque lecture-seule (chmod)
      - fichier cree par un autre utilisateur Windows (icacls)
    Ne deverrouille PAS un fichier ouvert dans un autre processus.
    """
    try:
        import stat
        path.chmod(path.stat().st_mode | stat.S_IWRITE)
    except OSError:
        pass
    if platform.system() == "Windows":
        try:
            import os, subprocess
            user = os.environ.get("USERNAME", "")
            if user:
                subprocess.run(
                    ["icacls", str(path), "/grant", f"{user}:(W,M)", "/Q"],
                    capture_output=True, check=False, timeout=5,
                )
        except Exception:
            pass


def _write_pdf_bytes(dest: Path, data: bytes) -> None:
    """
    Ecrit `data` dans `dest` de facon robuste (multi-utilisateur Windows).

    Strategies dans l'ordre :
      1. Ecriture directe (cas nominal).
      2. Temp + os.replace() : atomique, contourne les restrictions NTFS
         quand l'utilisateur a les droits sur le dossier mais pas sur le fichier.
      3. Suppression de l'ancien fichier + ecriture neuve : fonctionne quand
         le dossier accorde "Modifier les sous-fichiers" (droit NTFS Delete
         herite) meme si le fichier est possede par quelqu'un d'autre.
         C'est le cas typique des PDFs crees avant les modifications.
    """
    import tempfile, os as _os

    # Strategie 1 : ecriture directe
    try:
        dest.write_bytes(data)
        return
    except PermissionError:
        pass

    # Strategie 2 : temp + replace atomique
    tmp_path = None
    try:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, suffix=".tmp")
        tmp_path = Path(tmp)
        _os.close(fd)
        tmp_path.write_bytes(data)
        _os.replace(str(tmp_path), str(dest))
        return
    except Exception:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    # Strategie 3 : suppression de l'ancien + ecriture neuve
    # (fonctionne si le dossier accorde "Delete subfiles" mais que le fichier
    #  existant est possede par un autre utilisateur)
    try:
        if dest.exists():
            dest.unlink()
        dest.write_bytes(data)
        return
    except Exception:
        pass

    # Echec definitif
    raise PermissionError(
        f"Impossible d'écrire le PDF : {dest}\n\n"
        "Causes possibles :\n"
        "  • Le fichier est ouvert dans un lecteur PDF — fermez-le puis réessayez.\n"
        "  • Le fichier a été créé par un autre utilisateur sans droits partagés.\n"
        "    → Demandez à l'administrateur de vérifier les permissions du dossier."
    )


def generer_bon_pdf(inv, output_path, client=None, moteur=None,
                    photos_annexe=None):
    """
    Recupere le PDF du bon depuis l'API serveur.

    Cette fonction est appelable cote client (.exe) sans WeasyPrint
    car le PDF est genere sur le serveur. Si l'API est injoignable,
    tombe en fallback sur WeasyPrint local si disponible.
    """
    output_path = Path(output_path)

    # Retire l'attribut lecture-seule + ajuste les droits NTFS si necessaire
    if output_path.exists():
        _unlock_file(output_path)

    import sys
    _frozen = getattr(sys, "frozen", False)   # True quand lance depuis un .exe

    # 1. Tenter de recuperer le PDF via API (chemin normal : client ou .exe)
    inv_id = _g(inv, "id")
    if inv_id:
        try:
            from ems_client import api as _api
            base_url = _api._client.base_url
            if base_url:
                from urllib.request import urlopen
                url = f"{base_url.rstrip('/')}/interventions/{inv_id}/pdf"
                with urlopen(url, timeout=60) as resp:
                    data = resp.read()
                _write_pdf_bytes(output_path, data)
                return output_path
        except PermissionError:
            raise
        except Exception as e:
            if _frozen:
                # Dans un .exe, pas de WeasyPrint local : erreur explicite
                raise RuntimeError(
                    "Impossible de générer le PDF : le serveur EMS est injoignable.\n\n"
                    f"Détail : {e}\n\n"
                    "Vérifiez que le serveur EMS est démarré, puis réessayez."
                ) from e
            logger.warning("API indisponible (%s), tentative WeasyPrint local", e)
    elif _frozen:
        raise RuntimeError(
            "Impossible de générer le PDF : identifiant de bon manquant.\n"
            "Enregistrez d'abord le bon avant de générer le PDF."
        )

    # 2. Fallback WeasyPrint local (developpement uniquement, jamais en .exe)
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "PDF impossible : API serveur injoignable ET WeasyPrint non installe.\n"
            "Verifiez la connexion reseau ou installez : pip install weasyprint"
        ) from e

    html_str = _build_html(inv, client=client, moteur=moteur,
                           photos_annexe=photos_annexe, for_pdf=True)
    import tempfile as _tmp, os as _os
    fd, tmp = _tmp.mkstemp(dir=output_path.parent, suffix=".tmp")
    tmp_path = Path(tmp)
    try:
        _os.close(fd)
        HTML(string=html_str).write_pdf(str(tmp_path))
        _write_pdf_bytes(output_path, tmp_path.read_bytes())
    finally:
        tmp_path.unlink(missing_ok=True)
    return output_path


def sauvegarder_bon(inv, photos_annexe=None, generer_pdf=False,
                    client=None, moteur=None):
    """
    Sauvegarde le HTML dans le dossier de l'intervention.
    Si generer_pdf=True et WeasyPrint disponible, genere AUSSI le PDF.
    Retourne le chemin du fichier principal (PDF si genere, sinon HTML).
    """
    num_bon = _g(inv, "num_bon")
    if not num_bon:
        raise ValueError("Le bon n'a pas de num_bon")
    dossier = DOSSIERS_PATH / num_bon
    dossier.mkdir(parents=True, exist_ok=True)

    html = generer_bon_html(inv, client=client, moteur=moteur,
                            photos_annexe=photos_annexe)
    html_path = dossier / f"{num_bon}.html"
    # Si le fichier existe en lecture seule, retire l'attribut
    if html_path.exists():
        try:
            import stat
            html_path.chmod(html_path.stat().st_mode | stat.S_IWRITE)
        except OSError:
            pass
    html_path.write_text(html, encoding="utf-8")

    if generer_pdf:
        try:
            pdf_path = dossier / f"{num_bon}.pdf"
            generer_bon_pdf(inv, pdf_path, client=client, moteur=moteur,
                            photos_annexe=photos_annexe)
            return pdf_path
        except (PermissionError, RuntimeError):
            raise   # remonter a l'UI avec message lisible
        except Exception as e:
            # Erreur inattendue -> repli sur le HTML
            logger.warning("PDF non généré (%s), HTML disponible.", e)

    return html_path


def ouvrir_fichier(path):
    p = str(path)
    if platform.system() == "Windows":
        os.startfile(p)
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])

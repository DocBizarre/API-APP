"""
EMS - Génération de la fiche affaire en PDF.
Style cohérent avec bon_generator.py (mêmes couleurs, même structure).
"""
import base64
import json
from datetime import datetime
from pathlib import Path

LOGO_PATH = Path(__file__).parent / "assets" / "logo_ems.png"

try:
    from .logo_data import LOGO_EMS_B64
except ImportError:
    LOGO_EMS_B64 = ""


def _g(obj, key, default=""):
    if obj is None:
        return default
    try:
        v = obj[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def _esc(s):
    if s is None:
        return ""
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _logo_data_uri():
    if LOGO_PATH.is_file():
        try:
            b = LOGO_PATH.read_bytes()
            return "data:image/png;base64," + base64.b64encode(b).decode("ascii")
        except OSError:
            pass
    if LOGO_EMS_B64:
        return "data:image/png;base64," + LOGO_EMS_B64
    return ""


def _fmt_eur(val):
    """Formatte un montant en euros au format français : 1 000,00 €"""
    try:
        v = float(str(val).replace(",", ".").replace(" ", "").replace(" ", ""))
        # "15,000.00" → "15 000,00 €"
        s = f"{v:,.2f}"
        s = s.replace(",", " ").replace(".", ",")
        return s + " €"
    except (ValueError, TypeError):
        return str(val) if val else "—"


def _parse_ht(s):
    if not s:
        return None
    try:
        return float(str(s).replace(",", ".").replace(" ", "").replace(" ", ""))
    except (ValueError, TypeError):
        return None


def _statut_style(statut):
    styles = {
        "En cours":    ("background:#dbeafe;color:#1d4ed8;", "●"),
        "En attente":  ("background:#fef3c7;color:#92400e;", "●"),
        "À facturer":  ("background:#ede9fe;color:#5b21b6;", "●"),
        "Clos":        ("background:#d1fae5;color:#065f46;", "●"),
        "Annulé":      ("background:#f3f4f6;color:#4b5563;", "●"),
    }
    css, dot = styles.get(statut, ("background:#f3f4f6;color:#4b5563;", "●"))
    return f'<span style="{css}display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:20px;font-size:9.5px;font-weight:600">{dot} {_esc(statut)}</span>'


def _item_statut_style(statut):
    styles = {
        "À faire":   ("background:#f3f4f6;color:#4b5563;",    "○"),
        "En cours":  ("background:#dbeafe;color:#1d4ed8;",    "◐"),
        "Terminé":   ("background:#d1fae5;color:#065f46;",    "●"),
        "NC":        ("background:#fee2e2;color:#991b1b;",    "✕"),
    }
    css, dot = styles.get(statut, ("background:#f3f4f6;color:#4b5563;", "○"))
    return f'<span style="{css}display:inline-flex;align-items:center;gap:4px;padding:2px 7px;border-radius:10px;font-size:9px;font-weight:600">{dot} {_esc(statut)}</span>'


def _fmt_modalite(e):
    m = e.get("modalite", "")
    if m == "comptant":
        return "Comptant"
    if m == "jours":
        return f"{e.get('jours','?')} jours"
    if m == "jours_fm":
        return f"{e.get('jours','?')} j. fin mois"
    return "—"


def build_affaire_html(affaire: dict, items: list, client: dict | None = None,
                       for_pdf: bool = True, pdf_type: str = "complet") -> str:
    """
    Génère le HTML de la fiche affaire.
    pdf_type : "complet" (tout inclus) ou "technique" (sans données financières ni
                conditions de règlement — destiné à l'atelier).
    """
    num        = _g(affaire, "num_affaire")
    nom_projet = _g(affaire, "nom_projet")
    statut     = _g(affaire, "statut", "En cours")
    navire     = _g(affaire, "navire_machine")
    ref_int    = _g(affaire, "ref_interne")
    num_cmd    = _g(affaire, "num_commande_client")
    charge     = _g(affaire, "charge_affaire")
    resp_tech  = _g(affaire, "resp_technique")
    date_deb   = _g(affaire, "date_debut")
    date_fin   = _g(affaire, "date_fin_prevue")
    date_clo   = _g(affaire, "date_cloture")
    description  = _g(affaire, "description")
    commentaires = _g(affaire, "commentaires")
    conditions_reglement = _g(affaire, "conditions_reglement")
    garanties            = _g(affaire, "garanties")

    try:
        interlocuteurs = json.loads(_g(affaire, "interlocuteurs_client", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        interlocuteurs = []
    interlocuteurs = [it for it in interlocuteurs if it.get("nom") or it.get("email")]

    client_nom   = (client.get("nom", "") if client else "") or _g(affaire, "client_nom")
    fournisseur  = _g(affaire, "fournisseur")
    etab_fin     = _g(affaire, "etablissement_financier")
    date_achat   = _g(affaire, "date_achat")
    prix_ht_raw  = _g(affaire, "prix_ht")
    exo          = bool(int(_g(affaire, "exonere_tva", 0) or 0))

    ht  = _parse_ht(prix_ht_raw)
    tva = (ht * 0.20) if (ht is not None and not exo) else 0.0
    ttc = (ht + tva) if ht is not None else None

    try:
        echeances = json.loads(_g(affaire, "echeances_facturation", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        echeances = []

    logo_uri  = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS" style="max-width:180px;max-height:90px;">'
                 if logo_uri else '<div style="font-size:24px;font-weight:bold;color:#002b5c">EMS</div>')

    # Footer pied de page WeasyPrint
    css_page = ""
    body_padding = "60px 20px 16px 20px"
    if for_pdf:
        body_padding = "6mm 6mm 10mm 6mm"
        _safe = lambda s: str(s).replace('"', "'").replace("\\", "")
        pdf_label = f"Fiche affaire {_safe(num)}" + (" — TECHNIQUE" if pdf_type == "technique" else "")
        css_page = f"""
@page {{
  size: A4;
  margin: 10mm 5mm 18mm 5mm;
  @bottom-left {{
    content: "{pdf_label}";
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

    # ── Echéances (PDF complet uniquement) ──
    ech_section = ""
    if echeances and pdf_type != "technique":
        ech_rows = ""
        total_pct_ech   = 0.0
        total_paye_ech  = 0.0
        total_stade_ech = 0.0
        for e in echeances:
            pct_e      = float(e.get("pourcentage") or 0)
            paye_e     = float(str(e.get("montant_paye") or "0").replace(",", "."))
            montant_e  = (ttc * pct_e / 100) if ttc is not None else None
            reste_e    = (montant_e - paye_e) if montant_e is not None else None
            total_pct_ech  += pct_e
            total_paye_ech += paye_e
            if montant_e is not None:
                total_stade_ech += montant_e

            reste_style = ""
            if reste_e is not None:
                reste_style = "color:#059669;font-weight:600" if reste_e <= 0 else "color:#c62828;font-weight:600"

            ech_rows += f"""
<tr>
  <td style="padding:5px 8px;font-weight:500">{_esc(e.get('stade','—'))}</td>
  <td style="padding:5px 8px;text-align:center">{pct_e:.0f}&nbsp;%</td>
  <td style="padding:5px 8px;text-align:right">{_fmt_eur(montant_e) if montant_e is not None else '—'}</td>
  <td style="padding:5px 8px;text-align:right">{_fmt_eur(paye_e) if paye_e else '—'}</td>
  <td style="padding:5px 8px;text-align:right;{reste_style}">{_fmt_eur(reste_e) if reste_e is not None else '—'}</td>
  <td style="padding:5px 8px;font-size:9px;color:#6b7785">{_esc(_fmt_modalite(e))}</td>
</tr>"""

        total_reste_ech = total_stade_ech - total_paye_ech if echeances else None
        col_label = "HT" if exo else "TTC"

        tr_reste_style = ""
        if total_reste_ech is not None:
            tr_reste_style = "color:#059669;font-weight:600" if total_reste_ech <= 0 else "color:#c62828;font-weight:600"
        ech_section = f"""
<div class="section-header section-header-blue">ÉCHÉANCIER DE FACTURATION</div>
<table class="data-table">
  <thead>
    <tr>
      <th style="width:28%">Stade</th>
      <th style="width:8%;text-align:center">%</th>
      <th style="width:16%;text-align:right">Montant&nbsp;{col_label}</th>
      <th style="width:16%;text-align:right">Payé</th>
      <th style="width:16%;text-align:right">Reste</th>
      <th style="width:16%">Modalité</th>
    </tr>
  </thead>
  <tbody>
    {ech_rows}
  </tbody>
  <tfoot>
    <tr style="background:#002b5c;color:#fff;font-weight:700;font-size:9.5px">
      <td style="padding:5px 8px">Total</td>
      <td style="padding:5px 8px;text-align:center">{total_pct_ech:.0f}&nbsp;%</td>
      <td style="padding:5px 8px;text-align:right">{_fmt_eur(total_stade_ech) if echeances else '—'}</td>
      <td style="padding:5px 8px;text-align:right">{_fmt_eur(total_paye_ech)}</td>
      <td style="padding:5px 8px;text-align:right;{tr_reste_style}">{_fmt_eur(total_reste_ech) if total_reste_ech is not None else '—'}</td>
      <td></td>
    </tr>
  </tfoot>
</table>"""

    # ── Chapitres (une section par chapitre) ──
    def _parse_details(raw):
        try:
            parsed = json.loads(raw or "[]")
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict):
                return [{"style": "text", "libelle": k, "valeur": v, "unite": ""} for k, v in parsed.items()]
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
        return []

    def _detail_display(d):
        style  = d.get("style", "text")
        valeur = str(d.get("valeur", "") or "")
        unite  = str(d.get("unite", "") or "")
        if style == "check":
            return "✓" if valeur.lower() == "true" else "✗"
        if style == "measure" and unite:
            return f"{valeur} {unite}"
        if style == "multiselect":
            try:
                vals = json.loads(valeur) if valeur.startswith("[") else [v.strip() for v in valeur.split("|") if v.strip()]
                return ", ".join(vals) if vals else "—"
            except Exception:
                return valeur
        return valeur

    chapter_blocks = ""
    for idx, it in enumerate(items):
        type_item = it.get("type_item", "") or ""
        libelle   = it.get("libelle", "") or ""
        marque    = it.get("marque", "") or ""
        num_serie = it.get("num_serie", "") or ""
        objectif  = it.get("objectif", "") or ""
        suivi     = it.get("suivi", "") or ""
        statut_it = it.get("statut", "À faire") or "À faire"

        # Métadonnées (seulement si renseignées)
        meta_rows = ""
        if marque and num_serie:
            meta_rows += f'<tr><td class="lbl">Marque</td><td>{_esc(marque)}</td><td class="lbl">N° série</td><td style="font-family:monospace">{_esc(num_serie)}</td></tr>'
        elif marque:
            meta_rows += f'<tr><td class="lbl">Marque</td><td colspan="3">{_esc(marque)}</td></tr>'
        elif num_serie:
            meta_rows += f'<tr><td class="lbl">N° série</td><td colspan="3" style="font-family:monospace">{_esc(num_serie)}</td></tr>'
        if objectif:
            meta_rows += f'<tr><td class="lbl">Objectif</td><td colspan="3" style="white-space:pre-wrap">{_esc(objectif)}</td></tr>'
        if suivi:
            meta_rows += f'<tr><td class="lbl">Suivi</td><td colspan="3" style="white-space:pre-wrap;color:#4a5560;font-style:italic">{_esc(suivi)}</td></tr>'

        meta_table = ""
        if meta_rows:
            meta_table = f"""
<table class="bloc-info" style="border-radius:0">
  <colgroup><col style="width:22%"><col style="width:28%"><col style="width:22%"><col style="width:28%"></colgroup>
  {meta_rows}
</table>"""

        # Champs details_json (seulement ceux avec une valeur)
        details = _parse_details(it.get("details_json"))
        filled  = [d for d in details if str(d.get("valeur", "") or "").strip()]
        detail_table = ""
        if filled:
            chk_td = ('<td style="padding:4px 6px;width:20px;text-align:center"><span class="chk-box"></span></td>'
                      if pdf_type == "technique" else "")
            detail_rows = "".join(
                f'<tr>'
                f'{chk_td}'
                f'<td style="padding:4px 8px;font-size:10px;font-weight:600;color:#002b5c;background:#f5f7fa;width:40%">{_esc(d.get("libelle",""))}</td>'
                f'<td style="padding:4px 8px;font-size:10px">{_esc(_detail_display(d))}</td>'
                f'</tr>'
                for d in filled
            )
            detail_table = f"""
<table class="data-table" style="border-radius:0;margin-top:0;border-top:1px dashed #c8d0d9">
  <tbody>{detail_rows}</tbody>
</table>"""

        type_badge = (f'<span style="background:#eff6ff;color:#1d4ed8;padding:1px 6px;'
                      f'border-radius:10px;font-size:8.5px;font-weight:600;margin-right:6px">'
                      f'{_esc(type_item)}</span>') if type_item else ""

        chapter_blocks += f"""
<div class="ch-section" style="margin-top:{'14px' if idx else '0'};page-break-inside:avoid;break-inside:avoid">
  <div class="ch-section-header">
    <span style="display:flex;align-items:center;gap:6px;flex:1;min-width:0">
      {type_badge}<strong style="font-size:11px">{_esc(libelle)}</strong>
    </span>
    {_item_statut_style(statut_it)}
  </div>
  {meta_table}{detail_table}
</div>"""

    items_section = ""
    if items:
        total_items = len(items)
        items_section = f"""
<div class="section-header section-header-blue">CHAPITRES / TRAVAUX ({total_items})</div>
<div style="border:1px solid #b8c0c9;border-top:none;border-radius:0 0 4px 4px;padding:8px 10px">
  {chapter_blocks}
</div>"""

    # ── Financier (PDF complet uniquement) ──
    fin_section = ""
    if pdf_type != "technique":
        fin_rows = ""
        if ht is not None:
            fin_rows += f'<tr><td class="lbl">Prix HT</td><td><strong>{_fmt_eur(ht)}</strong></td>'
            if exo:
                fin_rows += '<td class="lbl">TVA</td><td style="color:#c62828;font-weight:600">Exonéré</td></tr>'
            else:
                fin_rows += f'<td class="lbl">TVA (20&nbsp;%)</td><td>{_fmt_eur(tva)}</td></tr>'
            if not exo and ttc is not None:
                fin_rows += f'<tr><td class="lbl">Prix TTC</td><td style="font-weight:700;color:#002b5c">{_fmt_eur(ttc)}</td><td></td><td></td></tr>'
        if etab_fin:
            fin_rows += f'<tr><td class="lbl">Établissement financier</td><td colspan="3">{_esc(etab_fin)}</td></tr>'
        if fournisseur:
            fin_rows += f'<tr><td class="lbl">Fournisseur</td><td>{_esc(fournisseur)}</td>'
            fin_rows += f'<td class="lbl">Date d\'achat</td><td>{_esc(date_achat) or "—"}</td></tr>'
        elif date_achat:
            fin_rows += f'<tr><td class="lbl">Date d\'achat</td><td colspan="3">{_esc(date_achat)}</td></tr>'

        if fin_rows:
            fin_section = f"""
<div class="section-header section-header-blue">DONNÉES FINANCIÈRES</div>
<table class="bloc-info">
  <colgroup><col style="width:28%"><col style="width:22%"><col style="width:28%"><col style="width:22%"></colgroup>
  {fin_rows}
</table>"""

    # ── Description & commentaires ──
    desc_section = ""
    if description:
        desc_section = f"""
<div class="section-bloc">
  <div class="section-title">DESCRIPTION :</div>
  <div class="zone-texte">{_esc(description)}</div>
</div>"""

    comm_section = ""
    if commentaires:
        comm_section = f"""
<div class="section-bloc">
  <div class="section-title">COMMENTAIRES :</div>
  <div class="zone-texte">{_esc(commentaires)}</div>
</div>"""

    # ── Conditions de règlement + Garanties (PDF complet uniquement) ──
    reglement_section = ""
    if conditions_reglement and pdf_type != "technique":
        reglement_section = f"""
<div class="section-header section-header-blue">CONDITIONS DE RÈGLEMENT</div>
<div style="border:1px solid #b8c0c9;border-top:none;border-radius:0 0 4px 4px;padding:10px 12px;white-space:pre-wrap;font-size:11px;line-height:1.6">
  {_esc(conditions_reglement)}
</div>"""

    garanties_section = ""
    if garanties and pdf_type != "technique":
        garanties_section = f"""
<div class="section-header section-header-blue">GARANTIES</div>
<div style="border:1px solid #b8c0c9;border-top:none;border-radius:0 0 4px 4px;padding:10px 12px;white-space:pre-wrap;font-size:11px;line-height:1.6">
  {_esc(garanties)}
</div>"""

    # ── Interlocuteur(s) client ──
    interlocuteurs_section = ""
    if interlocuteurs:
        interloc_rows = "".join(f"""
<tr>
  <td style="padding:5px 8px;font-weight:500">{_esc(' '.join(filter(None, [it.get('prenom',''), it.get('nom','')]))) or '—'}</td>
  <td style="padding:5px 8px">{_esc(it.get('email','')) or '—'}</td>
  <td style="padding:5px 8px">{_esc(it.get('telephone','')) or '—'}</td>
  <td style="padding:5px 8px;font-size:9px;color:#6b7785">{_esc(it.get('role','')) or '—'}</td>
</tr>""" for it in interlocuteurs)
        interlocuteurs_section = f"""
<div class="section-header section-header-blue">INTERLOCUTEUR(S) CLIENT</div>
<table class="data-table">
  <thead>
    <tr>
      <th style="width:28%">Nom</th>
      <th style="width:28%">Email</th>
      <th style="width:22%">Téléphone</th>
      <th style="width:22%">Rôle</th>
    </tr>
  </thead>
  <tbody>
    {interloc_rows}
  </tbody>
</table>"""

    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    type_label = " — FICHE TECHNIQUE" if pdf_type == "technique" else ""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Fiche affaire {_esc(num)}{type_label}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
  font-size: 11.5px; color: #1a2332; background: #fff;
  padding: {body_padding};
  -webkit-font-smoothing: antialiased;
}}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #b8c0c9; padding: 4px 6px; vertical-align: top; }}

/* En-tête */
.header {{ display: grid; grid-template-columns: 1fr 1.6fr 1fr; gap: 16px; align-items: center; margin-bottom: 14px; }}
.header-left {{ display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 4px; }}
.header-mid {{ text-align: center; }}
.header-mid h1 {{ font-size: 19px; font-weight: 700; color: #002b5c; margin: 0 0 6px; letter-spacing: .5px; }}
.header-mid .info {{ font-size: 10px; line-height: 1.5; color: #4a5560; }}
.header-right {{ padding: 4px 0 4px 8px; }}
.ref-box {{
  display: inline-block; background: #002b5c; color: #fff;
  padding: 5px 14px; font-size: 13px; font-weight: bold;
  border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,.15);
  margin-bottom: 6px;
}}
.technique-badge {{
  display: inline-block; background: #059669; color: #fff;
  padding: 3px 10px; font-size: 9.5px; font-weight: 700; border-radius: 4px;
  letter-spacing: .5px; text-transform: uppercase;
}}

/* Sections */
.section-header {{
  display: block; padding: 4px 10px; font-size: 10.5px; font-weight: 700;
  color: #fff; margin: 10px 0 0; border-radius: 4px 4px 0 0; letter-spacing: .5px;
}}
.section-header-blue {{ background: #002b5c; }}

.bloc-info {{ width: 100%; margin-top: 0; border-radius: 0 0 4px 4px; overflow: hidden; }}
.bloc-info td {{ font-size: 11px; height: 21px; }}
.bloc-info .lbl {{ background: #f5f7fa; font-weight: 600; width: 28%; color: #002b5c; }}

.data-table {{ width: 100%; margin-top: 0; border-radius: 0 0 4px 4px; overflow: hidden; }}
.data-table th {{
  background: #002b5c; color: #fff; font-size: 10px; font-weight: 600;
  text-align: left; padding: 5px 8px; letter-spacing: .3px;
}}
.data-table td {{ font-size: 11px; }}
.data-table tbody tr:nth-child(even) {{ background: #fafbfc; }}
.data-table tfoot td {{ border-top: 2px solid #b8c0c9; }}

.section-title {{
  font-weight: 700; font-size: 12px; color: #002b5c;
  margin: 14px 0 4px; padding-bottom: 3px;
  border-bottom: 2px solid #c62828;
  display: inline-block; padding-right: 12px; letter-spacing: .3px;
}}
.zone-texte {{
  border: 1px solid #b8c0c9; min-height: 40px; padding: 6px 8px;
  white-space: pre-wrap; font-size: 11px; line-height: 1.5;
  border-radius: 3px; background: #fafbfc;
  page-break-inside: avoid; break-inside: avoid;
}}
.section-bloc {{ page-break-inside: avoid; break-inside: avoid; }}

/* Sections chapitre */
.ch-section {{ border: 1px solid #c8d0d9; border-radius: 4px; overflow: hidden; }}
.ch-section-header {{
  display: flex; align-items: center; justify-content: space-between;
  background: #f0f4fa; padding: 5px 10px; gap: 8px;
  border-bottom: 1px solid #c8d0d9; font-size: 11px;
}}
.chk-box {{
  display: inline-block; width: 10px; height: 10px;
  border: 1.3px solid #002b5c; border-radius: 2px; background: #fff;
}}

/* Footer */
.footer {{
  border-top: 2px solid #002b5c; margin-top: 16px; padding-top: 8px;
  font-size: 9px; color: #6b7785; text-align: center; line-height: 1.7;
  page-break-inside: avoid; break-inside: avoid;
}}
.footer strong {{ color: #002b5c; }}

/* Print */
.print-btn {{
  position: fixed; top: 14px; right: 14px;
  background: #002b5c; color: #fff; border: 2px solid #fff;
  padding: 10px 18px; border-radius: 6px; font-size: 12px; font-weight: 700;
  cursor: pointer; font-family: 'Segoe UI', Arial, sans-serif;
  box-shadow: 0 3px 10px rgba(0,0,0,.35); z-index: 9999;
}}
.print-btn:hover {{ background: #003d7a; }}
@media print {{
  .print-btn {{ display: none !important; }}
  html, body {{ background: #fff !important; }}
  body {{ margin: 0 !important; padding: 6mm 6mm 8mm !important; font-size: 10.5pt; }}
}}
{css_page}
</style>
</head>
<body>
{"" if for_pdf else '<button class="print-btn" onclick="window.print()">Imprimer / PDF</button>'}

<!-- EN-TÊTE -->
<div class="header">
  <div class="header-left">{logo_html}</div>
  <div class="header-mid">
    <h1>FICHE D'AFFAIRE</h1>
    {f'<div style="margin-top:4px"><span class="technique-badge">Technique</span></div>' if pdf_type == "technique" else ""}
  </div>
  <div class="header-right">
    <div class="ref-box">{_esc(num)}</div>
  </div>
</div>

<!-- IDENTIFICATION -->
<div class="section-header section-header-blue">IDENTIFICATION</div>
<table class="bloc-info">
  <colgroup><col style="width:28%"><col style="width:22%"><col style="width:28%"><col style="width:22%"></colgroup>
  <tr>
    <td class="lbl">Client</td>
    <td><strong>{_esc(client_nom) or '—'}</strong></td>
    <td class="lbl">Chargé d'affaire</td>
    <td>{_esc(charge) or '—'}</td>
  </tr>
  <tr>
    <td class="lbl">Resp. technique</td>
    <td colspan="3">{_esc(resp_tech) or '—'}</td>
  </tr>
  <tr>
    <td class="lbl">Projet</td>
    <td>{_esc(nom_projet) or '—'}</td>
    <td class="lbl">Navire / Machine</td>
    <td>{_esc(navire) or '—'}</td>
  </tr>
  <tr>
    <td class="lbl">Référence interne</td>
    <td>{_esc(ref_int) or '—'}</td>
    <td class="lbl">Statut</td>
    <td>{_statut_style(statut)}</td>
  </tr>
  {f'<tr><td class="lbl">N° commande client</td><td colspan="3" style="font-family:monospace">{_esc(num_cmd)}</td></tr>' if num_cmd else ''}
  <tr>
    <td class="lbl">Date début</td>
    <td>{_esc(date_deb) or '—'}</td>
    <td class="lbl">Date de livraison</td>
    <td>{_esc(date_fin) or '—'}</td>
  </tr>
  {f'<tr><td class="lbl">Date clôture</td><td>{_esc(date_clo)}</td><td></td><td></td></tr>' if date_clo else ''}
</table>

{fin_section}
{desc_section}
{interlocuteurs_section}
{ech_section}
{items_section}
{reglement_section}
{garanties_section}
{comm_section}

<!-- FOOTER -->
<div class="footer">
  <em style="color:#aaa">Document généré le {now}</em>
</div>
</body>
</html>"""
    return html


def build_bon_facturation_html(affaire: dict, echelon: dict, echelon_idx: int,
                               client: dict | None = None) -> str:
    """Génère le HTML d'un bon de facturation pour un échelon spécifique."""
    num        = _g(affaire, "num_affaire")
    nom_projet = _g(affaire, "nom_projet")
    navire     = _g(affaire, "navire_machine")
    exo        = bool(int(_g(affaire, "exonere_tva", 0) or 0))
    ht_total   = _parse_ht(_g(affaire, "prix_ht"))

    stade      = echelon.get("stade") or f"Échelon {echelon_idx + 1}"
    pourcentage = float(echelon.get("pourcentage") or 0)
    modalite   = _fmt_modalite(echelon)

    ht_echelon  = (ht_total * pourcentage / 100) if ht_total is not None else None
    tva_echelon = (ht_echelon * 0.20) if (ht_echelon is not None and not exo) else 0.0
    ttc_echelon = (ht_echelon + tva_echelon) if ht_echelon is not None else None

    client_nom   = (client.get("nom", "") if client else "") or _g(affaire, "client_nom")
    client_addr  = (client.get("adresse", "") if client else "")
    client_email = (client.get("email", "") if client else "")
    client_tel   = (client.get("telephone", "") if client else "")
    client_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [client_addr, client_email and f"✉ {client_email}",
                  client_tel and f"☎ {client_tel}"]
        if v
    )

    conditions = _g(affaire, "conditions_reglement")
    date_emission = datetime.now().strftime("%d/%m/%Y")
    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS" style="max-width:160px;max-height:70px;">'
                 if logo_uri else '<div style="font-size:20px;font-weight:bold;color:#002b5c">EMS</div>')

    montant_principal = _fmt_eur(ht_echelon) if ht_echelon is not None else "—"
    montant_final     = _fmt_eur(ht_echelon if exo else ttc_echelon) if (ht_echelon if exo else ttc_echelon) is not None else "—"
    label_total       = "Total HT" if exo else "Total TTC"

    tva_row = ""
    if not exo and tva_echelon:
        tva_row = f"""<tr><td>TVA 20 %</td><td style="text-align:center">20 %</td>
          <td style="text-align:right">{_fmt_eur(tva_echelon)}</td></tr>"""
    exo_row = ""
    if exo:
        exo_row = '<tr><td colspan="3" style="color:#d97706;font-size:9pt">⚠️ TVA exonérée — justificatif requis</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
@page {{
  size: A4;
  margin: 12mm 10mm 18mm 10mm;
  @bottom-left {{ content: "Bon de facturation — {_esc(num)}"; font-size: 8pt; color: #6b7785; }}
  @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #6b7785; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #1a2a3a; }}
.header {{ display: flex; justify-content: space-between; align-items: flex-start;
           margin-bottom: 20px; border-bottom: 3px solid #002b5c; padding-bottom: 14px; }}
.doc-title {{ font-size: 18pt; font-weight: bold; color: #002b5c; text-transform: uppercase; }}
.ref-box {{ background: #002b5c; color: #fff; padding: 8px 16px; border-radius: 6px; text-align: right; }}
.ref-box .ref-label {{ font-size: 8pt; opacity: .8; }}
.ref-box .ref-num {{ font-size: 13pt; font-weight: bold; }}
.parties {{ display: flex; gap: 20px; margin-bottom: 16px; }}
.party-box {{ flex: 1; border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 14px; }}
.party-box h3 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 6px; }}
.party-box .name {{ font-size: 11pt; font-weight: bold; color: #002b5c; }}
.detail {{ font-size: 9pt; color: #4b5563; margin-top: 3px; }}
.objet-box {{ background: #f8faff; border: 1px solid #bfdbfe; border-radius: 6px;
              padding: 10px 14px; margin-bottom: 16px; display: flex; gap: 40px; flex-wrap: wrap; }}
.objet-box label {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; display: block; }}
.objet-box .val {{ font-size: 10.5pt; font-weight: 600; color: #1e3a5f; margin-top: 3px; }}
table.montants {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
table.montants th {{ background: #002b5c; color: #fff; padding: 7px 10px; font-size: 9pt; font-weight: 600; text-align: left; }}
table.montants td {{ padding: 8px 10px; border-bottom: 1px solid #e5eaf0; }}
table.montants tfoot td {{ background: #eff6ff; font-weight: 700; font-size: 11pt; border-bottom: none; border-top: 2px solid #002b5c; }}
.payment-box {{ border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 14px; }}
.payment-box h4 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 6px; }}
.stade-badge {{ display: inline-block; background: #dbeafe; color: #1d4ed8;
                padding: 5px 18px; border-radius: 20px; font-size: 11pt; font-weight: 700;
                margin-bottom: 16px; }}
</style>
</head>
<body>

  <div class="header">
    <div>
      {logo_html}
      <div style="margin-top:8px;font-size:8pt;color:#6b7785">Électromécanique Marine et Services</div>
    </div>
    <div style="text-align:right">
      <div class="doc-title">Bon de facturation</div>
      <div style="margin-top:10px" class="ref-box">
        <div class="ref-label">Affaire N°</div>
        <div class="ref-num">{_esc(num)}</div>
      </div>
      <div style="margin-top:6px;font-size:9pt;color:#6b7785">Émis le {_esc(date_emission)}</div>
    </div>
  </div>

  <div style="text-align:center"><span class="stade-badge">{_esc(stade)}</span></div>

  <div class="parties">
    <div class="party-box">
      <h3>Émetteur</h3>
      <div class="name">EMS</div>
      <div class="detail">Électromécanique Marine et Services</div>
    </div>
    <div class="party-box">
      <h3>Destinataire</h3>
      <div class="name">{_esc(client_nom or '—')}</div>
      {client_lines}
    </div>
  </div>

  <div class="objet-box">
    <div>
      <label>Projet / Affaire</label>
      <div class="val">{_esc(nom_projet or '—')}</div>
    </div>
    {'<div><label>Navire / Machine</label><div class="val">' + _esc(navire) + '</div></div>' if navire else ''}
    <div>
      <label>Stade de facturation</label>
      <div class="val">{_esc(stade)} — {pourcentage:.0f} %</div>
    </div>
  </div>

  <table class="montants">
    <thead>
      <tr>
        <th style="width:55%">Désignation</th>
        <th style="width:15%;text-align:center">Taux</th>
        <th style="width:30%;text-align:right">Montant HT</th>
      </tr>
    </thead>
    <tbody>
      <tr>
        <td>{_esc(nom_projet or 'Travaux')}<br>
            <span style="font-size:9pt;color:#6b7785">{_esc(stade)} ({pourcentage:.0f} % du total)</span></td>
        <td style="text-align:center">—</td>
        <td style="text-align:right">{montant_principal}</td>
      </tr>
      {tva_row}
      {exo_row}
    </tbody>
    <tfoot>
      <tr>
        <td colspan="2">{label_total}</td>
        <td style="text-align:right">{montant_final}</td>
      </tr>
    </tfoot>
  </table>

  <div class="payment-box">
    <h4>Conditions de paiement</h4>
    <div style="font-size:10pt">{_esc(modalite) if modalite and modalite != '—' else 'À convenir'}</div>
    {f'<div style="margin-top:8px;font-size:9pt;color:#4b5563;white-space:pre-wrap">{_esc(conditions)}</div>' if conditions else ''}
  </div>

</body>
</html>"""


def build_bon_commande_html(bon: dict, lignes: list, affaire: dict | None = None) -> str:
    """Génère le HTML d'un bon de commande (achat fournisseur) lié à une affaire."""
    try:
        from ems_api.config import settings
        entreprise = settings.ENTREPRISE
    except ImportError:
        entreprise = {
            "nom": "Emeraude Moteurs Systèmes",
            "adresse_1": "9 Rue d'Armorique – 35540 Miniac Morvan",
            "adresse_2": "",
            "tel": "02.99.19.01.99",
            "fax": "",
            "email": "service.technique@emeraudemoteurs.com",
            "siret": "431 976 729 00027",
            "tva": "FR 14 431 976 729",
            "site": "www.emeraudemoteurs.com",
        }

    num_bc     = _g(bon, "num_bc")
    statut     = _g(bon, "statut", "Brouillon")
    date_cmd   = _g(bon, "date_commande")
    date_liv   = _g(bon, "date_livraison_prevue")
    conditions = _g(bon, "conditions")
    notes      = _g(bon, "notes")
    exo        = bool(int(_g(bon, "exonere_tva", 0) or 0))

    num_affaire = _g(affaire, "num_affaire")
    nom_projet  = _g(affaire, "nom_projet")

    emetteur_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [entreprise.get("adresse_1", ""), entreprise.get("adresse_2", ""),
                  entreprise.get("tel") and f"☎ {entreprise['tel']}",
                  entreprise.get("email") and f"✉ {entreprise['email']}"]
        if v
    )

    fourn_nom   = _g(bon, "fournisseur_nom")
    fourn_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [_g(bon, "fournisseur_adresse"),
                  _g(bon, "fournisseur_contact") and f"Contact : {_g(bon, 'fournisseur_contact')}",
                  _g(bon, "fournisseur_email") and f"✉ {_g(bon, 'fournisseur_email')}",
                  _g(bon, "fournisseur_tel") and f"☎ {_g(bon, 'fournisseur_tel')}"]
        if v
    )

    date_emission = datetime.now().strftime("%d/%m/%Y")
    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="{_esc(entreprise.get("nom",""))}" style="max-width:160px;max-height:70px;">'
                 if logo_uri else f'<div style="font-size:20px;font-weight:bold;color:#002b5c">{_esc(entreprise.get("nom",""))}</div>')

    rows = ""
    total_ht = 0.0
    for l in lignes:
        qte = float(_g(l, "quantite", 0) or 0)
        pu  = float(_g(l, "prix_unitaire", 0) or 0)
        montant = float(_g(l, "montant_ligne", qte * pu) or 0)
        total_ht += montant
        rows += f"""<tr>
            <td>{_esc(_g(l, "reference"))}</td>
            <td>{_esc(_g(l, "libelle"))}</td>
            <td style="text-align:center">{qte:g}</td>
            <td style="text-align:right">{_fmt_eur(pu)}</td>
            <td style="text-align:right">{_fmt_eur(montant)}</td>
          </tr>"""

    tva = 0.0 if exo else round(total_ht * 0.20, 2)
    total_ttc = total_ht if exo else total_ht + tva

    sous_total_row = f"""<tr><td colspan="4" style="font-weight:600">Total HT</td>
      <td style="text-align:right;font-weight:600">{_fmt_eur(total_ht)}</td></tr>"""
    tva_row = ""
    if not exo:
        tva_row = f"""<tr><td colspan="4">TVA 20 %</td>
          <td style="text-align:right">{_fmt_eur(tva)}</td></tr>"""
    exo_row = ""
    if exo:
        exo_row = '<tr><td colspan="5" style="color:#d97706;font-size:9pt">⚠️ TVA exonérée — justificatif requis</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
@page {{
  size: A4;
  margin: 12mm 10mm 18mm 10mm;
  @bottom-left {{ content: "Bon de commande — {_esc(num_bc)}"; font-size: 8pt; color: #6b7785; }}
  @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #6b7785; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #1a2a3a; }}
.header {{ display: flex; justify-content: space-between; align-items: flex-start;
           margin-bottom: 20px; border-bottom: 3px solid #002b5c; padding-bottom: 14px; }}
.doc-title {{ font-size: 18pt; font-weight: bold; color: #002b5c; text-transform: uppercase; }}
.ref-box {{ background: #002b5c; color: #fff; padding: 8px 16px; border-radius: 6px; text-align: right; }}
.ref-box .ref-label {{ font-size: 8pt; opacity: .8; }}
.ref-box .ref-num {{ font-size: 13pt; font-weight: bold; }}
.parties {{ display: flex; gap: 20px; margin-bottom: 16px; }}
.party-box {{ flex: 1; border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 14px; }}
.party-box h3 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 6px; }}
.party-box .name {{ font-size: 11pt; font-weight: bold; color: #002b5c; }}
.detail {{ font-size: 9pt; color: #4b5563; margin-top: 3px; }}
.objet-box {{ background: #f8faff; border: 1px solid #bfdbfe; border-radius: 6px;
              padding: 10px 14px; margin-bottom: 16px; display: flex; gap: 40px; flex-wrap: wrap; }}
.objet-box label {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; display: block; }}
.objet-box .val {{ font-size: 10.5pt; font-weight: 600; color: #1e3a5f; margin-top: 3px; }}
table.montants {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
table.montants th {{ background: #002b5c; color: #fff; padding: 7px 10px; font-size: 9pt; font-weight: 600; text-align: left; }}
table.montants td {{ padding: 8px 10px; border-bottom: 1px solid #e5eaf0; }}
table.montants tfoot td {{ background: #eff6ff; font-weight: 700; font-size: 11pt; border-bottom: none; border-top: 2px solid #002b5c; }}
.conditions-box {{ border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 14px; }}
.conditions-box h4 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 6px; }}
</style>
</head>
<body>

  <div class="header">
    <div>
      {logo_html}
    </div>
    <div style="text-align:right">
      <div class="doc-title">Bon de commande</div>
      <div style="margin-top:10px" class="ref-box">
        <div class="ref-label">N° Bon de commande</div>
        <div class="ref-num">{_esc(num_bc)}</div>
      </div>
      <div style="margin-top:6px;font-size:9pt;color:#6b7785">Émis le {_esc(date_emission)}</div>
    </div>
  </div>

  <div class="parties">
    <div class="party-box">
      <h3>Émetteur</h3>
      <div class="name">{_esc(entreprise.get("nom", ""))}</div>
      {emetteur_lines}
    </div>
    <div class="party-box">
      <h3>Fournisseur</h3>
      <div class="name">{_esc(fourn_nom or '—')}</div>
      {fourn_lines}
    </div>
  </div>

  <div class="objet-box">
    <div>
      <label>Affaire</label>
      <div class="val">{_esc(num_affaire or '—')}{' — ' + _esc(nom_projet) if nom_projet else ''}</div>
    </div>
    {'<div><label>Date de commande</label><div class="val">' + _esc(date_cmd) + '</div></div>' if date_cmd else ''}
    {'<div><label>Livraison prévue</label><div class="val">' + _esc(date_liv) + '</div></div>' if date_liv else ''}
    <div>
      <label>Statut</label>
      <div class="val">{_esc(statut)}</div>
    </div>
  </div>

  <table class="montants">
    <thead>
      <tr>
        <th style="width:15%">Référence</th>
        <th style="width:35%">Désignation</th>
        <th style="width:10%;text-align:center">Qté</th>
        <th style="width:20%;text-align:right">PU HT</th>
        <th style="width:20%;text-align:right">Montant HT</th>
      </tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
    <tfoot>
      {sous_total_row}
      {tva_row}
      {exo_row}
      <tr>
        <td colspan="4">Total {"HT (exonéré)" if exo else "TTC"}</td>
        <td style="text-align:right">{_fmt_eur(total_ttc)}</td>
      </tr>
    </tfoot>
  </table>

  {f'''<div class="conditions-box">
    <h4>Conditions</h4>
    <div style="font-size:10pt;white-space:pre-wrap">{_esc(conditions)}</div>
  </div>''' if conditions else ''}
  {f'''<div class="conditions-box" style="margin-top:10px">
    <h4>Notes internes</h4>
    <div style="font-size:9pt;color:#4b5563;white-space:pre-wrap">{_esc(notes)}</div>
  </div>''' if notes else ''}

</body>
</html>"""

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


def _ech_table_html(echeances, ttc, col_label):
    """Tableau HTML d'un échéancier de facturation (utilisé pour l'échéancier
    global de l'affaire ou pour l'échéancier propre à un lot vendu)."""
    if not echeances:
        return ""
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

    total_reste_ech = total_stade_ech - total_paye_ech
    tr_reste_style = "color:#059669;font-weight:600" if total_reste_ech <= 0 else "color:#c62828;font-weight:600"
    return f"""
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
      <td style="padding:5px 8px;text-align:right">{_fmt_eur(total_stade_ech)}</td>
      <td style="padding:5px 8px;text-align:right">{_fmt_eur(total_paye_ech)}</td>
      <td style="padding:5px 8px;text-align:right;{tr_reste_style}">{_fmt_eur(total_reste_ech)}</td>
      <td></td>
    </tr>
  </tfoot>
</table>"""


def build_affaire_html(affaire: dict, items: list, client: dict | None = None,
                       for_pdf: bool = True, pdf_type: str = "complet",
                       moteurs: list | None = None) -> str:
    """
    Génère le HTML de la fiche affaire.
    pdf_type : "complet" (tout inclus) ou "technique" (sans données financières ni
                conditions de règlement — destiné à l'atelier).
    moteurs : liste des moteurs liés à l'affaire (via code_affaire), pour
              affichage de leur(s) numéro(s) de série.
    """
    num        = _g(affaire, "num_affaire")
    nom_projet = _g(affaire, "nom_projet")
    statut     = _g(affaire, "statut", "En cours")
    navire     = _g(affaire, "navire_machine")
    navire_immat = _g(affaire, "navire_immatriculation")
    navire_port  = _g(affaire, "navire_port_attache")
    navire_proprio = _g(affaire, "navire_proprietaire")
    navire_detail = "".join(
        f'<br><span style="font-size:9.5px;color:#6b7785">{_esc(v)}</span>'
        for v in [
            navire_immat and f"Immat. : {navire_immat}",
            navire_port and f"Port d'attache : {navire_port}",
            navire_proprio and f"Propriétaire : {navire_proprio}",
        ] if v
    )
    num_series_moteurs = [ns for ns in (_g(m, "num_serie") for m in (moteurs or [])) if ns]
    moteurs_row = ""
    if num_series_moteurs:
        lbl = "N° série moteur" if len(num_series_moteurs) == 1 else "N° série moteurs"
        moteurs_row = (f'<tr><td class="lbl">{lbl}</td>'
                        f'<td colspan="3" style="font-family:monospace">'
                        f'{_esc(", ".join(num_series_moteurs))}</td></tr>')

    ref_int    = _g(affaire, "ref_interne")
    num_cmd    = _g(affaire, "num_commande_client")
    charge     = _g(affaire, "charge_affaire")
    resp_tech  = _g(affaire, "resp_technique")
    date_deb   = _g(affaire, "date_debut")
    date_fat_    = _g(affaire, "date_fat")
    date_fin_fat = _g(affaire, "date_fin_fat")
    date_fin   = _g(affaire, "date_fin_prevue")
    date_clo   = _g(affaire, "date_cloture")
    date_visite_deb  = _g(affaire, "date_visite_appli_debut")
    date_visite_fin  = _g(affaire, "date_visite_appli_fin")
    date_comm_deb    = _g(affaire, "date_commissioning_debut")
    date_comm_fin    = _g(affaire, "date_commissioning_fin")
    description  = _g(affaire, "description")
    commentaires = _g(affaire, "commentaires")
    conditions_reglement = _g(affaire, "conditions_reglement")
    garanties            = _g(affaire, "garanties")

    try:
        interlocuteurs = json.loads(_g(affaire, "interlocuteurs_client", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        interlocuteurs = []
    interlocuteurs = [it for it in interlocuteurs if it.get("nom") or it.get("email")]

    if date_fat_ and date_fin_fat:
        fat_row = (f'<tr><td class="lbl">Début FAT</td><td>{_esc(date_fat_)}</td>'
                   f'<td class="lbl">Fin FAT</td><td>{_esc(date_fin_fat)}</td></tr>')
    elif date_fat_:
        fat_row = f'<tr><td class="lbl">Date FAT</td><td colspan="3">{_esc(date_fat_)}</td></tr>'
    elif date_fin_fat:
        fat_row = f'<tr><td class="lbl">Fin FAT</td><td colspan="3">{_esc(date_fin_fat)}</td></tr>'
    else:
        fat_row = ""

    if date_visite_deb and date_visite_fin:
        visite_row = (f'<tr><td class="lbl">Visite applicative — début</td><td>{_esc(date_visite_deb)}</td>'
                      f'<td class="lbl">Visite applicative — fin</td><td>{_esc(date_visite_fin)}</td></tr>')
    elif date_visite_deb:
        visite_row = f'<tr><td class="lbl">Visite applicative</td><td colspan="3">{_esc(date_visite_deb)}</td></tr>'
    elif date_visite_fin:
        visite_row = f'<tr><td class="lbl">Visite applicative — fin</td><td colspan="3">{_esc(date_visite_fin)}</td></tr>'
    else:
        visite_row = ""

    if date_comm_deb and date_comm_fin:
        commissioning_row = (f'<tr><td class="lbl">Commissioning — début</td><td>{_esc(date_comm_deb)}</td>'
                             f'<td class="lbl">Commissioning — fin</td><td>{_esc(date_comm_fin)}</td></tr>')
    elif date_comm_deb:
        commissioning_row = f'<tr><td class="lbl">Commissioning</td><td colspan="3">{_esc(date_comm_deb)}</td></tr>'
    elif date_comm_fin:
        commissioning_row = f'<tr><td class="lbl">Commissioning — fin</td><td colspan="3">{_esc(date_comm_fin)}</td></tr>'
    else:
        commissioning_row = ""

    client_nom   = (client.get("nom", "") if client else "") or _g(affaire, "client_nom")
    fournisseur  = _g(affaire, "fournisseur")
    ref_fourn    = _g(affaire, "reference_fournisseur")
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

    try:
        lots = json.loads(_g(affaire, "lots_vendus", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        lots = []
    lots = [l for l in lots if l.get("libelle") or l.get("prix_ht")]

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

    # ── Lots vendus / Echéances (PDF complet uniquement) ──
    col_label = "HT" if exo else "TTC"
    ech_section = ""
    if pdf_type != "technique":
        if lots:
            lots_rows = ""
            lots_total = 0.0
            for lot in lots:
                lot_ht = _parse_ht(lot.get("prix_ht")) or 0.0
                lots_total += lot_ht
                lots_rows += f"""
<tr>
  <td style="padding:5px 8px;font-weight:500">{_esc(lot.get('libelle') or '—')}</td>
  <td style="padding:5px 8px;text-align:right">{_fmt_eur(lot_ht)}</td>
</tr>"""
            lots_section = f"""
<div class="section-header section-header-blue">LOTS VENDUS</div>
<table class="data-table">
  <thead><tr><th>Désignation</th><th style="text-align:right;width:30%">Prix&nbsp;HT</th></tr></thead>
  <tbody>{lots_rows}</tbody>
  <tfoot>
    <tr style="background:#002b5c;color:#fff;font-weight:700;font-size:9.5px">
      <td style="padding:5px 8px">Total</td>
      <td style="padding:5px 8px;text-align:right">{_fmt_eur(lots_total)}</td>
    </tr>
  </tfoot>
</table>"""
            ech_blocks = ""
            for lot in lots:
                lot_echeances = lot.get("echeances") or []
                if not lot_echeances:
                    continue
                lot_ht  = _parse_ht(lot.get("prix_ht"))
                lot_tva = (lot_ht * 0.20) if (lot_ht is not None and not exo) else 0.0
                lot_ttc = (lot_ht + lot_tva) if lot_ht is not None else None
                ech_blocks += f"""
<div style="margin-top:8px;font-size:10px;font-weight:700;color:#002b5c">{_esc(lot.get('libelle') or 'Lot')}</div>
{_ech_table_html(lot_echeances, lot_ttc, col_label)}"""
            ech_section = lots_section + (f"""
<div class="section-header section-header-blue" style="margin-top:10px">ÉCHÉANCIER DE FACTURATION (PAR LOT)</div>
{ech_blocks}""" if ech_blocks else "")
        elif echeances:
            ech_section = f"""
<div class="section-header section-header-blue">ÉCHÉANCIER DE FACTURATION</div>
{_ech_table_html(echeances, ttc, col_label)}"""

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
        if ref_fourn:
            fin_rows += f'<tr><td class="lbl">Référence fournisseur</td><td colspan="3">{_esc(ref_fourn)}</td></tr>'

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
  <td style="padding:5px 8px;font-weight:500">{_esc(it.get('nom','')) or '—'}</td>
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
    <td>{_esc(navire) or '—'}{navire_detail}</td>
  </tr>
  <tr>
    <td class="lbl">Référence interne</td>
    <td>{_esc(ref_int) or '—'}</td>
    <td class="lbl">Statut</td>
    <td>{_statut_style(statut)}</td>
  </tr>
  {f'<tr><td class="lbl">N° commande client</td><td colspan="3" style="font-family:monospace">{_esc(num_cmd)}</td></tr>' if num_cmd else ''}
  {moteurs_row}
  <tr>
    <td class="lbl">Date début</td>
    <td>{_esc(date_deb) or '—'}</td>
    <td class="lbl">Date de livraison</td>
    <td>{_esc(date_fin) or '—'}</td>
  </tr>
  {fat_row}
  {visite_row}
  {commissioning_row}
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
                               client: dict | None = None, lot: dict | None = None) -> str:
    """Génère le HTML d'un bon de facturation pour un échelon spécifique.
    Si `lot` est fourni, l'échelon appartient à l'échéancier propre à ce lot
    vendu et le montant se base sur le prix HT du lot (et non sur le prix
    total de l'affaire)."""
    num        = _g(affaire, "num_affaire")
    nom_projet = _g(affaire, "nom_projet")
    navire     = _g(affaire, "navire_machine")
    navire_immat = _g(affaire, "navire_immatriculation")
    navire_port  = _g(affaire, "navire_port_attache")
    navire_detail = "".join(
        f'<br><span style="font-size:8pt;color:#6b7785;font-weight:400">{_esc(v)}</span>'
        for v in [
            navire_immat and f"Immat. : {navire_immat}",
            navire_port and f"Port d'attache : {navire_port}",
        ] if v
    )
    exo        = bool(int(_g(affaire, "exonere_tva", 0) or 0))
    num_cmd    = _g(affaire, "num_commande_client")
    lot_libelle = (lot or {}).get("libelle") or ""
    ht_total   = _parse_ht(lot.get("prix_ht")) if lot else _parse_ht(_g(affaire, "prix_ht"))

    stade      = echelon.get("stade") or f"Échelon {echelon_idx + 1}"
    pourcentage = float(echelon.get("pourcentage") or 0)
    modalite   = _fmt_modalite(echelon)
    is_acompte = "acompte" in stade.lower()
    doc_title  = "Demande d'acompte" if is_acompte else "Bon de facturation"

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
  @bottom-left {{ content: "{doc_title} — {_esc(num)}"; font-size: 8pt; color: #6b7785; }}
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
    </div>
    <div style="text-align:right">
      <div class="doc-title">{doc_title}</div>
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
    {'<div><label>Navire / Machine</label><div class="val">' + _esc(navire) + navire_detail + '</div></div>' if navire else ''}
    {'<div><label>Lot vendu</label><div class="val">' + _esc(lot_libelle) + '</div></div>' if lot_libelle else ''}
    {'<div><label>N° commande client</label><div class="val">' + _esc(num_cmd) + '</div></div>' if num_cmd else ''}
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
        <td>{_esc((lot_libelle or nom_projet) or 'Travaux')}<br>
            <span style="font-size:9pt;color:#6b7785">{_esc(stade)} ({pourcentage:.0f} % {'du lot' if lot_libelle else 'du total'})</span></td>
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
            "nom": "EMERAUDE MOTEURS SYSTÈMES",
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
                  entreprise.get("tel") and f"☎ {entreprise['tel']}"]
        if v
    )

    charge_nom   = _g(bon, "charge_commande_nom")
    charge_email = _g(bon, "charge_commande_email")
    charge_tel   = _g(bon, "charge_commande_tel")
    charge_html = ""
    if charge_nom or charge_email or charge_tel:
        charge_details = "".join(
            f'<div class="detail">{_esc(v)}</div>'
            for v in [charge_email and f"✉ {charge_email}", charge_tel and f"☎ {charge_tel}"]
            if v
        )
        charge_html = f"""<div style="margin-top:8px;padding-top:8px;border-top:1px dashed #d1d9e0">
      <div style="font-size:8pt;text-transform:uppercase;color:#6b7785;letter-spacing:.5px">Chargé de commande</div>
      <div style="font-size:10pt;font-weight:600;color:#1e3a5f;margin-top:2px">{_esc(charge_nom) or '—'}</div>
      {charge_details}
    </div>"""

    fourn_nom      = _g(bon, "fournisseur_nom")
    ref_fourn      = _g(bon, "reference_fournisseur")
    fourn_cp_ville = " ".join(v for v in [_g(bon, "fournisseur_code_postal"), _g(bon, "fournisseur_ville")] if v)
    fourn_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [_g(bon, "fournisseur_rue"),
                  fourn_cp_ville,
                  _g(bon, "fournisseur_pays"),
                  _g(bon, "fournisseur_contact") and f"Contact : {_g(bon, 'fournisseur_contact')}",
                  _g(bon, "fournisseur_email") and f"✉ {_g(bon, 'fournisseur_email')}",
                  _g(bon, "fournisseur_tel") and f"☎ {_g(bon, 'fournisseur_tel')}"]
        if v
    )

    livraison_nom    = _g(bon, "livraison_nom")
    livraison_cp_ville = " ".join(v for v in [_g(bon, "livraison_code_postal"), _g(bon, "livraison_ville")] if v)
    livraison_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [_g(bon, "livraison_rue"), livraison_cp_ville, _g(bon, "livraison_pays")]
        if v
    )

    date_emission = datetime.now().strftime("%d/%m/%Y")
    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="{_esc(entreprise.get("nom",""))}" style="max-width:240px;max-height:110px;">'
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

    frais_port = float(_g(bon, "frais_port", 0) or 0)
    sous_total_lignes_ht = total_ht
    total_ht += frais_port
    tva = 0.0 if exo else round(total_ht * 0.20, 2)
    total_ttc = total_ht if exo else total_ht + tva

    frais_port_row = ""
    if frais_port:
        frais_port_row = f"""<tr class="totals-row"><td colspan="4">Sous-total pièces HT</td>
      <td style="text-align:right">{_fmt_eur(sous_total_lignes_ht)}</td></tr>
      <tr class="totals-row" style="background:#f8faff"><td colspan="4" style="font-style:italic;color:#4b5563">Frais de port HT (hors pièces)</td>
      <td style="text-align:right;font-style:italic;color:#4b5563">{_fmt_eur(frais_port)}</td></tr>"""

    sous_total_row = f"""<tr class="totals-row"><td colspan="4" style="font-weight:600">Total HT</td>
      <td style="text-align:right;font-weight:600">{_fmt_eur(total_ht)}</td></tr>"""
    tva_row = ""
    if not exo:
        tva_row = f"""<tr class="totals-row"><td colspan="4">TVA 20 %</td>
          <td style="text-align:right">{_fmt_eur(tva)}</td></tr>"""
    exo_row = ""
    if exo:
        exo_row = '<tr class="totals-row"><td colspan="5" style="color:#d97706;font-size:9pt">⚠️ TVA exonérée — justificatif requis</td></tr>'

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
.parties {{ display: flex; gap: 12px; margin-bottom: 16px; }}
.party-box {{ flex: 1; min-width: 0; border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 12px; }}
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
table.montants tr {{ break-inside: avoid; }}
table.montants tr.totals-row td {{ background: #eff6ff; font-weight: 700; font-size: 11pt; border-bottom: none; border-top: 2px solid #002b5c; break-inside: avoid; }}
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
      {charge_html}
    </div>
    <div class="party-box">
      <h3>Fournisseur</h3>
      <div class="name">{_esc(fourn_nom or '—')}</div>
      {fourn_lines}
    </div>
    <div class="party-box">
      <h3>Livraison</h3>
      <div class="name">{_esc(livraison_nom or '—')}</div>
      {livraison_lines}
    </div>
  </div>

  <div class="objet-box">
    <div>
      <label>Affaire</label>
      <div class="val">{_esc(num_affaire or '—')}{' — ' + _esc(nom_projet) if nom_projet else ''}</div>
    </div>
    {'<div><label>Référence fournisseur</label><div class="val">' + _esc(ref_fourn) + '</div></div>' if ref_fourn else ''}
    {'<div><label>Date de commande</label><div class="val">' + _esc(date_cmd) + '</div></div>' if date_cmd else ''}
    {'<div><label>Livraison prévue</label><div class="val">' + _esc(date_liv) + '</div></div>' if date_liv else ''}
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
      {frais_port_row}
      {sous_total_row}
      {tva_row}
      {exo_row}
      <tr class="totals-row total-row">
        <td colspan="4">Total {"HT (exonéré)" if exo else "TTC"}</td>
        <td style="text-align:right">{_fmt_eur(total_ttc)}</td>
      </tr>
    </tbody>
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


def build_devis_html(devis: dict, lignes: list, client: dict | None = None,
                     moteur: dict | None = None,
                     moteurs_supplementaires: list | None = None) -> str:
    """Génère le HTML d'un devis client maritime (chiffré, lignes avec remise),
    avec mentions légales et conditions particulières d'intervention maritime."""
    try:
        from ems_api.config import settings
        entreprise = settings.ENTREPRISE
    except ImportError:
        entreprise = {
            "nom": "EMERAUDE MOTEURS SYSTÈMES",
            "forme_juridique": "SARL",
            "capital": "50 000",
            "adresse_1": "9 Rue d'Armorique – 35540 Miniac Morvan",
            "adresse_2": "",
            "tel": "02.99.19.01.99",
            "fax": "",
            "email": "service.technique@emeraudemoteurs.com",
            "siret": "431 976 729 00035",
            "rcs_ville": "Saint-Malo",
            "rcs_numero": "431 976 729",
            "tva": "FR 14 431 976 729",
            "site": "www.emeraudemoteurs.com",
            "iban": "[•]",
            "assurance_rc_assureur": "[•]",
            "assurance_rc_police": "[•]",
            "assurance_rc_couverture": "[•]",
        }

    def _e(key, default="[•]"):
        return entreprise.get(key) or default

    num_devis     = _g(devis, "num_devis")
    objet         = _g(devis, "objet")
    description   = _g(devis, "description")
    demande_client = _g(devis, "demande_client")
    date_devis    = _g(devis, "date_devis")
    date_validite = _g(devis, "date_validite")
    conditions    = _g(devis, "conditions")
    notes         = _g(devis, "notes")
    exo           = bool(int(_g(devis, "exonere_tva", 0) or 0))

    navire_nom      = _g(devis, "navire_nom")
    navire_immat    = _g(devis, "navire_immatriculation")
    navire_pavillon = _g(devis, "navire_pavillon")
    navire_port     = _g(devis, "navire_port_attache")
    navire_usage    = _g(devis, "navire_type_usage")
    lieu_intervention = _g(devis, "lieu_intervention")
    has_navire = bool(navire_nom or navire_immat or navire_pavillon or navire_port or navire_usage)

    emetteur_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [
            f"{_e('forme_juridique')} au capital de {_e('capital')} €",
            entreprise.get("adresse_1", ""), entreprise.get("adresse_2", ""),
            f"SIRET : {_e('siret')} – RCS/RM : {_e('rcs_ville')} {_e('rcs_numero')}",
            f"TVA intracommunautaire : {_e('tva')}",
            (entreprise.get("tel") or entreprise.get("email")) and
                f"Tél. : {entreprise.get('tel') or '[•]'} – Courriel : {entreprise.get('email') or '[•]'}",
        ]
        if v
    )

    client_nom   = _g(client, "nom")
    client_lines = "".join(
        f'<div class="detail">{_esc(v)}</div>'
        for v in [_g(client, "adresse"),
                  _g(client, "contact") and f"Représenté par : {_g(client, 'contact')}",
                  _g(client, "email") and f"✉ {_g(client, 'email')}",
                  _g(client, "telephone") and f"☎ {_g(client, 'telephone')}"]
        if v
    )

    dest_nom = _g(devis, "destinataire_nom")
    dest_email = _g(devis, "destinataire_email")
    dest_tel = _g(devis, "destinataire_telephone")
    destinataire_box = ""
    if dest_nom:
        dest_lines = "".join(
            f'<div class="detail">{_esc(v)}</div>'
            for v in [dest_email and f"✉ {dest_email}",
                      dest_tel and f"☎ {dest_tel}"]
            if v
        )
        destinataire_box = (
            '\n    <div class="party-box">\n'
            '      <h3>Destinataire du devis</h3>\n'
            f'      <div class="name">{_esc(dest_nom)}</div>\n'
            f'      {dest_lines}\n'
            '    </div>'
        )

    def _serie_line(m, idx=None):
        ns = _g(m, "num_serie")
        if not ns:
            return ""
        return f"N° série moteur {idx} : {ns}" if idx else f"N° série moteur : {ns}"

    eq_lines = []
    if moteur:
        line = _serie_line(moteur, 1 if moteurs_supplementaires else None)
        if line:
            eq_lines.append(line)
    for i, em in enumerate(moteurs_supplementaires or [], start=2):
        line = _serie_line(em, i)
        if line:
            eq_lines.append(line)

    if has_navire:
        navire_lines = "".join(
            f'<div class="detail">{_esc(v)}</div>'
            for v in [
                navire_immat and f"Immatriculation / n° francisation : {navire_immat}",
                (navire_pavillon or navire_port) and
                    f"Pavillon : {navire_pavillon or '—'} – Port d'attache : {navire_port or '—'}",
                navire_usage and f"Type / usage : {navire_usage}",
                lieu_intervention and f"Lieu d'intervention : {lieu_intervention}",
                *eq_lines,
            ]
            if v
        )
        navire_box = (
            '\n    <div class="party-box">\n'
            '      <h3>Navire concerné</h3>\n'
            f'      <div class="name">{_esc(navire_nom or "—")}</div>\n'
            f'      {navire_lines}\n'
            '    </div>'
        )
    elif eq_lines:
        navire_box = (
            '\n    <div class="party-box">\n'
            '      <h3>Équipement</h3>\n'
            f'      <div class="name">{_esc(eq_lines[0])}</div>\n'
            + "".join(f'      <div class="detail">{_esc(l)}</div>\n' for l in eq_lines[1:])
            + '    </div>'
        )
    else:
        navire_box = ""

    date_emission = datetime.now().strftime("%d/%m/%Y")
    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="{_esc(entreprise.get("nom",""))}" style="max-width:220px;max-height:100px;">'
                 if logo_uri else f'<div style="font-size:20px;font-weight:bold;color:#002b5c">{_esc(entreprise.get("nom",""))}</div>')

    rows = ""
    total_ht = 0.0
    for l in lignes:
        qte    = float(_g(l, "quantite", 0) or 0)
        pu     = float(_g(l, "prix_unitaire", 0) or 0)
        remise = float(_g(l, "remise_pct", 0) or 0)
        montant = float(_g(l, "montant_ligne", qte * pu * (1 - remise / 100)) or 0)
        total_ht += montant
        rows += f"""<tr>
            <td>{_esc(_g(l, "reference"))}</td>
            <td>{_esc(_g(l, "libelle"))}</td>
            <td style="text-align:center">{qte:g}</td>
            <td style="text-align:right">{_fmt_eur(pu)}</td>
            <td style="text-align:center">{f'{remise:g} %' if remise else '—'}</td>
            <td style="text-align:right">{_fmt_eur(montant)}</td>
          </tr>"""

    tva = 0.0 if exo else round(total_ht * 0.20, 2)
    total_ttc = total_ht if exo else total_ht + tva

    sous_total_row = f"""<tr class="totals-row"><td colspan="5" style="font-weight:600">Total HT</td>
      <td style="text-align:right;font-weight:600">{_fmt_eur(total_ht)}</td></tr>"""
    tva_row = ""
    if not exo:
        tva_row = f"""<tr class="totals-row"><td colspan="5">TVA 20 %</td>
          <td style="text-align:right">{_fmt_eur(tva)}</td></tr>"""
    exo_row = ""
    if exo:
        exo_row = '<tr class="totals-row"><td colspan="6" style="color:#d97706;font-size:9pt">⚠️ TVA exonérée — justificatif requis (art. 262 II 2° CGI)</td></tr>'

    validite_html = ""
    if date_validite:
        validite_html = (
            '<div style="margin-top:4px;font-size:9pt;color:#6b7785">'
            f"Validité de l'offre : jusqu'au {_esc(date_validite)}</div>"
        )

    description_html = ""
    if description:
        description_html = f'<div style="margin-top:8px;font-size:9.5pt;white-space:pre-wrap">{_esc(description)}</div>'

    demande_client_html = ""
    if demande_client:
        demande_client_html = (
            '\n  <div class="keep-together">\n'
            '    <div class="section-header">1. Demande client</div>\n'
            '    <div class="section-body section-body-flat" '
            f'style="font-size:9.5pt;white-space:pre-wrap">{_esc(demande_client)}</div>\n'
            '  </div>'
        )

    conditions_html = _esc(conditions) if conditions else "À convenir"

    notes_html = ""
    if notes:
        notes_html = (
            '<div class="keep-together">\n'
            '    <div class="section-header">Notes internes</div>\n'
            f'    <div class="section-body section-body-flat" style="font-size:9pt;color:#4b5563;white-space:pre-wrap">{_esc(notes)}</div>\n'
            '  </div>'
        )

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<style>
@page {{
  size: A4;
  margin: 12mm 10mm 20mm 10mm;
  @bottom-left {{ content: "Devis — {_esc(num_devis)}"; font-size: 8pt; color: #6b7785; }}
  @bottom-right {{ content: "Page " counter(page) " / " counter(pages); font-size: 8pt; color: #6b7785; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; font-size: 10pt; color: #1a2a3a; }}
.header {{ display: flex; justify-content: space-between; align-items: flex-start;
           margin-bottom: 16px; border-bottom: 3px solid #002b5c; padding-bottom: 14px; }}
.doc-title {{ font-size: 18pt; font-weight: bold; color: #002b5c; text-transform: uppercase; }}
.ref-box {{ background: #002b5c; color: #fff; padding: 8px 16px; border-radius: 6px; text-align: right; }}
.ref-box .ref-label {{ font-size: 8pt; opacity: .8; }}
.ref-box .ref-num {{ font-size: 13pt; font-weight: bold; }}
.parties {{ display: flex; gap: 12px; margin-bottom: 16px; page-break-inside: avoid; break-inside: avoid; }}
.party-box {{ flex: 1; min-width: 0; border: 1px solid #d1d9e0; border-radius: 6px; padding: 10px 12px; }}
.party-box h3 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 6px; }}
.party-box .name {{ font-size: 11pt; font-weight: bold; color: #002b5c; }}
.detail {{ font-size: 9pt; color: #4b5563; margin-top: 3px; }}
.section-header {{
  display: block; padding: 5px 12px; font-size: 10.5pt; font-weight: 700;
  color: #fff; background: #002b5c; margin: 16px 0 0; border-radius: 4px 4px 0 0;
  letter-spacing: .3px; text-transform: uppercase;
  page-break-after: avoid; break-after: avoid;
}}
/* La partie devis (sections 1 à 4, longueur variable selon le devis) est
   ainsi toujours séparée des conditions générales (texte fixe) : ces
   dernières démarrent systématiquement en haut d'une page, ce qui rend leur
   pagination (et donc la place disponible pour la signature) stable d'un
   devis à l'autre. */
.conditions-page-break {{ page-break-before: always; break-before: page; }}
.section-body {{
  border: 1px solid #d1d9e0; border-top: none; border-radius: 0 0 6px 6px;
  padding: 10px 14px; font-size: 9.5pt; line-height: 1.6;
}}
/* Sans cadre : pour les sections longues qui s'étendent sur plusieurs pages
   (ex. Conditions générales), un encart bordé y dessinerait une barre grise
   en haut et en bas de chaque page — on retire donc le cadre ici. */
.section-body-flat {{ border: none; border-radius: 0; padding: 10px 0 0; }}
/* Encart mis en avant : distingue visuellement les modalités de paiement
   (montants, IBAN, pénalités) du texte courant des conditions générales,
   pour que le client les repère au premier coup d'œil. */
.payment-highlight {{
  background: #f8faff; border: 1px solid #bfdbfe; border-left: 4px solid #002b5c;
  border-radius: 6px; padding: 10px 14px 10px 12px;
}}
/* Sections courtes : l'en-tête et son contenu ne doivent jamais être séparés
   par un saut de page (utilisé pour Libellé de l'intervention, Demande client,
   Acceptation du devis + signatures, Notes internes, Modalités de paiement). Les longues
   sections (prestations, conditions particulières maritimes) restent
   scindables entre pages, mais protègent chaque ligne/clause individuellement
   (cf. table.montants tr et .clause ci-dessous) pour ne jamais couper un
   paragraphe en plein milieu. */
.keep-together {{ page-break-inside: avoid; break-inside: avoid; }}
table.montants {{ width: 100%; border-collapse: collapse; margin-bottom: 0; }}
table.montants th {{ background: #002b5c; color: #fff; padding: 7px 10px; font-size: 8.5pt; font-weight: 600; text-align: left; }}
table.montants td {{ padding: 6px 10px; font-size: 8.5pt; border-bottom: 1px solid #e5eaf0; }}
table.montants tr {{ break-inside: avoid; }}
table.montants tr.totals-row td {{ background: #eff6ff; font-weight: 700; font-size: 10pt; border-bottom: none; border-top: 2px solid #002b5c; break-inside: avoid; }}
table.montants thead {{ display: table-header-group; }}
/* Annexe tarifaire : table longue, autorisée à se répartir sur plusieurs
   pages (contrairement à .clause, non scindable) — l'en-tête se répète et
   aucune ligne n'est jamais coupée en deux. */
.annexe-tarifaire {{ margin-top: 8px; }}
.annexe-tarifaire h5 {{ font-size: 9.5pt; color: #002b5c; margin-bottom: 2px; page-break-after: avoid; break-after: avoid; }}
/* Tableau de facturation (annexe tarifaire) : toujours sur sa propre page
   complète, jamais scindé — dimensionné (police/paddings) pour que les 23
   lignes + en-tête tiennent sur une seule page A4. */
.annexe-tarifaire-page {{ page-break-before: always; break-before: page; }}
.annexe-tarifaire-page table.montants th,
.annexe-tarifaire-page table.montants td {{ padding: 5px 10px; font-size: 8.5pt; }}
.annexe-tarifaire-page table.montants td[colspan] {{ padding-top: 4px; padding-bottom: 4px; }}
table.annexe-table thead {{ display: table-header-group; }}
table.annexe-table tbody tr {{ break-inside: avoid; page-break-inside: avoid; }}
table.annexe-table {{ orphans: 3; widows: 3; }}
.tva-note {{ font-size: 8pt; color: #6b7785; margin: 6px 0 0; font-style: italic; }}
.clause {{ margin-top: 6px; page-break-inside: avoid; break-inside: avoid; }}
.clause:first-child {{ margin-top: 0; }}
.clause h5 {{ font-size: 9pt; color: #002b5c; margin-bottom: 2px; }}
.clause p {{ font-size: 8.3pt; line-height: 1.4; color: #3a4552; text-align: justify; }}
.accord-box {{ display: flex; gap: 24px; margin-top: 16px; page-break-inside: avoid; break-inside: avoid; }}
.accord-box .accord-cell {{ flex: 1; border: 1px solid #d1d9e0; border-radius: 6px; padding: 14px 16px; min-height: 90px; }}
.accord-box h4 {{ font-size: 8pt; text-transform: uppercase; color: #6b7785; letter-spacing: .5px; margin-bottom: 30px; }}
/* Signatures : pas de saut de page forcé, pour qu'elles remontent sur la
   page précédente (fin des conditions générales) dès qu'il reste la place.
   L'ensemble (texte + accord-box + pied de page légal) reste néanmoins
   groupé et ne peut jamais être scindé entre deux pages. */
.signature-page {{ page-break-inside: avoid; break-inside: avoid; }}
.footer {{
  border-top: 2px solid #002b5c; margin-top: 16px; padding-top: 8px;
  font-size: 8pt; color: #6b7785; text-align: center; line-height: 1.7;
  page-break-inside: avoid; break-inside: avoid;
}}
.footer strong {{ color: #002b5c; }}
</style>
</head>
<body>

  <div class="header">
    <div>
      {logo_html}
      {emetteur_lines}
    </div>
    <div style="text-align:right">
      <div class="doc-title">Devis</div>
      <div style="margin-top:10px" class="ref-box">
        <div class="ref-label">N° Devis</div>
        <div class="ref-num">{_esc(num_devis)}</div>
      </div>
      <div style="margin-top:6px;font-size:9pt;color:#6b7785">Date d'établissement : {_esc(date_devis or date_emission)}</div>
      {validite_html}
    </div>
  </div>

  <div class="parties">
    <div class="party-box">
      <h3>Client (professionnel)</h3>
      <div class="name">{_esc(client_nom or '—')}</div>
      {client_lines}
    </div>
    {destinataire_box}
    {navire_box}
  </div>

  {demande_client_html}
  <div class="keep-together">
    <div class="section-header">2. Libellé de l'intervention</div>
    <div class="section-body section-body-flat">
      <div style="font-size:11pt;font-weight:600;color:#1e3a5f">{_esc(objet or '—')}</div>
      {description_html}
    </div>
  </div>

  <div class="section-header">3. Objet et détail des prestations</div>
  <div class="section-body" style="padding:0;border-radius:0 0 6px 6px;overflow:hidden">
    <table class="montants">
      <thead>
        <tr>
          <th style="width:14%">Référence</th>
          <th style="width:32%">Désignation</th>
          <th style="width:8%;text-align:center">Qté</th>
          <th style="width:15%;text-align:right">PU HT</th>
          <th style="width:11%;text-align:center">Remise</th>
          <th style="width:20%;text-align:right">Montant HT</th>
        </tr>
      </thead>
      <tbody>
        {rows}
        {sous_total_row}
        {tva_row}
        {exo_row}
        <tr class="totals-row total-row">
          <td colspan="5">Total {"HT (exonéré)" if exo else "TTC"}</td>
          <td style="text-align:right">{_fmt_eur(total_ttc)}</td>
        </tr>
      </tbody>
    </table>
  </div>

  <div class="keep-together">
    <div class="section-header">4. Modalités de paiement</div>
    <div class="section-body payment-highlight">
      <div style="font-size:10.5pt;white-space:pre-wrap">{conditions_html}</div>
    </div>
  </div>

  {notes_html}

  <div class="section-header conditions-page-break">5. Conditions générales de prestations de services et d'interventions</div>
  <div class="section-body section-body-flat">
    <div style="font-size:8pt;color:#6b7785;font-style:italic;margin-bottom:8px">Version 2026.01 – Applicable à compter du 10/08/2026</div>

    <div class="clause">
      <h5>Article 1 – Champ d'application – Hiérarchie contractuelle</h5>
      <p>Les présentes conditions générales de prestations de services (les « Conditions Services ») s'appliquent à toutes les prestations de services réalisées par {_esc(entreprise.get("nom",""))} (« EMS ») au profit de ses clients professionnels (le « Client ») : diagnostic, dépannage, réparation, révision, entretien, maintenance préventive ou corrective, installation, mise en service, réglage et essais de moteurs, équipements et systèmes, que ces prestations soient réalisées dans les ateliers d'EMS ou sur site (y compris, le cas échéant, à bord de navires ou sur les installations du Client).</p>
      <p>Toute demande d'intervention, acceptation de devis ou signature d'un ordre d'intervention emporte adhésion pleine et entière du Client aux présentes.</p>
      <p>La relation contractuelle entre EMS et le Client est régie, par ordre de priorité décroissant, par les documents suivants : le devis, l'ordre d'intervention et, le cas échéant, les conditions particulières expressément acceptées par EMS ; les présentes Conditions Services, pour l'ensemble des prestations de diagnostic, dépannage, réparation, révision, entretien, maintenance, installation, mise en service, réglage et essais ; les Conditions Générales de Vente d'EMS, pour la fourniture des pièces, matériels, ingrédients et consommables utilisés ou vendus dans le cadre de l'intervention.</p>
      <p>En cas de contradiction entre plusieurs documents contractuels, le document de rang supérieur prévaut. Les Conditions Services prévalent sur les Conditions Générales de Vente pour tout ce qui concerne l'exécution des prestations, tandis que les Conditions Générales de Vente demeurent applicables à la vente et à la fourniture des pièces et matériels.</p>
      <p>Aucun document, condition générale ou condition particulière émanant du Client ne fait partie du contrat, sauf acceptation expresse et écrite d'EMS.</p>
    </div>

    <div class="clause">
      <h5>Article 2 – Devis, ordres d'intervention et diagnostic</h5>
      <p>Les interventions font l'objet, selon leur nature et leur urgence, d'un devis préalable ou d'un ordre d'intervention signé par le Client. Sauf stipulation contraire, les devis sont valables trente (30) jours et sont établis sur la base des informations communiquées par le Client et, le cas échéant, d'un examen sommaire du matériel.</p>
      <p>Lorsque l'établissement du devis nécessite un démontage, une expertise ou un diagnostic, ces opérations sont facturées au tarif en vigueur, même si le devis n'est pas suivi d'une commande. En cas d'acceptation du devis, le coût du diagnostic pourra être déduit du montant de l'intervention si le devis le prévoit. Si, en cours d'intervention, des travaux supplémentaires non prévisibles s'avèrent nécessaires, EMS en informe le Client et recueille son accord (écrit, ou verbal confirmé par écrit) avant de les exécuter, sauf urgence tenant à la sécurité des personnes ou des biens.</p>
      <p>À défaut d'acceptation du devis dans le délai de validité, ou en cas de refus des travaux, le matériel démonté pour diagnostic est restitué en l'état, remonté sommairement sans garantie de fonctionnement, les frais de diagnostic et de remontage restant dus.</p>
    </div>

    <div class="clause">
      <h5>Article 3 – Prix et facturation des interventions</h5>
      <p><strong>3.1 Tarifs.</strong> Les prestations sont facturées, selon le cas, au forfait défini au devis ou en régie, sur la base des taux et forfaits figurant au tableau des coûts des prestations annexé aux présentes (l'« Annexe Tarifaire »), du temps passé (y compris temps de trajet), des frais de déplacement, de séjour et de transport, ainsi que des pièces, ingrédients et consommables utilisés.</p>
      <p>L'Annexe Tarifaire est révisée périodiquement par EMS, en principe une à deux fois par an. Les tarifs applicables sont ceux de l'Annexe Tarifaire en vigueur à la date de la demande d'intervention ou, pour les interventions faisant l'objet d'un devis, ceux du devis accepté pendant sa durée de validité. La version en vigueur de l'Annexe Tarifaire est communiquée au Client sur simple demande et jointe aux devis.</p>
      <p><strong>3.2 Majorations.</strong> Les interventions effectuées à la demande du Client en dehors des horaires normaux d'ouverture d'EMS, en urgence, de nuit, le samedi, le dimanche ou un jour férié, font l'objet des majorations prévues à l'Annexe Tarifaire.</p>
      <p><strong>3.3 Temps d'attente et annulation.</strong> Tout temps d'attente imputable au Client (matériel inaccessible, non consigné, absence d'interlocuteur, autorisations manquantes) est facturé au taux horaire en vigueur. Toute intervention annulée ou reportée par le Client moins de quarante-huit (48) heures ouvrées avant la date convenue pourra donner lieu à la facturation des frais engagés et d'une indemnité forfaitaire de 150 € ou égale à 10 % du montant du devis.</p>
    </div>

    <div class="clause">
      <h5>Article 4 – Obligations du Client</h5>
      <p>Le Client s'engage à : (i) communiquer à EMS, préalablement à l'intervention, toutes informations utiles sur le matériel (historique, pannes, modifications, documentation technique) et sur les conditions d'accès et de sécurité du site ; (ii) assurer un libre accès au matériel, le rendre disponible, accessible, propre, dégagé et, le cas échéant, consigné (électriquement, mécaniquement, hydrauliquement) conformément à la réglementation ; (iii) fournir les moyens d'accès, de levage et de manutention appropriés lorsque l'intervention le nécessite, ces moyens demeurant sous sa responsabilité ; (iv) respecter et faire respecter les règles d'hygiène et de sécurité applicables sur son site et établir avec EMS, lorsque la réglementation l'exige, un plan de prévention (articles R.4512-6 et suivants du Code du travail) ; (v) désigner un interlocuteur habilité présent ou joignable pendant l'intervention.</p>
      <p>Tout retard, surcoût ou impossibilité d'exécution résultant du non-respect de ces obligations est à la charge du Client. EMS pourra suspendre ou refuser toute intervention si les conditions de sécurité ne sont pas réunies, sans que sa responsabilité puisse être engagée.</p>
    </div>

    <div class="clause">
      <h5>Article 5 – Exécution des prestations</h5>
      <p>EMS exécute les prestations conformément aux règles de l'art et est tenue, sauf stipulation expresse contraire, à une obligation de moyens. Les délais d'intervention sont communiqués à titre indicatif ; leur dépassement ne peut donner lieu ni à pénalité, ni à indemnité, ni à annulation de la commande, sauf accord écrit contraire.</p>
      <p>EMS est libre du choix de ses intervenants et peut sous-traiter tout ou partie des prestations sous sa responsabilité. Les essais et mises en service sont réalisés en présence du Client ou de son représentant ; à défaut, ils sont réputés effectués contradictoirement.</p>
    </div>

    <div class="clause">
      <h5>Article 6 – Interventions à bord de navires – Garde juridique du navire</h5>
      <p>Lorsque l'intervention est réalisée à bord d'un navire, quel que soit le lieu où celui-ci se trouve (à quai, au mouillage, en cale sèche, sur terre-plein ou en cours d'essais en mer), le navire, ses apparaux, ses équipements et sa cargaison demeurent, pendant toute la durée de l'intervention, la propriété exclusive du Client et restent placés sous sa garde juridique, sa direction et sa responsabilité, ainsi que, le cas échéant, sous l'autorité de son capitaine. L'intervention d'EMS, qui porte exclusivement sur les moteurs, équipements et systèmes objets de la commande, n'emporte en aucun cas transfert de la garde du navire au sens de l'article 1242 du Code civil, ni constitution d'un dépôt, y compris lorsque l'intervention se déroule en l'absence du Client, de son équipage ou de tout représentant à bord.</p>
      <p>Le Client, en sa qualité de propriétaire ou d'armateur, conserve à sa charge : la sécurité et le maintien en état du navire (amarrage, stabilité, veille, prévention des voies d'eau et de l'incendie), l'obtention des autorisations nécessaires auprès des autorités portuaires ou maritimes, ainsi que l'assurance du navire (corps et machines) et de sa responsabilité civile, pour des montants suffisants, pendant toute la durée de l'intervention. Les essais à quai et en mer sont réalisés sous la seule autorité, direction et responsabilité du Client et de son capitaine, le personnel d'EMS présent à bord n'intervenant qu'en qualité d'exécutant technique des travaux commandés. Le Client renonce, et se porte fort de la renonciation de ses assureurs, à tout recours contre EMS et ses assureurs pour les dommages subis par le navire qui ne résulteraient pas directement d'une faute prouvée d'EMS dans l'exécution des travaux commandés.</p>
    </div>

    <div class="clause">
      <h5>Article 7 – Matériel confié – dépôt en atelier</h5>
      <p>Le matériel confié à EMS pour diagnostic ou réparation voyage aux frais et risques du Client, à l'aller comme au retour. Pendant sa présence en atelier, il est couvert par l'assurance d'EMS dans les limites de ses polices ; il appartient au Client d'assurer les risques excédant ces limites ainsi que la valeur de son matériel.</p>
      <p>Le Client est informé, conformément à la loi du 31 décembre 1903 relative à la vente de certains objets abandonnés, que tout matériel non retiré dans un délai d'un (1) an à compter de la notification de la mise à disposition pourra être vendu dans les conditions prévues par ladite loi, le produit de la vente étant affecté au paiement des sommes dues à EMS. Des frais de gardiennage de 50 € par jour pourront être facturés à compter du trentième (30e) jour suivant la mise à disposition du matériel réparé.</p>
    </div>

    <div class="clause">
      <h5>Article 8 – Réception des travaux</h5>
      <p>À l'issue de l'intervention, un rapport d'intervention, bon de travail ou procès-verbal d'essais (le « Bon d'Intervention ») est présenté à la signature du Client ou de son représentant ; sa signature vaut réception des travaux.</p>
      <p><strong>8.1 Absence du Client lors de l'intervention.</strong> Le Client est informé que certaines interventions, notamment à bord de navires ou sur des installations non gardées, peuvent être réalisées en son absence ou en l'absence de tout représentant. Dans ce cas, le Bon d'Intervention est établi par le technicien d'EMS, porte la mention expresse de l'absence du Client au moment de la signature, et est adressé au Client par courrier électronique, au moyen de l'outil d'envoi dématérialisé d'EMS, à l'adresse électronique communiquée par le Client lors de la commande ou figurant dans ses documents commerciaux. Le Client s'engage à communiquer une adresse électronique valide, à la maintenir à jour et à consulter régulièrement sa messagerie ; l'envoi à cette adresse vaut notification valable du Bon d'Intervention.</p>
      <p><strong>8.2 Réserves et acceptation tacite.</strong> Faute de réserves écrites notifiées à EMS dans les quarante-huit (48) heures suivantes, selon le cas, la fin de l'intervention signée contradictoirement, la remise du matériel réparé ou l'envoi du Bon d'Intervention par courrier électronique, les travaux sont réputés réceptionnés sans réserve. Il en est de même en cas de remise en exploitation du matériel ou d'appareillage du navire postérieurement à l'intervention. Les parties conviennent que le Bon d'Intervention établi et transmis dans les conditions ci-dessus, ainsi que les journaux d'envoi de l'outil de dématérialisation d'EMS (horodatage, adresse destinataire), font preuve entre elles de la réalité, de la consistance et de la date des travaux ainsi que de leur notification, conformément aux articles 1366 et suivants du Code civil.</p>
    </div>

    <div class="clause">
      <h5>Article 9 – Paiement</h5>
      <p><strong>9.1 Modalités et délais.</strong> Sauf convention contraire, les factures sont payables à trente (30) jours à compter de leur date d'émission, sans pouvoir dépasser les plafonds de l'article L.441-10 du Code de commerce (60 jours date de facture ou 45 jours fin de mois). EMS peut exiger un acompte à la commande et, pour les interventions importantes, des facturations intermédiaires à l'avancement. Les conditions de règlement figurant sur les factures sont réputées non négociables.</p>
      <p><strong>9.2 Paiement entre les mains du factor – subrogation.</strong> EMS a conclu un contrat d'affacturage. Lorsque la facture porte la mention de subrogation au profit du factor, seul le paiement effectué directement entre les mains de celui-ci est libératoire ; tout paiement effectué entre les mains d'EMS en violation de cette mention n'aura pas d'effet libératoire à l'égard du factor.</p>
      <p><strong>9.3 Retard de paiement.</strong> Tout retard de paiement entraîne de plein droit et sans mise en demeure : l'exigibilité immédiate de toutes les sommes restant dues ; des pénalités de retard au taux de la Banque centrale européenne majoré de dix (10) points de pourcentage (article L.441-10 du Code de commerce) ; une indemnité forfaitaire pour frais de recouvrement de quarante (40) euros par facture (articles L.441-10 et D.441-5 du Code de commerce), sans préjudice d'une indemnisation complémentaire sur justification ; et la faculté pour EMS de suspendre toute intervention en cours ou à venir. Le Client s'interdit toute compensation, retenue ou déduction unilatérale sans l'accord écrit et préalable d'EMS.</p>
      <p><strong>9.4 Droit de rétention.</strong> Conformément aux articles 2286 et suivants du Code civil, EMS pourra exercer un droit de rétention sur tout matériel du Client en sa possession jusqu'au complet paiement des sommes dues au titre des interventions réalisées sur ce matériel.</p>
    </div>

    <div class="clause">
      <h5>Article 10 – Garantie des interventions</h5>
      <p>Les travaux de réparation réalisés par EMS sont garantis contre tout défaut d'exécution pendant une durée de trois (3) mois à compter de la réception des travaux, dans la limite de deux cents (200) heures de fonctionnement du matériel si celles-ci sont atteintes avant l'expiration de ce délai. Cette garantie couvre exclusivement la reprise, dans les ateliers d'EMS ou sur site au choix d'EMS, des travaux reconnus défectueux. Les pièces neuves fournies dans le cadre de l'intervention sont garanties dans les conditions prévues aux Conditions Générales de Vente d'EMS ou, si elle est plus favorable, selon la garantie du fabricant.</p>
      <p>La garantie est exclue : lorsque le défaut résulte d'une usure normale, d'un défaut d'entretien, d'une utilisation anormale ou non conforme aux préconisations du constructeur, d'une intervention d'un tiers ou du Client sur les organes réparés, d'une pièce fournie par le Client, ou d'un cas fortuit ou de force majeure ; lorsque le Client a refusé l'exécution de travaux connexes que EMS lui avait signalés comme nécessaires ; ou lorsque l'intervention a été réalisée en urgence à titre provisoire ou conservatoire, ce dont le Client a été informé. Les frais de transport, de démontage et de remontage sur site, de déplacement et de séjour restent à la charge du Client. La présente garantie ne fait pas obstacle à la garantie légale des vices cachés (articles 1641 et suivants du Code civil) dans les conditions applicables entre professionnels.</p>
    </div>

    <div class="clause">
      <h5>Article 11 – Responsabilité</h5>
      <p>La responsabilité d'EMS est strictement limitée aux obligations définies aux présentes. Sauf faute lourde ou dolosive, la responsabilité d'EMS, toutes causes confondues, est plafonnée au montant hors taxes de l'intervention concernée. EMS ne pourra en aucun cas être tenue à la réparation des dommages indirects ou immatériels subis par le Client, tels que notamment perte de production, perte de profit, perte de chance, perte de données ou préjudice commercial. EMS ne saurait par ailleurs être tenue responsable des dommages ou dysfonctionnements affectant des organes, pièces ou équipements sur lesquels elle n'est pas intervenue, ni des conséquences de défauts préexistants à son intervention.</p>
      <p><strong>11.1 Exclusion des pertes d'exploitation.</strong> Il est expressément convenu qu'EMS ne pourra en aucun cas être tenue de réparer les pertes d'exploitation subies par le Client ou par des tiers, quelle qu'en soit la cause ou l'origine, y compris lorsqu'elles résultent d'un défaut d'exécution, d'un retard d'intervention, d'une immobilisation du matériel pendant ou après l'intervention, d'une reprise de travaux au titre de la garantie ou de l'indisponibilité de pièces de rechange. Par pertes d'exploitation, il faut entendre notamment toute perte de chiffre d'affaires, de marge, de production ou de revenus, tout surcoût d'exploitation, ainsi que les frais d'immobilisation, d'affrètement ou de location de matériel de remplacement et de personnel. Le Client déclare faire son affaire personnelle de l'assurance de ces risques et renonce, ainsi que ses assureurs, à tout recours contre EMS et ses assureurs à ce titre. La présente exclusion constitue une condition essentielle du consentement d'EMS, dont il a été tenu compte dans la détermination du prix.</p>
    </div>

    <div class="clause">
      <h5>Article 12 – Force majeure</h5>
      <p>Conformément à l'article 1218 du Code civil, aucune des parties ne pourra être tenue pour responsable de l'inexécution de ses obligations résultant d'un événement échappant à son contrôle, raisonnablement imprévisible lors de la conclusion du contrat et dont les effets ne peuvent être évités par des mesures appropriées. Sont notamment visés : intempéries exceptionnelles, grèves et conflits du travail (y compris chez les fournisseurs et transporteurs), pénuries de pièces ou de composants, épidémies, décisions des autorités et fait du prince. Si l'empêchement est temporaire, l'exécution est suspendue ; s'il est définitif, le contrat est résolu de plein droit dans les conditions des articles 1351 et 1351-1 du Code civil.</p>
    </div>

    <div class="clause">
      <h5>Article 13 – Données personnelles</h5>
      <p>EMS, agissant en qualité de responsable du traitement, collecte et traite les données à caractère personnel relatives au Client, à ses représentants, salariés et interlocuteurs, nécessaires à la gestion de la relation commerciale.</p>
      <p>Ces données sont traitées aux fins de gestion des demandes, devis, commandes et interventions, de suivi de la relation contractuelle, de facturation, de comptabilité, de recouvrement des créances, de gestion des réclamations et contentieux, ainsi que de respect des obligations légales et réglementaires auxquelles EMS est soumise.</p>
      <p>Les traitements reposent, selon leur finalité, sur l'exécution du contrat ou de mesures précontractuelles, sur le respect des obligations légales d'EMS, ainsi que sur son intérêt légitime à assurer la gestion de sa relation commerciale, le recouvrement de ses créances et la défense de ses droits.</p>
      <p>Les données sont destinées aux membres du personnel d'EMS habilités à les traiter ainsi qu'à ses prestataires, conseils, assureurs, établissements financiers et partenaires chargés du financement ou du recouvrement de ses créances. Elles peuvent notamment être communiquées au factor d'EMS lorsque les créances concernées lui sont transférées. Elles peuvent également être transmises aux autorités administratives ou judiciaires lorsque la loi l'exige.</p>
      <p>Les données sont conservées pendant la durée nécessaire à la gestion de la relation contractuelle, puis archivées pendant les durées requises par les obligations légales applicables et pendant les délais nécessaires à la constatation, à l'exercice ou à la défense des droits d'EMS.</p>
      <p>Dans les conditions prévues par la réglementation applicable, les personnes concernées disposent d'un droit d'accès, de rectification, d'effacement et de limitation du traitement de leurs données, ainsi que d'un droit d'opposition et, lorsqu'il est applicable, d'un droit à la portabilité de leurs données. Ces droits peuvent être exercés en écrivant à EMS. Les personnes concernées disposent également du droit d'introduire une réclamation auprès de la Commission nationale de l'informatique et des libertés.</p>
    </div>

    <div class="clause">
      <h5>Article 14 – Droit applicable et attribution de compétence</h5>
      <p>Les présentes Conditions Services et toutes les prestations qu'elles régissent sont soumises au droit français.</p>
      <p><strong>Il est expressément spécifié que tout litige pouvant se révéler entre EMS et l'un de ses clients au cours d'une opération relevant des présentes, y compris en cas de pluralité de défendeurs ou d'appel en garantie, sera du ressort du seul Tribunal de commerce de {_esc(_e('rcs_ville', 'Saint-Malo'))}.</strong></p>
    </div>
  </div>

  <div class="signature-page">
    <div class="keep-together">
      <div class="section-header">6. Acceptation du devis</div>
      <div class="section-body section-body-flat">
        <p style="font-size:9.5pt;text-align:justify">Le client, professionnel agissant dans le cadre de son activité, reconnaît avoir pris connaissance du présent devis et des conditions particulières ci-dessus, qu'il accepte sans réserve. Le devis signé vaut ordre de réparation / ordre de mission.</p>
      </div>

      <div class="accord-box">
        <div class="accord-cell">
          <h4>Le prestataire — Nom, qualité, date</h4>
          <div style="font-size:9pt;color:#6b7785">Signature et cachet :</div>
        </div>
        <div class="accord-cell">
          <h4>Le client — « Bon pour accord » — Nom, qualité, date</h4>
          <div style="font-size:9pt;color:#6b7785">Signature et cachet :</div>
        </div>
      </div>
    </div>

    <div class="footer">
      {_esc(entreprise.get("nom",""))} – {_esc(_e('forme_juridique'))} au capital de {_esc(_e('capital'))} € –
      SIRET {_esc(_e('siret'))} – RCS {_esc(_e('rcs_ville'))} {_esc(_e('rcs_numero'))} – TVA {_esc(_e('tva'))}<br>
      <em>Document généré le {date_emission}</em>
    </div>
  </div>

  <div class="annexe-tarifaire annexe-tarifaire-page">
    <h5>Annexe tarifaire — Tableau des coûts des prestations</h5>
    <p style="font-size:8.5pt;color:#6b7785;font-style:italic;margin-bottom:6px">Prix hors taxes, en vigueur à la date de la demande d'intervention (article 5.3).</p>
    <table class="montants annexe-table" style="margin-bottom:0">
      <thead>
        <tr><th style="width:60%">Prestation</th><th style="width:15%">Unité</th><th style="width:25%;text-align:right">Prix HT</th></tr>
      </thead>
      <tbody>
        <tr><td colspan="3" style="background:#eff6ff;font-weight:700">Main-d'œuvre</td></tr>
        <tr><td>Taux horaire mécanicien – atelier</td><td>Heure</td><td style="text-align:right">73,16 €</td></tr>
        <tr><td>Taux horaire mécanicien – sur site / à bord</td><td>Heure</td><td style="text-align:right">87,35 €</td></tr>
        <tr><td>Taux horaire technicien spécialisé (électronique, injection, régulation)</td><td>Heure</td><td style="text-align:right">98 €</td></tr>
        <tr><td>Minimum de facturation par intervention</td><td>Forfait</td><td style="text-align:right">150 €</td></tr>
        <tr><td colspan="3" style="background:#eff6ff;font-weight:700">Diagnostic et études</td></tr>
        <tr><td>Diagnostic / expertise en atelier (déductible en cas d'acceptation du devis, si prévu)</td><td>Heure</td><td style="text-align:right">125 €</td></tr>
        <tr><td>Diagnostic sur site / à bord</td><td>Heure</td><td style="text-align:right">125 €</td></tr>
        <tr><td>Étude, expertise technique et établissement des devis</td><td>Heure</td><td style="text-align:right">125 €</td></tr>
        <tr><td colspan="3" style="background:#eff6ff;font-weight:700">Déplacements</td></tr>
        <tr><td>Indemnité kilométrique (véhicule d'intervention)</td><td>Km</td><td style="text-align:right">1,75 €</td></tr>
        <tr><td>Temps de trajet du personnel</td><td>Heure</td><td style="text-align:right">65 €</td></tr>
        <tr><td>Frais de séjour (hôtel + petit déjeuner)</td><td>Jour</td><td style="text-align:right">108 € ou au réel</td></tr>
        <tr><td>Frais de restauration</td><td>Repas</td><td style="text-align:right">23,5 €</td></tr>
        <tr><td colspan="3" style="background:#eff6ff;font-weight:700">Majorations sur taux horaires</td></tr>
        <tr><td>Heures effectuées en dehors des horaires normaux (avant 8 h / après 18 h)</td><td>%</td><td style="text-align:right">+ 25 %</td></tr>
        <tr><td>Heures de nuit (21 h – 6 h)</td><td>%</td><td style="text-align:right">+ 100 %</td></tr>
        <tr><td>Samedi</td><td>%</td><td style="text-align:right">+ 50 %</td></tr>
        <tr><td>Dimanche et jours fériés</td><td>%</td><td style="text-align:right">+ 100 %</td></tr>
        <tr><td colspan="3" style="background:#eff6ff;font-weight:700">Frais divers</td></tr>
        <tr><td>Annulation ou report à moins de 48 h ouvrées (article 5.3)</td><td>Forfait</td><td style="text-align:right">150 €</td></tr>
        <tr><td>Consommables et petit outillage</td><td>% de la MO</td><td style="text-align:right">2 %</td></tr>
        <tr><td>Traitement des déchets (huiles, filtres, fluides)</td><td>Forfait</td><td style="text-align:right">10 €</td></tr>
      </tbody>
    </table>
    <p style="font-size:8pt;color:#6b7785;font-style:italic;margin-top:6px">Les majorations s'appliquent sur les taux horaires de main-d'œuvre et ne se cumulent pas entre elles : en cas de cumul de plusieurs situations, seule la majoration la plus élevée est retenue. Les pièces, ingrédients et consommables sont facturés en sus, au tarif en vigueur au jour de l'intervention. Toute heure entamée est due. Les frais de séjour (hébergement, repas) sont refacturés au réel ou au forfait indiqué au devis.</p>
  </div>

</body>
</html>"""


_MOIS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]

_GANTT_PHASE_FAB_COLOR  = "#2563eb"  # Début → FAT (fabrication / étude)
_GANTT_PHASE_FAT_COLOR  = "#d97706"  # Début FAT → Fin FAT (essai / réception usine)
_GANTT_PHASE_EXP_COLOR  = "#0d9488"  # Fin FAT → Visite applicative / Commissioning (expédition)
_GANTT_PHASE_VISITE_COLOR = "#7c3aed"  # Visite applicative
_GANTT_PHASE_COMM_COLOR   = "#db2777"  # Commissioning
_GANTT_DELIVERY_WEEK_COLOR = "#dc2626"  # Semaine de la date de livraison (toujours en rouge)
_GANTT_PHASE_IDLE_COLOR = "#d1d5db"  # Après livraison, hors visite/commissioning : rien à faire


def _build_planning_section(rows: list, year: int, sans_prix: bool = False) -> str:
    """
    Génère le HTML (bloc titre + légende + tableau) du planning atelier pour
    UNE année donnée. `rows` : liste de dicts déjà filtrés/triés par l'appelant,
    chacun avec num_affaire, client_nom, nom_projet, navire_machine, statut,
    prix_ht, complexite, date_debut, date_fin_prevue (dates au format
    JJ/MM/AAAA) — mêmes champs et même logique de répartition par semaine ISO
    que la vue web. `sans_prix` : masque le CA (colonne "CA HT" + KPI "CA
    planifié"), pour une version atelier du planning ne révélant pas les
    données commerciales.
    """
    from datetime import date as _date, timedelta as _timedelta

    def _parse_fr(s):
        try:
            j, m, a = str(s).split("/")
            return _date(int(a), int(m), int(j))
        except (ValueError, TypeError, AttributeError):
            return None

    nb_weeks = _date(year, 12, 28).isocalendar()[1]

    def _week_monday(w):
        return _date.fromisocalendar(year, w, 1)

    def _next_week_monday(d):
        # Lundi de la semaine ISO suivant celle contenant d : un jalon de fin de
        # phase ne doit écraser la couleur qu'à partir de la semaine suivante
        # (mêmes règles que le Gantt web dans suivi_affaires.html).
        iso_year, iso_week, _ = d.isocalendar()
        return _date.fromisocalendar(iso_year, iso_week, 1) + _timedelta(days=7)

    # Regroupement des colonnes semaine par mois (pour l'en-tête)
    month_groups = []
    for w in range(1, nb_weeks + 1):
        label = _MOIS_FR[_week_monday(w).month - 1]
        if month_groups and month_groups[-1][0] == label:
            month_groups[-1][1] += 1
        else:
            month_groups.append([label, 1])
    month_header = "".join(f'<th colspan="{n}">{_esc(lbl)}</th>' for lbl, n in month_groups)
    week_header = "".join(f'<th class="gw">{w}</th>' for w in range(1, nb_weeks + 1))

    def _chip(label, color):
        return (f'<span class="chip"><span class="chip-dot" style="background:{color}"></span>'
                f'{_esc(label)}</span>')

    _COMPLEXITE_COLORS = {
        "A": ("#d1fae5", "#065f46", "#059669"),
        "B": ("#fef3c7", "#92400e", "#d97706"),
        "C": ("#fee2e2", "#991b1b", "#dc2626"),
    }

    def _complexite_badge(c):
        bg, fg, dot = _COMPLEXITE_COLORS.get(c, ("#f3f4f6", "#9ca3af", "#d1d5db"))
        return (f'<span class="cx-badge" style="background:{bg};color:{fg}">'
                f'<span class="cx-dot" style="background:{dot}"></span>{_esc(c or "—")}</span>')

    total_ca = 0.0
    nb_clients = set()
    body_rows = ""
    for a in rows:
        ds, de = _parse_fr(a.get("date_debut")), _parse_fr(a.get("date_fin_prevue"))
        if not ds or not de or de < ds:
            continue
        statut = a.get("statut") or ""
        dfat = _parse_fr(a.get("date_fat"))
        dfinfat = _parse_fr(a.get("date_fin_fat"))
        dvisite_deb = _parse_fr(a.get("date_visite_appli_debut"))
        dvisite_fin = _parse_fr(a.get("date_visite_appli_fin"))
        dcomm_deb = _parse_fr(a.get("date_commissioning_debut"))
        dcomm_fin = _parse_fr(a.get("date_commissioning_fin"))
        has_fat = bool(dfat and ds <= dfat <= de)
        has_fin_fat = bool(dfinfat and ds <= dfinfat <= de and (not has_fat or dfinfat >= dfat))
        has_visite_deb = bool(dvisite_deb)
        has_visite_fin = bool(dvisite_fin and (not has_visite_deb or dvisite_fin >= dvisite_deb))
        has_comm_deb = bool(dcomm_deb)
        has_comm_fin = bool(dcomm_fin and (not has_comm_deb or dcomm_fin >= dcomm_deb))
        ht = _parse_ht(a.get("prix_ht"))
        total_ca += ht or 0.0
        client_nom = a.get("client_nom") or ""
        if client_nom:
            nb_clients.add(client_nom)

        # Chronologie des phases : chaque jalon renseigné ouvre un nouveau
        # segment de couleur jusqu'au jalon suivant (mêmes règles que le Gantt
        # web dans suivi_affaires.html).
        milestones = [(ds, _GANTT_PHASE_FAB_COLOR)]
        if has_fat:
            milestones.append((dfat, _GANTT_PHASE_FAT_COLOR))
        if has_fin_fat:
            milestones.append((_next_week_monday(dfinfat), _GANTT_PHASE_EXP_COLOR))
        if has_visite_deb:
            milestones.append((dvisite_deb, _GANTT_PHASE_VISITE_COLOR))
        if has_visite_fin:
            milestones.append((_next_week_monday(dvisite_fin), _GANTT_PHASE_EXP_COLOR))
        if has_comm_deb:
            milestones.append((dcomm_deb, _GANTT_PHASE_COMM_COLOR))
        if has_comm_fin:
            milestones.append((_next_week_monday(dcomm_fin), _GANTT_PHASE_EXP_COLOR))
        milestones.sort(key=lambda m: m[0])

        bar_end = de
        if has_visite_deb and dvisite_deb > bar_end:
            bar_end = dvisite_deb
        if has_visite_fin and dvisite_fin > bar_end:
            bar_end = dvisite_fin
        if has_comm_deb and dcomm_deb > bar_end:
            bar_end = dcomm_deb
        if has_comm_fin and dcomm_fin > bar_end:
            bar_end = dcomm_fin

        cells = []
        for w in range(1, nb_weeks + 1):
            monday = _week_monday(w)
            sunday = monday + _timedelta(days=6)
            on = sunday >= ds and monday <= bar_end
            bg = ""
            if on:
                bg = _GANTT_PHASE_FAB_COLOR
                for m_date, m_color in milestones:
                    if m_date <= sunday:
                        bg = m_color
                if monday > de and bg not in (_GANTT_PHASE_VISITE_COLOR, _GANTT_PHASE_COMM_COLOR):
                    bg = _GANTT_PHASE_IDLE_COLOR
                if monday <= de <= sunday:
                    bg = _GANTT_DELIVERY_WEEK_COLOR
            style = f"background:{bg};" if bg else ""
            cells.append(f'<td class="gw-cell" style="{style}"></td>')

        sub = a.get("nom_projet") or a.get("navire_machine") or ""
        client_display = client_nom or "—"
        if sub:
            client_display += f" — {sub}"
        ca_cell = "" if sans_prix else f'<td class="gt-ca">{_fmt_eur(ht) if ht is not None else "—"}</td>'
        body_rows += f"""
<tr>
  <td class="gt-num">{_esc(a.get("num_affaire"))}</td>
  <td class="gt-client">{_esc(client_display)}</td>
  <td class="gt-statut">{_statut_style(statut)}</td>
  <td class="gt-complexite">{_complexite_badge(a.get("complexite"))}</td>
  {ca_cell}
  {"".join(cells)}
</tr>"""

    nb_fixed_cols = 4 if sans_prix else 5
    if not body_rows:
        body_rows = (f'<tr><td colspan="{nb_fixed_cols + nb_weeks}" style="text-align:center;'
                      f'color:#6b7785;padding:20px;font-style:italic;border:1px solid #cbd2da">'
                      f'Aucune affaire planifiée sur {year}</td></tr>')

    legend_html = (
        _chip("Fabrication (début → FAT)", _GANTT_PHASE_FAB_COLOR)
        + _chip("FAT (essai usine)", _GANTT_PHASE_FAT_COLOR)
        + _chip("Expédition", _GANTT_PHASE_EXP_COLOR)
        + _chip("Visite applicative", _GANTT_PHASE_VISITE_COLOR)
        + _chip("Commissioning", _GANTT_PHASE_COMM_COLOR)
        + _chip("Semaine de livraison", _GANTT_DELIVERY_WEEK_COLOR)
        + _chip("Montage", _GANTT_PHASE_IDLE_COLOR)
    )

    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS" style="max-width:110px;max-height:52px;">'
                 if logo_uri else '<div style="font-size:16pt;font-weight:bold;color:#002b5c">EMS</div>')

    # Largeur des colonnes fixes (mm) ; les colonnes semaine n'ont pas de largeur
    # déclarée : avec table-layout:fixed, elles se partagent à parts égales tout
    # l'espace restant de la page, garantissant que le tableau remplit exactement
    # la largeur disponible quel que soit le nombre de semaines (52 ou 53).
    col_widths = (
        '<colgroup>'
        '<col style="width:22mm"><col style="width:48mm"><col style="width:20mm"><col style="width:14mm">'
        + ('' if sans_prix else '<col style="width:20mm">')
        + '<col>' * nb_weeks +
        '</colgroup>'
    )

    return f"""
<section class="year-section">

<table class="hdr-tbl"><tr>
  <td>
    <span class="logo-box">{logo_html}</span>
    <span class="title-box">
      <div class="title">PLANNING ATELIER — {year}{' (SANS PRIX)' if sans_prix else ''}</div>
      <div class="subtitle">Généré le {now} — échéances et périodes (début / FAT / livraison) des affaires</div>
    </span>
  </td>
  <td class="hdr-right">
    <table class="kpi-tbl"><tr>
      {'' if sans_prix else f'<td><span class="kpi-label">CA planifié</span><span class="kpi-value">{_fmt_eur(total_ca)}</span></td>'}
      <td><span class="kpi-label">Affaires</span><span class="kpi-value">{len(rows)}</span></td>
      <td><span class="kpi-label">Clients</span><span class="kpi-value">{len(nb_clients)}</span></td>
    </tr></table>
  </td>
</tr></table>

<div class="legend">{legend_html}</div>

<table class="plan-table">
  {col_widths}
  <thead>
    <tr><th colspan="{nb_fixed_cols}"></th>{month_header}</tr>
    <tr><th>Affaire</th><th>Client / Projet</th><th>Statut</th><th>Cplx.</th>{'' if sans_prix else '<th>CA HT</th>'}{week_header}</tr>
  </thead>
  <tbody>
    {body_rows}
  </tbody>
</table>

</section>"""


_PLANNING_STYLE = """
* { box-sizing: border-box; margin: 0; padding: 0; }
@page {
  size: A3 landscape;
  margin: 9mm 8mm 14mm 8mm;
  @bottom-left { content: "Planning atelier"; font-size: 7pt; color: #6b7785; }
  @bottom-right { content: "Page " counter(page) " / " counter(pages); font-size: 7pt; color: #6b7785; font-weight: 600; }
}
body { font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif; color: #1a2332; background: #fff; -webkit-font-smoothing: antialiased; }

.year-section + .year-section { break-before: page; page-break-before: always; }

/* En-tête : tableau (pas de flex) pour un alignement fiable et sans retour à la ligne */
.hdr-tbl { width: 100%; border-collapse: collapse; table-layout: auto; margin-bottom: 8px; }
.hdr-tbl td { border: none; padding: 0; height: auto; vertical-align: middle; }
.hdr-right { width: 1%; white-space: nowrap; text-align: right; }
.logo-box { display: inline-block; vertical-align: middle; margin-right: 12px; }
.title-box { display: inline-block; vertical-align: middle; }
.title { font-size: 16pt; font-weight: 700; color: #002b5c; letter-spacing: .5px; white-space: nowrap; }
.subtitle { font-size: 8.5pt; color: #4a5560; margin-top: 2px; white-space: nowrap; }

.kpi-tbl { display: inline-table; border-collapse: separate; border-spacing: 8px 0; }
.kpi-tbl td { border: 1px solid #dfe4ea; background: #f5f7fa; border-radius: 4px; padding: 4px 12px; text-align: center; white-space: nowrap; height: auto; }
.kpi-label { display: block; font-size: 7pt; text-transform: uppercase; letter-spacing: .3px; color: #6b7785; white-space: nowrap; }
.kpi-value { display: block; font-size: 12pt; font-weight: 700; color: #002b5c; margin-top: 2px; white-space: nowrap; }

/* Légende + puces de statut : mêmes puces partout (pas de flex → pas de rupture de ligne intempestive) */
.legend { font-size: 7.5pt; color: #4a5560; margin-bottom: 6px; }
.chip { display: inline-block; white-space: nowrap; font-size: 7.5pt; font-weight: 600; color: #1a2332; }
.legend .chip { margin-right: 16px; font-weight: 500; color: #4a5560; }
.chip-dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%; margin-right: 5px; vertical-align: middle; }

.plan-table { border-collapse: collapse; width: 100%; table-layout: fixed; }
.plan-table th, .plan-table td { border: 1px solid #cbd2da; padding: 0; height: 16px; overflow: hidden; white-space: nowrap; text-overflow: ellipsis; }
.plan-table thead { display: table-header-group; }
.plan-table tbody tr { page-break-inside: avoid; break-inside: avoid; }
.plan-table thead th { background: #eef1f5; color: #4a5560; font-weight: 600; font-size: 6.5pt; text-align: center; }
.plan-table thead tr:first-child th { background: #dfe6ee; color: #002b5c; font-weight: 700; font-size: 7pt; }
.gt-num, .gt-client, .gt-statut, .gt-complexite, .gt-ca {
  padding: 2px 5px; font-size: 7.5pt; text-align: left; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.gt-num { font-weight: 700; }
.gt-ca { color: #4a5560; }
.gt-complexite { text-align: center; }
.cx-badge { display: inline-flex; align-items: center; gap: 3px; padding: 1px 5px; border-radius: 8px; font-weight: 600; font-size: 6.5pt; }
.cx-dot { display: inline-block; width: 5px; height: 5px; border-radius: 50%; }
tbody tr:nth-child(even) .gt-num, tbody tr:nth-child(even) .gt-client,
tbody tr:nth-child(even) .gt-statut, tbody tr:nth-child(even) .gt-complexite, tbody tr:nth-child(even) .gt-ca { background: #fafbfc; }
"""


def build_planning_pdf(rows_by_year: dict, sans_prix: bool = False) -> str:
    """
    Génère le HTML complet (multi-pages, une section par année) du planning
    atelier. `rows_by_year` : dict {année: [rows]} déjà filtrés/triés par
    l'appelant (une même affaire peut apparaître dans plusieurs années si sa
    barre les traverse). Une nouvelle page PDF est démarrée à chaque année.
    """
    years = sorted(rows_by_year.keys())
    title_range = f"{years[0]}" if len(years) <= 1 else f"{years[0]}–{years[-1]}"
    sections = "".join(_build_planning_section(rows_by_year[y], y, sans_prix=sans_prix) for y in years)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Planning atelier {title_range}</title>
<style>{_PLANNING_STYLE}</style>
</head>
<body>
{sections}
</body>
</html>"""


def build_planning_html(rows: list, year: int, sans_prix: bool = False) -> str:
    """Génère le HTML du planning atelier pour une seule année (voir build_planning_pdf)."""
    return build_planning_pdf({year: rows}, sans_prix=sans_prix)

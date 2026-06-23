# -*- coding: utf-8 -*-
"""
EMS - Remise en page des accusés de réception de commande
==========================================================

Prend en entrée un (ou plusieurs) PDF "Accusé réception de commande" tel que
généré par l'ERP (toujours la même forme : en-tête, blocs Client/Expédier à,
tableau d'articles, commentaire, totaux, CGV en page 2) et régénère un PDF
propre dont la mise en page reprend l'identité visuelle des bons d'intervention
EMS (logo, bandeau titre, encart jaune sur les n° de commande, tableaux à
en-tête bleu, pied de page société + pagination).

Deux usages :
  - GUI :   python ems_accuse_reception.py
  - CLI :   python ems_accuse_reception.py fichier.pdf [dossier ...] [-o SORTIE] [--no-cgv] [--open]

Dépendances :  pip install pdfplumber weasyprint pypdf pillow
(WeasyPrint nécessite GTK3 sous Windows, déjà installé sur le serveur EMS.)
"""

import argparse
import base64
import html
import io
import os
import re
import sys
from pathlib import Path

# pdfplumber, pypdf, weasyprint et PIL sont importés lazily dans les fonctions
# qui en ont besoin — le .exe n'a ainsi plus besoin de les embarquer quand il
# fonctionne en mode serveur.

# ==========================================================================
#  IDENTITÉ EMS  (constantes société — calées sur le pied de page officiel)
# ==========================================================================
EMS = {
    "nom": "EMERAUDE MOTEURS SYSTEMES",
    "tva": "FR14431976729",
    "adresse1": "9 Rue d'Armorique",
    "adresse2": "35540 MINIAC MORVAN",
    "tel": "02.99.19.01.99",
    "tribunal": "Tribunal de Commerce de Saint-Malo",
}

# Couleurs calées sur la charte bon d'intervention EMS
COL = {
    "bleu":      "#002b5c",
    "bleu_fonce": "#013a7a",
    "rouge":     "#c62828",
    "ardoise":   "#1a2332",
    "jaune":     "#fffbe6",
    "jaune_bord": "#f5cf6d",
    "gris":      "#6b7785",
    "trait":     "#b8c0c9",
    "zebra":     "#f5f7fa",
}

CGV_MARKER = "CONDITIONS GENERALES DE VENTE"


# ==========================================================================
#  OUTILS DE PARSING
# ==========================================================================
def _clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def _join_cell(s):
    """Joint les lignes d'une cellule. Continuation <=2 caractères => coupure
    de mot (collé) ; sinon retour à la ligne sur un espace => espace."""
    if not s:
        return ""
    parts = str(s).split("\n")
    out = parts[0].strip()
    for nxt in parts[1:]:
        nxt = nxt.strip()
        if not nxt:
            continue
        is_short_word = (len(nxt) <= 2 and out and out[-1].isalnum() and nxt[0].isalnum())
        is_num_split = (out and nxt and (
            (out[-1] in ",." and nxt[0].isdigit()) or
            (out[-1].isdigit() and nxt[0] in ",.")
        ))
        if is_short_word or is_num_split:
            out += nxt
        else:
            out += " " + nxt
    return _clean(out)


def _lines(words, tol=3.5):
    """Regroupe une liste de mots pdfplumber en lignes (par coordonnée top)."""
    rows = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        placed = False
        for r in rows:
            if abs(r["top"] - w["top"]) <= tol:
                r["words"].append(w)
                placed = True
                break
        if not placed:
            rows.append({"top": w["top"], "words": [w]})
    for r in rows:
        r["words"].sort(key=lambda w: w["x0"])
        r["text"] = _clean(" ".join(w["text"] for w in r["words"]))
    rows.sort(key=lambda r: r["top"])
    return rows


def _split_cols(words, gap):
    """Découpe une ligne en colonnes dès qu'un écart horizontal > gap."""
    cols, cur, prev_x1 = [], [], None
    for w in sorted(words, key=lambda w: w["x0"]):
        if prev_x1 is not None and (w["x0"] - prev_x1) > gap:
            cols.append(cur)
            cur = []
        cur.append(w)
        prev_x1 = w["x1"]
    if cur:
        cols.append(cur)
    return [{"x0": c[0]["x0"], "text": _clean(" ".join(w["text"] for w in c))} for c in cols]


def _find_tables(page):
    """Retourne (table_articles, table_totaux) repérées par contenu d'en-tête."""
    t_items = t_tot = None
    for t in page.find_tables():
        try:
            raw = t.extract()
        except Exception:
            continue
        head = _clean(" ".join(c or "" for c in (raw[0] if raw else [])))
        if "Code" in head and "Libell" in head:
            t_items = t
        if "TVA" in head and "Total" in head and "Taux" in head:
            t_tot = t
    return t_items, t_tot


def _parse_totaux_from_words(words):
    """Fallback word-based pour les totaux quand find_tables() ne détecte pas la table.
    Cherche la ligne 'Taux de TVA … Total HT … TVA …' et extrait les 2-3 lignes suivantes."""
    lines = _lines(words)
    # Repérer la ligne d'en-tête des totaux
    hdr_idx = next(
        (i for i, l in enumerate(lines)
         if "Taux" in l["text"] and "TVA" in l["text"] and "Total" in l["text"]),
        None,
    )
    if hdr_idx is None:
        return [], []

    hdr_line = lines[hdr_idx]
    hdr_cols = _split_cols(hdr_line["words"], gap=8)
    headers = [c["text"] for c in hdr_cols]
    anchors = [c["x0"] for c in hdr_cols]
    if not headers:
        return [], []

    data_rows = []
    for line in lines[hdr_idx + 1: hdr_idx + 4]:
        row = [""] * len(headers)
        for vc in _split_cols(line["words"], gap=8):
            best = min(range(len(anchors)), key=lambda k: abs(anchors[k] - vc["x0"]))
            row[best] = (row[best] + " " + vc["text"]).strip() if row[best] else vc["text"]
        if any(row):
            data_rows.append(row)
    return headers, data_rows


def parse_commande(path):
    """Parse un PDF d'accusé de réception. Retourne un dict structuré."""
    import pdfplumber
    data = {
        "entete": {}, "client": [], "expedier": [], "articles_header": [],
        "articles": [], "commentaire_commande": [], "totaux_header": [],
        "totaux": [], "modalites": "",
    }
    with pdfplumber.open(path) as pdf:
        # Pages "document" = avant la première page de CGV
        cgv_idx = None
        for i, pg in enumerate(pdf.pages):
            if CGV_MARKER in (pg.extract_text() or "").upper():
                cgv_idx = i
                break
        doc_pages = pdf.pages[:cgv_idx] if cgv_idx else [pdf.pages[0]]
        data["cgv_start"] = cgv_idx  # index 0-based de la 1re page CGV (ou None)

        p0 = doc_pages[0]
        words0 = p0.extract_words(use_text_flow=False, keep_blank_chars=False)
        rows0 = _lines(words0)
        t_items0, _ = _find_tables(p0)
        title_top = next((r["top"] for r in rows0 if "Accus" in r["text"]), 0)
        items_top = t_items0.bbox[1] if t_items0 else 1e9

        # --- bandeau d'en-tête (Date / N° Cde EMS / N° Cde Client / ...) ---
        hdr_label = next((r for r in rows0 if r["top"] > title_top
                          and ("Cde" in r["text"] or "Date" in r["text"])), None)
        labels = ["Date", "N° Cde EMS", "N° Cde Client",
                  "Moyen de Paiement", "Échéances de Paiement"]
        for lab in labels:
            data["entete"][lab] = ""
        if hdr_label:
            lab_cols = _split_cols(hdr_label["words"], gap=14)
            anchors = [c["x0"] for c in lab_cols]
            val_row = next((r for r in rows0 if hdr_label["top"] + 4 < r["top"]
                            < hdr_label["top"] + 40), None)
            if val_row:
                for vc in _split_cols(val_row["words"], gap=14):
                    if not anchors:
                        continue
                    idx = min(range(len(anchors)),
                              key=lambda k: abs(anchors[k] - vc["x0"]))
                    if idx < len(labels):
                        data["entete"][labels[idx]] = vc["text"]

        # --- blocs Client / Expédier à ---
        cli_hdr = next((r for r in rows0 if "Client:" in r["text"]
                        or "Expédier" in r["text"]), None)
        if cli_hdr:
            xs = [w["x0"] for w in cli_hdr["words"]]
            split_x = (min(xs) + max(xs)) / 2 if len(xs) > 1 else 280
            region = [w for w in words0 if cli_hdr["top"] + 6 < w["top"] < items_top - 4]
            for r in _lines(region):
                lw = [w for w in r["words"] if w["x0"] < split_x]
                rw = [w for w in r["words"] if w["x0"] >= split_x]
                if lw:
                    data["client"].append(_clean(" ".join(w["text"] for w in lw)))
                if rw:
                    data["expedier"].append(_clean(" ".join(w["text"] for w in rw)))
        data["client"] = [l for l in data["client"] if l]
        data["expedier"] = [l for l in data["expedier"] if l]

        # --- articles : cumulés sur toutes les pages document ---
        header_set = False
        for pg in doc_pages:
            t_items, _ = _find_tables(pg)
            if not t_items:
                continue
            raw = t_items.extract()
            hdr = [_join_cell(c) for c in raw[0]]
            if not header_set:
                data["articles_header"] = hdr
                header_set = True
            for row in raw[1:]:
                cells = [_join_cell(c) for c in row]
                if not any(cells):
                    continue
                data["articles"].append(dict(zip(hdr, cells)))

        # --- commentaire, totaux, modalités ---
        # pL = dernière page contenant une table d'articles.
        # (≠ doc_pages[-1] si une page "Modalités" sans tableau suit la page principale)
        pL = doc_pages[0]
        for pg in doc_pages:
            if _find_tables(pg)[0] is not None:
                pL = pg
        wordsL = pL.extract_words(use_text_flow=False, keep_blank_chars=False)
        t_itemsL, t_totL = _find_tables(pL)

        # Commentaire : entre fin des articles et début des totaux
        if t_itemsL:
            items_bot = t_itemsL.bbox[3]
            if t_totL:
                tot_top = t_totL.bbox[1]
            else:
                taux_w = next((w for w in wordsL
                               if w["text"] == "Taux" and w["top"] > items_bot), None)
                tot_top = taux_w["top"] if taux_w else items_bot + 200
            band = [w for w in wordsL if items_bot + 2 < w["top"] < tot_top - 2
                    and w["x0"] < 250]
            blines = [r["text"] for r in _lines(band)]
            data["commentaire_commande"] = [b for b in blines if b
                                            and "Commentaire commande" not in b]

        # Totaux : table formelle, fallback word-based si non trouvée
        if t_totL:
            raw = t_totL.extract()
            data["totaux_header"] = [_clean(c) for c in raw[0]]
            for row in raw[1:]:
                data["totaux"].append([_clean(c) for c in row])

        if not data["totaux"]:
            data["totaux_header"], data["totaux"] = _parse_totaux_from_words(wordsL)

        # Modalités : chercher sur toutes les pages document (peut être page séparée)
        for pg_m in doc_pages:
            w_m = pg_m.extract_words(use_text_flow=False, keep_blank_chars=False)
            for l in _lines(w_m):
                if "Modalit" in l["text"]:
                    data["modalites"] = l["text"]
                    break
            if data["modalites"]:
                break
    return data


def extract_logo_datauri(path):
    """Extrait le logo EMS embarqué (1re image page 1, fusion RGB + smask) et
    le renvoie en data-URI base64 PNG. Renvoie None si indisponible."""
    try:
        from PIL import Image
    except Exception:
        return None
    try:
        from pypdf import PdfReader
        reader = PdfReader(path)
        page = reader.pages[0]
        imgs = list(page.images)
        if not imgs:
            return None
        # plus grande image = logo
        best = max(imgs, key=lambda im: getattr(im.image, "width", 0)
                   * getattr(im.image, "height", 0))
        im = best.image.convert("RGBA")
        bbox = im.getbbox()
        if bbox:
            im = im.crop(bbox)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return "data:image/png;base64," + b64
    except Exception:
        return None


# ==========================================================================
#  GÉNÉRATION HTML  ——  mise en page calée sur le bon d'intervention EMS
#  (bloc <style> isolé : remplaçable par le CSS exact de bon_generator.py)
# ==========================================================================
def _esc(s):
    return html.escape(str(s)) if s is not None else ""


def _load_cgv_logo_uri():
    """Charge logo_cgv.png (ou logo_ems.png en fallback) depuis les assets."""
    base = Path(__file__).resolve().parent
    for name in ("logo_cgv.png", "logo_ems.png"):
        for folder in (base / "shared" / "assets", base / "assets"):
            p = folder / name
            if p.is_file():
                try:
                    return "data:image/png;base64," + base64.b64encode(
                        p.read_bytes()).decode("ascii")
                except OSError:
                    pass
    return None


def _fmt_remise(val):
    """'1008,9 (30,00%)' -> '-30,00 %' ; '(0,00%)' -> '0,00 %'."""
    m = re.search(r"\(([\d.,]+)\s*%\)", val or "")
    if not m:
        return _esc(_clean(val))
    pct = m.group(1)
    return ("-" if pct not in ("0", "0,00", "0.00") else "") + pct + " %"


def _bloc_adresse(lines):
    if not lines:
        return '<span class="muted">—</span>'
    out = []
    for i, l in enumerate(lines):
        cls = "nom" if i == 0 else ("mail" if "@" in l else "")
        out.append(f'<div class="{cls}">{_esc(l)}</div>')
    return "\n".join(out)


def build_html(data, logo_datauri=None):
    e = data["entete"]
    num_ems = e.get("N° Cde EMS", "") or "—"
    num_cli = e.get("N° Cde Client", "")
    date = e.get("Date", "")
    moyen = e.get("Moyen de Paiement", "")
    echeance = e.get("Échéances de Paiement", "")

    logo_html = (f'<img src="{logo_datauri}" alt="EMS">'
                 if logo_datauri else f'<div class="logo-fallback">EMS</div>')

    num_cli_html = (
        f'<div class="num-cmd-box">N&deg; commande client&nbsp;:&nbsp;'
        f'<strong>{_esc(num_cli)}</strong></div>'
        if num_cli else ""
    )

    # --- tableau articles ---
    cols = ["Code", "Libellé", "Qté Cde", "PU HT", "Remise", "Total HT", "Commentaire"]
    num_cols = {"Qté Cde", "PU HT", "Remise", "Total HT"}
    th = "".join(
        f'<th class="{"num" if c in num_cols else ""}">{_esc(c)}</th>' for c in cols)
    trs = []
    for art in data["articles"]:
        tds = []
        for c in cols:
            v = art.get(c, "")
            if c == "Remise":
                v = _fmt_remise(v)
            else:
                v = _esc(_clean(v))
            cls = "num" if c in num_cols else ("code" if c == "Code" else "")
            tds.append(f'<td class="{cls}">{v}</td>')
        trs.append("<tr>" + "".join(tds) + "</tr>")
    items_html = "\n".join(trs) if trs else \
        '<tr><td colspan="7" class="muted" style="text-align:center">Aucun article</td></tr>'

    # --- commentaire commande ---
    com = data["commentaire_commande"]
    com_html = ""
    if com:
        lignes = "<br>".join(_esc(c) for c in com)
        com_html = (
            '<div class="note">'
            '<div class="note-lab">Commentaire commande</div>'
            f'<div class="note-body">{lignes}</div></div>')

    # --- totaux : on privilégie la ligne "Total" ---
    th_tot = [_clean(h) for h in data["totaux_header"]]
    row_total = None
    row_rate = None
    for r in data["totaux"]:
        if r and r[0].strip().lower().startswith("total"):
            row_total = r
        elif r:
            row_rate = r
    src = row_total or row_rate or []
    tmap = dict(zip(th_tot, src)) if src else {}
    taux = (row_rate[0] if row_rate else tmap.get("Taux de TVA", "")) or "—"

    def g(k):
        return _esc(_clean(tmap.get(k, ""))) or "—"

    totals_rows = [
        ("Total HT", g("Total HT")),
        ("Remise", g("Remise")),
        ("Prix HT remisé", g("Prix HT remisé")),
        (f"TVA ({_esc(_clean(taux))})", g("TVA")),
    ]
    totals_html = "".join(
        f'<div class="t-row"><span class="t-lab">{lab}</span>'
        f'<span class="t-val">{val}</span></div>' for lab, val in totals_rows)
    ttc = g("Total TTC")

    modalites = _esc(_clean(data.get("modalites", ""))) or \
        "Modalités de paiement : les conditions de règlement sont définies au contrat."

    # ----------------------------------------------------------------------
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<style>
/* ====== STYLE calé sur le bon d'intervention EMS ======================== */
@page {{
  size: A4;
  margin: 10mm 10mm 18mm 10mm;
  @bottom-left  {{ content: "Cde EMS {_esc(num_ems)}";
                   font: 8pt 'Segoe UI', Arial, sans-serif; color: {COL['gris']}; }}
  @bottom-center{{ content: "{EMS['nom']} — {EMS['adresse2']}";
                   font: 7pt 'Segoe UI', Arial, sans-serif; color: {COL['gris']}; }}
  @bottom-right {{ content: "Page " counter(page) " / " counter(pages);
                   font: 8pt 'Segoe UI', Arial, sans-serif; color: {COL['gris']};
                   font-weight: 600; }}
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
        font-size: 10.5px; color: {COL['ardoise']}; background: #fff; }}
.muted {{ color: {COL['gris']}; }}

/* ---- en-tête 3 colonnes (même grille que le bon d'intervention) ---- */
.header-wrap {{ margin-bottom: 14px; padding-bottom: 4px; }}
.header {{ display: grid; grid-template-columns: 1fr 1.6fr 1fr;
           gap: 16px; align-items: center; }}
.header-left {{ display: flex; align-items: center; justify-content: center; padding: 4px; }}
.header-left img {{ max-width: 200px; max-height: 110px; }}
.logo-fallback {{ font-size: 28px; font-weight: bold; color: {COL['bleu']}; letter-spacing: 3px; }}
.header-mid {{ text-align: center; padding: 4px; }}
.header-mid h1 {{ font-size: 17px; font-weight: 700; color: {COL['bleu']};
                  margin: 0 0 6px 0; letter-spacing: 0.5px; }}
.header-mid .info {{ font-size: 9px; line-height: 1.5; color: {COL['gris']}; }}
.header-right {{ padding: 4px 0 4px 8px; font-size: 10px; line-height: 1.7; }}
.header-right .titre {{ font-weight: bold; font-size: 11px;
                         color: {COL['bleu']}; margin-bottom: 4px; }}

/* ---- ref-box (N° Cde EMS) et num-cmd-box (N° Cde Client) ---- */
.ref-box {{ display: inline-block; background: {COL['bleu']}; color: #fff;
            padding: 5px 12px; font-size: 11px; font-weight: bold;
            border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,.15);
            margin-bottom: 6px; }}
.num-cmd-box {{ display: inline-block; margin-left: 8px;
                background: {COL['jaune']}; color: #6b4400;
                padding: 5px 10px; font-size: 10px;
                border: 1px solid {COL['jaune_bord']}; border-radius: 4px;
                margin-bottom: 6px; }}
.num-cmd-box strong {{ color: #6b4400; }}

/* ---- blocs adresse ---- */
.parties {{ display: flex; gap: 10px; margin-bottom: 12px; }}
.party {{ flex: 1; border: 1px solid {COL['trait']}; border-radius: 3px; overflow: hidden; }}
.party-h {{ background: {COL['bleu']}; color: #fff; font-size: 10px;
            font-weight: 700; letter-spacing: 1px; padding: 4px 10px;
            text-transform: uppercase; }}
.party-b {{ padding: 7px 9px; line-height: 1.35; font-size: 10px; }}
.party-b .nom {{ font-weight: 700; }}
.party-b .mail {{ color: {COL['bleu_fonce']}; }}

/* ---- titre de section (soulignement rouge, comme le bon) ---- */
.section-title {{ font-weight: 700; font-size: 11px; color: {COL['bleu']};
                  margin: 14px 0 4px; padding-bottom: 3px;
                  border-bottom: 2px solid {COL['rouge']};
                  display: inline-block; padding-right: 12px;
                  letter-spacing: 0.3px; }}

/* ---- tableau articles ---- */
table.items {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
table.items th {{ background: {COL['bleu']}; color: #fff; font-size: 10px;
                  font-weight: 700; text-align: left; padding: 6px 8px;
                  letter-spacing: .3px; }}
table.items th.num {{ text-align: right; }}
table.items td {{ padding: 5px 7px; border: 1px solid {COL['trait']};
                  font-size: 10px; vertical-align: top; }}
table.items tr:nth-child(even) td {{ background: {COL['zebra']}; }}
table.items td.num {{ text-align: right; white-space: nowrap; }}
table.items td.code {{ font-weight: 700; color: {COL['bleu_fonce']}; white-space: nowrap; }}

/* ---- commentaire ---- */
.note {{ border: 1px solid {COL['trait']}; border-left: 3px solid {COL['rouge']};
         border-radius: 3px; padding: 6px 9px; margin-bottom: 12px;
         background: #fafbfc; }}
.note-lab {{ font-size: 9px; text-transform: uppercase; letter-spacing: .5px;
             color: {COL['rouge']}; font-weight: 700; margin-bottom: 2px; }}
.note-body {{ font-size: 10px; line-height: 1.35; }}

/* ---- totaux ---- */
.bottom {{ display: flex; justify-content: flex-end; margin-bottom: 12px; }}
.totals {{ width: 46%; border: 1px solid {COL['trait']}; border-radius: 3px; overflow: hidden; }}
.t-row {{ display: flex; justify-content: space-between; padding: 4px 10px;
          font-size: 10px; border-bottom: 1px solid {COL['trait']}; }}
.t-lab {{ color: {COL['gris']}; }}
.t-val {{ font-weight: 600; }}
.t-ttc {{ display: flex; justify-content: space-between; padding: 7px 10px;
          background: {COL['bleu']}; color: #fff; }}
.t-ttc .l {{ font-weight: 700; letter-spacing: .5px; }}
.t-ttc .v {{ font-weight: 800; font-size: 12pt; }}

/* ---- pied ---- */
.modal {{ margin-top: 14px; font-size: 8pt; color: {COL['gris']}; font-style: italic; }}
.footer {{ border-top: 2px solid {COL['bleu']}; margin-top: 16px; padding-top: 8px;
           font-size: 8.5px; color: {COL['gris']}; text-align: center; line-height: 1.7; }}
.footer strong {{ color: {COL['bleu']}; }}
</style></head><body>

<div class="ref-box">Cde EMS&nbsp;{_esc(num_ems)}</div>
{num_cli_html}

<div class="header-wrap">
<div class="header">
  <div class="header-left">
    {logo_html}
  </div>
  <div class="header-mid">
    <h1>ACCUSÉ DE RÉCEPTION<br>DE COMMANDE</h1>
    <div class="info">
      Tél.&nbsp;: {EMS['tel']}<br>
      N° TVA&nbsp;: {EMS['tva']}<br>
      {EMS['adresse1']} — {EMS['adresse2']}
    </div>
  </div>
  <div class="header-right">
    <div class="titre">Informations commande</div>
    Date&nbsp;: <strong>{_esc(date) or "—"}</strong><br>
    Paiement&nbsp;: <strong>{_esc(moyen) or "—"}</strong><br>
    Échéance(s)&nbsp;: <strong>{_esc(echeance) or "—"}</strong>
  </div>
</div>
</div>

<div class="parties">
  <div class="party">
    <div class="party-h">Client</div>
    <div class="party-b">{_bloc_adresse(data['client'])}</div>
  </div>
  <div class="party">
    <div class="party-h">Expédier à</div>
    <div class="party-b">{_bloc_adresse(data['expedier'])}</div>
  </div>
</div>

<div class="section-title">ARTICLES</div>
<table class="items">
  <thead><tr>{th}</tr></thead>
  <tbody>{items_html}</tbody>
</table>

{com_html}

<div class="bottom">
  <div class="totals">
    {totals_html}
    <div class="t-ttc"><span class="l">TOTAL TTC</span><span class="v">{ttc}</span></div>
  </div>
</div>

<div class="modal">{modalites}</div>

<div class="footer">
  <strong>{EMS['nom']}</strong> — Constructeur de groupe de puissance<br>
  {EMS['adresse1']} — {EMS['adresse2']} — Tél.&nbsp;: {EMS['tel']}<br>
  N° TVA&nbsp;: {EMS['tva']} &nbsp;|&nbsp; {EMS['tribunal']}
</div>

</body></html>"""


# ==========================================================================
#  RENDU PDF
# ==========================================================================
def _extract_cgv_text(source_pdf, cgv_start):
    """Extrait le texte brut des pages CGV du PDF source."""
    try:
        import pdfplumber
        with pdfplumber.open(source_pdf) as pdf:
            parts = []
            for pg in pdf.pages[cgv_start:]:
                t = (pg.extract_text() or "").strip()
                if t:
                    parts.append(t)
            return "\n".join(parts)
    except Exception:
        return ""


def _build_cgv_logo_html(cgv_text, logo_uri=None):
    """Génère une page CGV 2 colonnes + logo en bas, CSS identique aux bons."""
    paragraphs = []
    for line in cgv_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "CONDITIONS" in line.upper() and "VENTE" in line.upper():
            continue
        if re.match(r'^[A-Z]{1,2}\s*[•·–\-]\s', line) or (line.isupper() and len(line) < 60):
            paragraphs.append(
                f'<div class="cgv-section">{html.escape(line)}</div>')
        else:
            paragraphs.append(f'<p class="cgv-p">{html.escape(line)}</p>')
    body = "\n".join(paragraphs) if paragraphs else \
        '<p class="cgv-p">Conditions générales de vente disponibles sur demande.</p>'
    logo_html = (f'<img src="{logo_uri}" alt="Emeraude Moteurs Systemes" '
                 f'style="max-width:340px;max-height:190px;">'
                 if logo_uri else "")
    return f"""<!DOCTYPE html>
<html lang="fr"><head><meta charset="utf-8">
<style>
@page {{ size: A4; margin: 10mm 5mm 8mm 5mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', Arial, sans-serif;
       font-size: 7.8px; line-height: 1.38; color: #1a2332; }}
.cgv-title {{
  font-size: 9px; font-weight: 700; color: #002b5c;
  text-align: center; margin-bottom: 6px; padding-bottom: 4px;
  border-bottom: 2px solid #002b5c; letter-spacing: 0.3px;
}}
.cgv-body {{
  column-count: 2; column-gap: 12px;
  column-rule: 1px solid #d0d4d9;
}}
.cgv-section {{
  font-size: 8px; font-weight: 700; color: #002b5c;
  margin: 6px 0 1px; text-transform: uppercase; letter-spacing: 0.2px;
  break-before: avoid; page-break-before: avoid;
}}
.cgv-p {{ margin: 0 0 3px; text-align: justify; }}
.cgv-logo-wrap {{
  margin-top: 10px; text-align: center;
  padding-top: 8px; border-top: 1px solid #b8c0c9;
}}
</style></head><body>
<div class="cgv-title">CONDITIONS GÉNÉRALES DE VENTE – EMERAUDE MOTEURS SYSTEMES</div>
<div class="cgv-body">
{body}
</div>
<div class="cgv-logo-wrap">{logo_html}</div>
</body></html>"""


def _fit_cgv_one_page(cgv_text, logo_uri=None):
    """Rend la page CGV+logo (CSS identique aux bons d'intervention)."""
    from weasyprint import HTML as _WH
    return _WH(string=_build_cgv_logo_html(cgv_text, logo_uri)).write_pdf()


def _render_to_bytes(data, html_str, source_pdf=None, include_cgv=True):
    """Rend le HTML en PDF et retourne les bytes (sans écrire de fichier)."""
    from weasyprint import HTML
    from pypdf import PdfReader, PdfWriter
    pdf_bytes = HTML(string=html_str).write_pdf()

    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(pdf_bytes)).pages:
        writer.add_page(page)

    cgv_start = data.get("cgv_start")
    logo_uri = _load_cgv_logo_uri()

    if include_cgv and source_pdf and cgv_start is not None:
        cgv_text = _extract_cgv_text(source_pdf, cgv_start)
    else:
        cgv_text = ""

    try:
        cgv_pdf = _fit_cgv_one_page(cgv_text, logo_uri)
        for page in PdfReader(io.BytesIO(cgv_pdf)).pages:
            writer.add_page(page)
    except Exception:
        if include_cgv and source_pdf and cgv_start is not None:
            from pypdf import PdfReader as _PR
            for page in _PR(source_pdf).pages[cgv_start:]:
                writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def render_pdf(data, html_str, out_path, source_pdf=None, include_cgv=True):
    """Rend le HTML en PDF (WeasyPrint) puis ajoute une page CGV+logo."""
    pdf_bytes = _render_to_bytes(data, html_str, source_pdf, include_cgv)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    return out_path


def process_file(in_path, out_dir=None, include_cgv=True):
    """Traite un PDF -> chemin du PDF régénéré."""
    in_path = Path(in_path)
    data = parse_commande(str(in_path))
    logo = extract_logo_datauri(str(in_path))
    html_str = build_html(data, logo)

    num = _clean(data["entete"].get("N° Cde EMS", "")) or in_path.stem
    safe = re.sub(r"[^\w\-]+", "_", num).strip("_") or in_path.stem
    out_dir = Path(out_dir) if out_dir else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{safe}_accuse_EMS.pdf"

    render_pdf(data, html_str, str(out_path), str(in_path), include_cgv)
    return str(out_path)


# ==========================================================================
#  MODE SERVEUR — lecture config + upload vers l'API
# ==========================================================================
def _read_server_url():
    """Lit l'URL du serveur EMS depuis config.ini (à côté de l'exe ou du script)."""
    from configparser import ConfigParser
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) \
        else Path(__file__).resolve().parent
    for p in (base / "config.ini", Path(__file__).resolve().parent / "config.ini"):
        if p.is_file():
            cp = ConfigParser()
            cp.read(str(p), encoding="utf-8")
            url = cp.get("server", "url", fallback="").strip()
            if url:
                return url
    return None


def process_file_via_api(in_path, server_url, out_dir=None, include_cgv=True):
    """Envoie le PDF au serveur EMS, récupère le PDF converti et le sauvegarde."""
    import requests
    in_path = Path(in_path)
    url = server_url.rstrip("/") + "/pdf/accuse-reception"
    with open(in_path, "rb") as fh:
        resp = requests.post(
            url,
            files={"file": (in_path.name, fh, "application/pdf")},
            params={"include_cgv": "true" if include_cgv else "false"},
            timeout=120,
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Serveur {resp.status_code} : {resp.text[:300]}")

    cd = resp.headers.get("Content-Disposition", "")
    m = re.search(r'filename="([^"]+)"', cd)
    out_name = m.group(1) if m else f"{in_path.stem}_accuse_EMS.pdf"
    out_dir = Path(out_dir) if out_dir else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / out_name
    with open(out_path, "wb") as fh:
        fh.write(resp.content)
    return str(out_path)


# ==========================================================================
#  COLLECTE DES ENTRÉES
# ==========================================================================
def collect_pdfs(inputs):
    files = []
    for item in inputs:
        p = Path(item)
        if p.is_dir():
            files += sorted(str(f) for f in p.glob("*.pdf"))
        elif p.is_file() and p.suffix.lower() == ".pdf":
            files.append(str(p))
    # dédoublonnage en conservant l'ordre
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def open_path(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # noqa
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
    except Exception:
        pass


# ==========================================================================
#  INTERFACE GRAPHIQUE (Tkinter)
# ==========================================================================
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, ttk

    root = tk.Tk()
    root.title("EMS — Mise en page des accusés de réception")
    root.geometry("760x560")
    root.minsize(680, 480)

    BLEU, ARDOISE = "#002b5c", "#1a2332"
    files = []

    ROUGE = "#c62828"
    head = tk.Frame(root, bg=BLEU, height=60)
    head.pack(fill="x")
    head.pack_propagate(False)
    tk.Frame(head, bg=ROUGE, width=5).pack(side="left", fill="y")
    tk.Label(head, text="Accusés de réception — Mise en page format EMS", bg=BLEU,
             fg="white", font=("Segoe UI", 13, "bold")).pack(side="left", padx=16, pady=14)

    body = tk.Frame(root, padx=14, pady=12)
    body.pack(fill="both", expand=True)

    srv = _read_server_url()
    if srv:
        mode_txt = f"Mode serveur : {srv}"
        mode_fg = "#1A7F37"
    else:
        mode_txt = "Mode local (bibliothèques embarquées)"
        mode_fg = "#B4202F"
    tk.Label(body, text=mode_txt, font=("Segoe UI", 8), fg=mode_fg).pack(anchor="w", pady=(0, 4))

    tk.Label(body, text="PDF à traiter :", font=("Segoe UI", 10, "bold"),
             fg=ARDOISE).pack(anchor="w")
    lst_frame = tk.Frame(body)
    lst_frame.pack(fill="both", expand=True, pady=(4, 8))
    sb = tk.Scrollbar(lst_frame)
    sb.pack(side="right", fill="y")
    listbox = tk.Listbox(lst_frame, yscrollcommand=sb.set, height=8,
                         font=("Consolas", 9))
    listbox.pack(side="left", fill="both", expand=True)
    sb.config(command=listbox.yview)

    def refresh():
        listbox.delete(0, tk.END)
        for f in files:
            listbox.insert(tk.END, Path(f).name)

    def add_files():
        for f in filedialog.askopenfilenames(
                title="Choisir des PDF", filetypes=[("PDF", "*.pdf")]):
            if f not in files:
                files.append(f)
        refresh()

    def add_folder():
        d = filedialog.askdirectory(title="Choisir un dossier")
        if d:
            for f in collect_pdfs([d]):
                if f not in files:
                    files.append(f)
            refresh()

    def clear_all():
        files.clear()
        refresh()

    btns = tk.Frame(body)
    btns.pack(fill="x")
    tk.Button(btns, text="+ Ajouter PDF…", command=add_files).pack(side="left")
    tk.Button(btns, text="+ Ajouter dossier…", command=add_folder).pack(side="left", padx=6)
    tk.Button(btns, text="Vider", command=clear_all).pack(side="left")

    opt = tk.Frame(body)
    opt.pack(fill="x", pady=(10, 6))
    out_var = tk.StringVar(value="")
    cgv_var = tk.BooleanVar(value=True)
    tk.Checkbutton(opt, text="Conserver les CGV (page 2)", variable=cgv_var,
                   fg=ARDOISE).pack(side="left")

    out_frame = tk.Frame(body)
    out_frame.pack(fill="x")
    tk.Label(out_frame, text="Dossier de sortie :", fg=ARDOISE).pack(side="left")
    tk.Entry(out_frame, textvariable=out_var).pack(side="left", fill="x",
                                                   expand=True, padx=6)

    def choose_out():
        d = filedialog.askdirectory(title="Dossier de sortie")
        if d:
            out_var.set(d)
    tk.Button(out_frame, text="…", command=choose_out, width=3).pack(side="left")
    tk.Label(body, text="(vide = à côté de chaque PDF source)", fg="#6B7785",
             font=("Segoe UI", 8)).pack(anchor="w")

    log = tk.Text(body, height=8, font=("Consolas", 9), state="disabled",
                  bg="#F7F9FB")
    log.pack(fill="both", expand=True, pady=(8, 6))

    def logw(msg, tag=None):
        log.config(state="normal")
        log.insert(tk.END, msg + "\n", tag)
        log.see(tk.END)
        log.config(state="disabled")
        root.update_idletasks()
    log.tag_config("ok", foreground="#1A7F37")
    log.tag_config("err", foreground="#B4202F")

    last_out = {"dir": None}

    def generate():
        if not files:
            logw("Aucun PDF sélectionné.", "err")
            return
        out_dir = out_var.get().strip() or None
        server_url = _read_server_url()
        ok = 0
        for f in list(files):
            try:
                logw(f"→ {Path(f).name} …")
                if server_url:
                    res = process_file_via_api(f, server_url, out_dir, cgv_var.get())
                else:
                    res = process_file(f, out_dir, cgv_var.get())
                last_out["dir"] = str(Path(res).parent)
                logw(f"   ✓ {Path(res).name}", "ok")
                ok += 1
            except Exception as ex:
                logw(f"   ✗ Erreur : {ex}", "err")
        logw(f"Terminé : {ok}/{len(files)} fichier(s).", "ok" if ok else "err")
        if last_out["dir"]:
            open_btn.config(state="normal")

    act = tk.Frame(body)
    act.pack(fill="x")
    tk.Button(act, text="Générer", command=generate, bg=BLEU, fg="white",
              font=("Segoe UI", 11, "bold"), padx=18, pady=4,
              relief="flat", cursor="hand2").pack(side="left")
    open_btn = tk.Button(act, text="Ouvrir le dossier de sortie",
                         command=lambda: open_path(last_out["dir"]),
                         state="disabled")
    open_btn.pack(side="left", padx=8)

    root.mainloop()


# ==========================================================================
#  POINT D'ENTRÉE
# ==========================================================================
def main():
    ap = argparse.ArgumentParser(
        description="Remet en page des accusés de réception de commande EMS "
                    "au format bon d'intervention.")
    ap.add_argument("inputs", nargs="*", help="Fichiers PDF ou dossiers")
    ap.add_argument("-o", "--output-dir", help="Dossier de sortie")
    ap.add_argument("--no-cgv", action="store_true",
                    help="Ne pas conserver les pages CGV")
    ap.add_argument("--open", action="store_true",
                    help="Ouvrir chaque PDF généré")
    args = ap.parse_args()

    if not args.inputs:
        try:
            run_gui()
        except Exception as ex:
            print(f"GUI indisponible ({ex}).\n"
                  f"Usage CLI : python {Path(sys.argv[0]).name} fichier.pdf "
                  f"[-o sortie] [--no-cgv]")
        return

    pdfs = collect_pdfs(args.inputs)
    if not pdfs:
        print("Aucun PDF trouvé.")
        return
    for f in pdfs:
        try:
            res = process_file(f, args.output_dir, not args.no_cgv)
            print(f"✓ {Path(f).name} -> {res}")
            if args.open:
                open_path(res)
        except Exception as ex:
            print(f"✗ {Path(f).name} : {ex}")


if __name__ == "__main__":
    main()

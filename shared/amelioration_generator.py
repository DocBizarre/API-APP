"""
EMS – Génération de la fiche HTML d'un sujet d'amélioration continue.
Réutilise le logo et le style visuel des bons d'intervention.
"""

from pathlib import Path
from datetime import datetime

from .bon_generator import _esc, _logo_data_uri, ouvrir_fichier

AMELIO_DIR = Path(__file__).parent / "ameliorations"

_PRIO_CLS = {"Basse": "p-basse", "Moyenne": "p-moy",
             "Haute": "p-haute", "Critique": "p-crit"}
_STATUT_CLS = {"À étudier": "s-etud", "Accepté": "s-acc", "En cours": "s-enc",
               "Déployé": "s-depl", "Clos": "s-clos"}


def _g(row, key, default=""):
    if row is None:
        return default
    try:
        v = row[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def generer_html(amelio):
    num     = _g(amelio, "num_ticket")
    titre   = _g(amelio, "titre")
    client  = _g(amelio, "client_nom")
    desc    = _g(amelio, "description")
    prio    = _g(amelio, "priorite", "Moyenne")
    statut  = _g(amelio, "statut", "À étudier")
    tech    = _g(amelio, "technicien")
    cible   = _g(amelio, "date_cible")
    comm    = _g(amelio, "commentaires")
    cree    = _g(amelio, "created_at")
    maj     = _g(amelio, "updated_at")

    logo_uri = _logo_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS">' if logo_uri
                 else '<div class="logo-fallback">EMS</div>')
    prio_cls   = _PRIO_CLS.get(prio, "p-moy")
    statut_cls = _STATUT_CLS.get(statut, "s-etud")
    gen_date = datetime.now().strftime("%d/%m/%Y à %H:%M")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>{_esc(num)} – {_esc(titre)}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI','Helvetica Neue',Arial,sans-serif;
       font-size: 11px; color: #1a2332; background: #fff; padding: 20px 26px; }}
.header {{ display: grid; grid-template-columns: 160px 1fr; gap: 16px;
           border-bottom: 3px solid #002b5c; padding-bottom: 10px;
           margin-bottom: 16px; position: relative; }}
.header::after {{ content:''; position:absolute; bottom:-3px; left:0;
                  width:70px; height:3px; background:#c62828; }}
.header-left {{ display:flex; align-items:center; justify-content:center; }}
.header-left img {{ max-width: 150px; max-height: 90px; }}
.header-left .logo-fallback {{ font-size:30px; font-weight:bold; color:#002b5c;
                                letter-spacing:3px; }}
.header-mid h1 {{ font-size:18px; color:#002b5c; margin-bottom:4px; }}
.header-mid .sub {{ font-size:10px; color:#6b7785; }}
.ref-box {{ display:inline-block; background:#002b5c; color:#fff;
            padding:5px 14px; border-radius:5px; font-weight:bold;
            font-size:12px; margin-top:6px; }}
.badges {{ margin-top:8px; }}
.badge {{ display:inline-block; padding:3px 12px; border-radius:12px;
          font-size:10px; font-weight:bold; margin-right:6px; }}
.p-basse {{ background:#eef0f3; color:#6b7785; }}
.p-moy   {{ background:#eff6ff; color:#3b82f6; }}
.p-haute {{ background:#fff7ed; color:#e67e22; }}
.p-crit  {{ background:#fef2f2; color:#c62828; }}
.s-etud  {{ background:#eef0f3; color:#6b7785; }}
.s-acc   {{ background:#eef2ff; color:#6366f1; }}
.s-enc   {{ background:#fff7ed; color:#f59e0b; }}
.s-depl  {{ background:#eff6ff; color:#3b82f6; }}
.s-clos  {{ background:#ecfdf5; color:#10b981; }}
table {{ border-collapse:collapse; width:100%; margin-top:6px; }}
td {{ border:1px solid #b8c0c9; padding:7px 10px; font-size:10.5px;
      vertical-align:top; }}
.lbl {{ background:#f5f7fa; font-weight:600; color:#002b5c; width:24%; }}
.section-title {{ font-weight:700; font-size:12px; color:#002b5c;
                  margin:18px 0 4px; padding-bottom:3px;
                  border-bottom:2px solid #c62828; display:inline-block;
                  padding-right:14px; }}
.zone {{ border:1px solid #b8c0c9; border-radius:3px; padding:10px 12px;
         background:#fafbfc; white-space:pre-wrap; font-size:10.5px;
         line-height:1.6; min-height:60px; }}
.footer {{ border-top:2px solid #002b5c; margin-top:22px; padding-top:8px;
           font-size:8.5px; color:#6b7785; text-align:center; line-height:1.7;
           position:relative; }}
.footer::before {{ content:''; position:absolute; top:-2px; left:50%;
                   transform:translateX(-50%); width:80px; height:2px;
                   background:#c62828; }}
.footer strong {{ color:#002b5c; }}
.print-btn {{ position:fixed; top:12px; right:12px; background:#002b5c;
              color:#fff; border:0; padding:10px 20px; border-radius:6px;
              font-size:11px; font-weight:600; cursor:pointer;
              box-shadow:0 2px 6px rgba(0,0,0,0.2); }}
.print-btn:hover {{ background:#003d7a; }}
@media print {{ .print-btn {{ display:none; }} body {{ padding:8mm; }} }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">🖨 Imprimer / PDF</button>

<div class="header">
  <div class="header-left">{logo_html}</div>
  <div class="header-mid">
    <h1>Fiche d'amélioration continue</h1>
    <div class="sub">Suivi des demandes d'amélioration clients</div>
    <div class="ref-box">{_esc(num)}</div>
    <div class="badges">
      <span class="badge {prio_cls}">Priorité : {_esc(prio)}</span>
      <span class="badge {statut_cls}">Statut : {_esc(statut)}</span>
    </div>
  </div>
</div>

<table>
  <tr><td class="lbl">Sujet</td><td><strong>{_esc(titre)}</strong></td></tr>
  <tr><td class="lbl">Client demandeur</td><td>{_esc(client)}</td></tr>
  <tr><td class="lbl">Technicien / Responsable</td><td>{_esc(tech)}</td></tr>
  <tr><td class="lbl">Date cible</td><td>{_esc(cible)}</td></tr>
  <tr><td class="lbl">Créé le</td><td>{_esc(str(cree)[:16])}</td></tr>
  <tr><td class="lbl">Dernière mise à jour</td><td>{_esc(str(maj)[:16])}</td></tr>
</table>

<div class="section-title">DESCRIPTION DE LA DEMANDE</div>
<div class="zone">{_esc(desc) or "—"}</div>

<div class="section-title">COMMENTAIRES / SUIVI</div>
<div class="zone">{_esc(comm) or "—"}</div>

<div class="footer">
  <strong>Emeraude Moteurs Systèmes</strong> – Amélioration continue<br>
  9bis avenue Louis Martin – 35400 Saint Malo |
  Tél : 02.99.19.01.99 | www.emeraudemoteurs.com<br>
  <em>Fiche générée le {gen_date}</em>
</div>
</body>
</html>"""


def sauvegarder_fiche(amelio):
    """Génère la fiche HTML dans le dossier du ticket et retourne le chemin."""
    num = _g(amelio, "num_ticket")
    dossier = AMELIO_DIR / num
    dossier.mkdir(parents=True, exist_ok=True)
    path = dossier / f"{num}.html"
    path.write_text(generer_html(amelio), encoding="utf-8")
    return path

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
LOGO_PATH     = Path(__file__).parent / "assets" / "logo_ems.png"
LOGO_CGV_PATH = Path(__file__).parent / "assets" / "logo_cgv.png"

# Logos embarqués (fallback si les fichiers assets/ sont absents)
try:
    from .logo_data import LOGO_EMS_B64
except ImportError:
    LOGO_EMS_B64 = ""

try:
    from .logo_data import LOGO_CGV_B64
except ImportError:
    LOGO_CGV_B64 = ""

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


def _logo_cgv_data_uri():
    """Retourne le logo CGV (avec logos partenaires) en data:URI.
    Priorité : logo_cgv.png > logo_ems.png > LOGO_CGV_B64 > LOGO_EMS_B64."""
    if LOGO_CGV_PATH.is_file():
        try:
            b = LOGO_CGV_PATH.read_bytes()
            return "data:image/png;base64," + base64.b64encode(b).decode("ascii")
        except OSError:
            pass
    if LOGO_CGV_B64:
        return "data:image/png;base64," + LOGO_CGV_B64
    if LOGO_PATH.is_file():
        try:
            b = LOGO_PATH.read_bytes()
            return "data:image/png;base64," + base64.b64encode(b).decode("ascii")
        except OSError:
            pass
    if LOGO_EMS_B64:
        return "data:image/png;base64," + LOGO_EMS_B64
    return ""


def apply_icon(win) -> None:
    """Applique favicon.ico comme icône de fenêtre (barre de titre + taskbar)."""
    import sys as _sys
    # Taskbar Windows : force l'icône de l'exe au lieu de l'icône Python
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            u"EmeraudeMoteursSystèmes.EMS")
    except Exception:
        pass
    # Barre de titre
    try:
        if getattr(_sys, "frozen", False):
            win.iconbitmap(_sys.executable)
        else:
            ico = Path(__file__).resolve().parent.parent / "favicon.ico"
            if ico.is_file():
                win.iconbitmap(str(ico))
    except Exception:
        pass


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


def _bloc_cgv():
    """Génère la page Conditions Générales de Vente + logo partenaires."""
    logo_uri = _logo_cgv_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS – Emeraude Moteurs Systemes" '
                 f'style="max-width:340px;max-height:190px;">'
                 if logo_uri else "")
    return f"""
<div class="cgv-page">
  <div class="cgv-title">CONDITIONS GÉNÉRALES DE VENTE – EMERAUDE MOTEURS SYSTEMES</div>
  <div class="cgv-body">
  <p class="cgv-p">Le fait pour nos clients de passer commande à EMERAUDE MOTEURS SYSTEMES implique, en l'absence de contrat particulier ou d'un accord écrit valant contrat entre nos clients et EMERAUDE MOTEURS SYSTEMES, l'acceptation de nos conditions générales de vente ci-dessous énoncées.</p>

  <div class="cgv-section">A • OFFRES</div>
  <div class="cgv-sub">1 • Matériels</div>
  <p class="cgv-p cgv-indent">a) <em>Caractéristiques</em> : les caractéristiques des produits proposés à la vente par EMERAUDE MOTEURS SYSTEMES lui sont communiquées par ses fournisseurs au moyen de documents mis à disposition. EMERAUDE MOTEURS SYSTEMES n'ayant pas compétence de contrôle de ceux-ci, ne peut donc pas être tenue pour responsable en cas d'erreur ou d'information erronée qui se serait introduite dans les documents techniques ou commerciaux des fabricants ou de ses propres documents.</p>
  <p class="cgv-p cgv-indent">b) <em>Spécifications</em> : de même, EMERAUDE MOTEURS SYSTEMES ne peut pas être tenu pour responsable des conséquences qui pourraient survenir dans le cas de changements dans les spécifications des produits ou matériels qu'elle commercialise.</p>
  <div class="cgv-sub">2 • Prix</div>
  <p class="cgv-p">Les prix donnés par EMERAUDE MOTEURS SYSTEMES dans ses offres ou ses tarifs peuvent avoir pour bases des éléments de calcul dont les valeurs sont du ressort des autorités politiques, administratives, ou monétaires, donnant alors le caractère de force majeure autorisant EMERAUDE MOTEURS SYSTEMES à réajuster éventuellement ses offres et ses tarifs.</p>
  <div class="cgv-sub">3 • Délais</div>
  <p class="cgv-p">Sauf pour les marchandises disponibles sur stock et dans la limite de validité spécifiée dans nos offres, les délais indiqués dans celles-ci ne valent que pour information, les délais réels étant ceux confirmés par les fournisseurs d'EMERAUDE MOTEURS SYSTEMES le jour de réception de nos commandes, auxquels s'ajoutent les délais des transporteurs et affréteurs.</p>

  <div class="cgv-section">B • COMMANDES</div>
  <p class="cgv-p">Pour des raisons d'efficacité et de rapidité dans l'exécution des commandes de nos clients, seules les commandes dont les délais atteignent ou dépassent 8 jours ouvrables seront confirmées par EMERAUDE MOTEURS SYSTEMES. Pour certains matériels devant faire l'objet d'une homologation technique après installation, EMERAUDE MOTEURS SYSTEMES se réserve le droit de ne pas accepter de commande de ces matériels sans garantie satisfaisante d'obtention de cette homologation. Pour toutes opérations commerciales, EMERAUDE MOTEURS SYSTEMES se réserve le droit de refuser de livrer, sauf contre paiement avant expédition ou garantie satisfaisante.</p>

  <div class="cgv-section">C • LIVRAISONS</div>
  <div class="cgv-sub">1 • Délais</div>
  <p class="cgv-p">Sauf stipulation contraire de nos clients clairement exprimée au moment de la commande, nos livraisons sont faites au fur et à mesure des disponibilités des matériels. EMERAUDE MOTEURS SYSTEMES ne peut être tenue pour responsable des retards ou de la non-exécution de ses livraisons du fait du mauvais temps, de grèves ou autres conflits du travail, du fait du prince, ou du cas de force majeure.</p>
  <div class="cgv-sub">2 • Risques</div>
  <p class="cgv-p">Nos marchandises, même expédiées franco de port, voyagent aux risques et périls du destinataire qui devra faire toutes réserves auprès du transporteur, seul responsable en cas de retard, vol, perte, avarie, c'est-à-dire de la bonne exécution de la prestation.</p>
  <div class="cgv-sub">3 • Emballages</div>
  <p class="cgv-p">Sauf stipulation contraire, nos emballages ne sont pas consignés et ne doivent donc pas nous être retournés, ni ne peuvent faire l'objet d'avoir ou de remise. Dans le cas d'un emballage consigné, celui-ci doit nous être retourné franco de port dans les 15 jours qui suivent la livraison. Passé ce délai, il sera facturé au prix indiqué sur le bordereau de consignation accompagnant la facture du matériel.</p>
  <div class="cgv-sub">4 • Réclamation</div>
  <p class="cgv-p">Pour être recevable, toute réclamation devra nous être adressée dans les 48 heures à réception des marchandises. La transformation, la modification de quelque manière que ce soit, ou la revente de marchandises livrées vaut renonciation à tout recours à l'encontre d'EMERAUDE MOTEURS SYSTEMES pour quelque raison que ce soit.</p>

  <div class="cgv-section">D • FACTURATION</div>
  <p class="cgv-p">La livraison des marchandises objet des commandes de nos clients déclenche l'édition de nos factures, qui sont établies suivant nos Conditions Générales de Vente objet des présentes, et les accords conclus avec nos clients préalablement à la commande. Les conditions de règlement figurant sur nos factures sont donc réputées non négociables.</p>

  <div class="cgv-section">E • PAIEMENT</div>
  <div class="cgv-sub">1 • Modalités de paiement</div>
  <p class="cgv-p">Nos marchandises sont payables à l'échéance figurant sur nos factures, entendue comme date de décaissement chez l'acheteur. Il convient donc que l'acheteur prenne de lui-même ses dispositions pour nous faire parvenir son règlement en temps et en heure pour respecter cette date. C'est entre autre le cas des traites émises par nos soins qui doivent nous être retournées dûment acceptées dans les 48 heures ouvrables, comme stipulé par l'article 135 du code du commerce.</p>
  <div class="cgv-sub">2 • Paiement anticipé</div>
  <p class="cgv-p">Le paiement anticipé de nos factures, après accord de notre part, donnera lieu à un escompte au taux de 0.5 % par période entière d'un mois. L'obtention et le montant de cet acompte ne seront effectifs qu'après constat de la date réelle de règlement. En cas d'escompte pour paiement comptant ou anticipé, celui-ci fera l'objet soit d'une note de crédit, soit d'un crédit sur le compte du client, les deux cas étant assujettis au régime normal de la T.V.A.</p>
  <div class="cgv-sub">3 • Retard ou défaut de paiement</div>
  <p class="cgv-p">Tout retard de paiement entraînera : l'exigibilité immédiate de toutes les sommes restant dû quel que soit le mode et la date de règlement prévu. Le paiement d'un intérêt de retard, par périodes d'un mois entier, égal à une fois et demie l'intérêt légal en vigueur sans pouvoir dépasser le taux de l'usure, auquel s'ajoutera une indemnité de gestion légale à 15 % des sommes dues plafonnées à 70 euros. Cet intérêt, calculé à dater du premier jour de retard, est mis en œuvre dès réception d'une mise en demeure envoyée par lettre recommandée avec accusé de réception, et exigible dès l'émission de la facture de cet intérêt. Dans le cas où les sommes dues sont versées après la date de règlement mentionnée sur la facture, une indemnité forfaitaire pour frais de recouvrement d'un montant de 40 euros sera due en plus des pénalités de retard.</p>
  <div class="cgv-sub">4 • Compensation des effets de commerce</div>
  <p class="cgv-p">Sauf convention écrite contraire signée par le responsable financier d'EMERAUDE MOTEURS SYSTEMES, le client accepte expressément que la compensation puisse être effectuée à tout moment pour les créances et les dettes réciproques échues et exigibles dès que nous lui en notifierons l'information.</p>

  <div class="cgv-section">F • RÉSERVE DE PROPRIÉTÉ</div>
  <div class="cgv-sub">1 • Transfert de propriété</div>
  <p class="cgv-p">Conformément au texte de loi n° 80.335 du 12 mai 1980 relative à la clause de réserve de propriété, les marchandises livrées restent la propriété d'EMERAUDE MOTEURS SYSTEMES jusqu'au complet paiement de leur prix principal et accessoires, paiement qui fera foi du transfert de propriété de ces marchandises d'EMERAUDE MOTEURS SYSTEMES à son client. Par contre, les risques de ces marchandises passent à la charge du client dès leur livraison. L'acheteur peut cependant revendre ou transformer ces marchandises dans le cadre de ses activités normales. Cette autorisation de revente est automatiquement retirée en cas de cessation de paiement de l'acheteur.</p>
  <div class="cgv-sub">2 • Saisie</div>
  <p class="cgv-p">En cas de saisie opérée par des tiers sur des marchandises livrées et facturées par EMERAUDE MOTEURS SYSTEMES mais non encore payées, l'acheteur est tenu d'en informer immédiatement EMERAUDE MOTEURS SYSTEMES.</p>
  <div class="cgv-sub">3 • Acomptes</div>
  <p class="cgv-p">EMERAUDE MOTEURS SYSTEMES se réserve le droit de conserver tout acompte, avoir, trop perçus, ou autre somme qui viendrait à se trouver dans sa comptabilité au crédit de son client se trouvant en défaut de paiement, ces sommes seraient alors déduites du règlement final à l'exception des éventuels intérêts et pénalités de retard.</p>

  <div class="cgv-section">G • GARANTIES</div>
  <p class="cgv-p">Tout défaut de matière ou de vice de fabrication reconnue dans nos fournitures ne peut donner lieu qu'au remplacement pur et simple des pièces défectueuses par les services techniques correspondant au constructeur des matériels et aux frais de montage et démontage du moteur. La durée de cette garantie est de 12 mois à compter de la date d'achat. La garantie ne s'applique qu'au matériel distribué par EMERAUDE MOTEURS SYSTEMES. Tout retour de moteurs ou de pièces détachées doit être effectué en port payé par l'acheteur. La garantie est refusée par EMERAUDE MOTEURS SYSTEMES dans les cas suivants : lorsque les pièces d'origine auront été remplacées par des pièces ne provenant pas d'EMERAUDE MOTEURS SYSTEMES ; en cas de modification du matériel ; lorsque les avaries seront dues à une mauvaise utilisation du moteur, à un gasoil non conforme ou pollué, à un défaut de montage et/ou au non-respect des préconisations d'installations, à tout évènement extérieur (engagement d'hélice, projection d'eau de mer, travaux de soudure…), au non-respect des conditions d'entretien et de maintenance, à la négligence de l'utilisateur ; lorsque les réparations auront été effectuées en dehors du réseau EMERAUDE MOTEURS SYSTEMES. Toutefois, en cas de non-paiement total ou partiel de ses factures EMERAUDE MOTEURS SYSTEMES ne sera pas tenu à cette garantie, le contrat de vente n'étant pas complètement respecté et le transfert de propriété non effectif. En aucun cas EMERAUDE MOTEURS SYSTEMES ne peut-être leur responsable des pertes d'exploitations occasionnées par des pannes survenues sur le matériel en cours de garanties.</p>

  <div class="cgv-section">H • ATTRIBUTION DE COMPÉTENCE</div>
  <p class="cgv-p">Il est expressément spécifié que tout litige pouvant se révéler entre EMERAUDE MOTEURS SYSTEMES et un de ses clients au cours d'une opération relevant d'un des thèmes énoncés ci-dessus sera du ressort du seul Tribunal de Commerce de Saint-Malo.</p>
  </div><!-- /cgv-body -->

  <div class="cgv-logo-wrap">
    {logo_html}
  </div>
</div>"""


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
    navire    = _g(moteur, "navire")           or _g(inv, "navire")
    machine   = _g(moteur, "machine")          or _g(inv, "machine")
    type_mot  = _g(moteur, "type_moteur")      or _g(inv, "type_moteur")
    num_serie = _g(moteur, "num_serie")        or _g(inv, "num_serie")
    date_svc  = _g(moteur, "date_mise_service") or _g(inv, "date_mise_service")
    nb_heures = _g(inv, "nb_heures_fct")
    marque    = _g(moteur, "marque")           or _g(inv, "marque")
    ref_const = _g(moteur, "ref_constructeur") or _g(inv, "ref_constructeur")

    def _moteur_bloc(label, nav, mac, mar, ns, tmot, ref, nbh, svc):
        """Génère le HTML d'un bloc moteur — template unique partagé."""
        return f"""
<table class="bloc-info">
  <colgroup>
    <col style="width:28%"><col style="width:22%">
    <col style="width:28%"><col style="width:22%">
  </colgroup>
  <tr>
    <td colspan="4" style="background:#eef2f7;font-weight:700;font-size:9.5px;
        color:#002b5c;padding:3px 8px;letter-spacing:.3px;">{label}</td>
  </tr>
  <tr>
    <td class="lbl">Navire / Site</td>
    <td>{_esc(nav)}</td>
    <td class="lbl">Type machine</td>
    <td>{_esc(mac)}</td>
  </tr>
  <tr>
    <td class="lbl">Marque moteur</td>
    <td>{_esc(mar)}</td>
    <td class="lbl">N&deg; de serie</td>
    <td><strong>{_esc(ns)}</strong></td>
  </tr>
  <tr>
    <td class="lbl">Type moteur</td>
    <td>{_esc(tmot)}</td>
    <td class="lbl">R&eacute;f. constructeur</td>
    <td>{_esc(ref)}</td>
  </tr>
  <tr>
    <td class="lbl">Nb heures de fonctionnement</td>
    <td>{_esc(nbh)}</td>
    <td class="lbl">Date mise en service</td>
    <td>{_esc(svc)}</td>
  </tr>
</table>"""

    # Moteurs supplémentaires : parsing JSON avant utilisation
    try:
        extra_moteurs = json.loads(_g(inv, "moteurs_supplementaires_json", "[]") or "[]")
    except (json.JSONDecodeError, TypeError):
        extra_moteurs = []

    _extra_moteurs_html = "".join(
        _moteur_bloc(
            f"MOTEUR {_i}",
            _g(_em, "navire"), _g(_em, "machine"), _g(_em, "marque"),
            _g(_em, "num_serie"), _g(_em, "type_moteur"),
            _g(_em, "ref_constructeur"), _g(_em, "nb_heures_fct"),
            _g(_em, "date_mise_service"),
        )
        for _i, _em in enumerate(extra_moteurs, 2)
        if _g(_em, "num_serie")
    )

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
        _depl_raw = json.loads(_g(inv, "deplacements_json", "{}") or "{}")
    except (json.JSONDecodeError, TypeError):
        _depl_raw = {}

    # Normalise vers liste de jours, chaque jour ayant une liste de techniciens.
    # Retrocompat : ancien format plat, ou jours sans cle "techniciens".
    _TECH_KEYS = ["nom", "trajet_aller_retour", "duree_intervention",
                  "temps_preparation", "temps_rangement",
                  "frais_repas", "frais_hotel", "frais_peages"]

    def _norm_jour(j):
        if "techniciens" in j and isinstance(j.get("techniciens"), list):
            return j
        return {"date": j.get("date", ""),
                "techniciens": [{k: j.get(k, "") for k in _TECH_KEYS}]}

    if "jours" in _depl_raw and isinstance(_depl_raw.get("jours"), list):
        jours_list = [_norm_jour(j) for j in _depl_raw["jours"]] or \
                     [{"date": "", "techniciens": [{}]}]
    else:
        jours_list = [{"date": "", "techniciens":
                       [{k: _depl_raw.get(k, "") for k in _TECH_KEYS}]}]

    depl = jours_list[0]["techniciens"][0] if jours_list else {}  # retrocompat

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

    def _build_jour_table(jour_data, jour_num):
        date_jour = _esc(jour_data.get("date", ""))
        techs = jour_data.get("techniciens", [{}])
        multi_jours = len(jours_list) > 1

        if multi_jours or date_jour:
            hdr_txt = f"JOUR {jour_num}"
            if date_jour:
                hdr_txt += f" &ndash; {date_jour}"
            jour_hdr = (f'<tr><td colspan="4" style="background:#eef2f7;'
                        f'font-weight:700;font-size:9.5px;color:#002b5c;'
                        f'padding:3px 8px;">{hdr_txt}</td></tr>')
        else:
            jour_hdr = ""

        rows_html = ""
        multi_techs = len(techs) > 1
        for i, tech in enumerate(techs):
            nom = _esc(tech.get("nom", ""))
            if multi_techs or nom:
                lbl = nom or f"Technicien {i + 1}"
                sep = ('<tr><td colspan="4" style="padding:0;height:1px;'
                       'background:#d0d4d9;border:none;"></td></tr>'
                       if i > 0 else "")
                rows_html += (f'{sep}<tr><td colspan="4" style="font-style:italic;'
                              f'color:#4a5560;font-size:9px;padding:2px 8px;'
                              f'background:#fafbfc;">{lbl}</td></tr>')
            t_ar = _esc(tech.get("trajet_aller_retour", ""))
            d_i  = _esc(tech.get("duree_intervention", ""))
            t_p  = _esc(tech.get("temps_preparation", ""))
            t_r  = _esc(tech.get("temps_rangement", ""))
            rows_html += (
                f'<tr><td class="lbl">Temps de trajet</td>'
                f'<td class="val">{t_ar}</td>'
                f'<td class="lbl">Frais de repas</td>'
                f'<td class="val">{_check(tech.get("frais_repas", 0))}</td></tr>'
                f'<tr><td class="lbl">Duree de l\'intervention</td>'
                f'<td class="val">{d_i}</td>'
                f'<td class="lbl">Frais d\'hotel</td>'
                f'<td class="val">{_check(tech.get("frais_hotel", 0))}</td></tr>'
                f'<tr><td class="lbl">Temps de preparation</td>'
                f'<td class="val">{t_p}</td>'
                f'<td class="lbl">Frais de peages</td>'
                f'<td class="val">{_check(tech.get("frais_peages", 0))}</td></tr>'
                f'<tr><td class="lbl">Temps de rangement</td>'
                f'<td class="val">{t_r}</td>'
                f'<td class="lbl"></td><td class="val"></td></tr>'
            )
        return f'<table class="depl">{jour_hdr}{rows_html}</table>'

    # Totaux
    import re as _re

    def _parse_h(s):
        s = str(s).strip().lower().replace(',', '.')
        if not s:
            return None
        m = _re.match(r'^(\d+):(\d{2})$', s)
        if m:
            return int(m.group(1)) + int(m.group(2)) / 60
        m = _re.match(r'^(\d+(?:\.\d+)?)h(\d{0,2})$', s)
        if m:
            return float(m.group(1)) + (int(m.group(2)) if m.group(2) else 0) / 60
        m = _re.match(r'^(\d+(?:\.\d+)?)min$', s)
        if m:
            return float(m.group(1)) / 60
        m = _re.match(r'^(\d+(?:\.\d+)?)$', s)
        if m:
            return float(m.group(1))
        return None

    def _fmt_h(h):
        hi = int(h)
        mi = round((h - hi) * 60)
        if mi == 60:
            hi += 1; mi = 0
        return f"{hi}h{mi:02d}" if mi else f"{hi}h"

    _t_keys = ["trajet_aller_retour", "duree_intervention",
               "temps_preparation", "temps_rangement"]
    _f_keys = ["frais_repas", "frais_hotel", "frais_peages"]
    _totaux = {k: None for k in _t_keys}
    _frais  = {k: 0 for k in _f_keys}
    _nb_tech_jours = 0
    for _j in jours_list:
        for _t in _j.get("techniciens", []):
            _nb_tech_jours += 1
            for _k in _t_keys:
                _v = _parse_h(_t.get(_k, ""))
                if _v is not None:
                    _totaux[_k] = (_totaux[_k] or 0) + _v
            for _k in _f_keys:
                _frais[_k] += 1 if _t.get(_k, 0) else 0

    def _tv(k):
        return _fmt_h(_totaux[k]) if _totaux[k] is not None else "&mdash;"

    _show_totaux = (len(jours_list) > 1 or _nb_tech_jours > 1 or
                    any(v is not None for v in _totaux.values()))

    if _show_totaux:
        _nb_j_lbl = f"{len(jours_list)}&nbsp;jour{'s' if len(jours_list) > 1 else ''}"
        _nb_t_lbl = (f"{_nb_tech_jours}&nbsp;technicien"
                     f"{'s' if _nb_tech_jours > 1 else ''}-jour"
                     f"{'s' if _nb_tech_jours > 1 else ''}")
        _totaux_html = (
            f'<table class="depl" style="margin-top:8px;">'
            f'<tr><td colspan="4" style="background:#002b5c;color:#fff;'
            f'font-weight:700;font-size:9.5px;padding:3px 8px;letter-spacing:.3px;">'
            f'TOTAUX ({_nb_j_lbl} &ndash; {_nb_t_lbl})</td></tr>'
            f'<tr><td class="lbl">Duree interventions</td>'
            f'<td class="val"><strong>{_tv("duree_intervention")}</strong></td>'
            f'<td class="lbl">Trajet total</td>'
            f'<td class="val">{_tv("trajet_aller_retour")}</td></tr>'
            f'<tr><td class="lbl">Preparation</td>'
            f'<td class="val">{_tv("temps_preparation")}</td>'
            f'<td class="lbl">Rangement</td>'
            f'<td class="val">{_tv("temps_rangement")}</td></tr>'
            f'<tr><td class="lbl">Repas</td>'
            f'<td class="val">{_frais["frais_repas"]}</td>'
            f'<td class="lbl">Hotel / Peages</td>'
            f'<td class="val">{_frais["frais_hotel"]} / {_frais["frais_peages"]}</td></tr>'
            f'</table>'
        )
    else:
        _totaux_html = ""

    _depl_tables_html = ("\n".join(
        _build_jour_table(j, i) for i, j in enumerate(jours_list, 1)
    ) + _totaux_html)

    statut_cls = {"En cours": "ec", "A facturer": "afact",
                  "Facture": "fact", "Clos": "clos"}.get(statut, "ec")
    urg_cls = {"Critique": "crit", "Urgente": "urg",
               "Normale": "norm"}.get(urgence, "norm")

    type_inv_display = _esc(type_inv) if type_inv else "—"

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
.type-selected {{ font-size: 13px; font-weight: 700; color: #002b5c;
    padding: 6px 0 2px 0; }}
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

/* === PAGE CGV === */
.cgv-page {{
  page-break-before: always; break-before: page;
  font-size: 7.8px; line-height: 1.38; color: #1a2332;
}}
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
.cgv-sub {{
  font-size: 7.8px; font-weight: 600; color: #1a2332;
  margin: 3px 0 1px;
}}
.cgv-p {{ margin: 0 0 3px; text-align: justify; }}
.cgv-indent {{ padding-left: 10px; }}
.cgv-logo-wrap {{
  margin-top: 10px; text-align: center;
  padding-top: 8px; border-top: 1px solid #b8c0c9;
}}

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
    <div class="type-selected">{type_inv_display}</div>
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
{_moteur_bloc("MOTEUR 1", navire, machine, marque, num_serie, type_mot, ref_const, nb_heures, date_svc)}
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
  <span class="opt"><strong>Photos :</strong>
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
{_depl_tables_html}
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
{_bloc_cgv()}
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
    # 1. Tenter de recuperer le PDF via API (cas normal cote client)
    #    On utilise POST /pdf/render avec le HTML complet (photos embarquees
    #    en base64 cote client) plutot que GET /interventions/{id}/pdf qui
    #    reconstruit le HTML cote serveur sans acces aux fichiers locaux.
    try:
        from ems_client import api as _api
        base_url = getattr(_api, "BASE_URL", None)
        if not base_url and hasattr(_api, "_read_ini_server_url"):
            base_url = _api._read_ini_server_url()
        if not base_url:
            base_url = getattr(getattr(_api, "_client", None), "base_url", None)
        if base_url:
            import urllib.request
            html_str = _build_html(inv, client=client, moteur=moteur,
                                   photos_annexe=photos_annexe, for_pdf=True)
            url = f"{base_url.rstrip('/')}/pdf/render"
            req = urllib.request.Request(
                url,
                data=html_str.encode("utf-8"),
                method="POST",
            )
            req.add_header("Content-Type", "text/html; charset=utf-8")
            api_key = (getattr(getattr(_api, "_client", None), "api_key", "")
                       or os.environ.get("EMS_API_KEY", ""))
            if api_key:
                req.add_header("X-API-Key", api_key)
            with urllib.request.urlopen(req, timeout=120) as resp:
                _write_pdf_bytes(Path(output_path), resp.read())
            return Path(output_path)
    except Exception as e:
        print(f"[bon_generator] API indisponible ({e}), tentative WeasyPrint local")

    # 2. Fallback : WeasyPrint local (cote serveur ou dev avec WeasyPrint installe)
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            "PDF impossible : API serveur injoignable ET WeasyPrint non installe.\n"
            "Verifiez la connexion reseau ou installez : pip install weasyprint"
        ) from e

    html_str = _build_html(inv, client=client, moteur=moteur,
                           photos_annexe=photos_annexe, for_pdf=True)
    HTML(string=html_str).write_pdf(str(output_path))
    return Path(output_path)


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

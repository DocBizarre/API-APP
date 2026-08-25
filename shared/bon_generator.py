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

    p = base_default / "DOSSIER-INTERVENTION-DEVIS"
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
    """Génère les 2 pages de Conditions Générales de Prestations de Services
    et d'Interventions (bon d'intervention = rapport de services, pas une
    vente de matériel) + logo partenaires en bas de la dernière page.

    Le texte est réparti en 2 blocs équilibrés (Articles 1-7 / Articles
    8-14, ~52 % / ~48 % du texte), chacun sur sa propre page (page-break
    avant chaque .cgv-page) : ça évite de laisser le rendu déborder de façon
    imprévisible selon la police/les colonnes, et ça garde le logo ancré au
    bas de la page 2 uniquement (cf. .cgv-logo-wrap / @page cgv-conditions)."""
    logo_uri = _logo_cgv_data_uri()
    logo_html = (f'<img src="{logo_uri}" alt="EMS – Emeraude Moteurs Systemes" '
                 f'style="max-width:260px;max-height:130px;">'
                 if logo_uri else "")
    return f"""
<div class="cgv-page">
  <div class="cgv-title">CONDITIONS GÉNÉRALES DE PRESTATIONS DE SERVICES ET D'INTERVENTIONS – EMERAUDE MOTEURS SYSTEMES</div>
  <div class="cgv-body">
  <p class="cgv-p" style="font-style:italic;color:#6b7785">Version 2026.01 – Applicable à compter du 10/08/2026</p>

  <div class="cgv-section">Article 1 – Champ d'application – Hiérarchie contractuelle</div>
  <p class="cgv-p">Les présentes conditions générales de prestations de services (les « Conditions Services ») s'appliquent à toutes les prestations de services réalisées par EMERAUDE MOTEURS SYSTEMES (« EMS ») au profit de ses clients professionnels (le « Client ») : diagnostic, dépannage, réparation, révision, entretien, maintenance préventive ou corrective, installation, mise en service, réglage et essais de moteurs, équipements et systèmes, que ces prestations soient réalisées dans les ateliers d'EMS ou sur site (y compris, le cas échéant, à bord de navires ou sur les installations du Client).</p>
  <p class="cgv-p">Toute demande d'intervention, acceptation de devis ou signature d'un ordre d'intervention emporte adhésion pleine et entière du Client aux présentes.</p>
  <p class="cgv-p">La relation contractuelle entre EMS et le Client est régie, par ordre de priorité décroissant, par les documents suivants : le devis, l'ordre d'intervention et, le cas échéant, les conditions particulières expressément acceptées par EMS ; les présentes Conditions Services, pour l'ensemble des prestations de diagnostic, dépannage, réparation, révision, entretien, maintenance, installation, mise en service, réglage et essais ; les Conditions Générales de Vente d'EMS, pour la fourniture des pièces, matériels, ingrédients et consommables utilisés ou vendus dans le cadre de l'intervention.</p>
  <p class="cgv-p">En cas de contradiction entre plusieurs documents contractuels, le document de rang supérieur prévaut. Les Conditions Services prévalent sur les Conditions Générales de Vente pour tout ce qui concerne l'exécution des prestations, tandis que les Conditions Générales de Vente demeurent applicables à la vente et à la fourniture des pièces et matériels. Aucun document, condition générale ou condition particulière émanant du Client ne fait partie du contrat, sauf acceptation expresse et écrite d'EMS.</p>

  <div class="cgv-section">Article 2 – Devis, ordres d'intervention et diagnostic</div>
  <p class="cgv-p">Les interventions font l'objet, selon leur nature et leur urgence, d'un devis préalable ou d'un ordre d'intervention signé par le Client. Sauf stipulation contraire, les devis sont valables trente (30) jours et sont établis sur la base des informations communiquées par le Client et, le cas échéant, d'un examen sommaire du matériel.</p>
  <p class="cgv-p">Lorsque l'établissement du devis nécessite un démontage, une expertise ou un diagnostic, ces opérations sont facturées au tarif en vigueur, même si le devis n'est pas suivi d'une commande. En cas d'acceptation du devis, le coût du diagnostic pourra être déduit du montant de l'intervention si le devis le prévoit. Si, en cours d'intervention, des travaux supplémentaires non prévisibles s'avèrent nécessaires, EMS en informe le Client et recueille son accord (écrit, ou verbal confirmé par écrit) avant de les exécuter, sauf urgence tenant à la sécurité des personnes ou des biens.</p>
  <p class="cgv-p">À défaut d'acceptation du devis dans le délai de validité, ou en cas de refus des travaux, le matériel démonté pour diagnostic est restitué en l'état, remonté sommairement sans garantie de fonctionnement, les frais de diagnostic et de remontage restant dus.</p>

  <div class="cgv-section">Article 3 – Prix et facturation des interventions</div>
  <div class="cgv-sub">3.1 Tarifs</div>
  <p class="cgv-p">Les prestations sont facturées, selon le cas, au forfait défini au devis ou en régie, sur la base des taux et forfaits figurant au tableau des coûts des prestations annexé aux présentes (l'« Annexe Tarifaire »), du temps passé (y compris temps de trajet), des frais de déplacement, de séjour et de transport, ainsi que des pièces, ingrédients et consommables utilisés. L'Annexe Tarifaire est révisée périodiquement par EMS, en principe une à deux fois par an. Les tarifs applicables sont ceux de l'Annexe Tarifaire en vigueur à la date de la demande d'intervention ou, pour les interventions faisant l'objet d'un devis, ceux du devis accepté pendant sa durée de validité.</p>
  <div class="cgv-sub">3.2 Majorations</div>
  <p class="cgv-p">Les interventions effectuées à la demande du Client en dehors des horaires normaux d'ouverture d'EMS, en urgence, de nuit, le samedi, le dimanche ou un jour férié, font l'objet des majorations prévues à l'Annexe Tarifaire.</p>
  <div class="cgv-sub">3.3 Temps d'attente et annulation</div>
  <p class="cgv-p">Tout temps d'attente imputable au Client (matériel inaccessible, non consigné, absence d'interlocuteur, autorisations manquantes) est facturé au taux horaire en vigueur. Toute intervention annulée ou reportée par le Client moins de quarante-huit (48) heures ouvrées avant la date convenue pourra donner lieu à la facturation des frais engagés et d'une indemnité forfaitaire de 150 € ou égale à 10 % du montant du devis.</p>

  <div class="cgv-section">Article 4 – Obligations du Client</div>
  <p class="cgv-p">Le Client s'engage à : (i) communiquer à EMS, préalablement à l'intervention, toutes informations utiles sur le matériel (historique, pannes, modifications, documentation technique) et sur les conditions d'accès et de sécurité du site ; (ii) assurer un libre accès au matériel, le rendre disponible, accessible, propre, dégagé et, le cas échéant, consigné (électriquement, mécaniquement, hydrauliquement) conformément à la réglementation ; (iii) fournir les moyens d'accès, de levage et de manutention appropriés lorsque l'intervention le nécessite, ces moyens demeurant sous sa responsabilité ; (iv) respecter et faire respecter les règles d'hygiène et de sécurité applicables sur son site et établir avec EMS, lorsque la réglementation l'exige, un plan de prévention (articles R.4512-6 et suivants du Code du travail) ; (v) désigner un interlocuteur habilité présent ou joignable pendant l'intervention. Tout retard, surcoût ou impossibilité d'exécution résultant du non-respect de ces obligations est à la charge du Client. EMS pourra suspendre ou refuser toute intervention si les conditions de sécurité ne sont pas réunies, sans que sa responsabilité puisse être engagée.</p>

  <div class="cgv-section">Article 5 – Exécution des prestations</div>
  <p class="cgv-p">EMS exécute les prestations conformément aux règles de l'art et est tenue, sauf stipulation expresse contraire, à une obligation de moyens. Les délais d'intervention sont communiqués à titre indicatif ; leur dépassement ne peut donner lieu ni à pénalité, ni à indemnité, ni à annulation de la commande, sauf accord écrit contraire. EMS est libre du choix de ses intervenants et peut sous-traiter tout ou partie des prestations sous sa responsabilité. Les essais et mises en service sont réalisés en présence du Client ou de son représentant ; à défaut, ils sont réputés effectués contradictoirement.</p>

  <div class="cgv-section">Article 6 – Interventions à bord de navires – Garde juridique du navire</div>
  <p class="cgv-p">Lorsque l'intervention est réalisée à bord d'un navire, quel que soit le lieu où celui-ci se trouve (à quai, au mouillage, en cale sèche, sur terre-plein ou en cours d'essais en mer), le navire, ses apparaux, ses équipements et sa cargaison demeurent, pendant toute la durée de l'intervention, la propriété exclusive du Client et restent placés sous sa garde juridique, sa direction et sa responsabilité, ainsi que, le cas échéant, sous l'autorité de son capitaine. L'intervention d'EMS, qui porte exclusivement sur les moteurs, équipements et systèmes objets de la commande, n'emporte en aucun cas transfert de la garde du navire au sens de l'article 1242 du Code civil, ni constitution d'un dépôt, y compris lorsque l'intervention se déroule en l'absence du Client, de son équipage ou de tout représentant à bord.</p>
  <p class="cgv-p">Le Client, en sa qualité de propriétaire ou d'armateur, conserve à sa charge : la sécurité et le maintien en état du navire, l'obtention des autorisations nécessaires auprès des autorités portuaires ou maritimes, ainsi que l'assurance du navire (corps et machines) et de sa responsabilité civile, pendant toute la durée de l'intervention. Les essais à quai et en mer sont réalisés sous la seule autorité, direction et responsabilité du Client et de son capitaine, le personnel d'EMS présent à bord n'intervenant qu'en qualité d'exécutant technique des travaux commandés. Le Client renonce, et se porte fort de la renonciation de ses assureurs, à tout recours contre EMS et ses assureurs pour les dommages subis par le navire qui ne résulteraient pas directement d'une faute prouvée d'EMS dans l'exécution des travaux commandés.</p>

  <div class="cgv-section">Article 7 – Matériel confié – dépôt en atelier</div>
  <p class="cgv-p">Le matériel confié à EMS pour diagnostic ou réparation voyage aux frais et risques du Client, à l'aller comme au retour. Pendant sa présence en atelier, il est couvert par l'assurance d'EMS dans les limites de ses polices ; il appartient au Client d'assurer les risques excédant ces limites ainsi que la valeur de son matériel. Conformément à la loi du 31 décembre 1903 relative à la vente de certains objets abandonnés, tout matériel non retiré dans un délai d'un (1) an à compter de la notification de la mise à disposition pourra être vendu, le produit de la vente étant affecté au paiement des sommes dues à EMS. Des frais de gardiennage de 50 € par jour pourront être facturés à compter du trentième (30e) jour suivant la mise à disposition du matériel réparé.</p>
  </div><!-- /cgv-body -->
</div><!-- /cgv-page 1/2 -->

<div class="cgv-page">
  <div class="cgv-body">

  <div class="cgv-section">Article 8 – Réception des travaux</div>
  <p class="cgv-p">À l'issue de l'intervention, un rapport d'intervention, bon de travail ou procès-verbal d'essais (le « Bon d'Intervention ») est présenté à la signature du Client ou de son représentant ; sa signature vaut réception des travaux.</p>
  <div class="cgv-sub">8.1 Absence du Client lors de l'intervention</div>
  <p class="cgv-p">Le Client est informé que certaines interventions, notamment à bord de navires ou sur des installations non gardées, peuvent être réalisées en son absence. Dans ce cas, le Bon d'Intervention est établi par le technicien d'EMS, porte la mention expresse de l'absence du Client au moment de la signature, et est adressé au Client par courrier électronique à l'adresse communiquée lors de la commande ; l'envoi à cette adresse vaut notification valable du Bon d'Intervention.</p>
  <div class="cgv-sub">8.2 Réserves et acceptation tacite</div>
  <p class="cgv-p">Faute de réserves écrites notifiées à EMS dans les quarante-huit (48) heures suivant, selon le cas, la fin de l'intervention signée contradictoirement, la remise du matériel réparé ou l'envoi du Bon d'Intervention par courrier électronique, les travaux sont réputés réceptionnés sans réserve. Le Bon d'Intervention ainsi transmis, ainsi que les journaux d'envoi de l'outil de dématérialisation d'EMS, font preuve entre les parties de la réalité, de la consistance et de la date des travaux ainsi que de leur notification, conformément aux articles 1366 et suivants du Code civil.</p>

  <div class="cgv-section">Article 9 – Paiement</div>
  <div class="cgv-sub">9.1 Modalités et délais</div>
  <p class="cgv-p">Sauf convention contraire, les factures sont payables à trente (30) jours à compter de leur date d'émission, sans pouvoir dépasser les plafonds de l'article L.441-10 du Code de commerce (60 jours date de facture ou 45 jours fin de mois). EMS peut exiger un acompte à la commande et, pour les interventions importantes, des facturations intermédiaires à l'avancement.</p>
  <div class="cgv-sub">9.2 Paiement entre les mains du factor – subrogation</div>
  <p class="cgv-p">EMS a conclu un contrat d'affacturage. Lorsque la facture porte la mention de subrogation au profit du factor, seul le paiement effectué directement entre les mains de celui-ci est libératoire.</p>
  <div class="cgv-sub">9.3 Retard de paiement</div>
  <p class="cgv-p">Tout retard de paiement entraîne de plein droit et sans mise en demeure : l'exigibilité immédiate de toutes les sommes restant dues ; des pénalités de retard au taux de la Banque centrale européenne majoré de dix (10) points de pourcentage (article L.441-10 du Code de commerce) ; une indemnité forfaitaire pour frais de recouvrement de quarante (40) euros par facture (articles L.441-10 et D.441-5 du Code de commerce) ; et la faculté pour EMS de suspendre toute intervention en cours ou à venir. Le Client s'interdit toute compensation, retenue ou déduction unilatérale sans l'accord écrit et préalable d'EMS.</p>
  <div class="cgv-sub">9.4 Droit de rétention</div>
  <p class="cgv-p">Conformément aux articles 2286 et suivants du Code civil, EMS pourra exercer un droit de rétention sur tout matériel du Client en sa possession jusqu'au complet paiement des sommes dues au titre des interventions réalisées sur ce matériel.</p>

  <div class="cgv-section">Article 10 – Garantie des interventions</div>
  <p class="cgv-p">Les travaux de réparation réalisés par EMS sont garantis contre tout défaut d'exécution pendant une durée de trois (3) mois à compter de la réception des travaux, dans la limite de deux cents (200) heures de fonctionnement du matériel si celles-ci sont atteintes avant l'expiration de ce délai. Cette garantie couvre exclusivement la reprise, dans les ateliers d'EMS ou sur site au choix d'EMS, des travaux reconnus défectueux. Les pièces neuves fournies dans le cadre de l'intervention sont garanties dans les conditions prévues aux Conditions Générales de Vente d'EMS ou, si elle est plus favorable, selon la garantie du fabricant.</p>
  <p class="cgv-p">La garantie est exclue : lorsque le défaut résulte d'une usure normale, d'un défaut d'entretien, d'une utilisation anormale ou non conforme aux préconisations du constructeur, d'une intervention d'un tiers ou du Client sur les organes réparés, d'une pièce fournie par le Client, ou d'un cas fortuit ou de force majeure ; lorsque le Client a refusé l'exécution de travaux connexes signalés comme nécessaires ; ou lorsque l'intervention a été réalisée en urgence à titre provisoire ou conservatoire. Les frais de transport, de démontage et de remontage sur site, de déplacement et de séjour restent à la charge du Client. La présente garantie ne fait pas obstacle à la garantie légale des vices cachés (articles 1641 et suivants du Code civil) entre professionnels.</p>

  <div class="cgv-section">Article 11 – Responsabilité</div>
  <p class="cgv-p">La responsabilité d'EMS est strictement limitée aux obligations définies aux présentes. Sauf faute lourde ou dolosive, la responsabilité d'EMS, toutes causes confondues, est plafonnée au montant hors taxes de l'intervention concernée. EMS ne pourra en aucun cas être tenue à la réparation des dommages indirects ou immatériels subis par le Client (perte de production, de profit, de chance, de données ou préjudice commercial), ni des dommages affectant des organes sur lesquels elle n'est pas intervenue.</p>
  <div class="cgv-sub">11.1 Exclusion des pertes d'exploitation</div>
  <p class="cgv-p">EMS ne pourra en aucun cas être tenue de réparer les pertes d'exploitation subies par le Client ou des tiers, quelle qu'en soit la cause, y compris en cas de défaut d'exécution, de retard, d'immobilisation du matériel, de reprise de travaux au titre de la garantie ou d'indisponibilité de pièces. Le Client déclare faire son affaire personnelle de l'assurance de ces risques et renonce, ainsi que ses assureurs, à tout recours contre EMS à ce titre. Cette exclusion constitue une condition essentielle du consentement d'EMS, dont il a été tenu compte dans la détermination du prix.</p>

  <div class="cgv-section">Article 12 – Force majeure</div>
  <p class="cgv-p">Conformément à l'article 1218 du Code civil, aucune des parties ne pourra être tenue pour responsable de l'inexécution de ses obligations résultant d'un événement échappant à son contrôle, raisonnablement imprévisible et dont les effets ne peuvent être évités par des mesures appropriées (intempéries exceptionnelles, grèves, pénuries de pièces, épidémies, décisions des autorités, fait du prince). Si l'empêchement est temporaire, l'exécution est suspendue ; s'il est définitif, le contrat est résolu de plein droit.</p>

  <div class="cgv-section">Article 13 – Données personnelles</div>
  <p class="cgv-p">EMS, responsable du traitement, collecte et traite les données personnelles du Client et de ses interlocuteurs aux fins de gestion des demandes, devis, commandes, interventions, facturation et recouvrement, sur le fondement de l'exécution du contrat, du respect de ses obligations légales et de son intérêt légitime. Les données peuvent être communiquées au factor d'EMS et à ses partenaires financiers. Les personnes concernées disposent d'un droit d'accès, de rectification, d'effacement, de limitation, d'opposition et de portabilité, à exercer par écrit auprès d'EMS, ainsi que du droit d'introduire une réclamation auprès de la CNIL.</p>

  <div class="cgv-section">Article 14 – Droit applicable et attribution de compétence</div>
  <p class="cgv-p">Les présentes Conditions Services et toutes les prestations qu'elles régissent sont soumises au droit français. Il est expressément spécifié que tout litige pouvant se révéler entre EMS et l'un de ses clients au cours d'une opération relevant des présentes, y compris en cas de pluralité de défendeurs ou d'appel en garantie, sera du ressort du seul Tribunal de commerce de Saint-Malo.</p>
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

    cls_garantie = _g(inv, "garantie_intervention", 0)
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
    navire_immat = _g(moteur, "navire_immatriculation") or _g(inv, "navire_immatriculation")
    navire_port  = _g(moteur, "navire_port_attache")    or _g(inv, "navire_port_attache")
    machine   = _g(moteur, "machine")          or _g(inv, "machine")
    type_mot  = _g(moteur, "type_moteur")      or _g(inv, "type_moteur")
    num_serie = _g(moteur, "num_serie")        or _g(inv, "num_serie")
    date_svc  = _g(moteur, "date_mise_service") or _g(inv, "date_mise_service")
    nb_heures = _g(inv, "nb_heures_fct")
    marque    = _g(moteur, "marque")           or _g(inv, "marque")
    ref_const = _g(moteur, "ref_constructeur") or _g(inv, "ref_constructeur")

    def _moteur_bloc(label, nav, mac, mar, ns, tmot, ref, nbh, svc, nav_immat="", nav_port=""):
        """Génère le HTML d'un bloc moteur — template unique partagé."""
        nav_detail = "".join(
            f'<br><span style="font-size:8pt;color:#6b7785;font-weight:400">{_esc(v)}</span>'
            for v in [
                nav_immat and f"Immat. : {nav_immat}",
                nav_port and f"Port d'attache : {nav_port}",
            ] if v
        )
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
    <td>{_esc(nav)}{nav_detail}</td>
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
            nav_immat=_g(_em, "navire_immatriculation"),
            nav_port=_g(_em, "navire_port_attache"),
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
                        f'padding:3px 8px;text-align:center;">{hdr_txt}</td></tr>')
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
                f'<tr><td class="lbl">Km parcourus</td>'
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

    def _parse_km(s):
        s = str(s).strip().lower().replace(',', '.').replace(' ', '')
        if not s:
            return None
        m = _re.match(r'^(\d+(?:\.\d+)?)(?:km)?$', s)
        return float(m.group(1)) if m else None

    def _fmt_km(v):
        return f"{int(v)} km" if v == int(v) else f"{v:.1f} km"

    _h_keys = ["duree_intervention", "temps_preparation", "temps_rangement"]
    _km_keys = ["trajet_aller_retour"]
    _t_keys = _km_keys + _h_keys
    _f_keys = ["frais_repas", "frais_hotel", "frais_peages"]
    _totaux = {k: None for k in _t_keys}
    _frais  = {k: 0 for k in _f_keys}
    _nb_tech_jours = 0
    for _j in jours_list:
        for _t in _j.get("techniciens", []):
            _nb_tech_jours += 1
            for _k in _h_keys:
                _v = _parse_h(_t.get(_k, ""))
                if _v is not None:
                    _totaux[_k] = (_totaux[_k] or 0) + _v
            for _k in _km_keys:
                _v = _parse_km(_t.get(_k, ""))
                if _v is not None:
                    _totaux[_k] = (_totaux[_k] or 0) + _v
            for _k in _f_keys:
                _frais[_k] += 1 if _t.get(_k, 0) else 0

    def _tv(k):
        return _fmt_h(_totaux[k]) if _totaux[k] is not None else "&mdash;"

    def _tv_km(k):
        return _fmt_km(_totaux[k]) if _totaux[k] is not None else "&mdash;"

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
            f'<td class="lbl">Distance totale</td>'
            f'<td class="val">{_tv_km("trajet_aller_retour")}</td></tr>'
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
    _cls_parts = []
    if cls_garantie: _cls_parts.append("Garantie")
    if cls_factur:   _cls_parts.append("Facturable")
    if cls_interne:  _cls_parts.append("Interne")
    cls_display = " / ".join(_cls_parts)

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
            _footer_left += f"  –  N° CMD : {_safe(num_cmd)}"
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
/* Gabarit dedie aux 2 pages de conditions generales (.cgv-page, assignees
   via la propriete CSS "page") : marge basse agrandie pour loger le logo
   partenaires, ancre dans @bottom-center via l'element "running" declare
   sur la derniere page (cf. .cgv-logo-wrap) — il n'apparait donc que sur
   cette page-la, pas sur la premiere page de conditions. */
@page cgv-conditions {{
  size: A4;
  margin: 10mm 5mm 46mm 5mm;
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
  @bottom-center {{
    content: element(cgv-logo);
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
/* Chaque bloc .cgv-page force une nouvelle page (page-break-before), et
   utilise le gabarit @page cgv-conditions (marge basse agrandie pour loger
   le logo — cf. css_pdf_extra) : les 2 pages de conditions se suivent, et le
   logo (position: running(), ci-dessous) ne s'affiche que sur la dernière,
   sur laquelle il est effectivement déclaré dans le flux. */
.cgv-page {{
  page-break-before: always; break-before: page;
  page: cgv-conditions;
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
/* Tiré du flux normal et poussé dans la marge basse de la page (via @page
   cgv-conditions / @bottom-center, cf. css_pdf_extra) : le logo se retrouve
   ainsi ancré en bas de la dernière page de conditions uniquement, plutôt
   que de suivre le texte au fil de la mise en page. */
.cgv-logo-wrap {{
  position: running(cgv-logo);
  text-align: center;
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
    {f'<div class="type-selected" style="margin-top:2px;">{_esc(cls_display)}</div>' if cls_display else ''}
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
    <td class="lbl-section" colspan="4">Demandeur</td>
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
    <td class="lbl-section" colspan="4">Signataire</td>
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
{_moteur_bloc("MOTEUR 1", navire, machine, marque, num_serie, type_mot, ref_const, nb_heures, date_svc, nav_immat=navire_immat, nav_port=navire_port)}
{_extra_moteurs_html}
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
    num_bon = num_bon.upper()
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

"""
EMS - Notifications par email.

Strategie d'envoi (ordre de priorite) :
  1. Outlook COM (win32com) : brouillon avec PDF en piece jointe automatique.
  2. Fallback mailto: + ouverture du dossier pour drag&drop manuel.
"""

import os
from pathlib import Path
from urllib.parse import quote
import webbrowser


def _esc(s):
    """Encode pour query string mailto."""
    return quote(str(s or ""), safe="")


def _build_mailto(to="", cc="", subject="", body=""):
    parts = []
    if cc:
        parts.append(f"cc={_esc(cc)}")
    if subject:
        parts.append(f"subject={_esc(subject)}")
    if body:
        parts.append(f"body={_esc(body)}")
    qs = "&".join(parts)
    return f"mailto:{_esc(to)}" + (f"?{qs}" if qs else "")


def _ouvrir_brouillon(to, cc, subject, body, attachment_path=""):
    """
    Ouvre un brouillon email avec la PJ déjà attachée.

    Stratégie :
      1. Outlook COM (win32com.client) — PJ automatique
      2. Fallback : mailto: + Explorateur ouvert sur le dossier
    """
    import logging as _log
    _logger = _log.getLogger(__name__)

    # Chemin absolu obligatoire pour Outlook COM
    pj = os.path.abspath(str(attachment_path)) if attachment_path else ""

    # ── Tentative Outlook COM ─────────────────────────────────────────────
    if pj and os.path.isfile(pj):
        try:
            import pythoncom
            import win32com.client as _wc
            # Initialiser COM sur le thread courant (requis hors thread COM natif)
            pythoncom.CoInitialize()
            ol   = _wc.Dispatch("Outlook.Application")
            mail = ol.CreateItem(0)       # 0 = olMailItem
            mail.To      = to or ""
            mail.CC      = cc or ""
            mail.Subject = subject or ""
            mail.Body    = body or ""
            mail.Attachments.Add(Source=pj)   # Source= requis, chemin absolu
            mail.Display(True)                 # True = fenêtre modale (+ fiable)
            return
        except Exception as _e:
            _logger.warning("Outlook COM indisponible (%s) — fallback mailto", _e)

    # ── Fallback : mailto + ouvrir le dossier pour drag-and-drop ─────────
    url = _build_mailto(to=to, cc=cc, subject=subject, body=body)
    webbrowser.open(url)
    if pj:
        try:
            dossier = Path(pj).parent
            if dossier.is_dir():
                os.startfile(str(dossier))
        except Exception:
            pass


# Templates
TEMPLATE_CLIENT = """Bonjour{contact_line},

Nous accusons reception de votre demande d'intervention.

Reference du bon : {num_bon}
Equipement : {machine}{navire_line}
N de serie : {num_serie}
Type d'intervention : {type_intervention}
Date prevue : {date_creation}

Votre dossier est desormais pris en charge par notre service technique. {technicien_line}vous contactera prochainement pour convenir des modalites d'intervention.

Pour toute question, n'hesitez pas a nous contacter au 02.99.19.01.99.

Cordialement,

L'equipe EMS - Emeraude Moteurs Systemes
9bis avenue Louis Martin - 35400 Saint Malo
Tel : 02.99.19.01.99
www.emeraudemoteurs.com
"""

TEMPLATE_TECHNICIEN = """Bonjour {technicien},

Une nouvelle intervention vous est assignee.

================================================
Reference : {num_bon}
Statut    : {statut}
Date      : {date_creation}
================================================

CLIENT
  Nom      : {client_nom}
  Contact  : {contact}
  Tel      : {tel}
  Email    : {email}
  Adresse  : {adresse}

DEMANDEUR (personne ayant appele)
  Nom   : {nom_demandeur}
  Email : {email_demandeur}
  Tel   : {tel_demandeur}

SIGNATAIRE
  Nom   : {nom_signataire}
  Email : {email_signataire}
  Tel   : {tel_signataire}

EQUIPEMENT
  Navire/Site : {navire}
  Machine     : {machine}
  N de serie  : {num_serie}
  Mise en service : {date_mise_service}

INTERVENTION
  Type        : {type_intervention}
  Description : {description}

Bon HTML/PDF a joindre depuis le dossier :
{bon_path}

Bon courage,
EMS
"""


TEMPLATE_CLOTURE = """Bonjour{contact_line},

Nous avons le plaisir de vous informer que l'intervention suivante est desormais cloturee.

================================================
Reference du bon : {num_bon}
Date d'intervention : {date_creation}
Date de cloture     : {date_cloture}
================================================

EQUIPEMENT
  Navire / Site : {navire}
  Machine       : {machine}
  N de serie    : {num_serie}

INTERVENTION
  Type       : {type_intervention}
  Technicien : {technicien}

TRAVAUX REALISES
{travaux}

PRECONISATIONS
{preconisation}

Le rapport complet (bon d'intervention signe) est joint a ce message.

Pour toute question ou suivi, n'hesitez pas a nous contacter au 02.99.19.01.99.

Cordialement,

L'equipe EMS - Emeraude Moteurs Systemes
Tel : 02.99.19.01.99
www.emeraudemoteurs.com
"""


def _safe(d, key, default=""):
    """Acces tolerant pour dict ou sqlite3.Row."""
    if d is None:
        return default
    try:
        v = d[key]
        return v if v is not None else default
    except (KeyError, IndexError):
        return default


def _join_emails(emails):
    """Convertit une liste/string/tuple d'emails en string CSV pour mailto."""
    if emails is None:
        return ""
    if isinstance(emails, str):
        return emails.strip()
    if isinstance(emails, (list, tuple, set)):
        return ",".join(str(e).strip() for e in emails if e and str(e).strip())
    return str(emails).strip()


def email_client(inv, client, moteur, bon_path=""):
    """
    Ouvre le client mail avec un brouillon de notification client.

    Destinataire prioritaire : email du SIGNATAIRE renseigne sur le bon.
    Fallback : email du client par defaut.
    Si un demandeur different est renseigne avec un email, il est mis en CC.

    Ouvre aussi l'Explorateur sur le dossier de l'intervention pour faciliter
    le glisser-deposer du HTML/PDF en piece jointe.
    """
    nom            = _safe(client, "nom")
    nom_signataire = _safe(inv, "nom_signataire")
    nom_demandeur  = _safe(inv, "nom_demandeur")

    # Priorite : email demandeur > email signataire > email client
    email_demandeur  = _safe(inv, "email_demandeur")
    email_signataire = _safe(inv, "email_signataire")
    email = email_demandeur or email_signataire or _safe(client, "email")

    # Nom de contact : demandeur > signataire > contact client > nom client
    contact = nom_demandeur or nom_signataire or _safe(client, "contact").strip() or nom

    # CC : email signataire si different du destinataire principal
    cc = email_signataire if email_signataire and email_signataire != email else ""

    machine = _safe(moteur, "machine") or _safe(inv, "machine")
    navire  = _safe(moteur, "navire")  or _safe(inv, "navire")
    num_bon = _safe(inv, "num_bon")

    contact_line = f" {contact}" if contact else ""
    navire_line  = f" - {navire}" if navire else ""
    technicien   = _safe(inv, "technicien")
    technicien_line = f"Notre technicien {technicien} " if technicien else "Un technicien "

    subject = f"[EMS] Prise en charge de votre demande - {num_bon}"
    body = TEMPLATE_CLIENT.format(
        contact_line=contact_line,
        num_bon=num_bon,
        machine=machine or "-",
        navire_line=navire_line,
        num_serie=_safe(moteur, "num_serie") or _safe(inv, "num_serie"),
        type_intervention=_safe(inv, "type_intervention"),
        date_creation=_safe(inv, "date_creation"),
        technicien_line=technicien_line,
    )

    _ouvrir_brouillon(to=email, cc=cc, subject=subject, body=body,
                      attachment_path=bon_path)
    return email


def email_technicien(inv, client, moteur, technicien_email="", bon_path=""):
    """
    Ouvre le client mail avec un brouillon d'assignation au technicien.

    technicien_email : peut etre une chaine, une liste, ou un tuple d'emails.
                       Si liste, ils sont separes par virgules dans le To.
                       Vide = laisse a completer manuellement par l'utilisateur.
    """
    to_str = _join_emails(technicien_email)
    num_bon = _safe(inv, "num_bon")
    subject = f"[EMS] Nouveau bon assigne - {num_bon} - {_safe(inv, 'type_intervention')}"
    body = TEMPLATE_TECHNICIEN.format(
        technicien=_safe(inv, "technicien"),
        num_bon=num_bon,
        statut=_safe(inv, "statut", "En cours"),
        date_creation=_safe(inv, "date_creation"),
        client_nom=_safe(client, "nom") or _safe(inv, "client_nom"),
        contact=_safe(client, "contact"),
        tel=_safe(client, "telephone"),
        email=_safe(client, "email"),
        adresse=_safe(client, "adresse"),
        nom_demandeur=_safe(inv, "nom_demandeur") or "-",
        email_demandeur=_safe(inv, "email_demandeur") or "-",
        tel_demandeur=_safe(inv, "telephone_demandeur") or "-",
        nom_signataire=_safe(inv, "nom_signataire") or "-",
        email_signataire=_safe(inv, "email_signataire") or "-",
        tel_signataire=_safe(inv, "telephone_signataire") or "-",
        navire=_safe(moteur, "navire") or _safe(inv, "navire"),
        machine=_safe(moteur, "machine") or _safe(inv, "machine"),
        num_serie=_safe(moteur, "num_serie") or _safe(inv, "num_serie"),
        date_mise_service=_safe(moteur, "date_mise_service"),
        type_intervention=_safe(inv, "type_intervention"),
        description=_safe(inv, "description"),
        bon_path=bon_path or "(a generer)",
    )
    _ouvrir_brouillon(to=to_str, cc="", subject=subject, body=body,
                      attachment_path=bon_path)
    return to_str


def email_cloture(inv, client, moteur, technicien_emails=None, bon_path=""):
    """
    Envoie (brouillon) le mail de clôture d'intervention.

    Destinataires :
      - TO  : email_demandeur + email_signataire (dédupliqués)
      - CC  : emails des techniciens assignés
    """
    # Destinataires principaux
    email_demandeur  = _safe(inv, "email_demandeur")
    email_signataire = _safe(inv, "email_signataire")
    to_list = [e for e in [email_demandeur, email_signataire]
               if e and e not in (to_list := [])]
    # déduplication en conservant l'ordre
    seen, to_list = set(), []
    for e in [email_demandeur, email_signataire]:
        if e and e not in seen:
            seen.add(e)
            to_list.append(e)
    to_str = ", ".join(to_list)

    # Copies : techniciens
    cc_str = _join_emails(technicien_emails or [])

    # Nom de contact pour l'accroche
    nom_demandeur  = _safe(inv, "nom_demandeur")
    nom_signataire = _safe(inv, "nom_signataire")
    contact = nom_demandeur or nom_signataire or _safe(client, "contact") or _safe(client, "nom")
    contact_line = f" {contact}" if contact else ""

    num_bon   = _safe(inv, "num_bon")
    machine   = _safe(moteur, "machine") or _safe(inv, "machine")
    navire    = _safe(moteur, "navire")  or _safe(inv, "navire")
    num_serie = _safe(moteur, "num_serie") or _safe(inv, "num_serie")

    travaux   = _safe(inv, "travaux") or "-"
    preco     = _safe(inv, "preconisation_text") or "-"

    subject = f"[EMS] Intervention clôturée - {num_bon}"
    body = TEMPLATE_CLOTURE.format(
        contact_line=contact_line,
        num_bon=num_bon,
        date_creation=_safe(inv, "date_creation"),
        date_cloture=_safe(inv, "date_cloture") or "—",
        navire=navire or "-",
        machine=machine or "-",
        num_serie=num_serie or "-",
        type_intervention=_safe(inv, "type_intervention") or "-",
        technicien=_safe(inv, "technicien") or "-",
        travaux=travaux,
        preconisation=preco,
    )

    _ouvrir_brouillon(to=to_str, cc=cc_str, subject=subject, body=body,
                      attachment_path=bon_path)
    return to_str

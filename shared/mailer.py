"""
EMS - Notifications par email.

Strategie d'envoi (ordre de priorite) :
  1. Outlook classique COM (win32com) — PJ automatique, si OUTLOOK.EXE installe.
  2. Simple MAPI (MAPISendMailW) — PJ automatique (Thunderbird, Windows Mail…),
     uniquement si Outlook classique est present (evite le dialogue d'erreur
     Windows avec le nouvel Outlook Store qui ne supporte pas MAPI).
  3. Fallback mailto: + ouverture du dossier + message informatif.
"""

import os
import base64
import html as _html_mod
from pathlib import Path
from urllib.parse import quote
import webbrowser

_LOGO_PATH = Path(__file__).parent / "assets" / "logo_ems.png"


def _logo_email_uri():
    """Logo EMS en data URI (priorité : fichier PNG, fallback logo_data embarqué)."""
    if _LOGO_PATH.is_file():
        try:
            return "data:image/png;base64," + base64.b64encode(
                _LOGO_PATH.read_bytes()).decode("ascii")
        except OSError:
            pass
    try:
        from .logo_data import LOGO_EMS_B64
        if LOGO_EMS_B64:
            return "data:image/png;base64," + LOGO_EMS_B64
    except ImportError:
        pass
    return ""


def _text_to_html(body, logo_uri=""):
    """Convertit un corps texte brut en HTML, avec logo EMS en pied de mail."""
    safe = _html_mod.escape(body or "").replace("\n", "<br>\n")
    logo_block = ""
    if logo_uri:
        logo_block = (
            '<br><hr style="border:none;border-top:1px solid #d0d7de;margin:24px 0 16px">'
            f'<img src="{logo_uri}" alt="EMS – Emeraude Moteurs Systemes" '
            'style="max-height:56px;display:block;margin-bottom:6px">'
            '<span style="font-family:\'Segoe UI\',Arial,sans-serif;font-size:11px;'
            'color:#6b7785;line-height:1.6">'
            'EMS – Emeraude Moteurs Systemes<br>'
            '9 Rue d\'Armorique – 35540 Miniac Morvan<br>'
            '<a href="https://www.emeraudemoteurs.com" '
            'style="color:#002b5c;text-decoration:none;">'
            'www.emeraudemoteurs.com</a>&nbsp;&middot;&nbsp;02.99.19.01.99'
            '</span>'
        )
    return (
        '<!DOCTYPE html><html><body style="font-family:\'Segoe UI\',Arial,sans-serif;'
        'font-size:13px;color:#1a2332;line-height:1.6;max-width:620px;margin:0;padding:0">'
        f'{safe}{logo_block}'
        '</body></html>'
    )


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


def _outlook_classique_installe():
    """
    Retourne True uniquement si l'Outlook desktop (Microsoft Office/365) est installe.
    Le nouvel Outlook (application Microsoft Store) n'est PAS detecte comme classique.
    """
    try:
        import winreg
        for hive, path in [
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"),
            (winreg.HKEY_LOCAL_MACHINE,
             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"),
        ]:
            try:
                k = winreg.OpenKey(hive, path)
                v, _ = winreg.QueryValueEx(k, "")
                winreg.CloseKey(k)
                if v and os.path.isfile(v):
                    return True
            except FileNotFoundError:
                continue
    except Exception:
        pass
    return False


def _mapi_dialog(to, cc, subject, body, pj=""):
    """
    Ouvre un brouillon via Windows Simple MAPI (MAPISendMailW).
    Compatible avec Thunderbird, Windows Mail, Outlook classique (sans COM).
    Retourne True si le dialogue a ete ouvert avec succes.
    NE PAS appeler avec le nouvel Outlook Store (provoque une erreur Windows).
    """
    import ctypes

    try:
        mapi = ctypes.WinDLL("mapi32.dll")
        fn = mapi.MAPISendMailW
    except (OSError, AttributeError):
        return False

    class _Recip(ctypes.Structure):
        _fields_ = [
            ("ulReserved",   ctypes.c_ulong),
            ("ulRecipClass", ctypes.c_ulong),
            ("lpszName",     ctypes.c_wchar_p),
            ("lpszAddress",  ctypes.c_wchar_p),
            ("ulEIDSize",    ctypes.c_ulong),
            ("lpEntryID",    ctypes.c_void_p),
        ]

    class _File(ctypes.Structure):
        _fields_ = [
            ("ulReserved",   ctypes.c_ulong),
            ("flFlags",      ctypes.c_ulong),
            ("nPosition",    ctypes.c_ulong),
            ("lpszPathName", ctypes.c_wchar_p),
            ("lpszFileName", ctypes.c_wchar_p),
            ("lpFileType",   ctypes.c_void_p),
        ]

    class _Msg(ctypes.Structure):
        _fields_ = [
            ("ulReserved",         ctypes.c_ulong),
            ("lpszSubject",        ctypes.c_wchar_p),
            ("lpszNoteText",       ctypes.c_wchar_p),
            ("lpszMessageType",    ctypes.c_wchar_p),
            ("lpszDateReceived",   ctypes.c_wchar_p),
            ("lpszConversationID", ctypes.c_wchar_p),
            ("flFlags",            ctypes.c_ulong),
            ("lpOriginator",       ctypes.c_void_p),
            ("nRecipCount",        ctypes.c_ulong),
            ("lpRecips",           ctypes.c_void_p),
            ("nFileCount",         ctypes.c_ulong),
            ("lpFiles",            ctypes.c_void_p),
        ]

    MAPI_DIALOG = 0x00000008

    recips = []
    for addr in (to or "").split(","):
        addr = addr.strip()
        if addr:
            recips.append(_Recip(ulRecipClass=1, lpszName=addr,
                                 lpszAddress=f"SMTP:{addr}"))
    for addr in (cc or "").split(","):
        addr = addr.strip()
        if addr:
            recips.append(_Recip(ulRecipClass=2, lpszName=addr,
                                 lpszAddress=f"SMTP:{addr}"))

    files = []
    if pj and os.path.isfile(pj):
        files.append(_File(nPosition=0xFFFFFFFF,
                           lpszPathName=pj,
                           lpszFileName=Path(pj).name))

    recip_arr = (_Recip * len(recips))(*recips) if recips else None
    file_arr  = (_File  * len(files)) (*files)  if files  else None

    msg = _Msg(
        lpszSubject  = subject or "",
        lpszNoteText = body    or "",
        nRecipCount  = len(recips),
        lpRecips     = ctypes.cast(recip_arr, ctypes.c_void_p) if recip_arr else None,
        nFileCount   = len(files),
        lpFiles      = ctypes.cast(file_arr,  ctypes.c_void_p) if file_arr  else None,
    )

    try:
        ret = fn(
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
            ctypes.byref(msg),
            ctypes.c_ulong(MAPI_DIALOG),
            ctypes.c_ulong(0),
        )
        return ret == 0
    except Exception:
        return False


def _ouvrir_brouillon(to, cc, subject, body, attachment_path=""):
    """
    Ouvre un brouillon email.
    Retourne True si la PJ a ete attachee automatiquement, False sinon.

    Strategie :
      1. Outlook classique COM — PJ automatique (seulement si OUTLOOK.EXE present)
      2. Simple MAPI           — PJ automatique (seulement si Outlook classique present)
      3. mailto: + dossier     — PJ manuelle (fonctionne avec le nouvel Outlook Store)
    """
    import logging as _log
    _logger = _log.getLogger(__name__)

    pj = os.path.abspath(str(attachment_path)) if attachment_path else ""
    outlook_ok = _outlook_classique_installe()

    # ── 1 & 2. Methodes avec PJ auto (uniquement Outlook classique) ────────
    if pj and os.path.isfile(pj) and outlook_ok:
        # Tentative Outlook COM
        try:
            import pythoncom
            import win32com.client as _wc
            pythoncom.CoInitialize()
            ol   = _wc.Dispatch("Outlook.Application")
            mail = ol.CreateItem(0)
            mail.To       = to or ""
            mail.CC       = cc or ""
            mail.Subject  = subject or ""
            mail.HTMLBody = _text_to_html(body, _logo_email_uri())
            mail.Attachments.Add(Source=pj)
            mail.Display(True)
            return True
        except Exception as _e:
            _logger.warning("Outlook COM indisponible (%s) — tentative MAPI", _e)

        # Tentative Simple MAPI
        try:
            if _mapi_dialog(to=to, cc=cc, subject=subject, body=body, pj=pj):
                return True
            _logger.warning("MAPI a echoue — fallback mailto")
        except Exception as _e:
            _logger.warning("MAPI indisponible (%s) — fallback mailto", _e)

    # ── 3. Fallback universel : mailto: + ouverture du dossier ────────────
    # Compatible avec le nouvel Outlook (Store), Thunderbird, webmail, etc.
    url = _build_mailto(to=to, cc=cc, subject=subject, body=body)
    try:
        webbrowser.open(url)
    except Exception as _e:
        _logger.warning("webbrowser.open echoue (%s)", _e)

    if pj:
        try:
            dossier = Path(pj).parent
            if dossier.is_dir():
                _ouvrir_dossier_reduit(dossier)
        except Exception:
            pass

    return False  # PJ non attachee automatiquement


def _ouvrir_dossier_reduit(dossier):
    """
    Ouvre le dossier dans une fenetre de taille normale (non maximisee),
    positionnee sur le cote droit de l'ecran pour ne pas recouvrir le mail.
    Utilise Shell.Application via PowerShell pour controler taille et position.
    """
    import subprocess, ctypes

    dossier_str = str(dossier)
    dossier_ps  = dossier_str.replace("'", "''")   # echapper apostrophes PowerShell

    screen_w = ctypes.windll.user32.GetSystemMetrics(0)
    screen_h = ctypes.windll.user32.GetSystemMetrics(1)

    # Fenetre a droite : ~42 % de la largeur, ~65 % de la hauteur
    w = max(520, int(screen_w * 0.42))
    h = max(420, int(screen_h * 0.65))
    x = screen_w - w - 20          # collée au bord droit, 20px de marge
    y = max(40, (screen_h - h) // 2)

    # Shell.Application.Open() crée toujours une nouvelle fenetre Explorer.
    # On attend 700 ms puis on redimensionne la derniere fenetre ouverte.
    ps = (
        f"$s = New-Object -ComObject Shell.Application; "
        f"$s.Open('{dossier_ps}'); "
        f"Start-Sleep -Milliseconds 700; "
        f"$w = ($s.Windows() | Sort-Object {{$_.HWND}} | Select-Object -Last 1); "
        f"if ($w) {{ $w.Left={x}; $w.Top={y}; $w.Width={w}; $w.Height={h} }}"
    )

    try:
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden",
             "-ExecutionPolicy", "Bypass", "-Command", ps],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception:
        try:
            os.startfile(dossier_str)      # fallback si PowerShell indisponible
        except Exception:
            pass


# Templates
TEMPLATE_CLIENT = """Bonjour{contact_line},

Nous accusons reception de votre demande d'intervention.

Reference du bon : {num_bon}
{equipements_block}
Type d'intervention : {type_intervention}
Date prevue : {date_creation}

Votre dossier est desormais pris en charge par notre service technique. {technicien_line}vous contactera prochainement pour convenir des modalites d'intervention.

Pour toute question, n'hesitez pas a nous contacter au 02.99.19.01.99.

Cordialement,

L'equipe EMS - Emeraude Moteurs Systemes
9 Rue d'Armorique - 35540 Miniac Morvan
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

DEMANDEUR
  Nom   : {nom_demandeur}
  Email : {email_demandeur}
  Tel   : {tel_demandeur}

SIGNATAIRE
  Nom   : {nom_signataire}
  Email : {email_signataire}
  Tel   : {tel_signataire}

{equipements_block}

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

{equipements_block}

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


def _extra_moteurs(inv):
    """Parse moteurs_supplementaires_json depuis l'intervention."""
    import json as _json
    try:
        raw = _safe(inv, "moteurs_supplementaires_json") or "[]"
        return _json.loads(raw)
    except (ValueError, TypeError):
        return []


def _equipements_client(moteur, extras):
    """Bloc équipement pour l'email client (format simple)."""
    items = []
    m = _safe(moteur, "machine"); n = _safe(moteur, "navire"); s = _safe(moteur, "num_serie")
    if m or s:
        items.append((m, n, s))
    for em in extras:
        m2 = _safe(em, "machine"); n2 = _safe(em, "navire"); s2 = _safe(em, "num_serie")
        if m2 or s2:
            items.append((m2, n2, s2))

    if not items:
        return "Equipement : -\nN de serie : -"
    if len(items) == 1:
        m, n, s = items[0]
        navire_part = f" - {n}" if n else ""
        return f"Equipement : {m or '-'}{navire_part}\nN de serie : {s or '-'}"

    lines = ["Equipements :"]
    for i, (m, n, s) in enumerate(items, 1):
        navire_part = f" ({n})" if n else ""
        serie_part  = f" - N° serie : {s}" if s else ""
        lines.append(f"  {i}. {m or '-'}{navire_part}{serie_part}")
    return "\n".join(lines)


def _equipements_technicien(moteur, extras):
    """Bloc EQUIPEMENT pour l'email technicien (format détaillé)."""
    items = []
    if moteur or extras:
        items.append({
            "machine": _safe(moteur, "machine"),
            "navire":  _safe(moteur, "navire"),
            "serie":   _safe(moteur, "num_serie"),
            "svc":     _safe(moteur, "date_mise_service"),
        })
        for em in extras:
            items.append({
                "machine": _safe(em, "machine"),
                "navire":  _safe(em, "navire"),
                "serie":   _safe(em, "num_serie"),
                "svc":     _safe(em, "date_mise_service"),
            })

    if not items:
        return ("EQUIPEMENT\n"
                "  Navire/Site     : -\n"
                "  Machine         : -\n"
                "  N de serie      : -\n"
                "  Mise en service : -")
    if len(items) == 1:
        it = items[0]
        return (f"EQUIPEMENT\n"
                f"  Navire/Site     : {it['navire'] or '-'}\n"
                f"  Machine         : {it['machine'] or '-'}\n"
                f"  N de serie      : {it['serie'] or '-'}\n"
                f"  Mise en service : {it['svc'] or '-'}")

    lines = ["EQUIPEMENTS"]
    for i, it in enumerate(items, 1):
        lines.append(f"  --- Moteur {i} ---")
        lines.append(f"  Navire/Site     : {it['navire'] or '-'}")
        lines.append(f"  Machine         : {it['machine'] or '-'}")
        lines.append(f"  N de serie      : {it['serie'] or '-'}")
        lines.append(f"  Mise en service : {it['svc'] or '-'}")
    return "\n".join(lines)


def _equipements_cloture(moteur, extras):
    """Bloc EQUIPEMENT pour l'email de clôture."""
    items = []
    if moteur or extras:
        items.append({
            "machine": _safe(moteur, "machine"),
            "navire":  _safe(moteur, "navire"),
            "serie":   _safe(moteur, "num_serie"),
        })
        for em in extras:
            items.append({
                "machine": _safe(em, "machine"),
                "navire":  _safe(em, "navire"),
                "serie":   _safe(em, "num_serie"),
            })

    if not items:
        return ("EQUIPEMENT\n"
                "  Navire / Site : -\n"
                "  Machine       : -\n"
                "  N de serie    : -")
    if len(items) == 1:
        it = items[0]
        return (f"EQUIPEMENT\n"
                f"  Navire / Site : {it['navire'] or '-'}\n"
                f"  Machine       : {it['machine'] or '-'}\n"
                f"  N de serie    : {it['serie'] or '-'}")

    lines = ["EQUIPEMENTS"]
    for i, it in enumerate(items, 1):
        lines.append(f"  --- Moteur {i} ---")
        lines.append(f"  Navire / Site : {it['navire'] or '-'}")
        lines.append(f"  Machine       : {it['machine'] or '-'}")
        lines.append(f"  N de serie    : {it['serie'] or '-'}")
    return "\n".join(lines)


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

    num_bon = _safe(inv, "num_bon")

    contact_line    = f" {contact}" if contact else ""
    technicien      = _safe(inv, "technicien")
    technicien_line = f"Notre technicien {technicien} " if technicien else "Un technicien "

    extras           = _extra_moteurs(inv)
    equipements_block = _equipements_client(moteur, extras)

    subject = f"[EMS] Prise en charge de votre demande - {num_bon}"
    body = TEMPLATE_CLIENT.format(
        contact_line=contact_line,
        num_bon=num_bon,
        equipements_block=equipements_block,
        type_intervention=_safe(inv, "type_intervention"),
        date_creation=_safe(inv, "date_creation"),
        technicien_line=technicien_line,
    )

    pj_auto = _ouvrir_brouillon(to=email, cc=cc, subject=subject, body=body,
                               attachment_path=bon_path)
    return email, pj_auto


def email_technicien(inv, client, moteur, technicien_email="", bon_path=""):
    """
    Ouvre le client mail avec un brouillon d'assignation au technicien.

    technicien_email : peut etre une chaine, une liste, ou un tuple d'emails.
                       Si liste, ils sont separes par virgules dans le To.
                       Vide = laisse a completer manuellement par l'utilisateur.
    """
    to_str = _join_emails(technicien_email)
    num_bon = _safe(inv, "num_bon")

    extras            = _extra_moteurs(inv)
    equipements_block = _equipements_technicien(moteur, extras)

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
        equipements_block=equipements_block,
        type_intervention=_safe(inv, "type_intervention"),
        description=_safe(inv, "description"),
        bon_path=bon_path or "(a generer)",
    )
    pj_auto = _ouvrir_brouillon(to=to_str, cc="", subject=subject, body=body,
                               attachment_path=bon_path)
    return to_str, pj_auto


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

    num_bon = _safe(inv, "num_bon")
    travaux = _safe(inv, "travaux") or "-"
    preco   = _safe(inv, "preconisation_text") or "-"

    extras            = _extra_moteurs(inv)
    equipements_block = _equipements_cloture(moteur, extras)

    subject = f"[EMS] Intervention clôturée - {num_bon}"
    body = TEMPLATE_CLOTURE.format(
        contact_line=contact_line,
        num_bon=num_bon,
        date_creation=_safe(inv, "date_creation"),
        date_cloture=_safe(inv, "date_cloture") or "—",
        equipements_block=equipements_block,
        type_intervention=_safe(inv, "type_intervention") or "-",
        technicien=_safe(inv, "technicien") or "-",
        travaux=travaux,
        preconisation=preco,
    )

    pj_auto = _ouvrir_brouillon(to=to_str, cc=cc_str, subject=subject, body=body,
                               attachment_path=bon_path)
    return to_str, pj_auto


# ─── Templates garantie ──────────────────────────────────────────────────────

_TEMPLATE_GARANTIE_CLIENT = """\
Madame, Monsieur{contact_line},

Nous vous contactons au sujet de votre dossier de demande de garantie \
n° {num_ems} concernant le moteur {num_serie}.

Statut actuel : {statut}
Attribution    : {attribution}
Responsable    : {responsable}
Date d'ouverture : {date_ouverture}

{description}

Nous restons à votre disposition pour tout renseignement complémentaire.

Cordialement,
EMS – Emeraude Moteurs Systemes
"""

_TEMPLATE_GARANTIE_TECH = """\
Bonjour {responsable},

Vous êtes désigné(e) responsable du dossier de garantie n° {num_ems}.

Client       : {client_nom}
Moteur       : {num_serie}
Attribution  : {attribution}
Statut       : {statut}
Date ouv.    : {date_ouverture}

Description :
{description}

Merci de prendre en charge ce dossier.

Cordialement,
EMS – Emeraude Moteurs Systemes
"""


def email_garantie_client(g: dict, client: dict, moteur: dict,
                          fiche_path: str = "") -> tuple:
    """Brouillon de notification client pour une demande de garantie."""
    email = (_safe(client, "email") or "")
    contact = (_safe(client, "contact") or _safe(client, "nom") or "")
    contact_line = f" {contact}" if contact else ""
    subject = f"[EMS] Dossier de garantie {_safe(g, 'num_ems')}"
    body = _TEMPLATE_GARANTIE_CLIENT.format(
        contact_line=contact_line,
        num_ems=_safe(g, "num_ems"),
        num_serie=_safe(moteur, "num_serie") or _safe(g, "num_serie"),
        statut=_safe(g, "statut"),
        attribution=_safe(g, "attribution"),
        responsable=_safe(g, "responsable") or "—",
        date_ouverture=_safe(g, "date_ouverture") or "—",
        description=_safe(g, "description") or "—",
    )
    pj_auto = _ouvrir_brouillon(to=email, cc="", subject=subject, body=body,
                                attachment_path=fiche_path)
    return email, pj_auto


def email_garantie_technicien(g: dict, client: dict, moteur: dict,
                              tech_email: str = "",
                              fiche_path: str = "") -> tuple:
    """Brouillon d'assignation du responsable garantie."""
    subject = (f"[EMS] Dossier de garantie assigné – "
               f"{_safe(g, 'num_ems')} – {_safe(moteur, 'num_serie') or _safe(g, 'num_serie')}")
    body = _TEMPLATE_GARANTIE_TECH.format(
        responsable=_safe(g, "responsable") or "Responsable",
        num_ems=_safe(g, "num_ems"),
        client_nom=_safe(client, "nom") or _safe(g, "client_nom"),
        num_serie=_safe(moteur, "num_serie") or _safe(g, "num_serie"),
        attribution=_safe(g, "attribution"),
        statut=_safe(g, "statut"),
        date_ouverture=_safe(g, "date_ouverture") or "—",
        description=_safe(g, "description") or "—",
    )
    pj_auto = _ouvrir_brouillon(to=tech_email, cc="", subject=subject, body=body,
                                attachment_path=fiche_path)
    return tech_email, pj_auto

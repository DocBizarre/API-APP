"""
═══════════════════════════════════════════════════════════════════════════════
  EMS CLIENT — Wrapper API pour les apps Tkinter — VERSION CONSOLIDEE FINALE
═══════════════════════════════════════════════════════════════════════════════

Drop-in remplacement de l'ancien `database.py`. Toutes les fonctions ont
exactement la même signature que ce que le code Tkinter (main.py,
app_garanties.py, app_amelioration.py) attend.

Cette version regroupe TOUS les correctifs et ajouts de la journee :
  • Filtres "Toutes"/"Tous" ignorés (urgence, statut, priorite, attribution)
  • Signatures upsert avec _id kwarg (client_id, moteur_id, tech_id, piece_id)
  • add_type_intervention / add_statut_garantie retournent bool (True/False)
  • update_type_intervention / update_statut_garantie idem
  • Constantes : GARANTIE_ATTRIBUTION_DEFAULT, AMELIO_STATUTS, AMELIO_PRIORITES,
    GARANTIE_DIR, AMELIO_DIR
  • garantie_status(date, duree) -> (statut, jours)
  • get_moteurs_garantie_expirante renvoie [{moteur, jours_restants}]
  • get_stats_garanties avec Total / Ouvertes / Cloturees / par_attribution / par_statut
  • Timeout 60s
  • Catalogue pieces (CRUD + bulk import + search + count + find_by_reference)

Configuration via variables d'environnement :
    EMS_API_URL   (defaut : http://127.0.0.1:8765)
    EMS_API_KEY   (vide = pas d'authentification)
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import os
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path as _Path
from typing import Any, Optional, List, Dict, Tuple
import requests


# ═══════════════════════════════════════════════════════════════════════════
#   Client HTTP de bas niveau
# ═══════════════════════════════════════════════════════════════════════════

class APIError(Exception):
    """Erreur retournee par l'API EMS."""
    def __init__(self, message: str, status_code: int = 0, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _read_ini_server_url() -> Optional[str]:
    """Lit l'URL serveur depuis config.ini place a cote de l'executable
    (ou du script). Retourne None si non trouve."""
    import sys
    from configparser import ConfigParser
    # Determiner le repertoire de l'exe (PyInstaller) ou du script
    base = _Path(sys.executable).parent if getattr(sys, "frozen", False) \
        else _Path(__file__).resolve().parent.parent
    for candidate in (base / "config.ini",
                       _Path(__file__).resolve().parent.parent / "config.ini"):
        if candidate.is_file():
            try:
                cp = ConfigParser()
                cp.read(candidate, encoding="utf-8")
                url = cp.get("server", "url", fallback="").strip()
                if url:
                    return url
            except Exception:
                continue
    return None


class EMSClient:
    """Client REST minimaliste pour l'API EMS."""

    def __init__(self, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout: float = 60.0):
        self.base_url = (base_url
                         or _read_ini_server_url()
                         or os.environ.get("EMS_API_URL",
                                            "http://127.0.0.1:8765")).rstrip("/")
        self.api_key = api_key or os.environ.get("EMS_API_KEY", "")
        self.timeout = timeout
        self._session = requests.Session()
        if self.api_key:
            self._session.headers["X-API-Key"] = self.api_key

    def _request(self, method: str, path: str, **kw) -> Any:
        url = f"{self.base_url}{path}"
        try:
            r = self._session.request(method, url, timeout=self.timeout, **kw)
        except requests.RequestException as e:
            raise APIError(f"Connexion a l'API impossible : {e}") from e
        if r.status_code == 204:
            return None
        try:
            data = r.json()
        except ValueError:
            data = r.text
        if not r.ok:
            detail = data.get("detail") if isinstance(data, dict) else data
            raise APIError(f"{r.status_code} {r.reason} : {detail}",
                           r.status_code, detail)
        return data

    def get(self, path, **params):
        return self._request("GET", path,
                              params={k: v for k, v in params.items()
                                      if v is not None and v != ""})
    def post(self, path, json):   return self._request("POST", path, json=json)
    def put(self, path, json):    return self._request("PUT", path, json=json)
    def delete(self, path):       return self._request("DELETE", path)


# Singleton global
_client = EMSClient()


def configure(base_url: Optional[str] = None, api_key: Optional[str] = None):
    """Reconfigure le client a chaud (ex: changer de serveur)."""
    global _client
    _client = EMSClient(base_url=base_url, api_key=api_key)


# ═══════════════════════════════════════════════════════════════════════════
#   Helpers locaux (pas d'appel API)
# ═══════════════════════════════════════════════════════════════════════════

def parse_techniciens(csv: str) -> List[str]:
    """'A, B, C' -> ['A', 'B', 'C']"""
    if not csv:
        return []
    return [t.strip() for t in csv.split(",") if t.strip()]


def format_techniciens(noms: List[str]) -> str:
    """['A', 'B'] -> 'A, B'"""
    return ", ".join(n.strip() for n in noms if n.strip())


def email_looks_valid(email: str) -> bool:
    if not email or "@" not in email:
        return False
    parts = email.split("@")
    return len(parts) == 2 and parts[0] and "." in parts[1]


def fmt_paris_short(dt_str) -> str:
    """Formate un datetime ISO (string ou datetime) en 'JJ/MM HH:MM'."""
    if not dt_str:
        return ""
    if isinstance(dt_str, datetime):
        dt = dt_str
    else:
        s = str(dt_str)
        dt = None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
                    "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s.replace("Z", ""), fmt)
                break
            except ValueError:
                continue
        if dt is None:
            return s[:16]
    return dt.strftime("%d/%m %H:%M")


def garantie_status(date_mise_service: str,
                     duree_garantie: str) -> Tuple[str, int]:
    """
    Retourne (statut, jours) :
      - statut : 'Active' / 'Expiree' / '-'
      - jours  : nombre de jours restants (>=0) ou ecoules (>=0 si expiree)
    """
    if not date_mise_service or not duree_garantie:
        return ("-", 0)
    try:
        d = datetime.strptime(date_mise_service, "%d/%m/%Y")
        mois = int(str(duree_garantie).strip())
        fin = d + timedelta(days=mois * 30)
        delta = (fin - datetime.now()).days
        if delta >= 0:
            return ("Active", delta)
        return ("Expiree", abs(delta))
    except (ValueError, TypeError):
        return ("-", 0)


def check_api(timeout: float = 5.0) -> Tuple[bool, str]:
    """Vérifie que le serveur est joignable. Retourne (ok, message)."""
    url = _client.base_url
    try:
        import requests as _req
        r = _req.get(f"{url}/health", timeout=timeout)
        if r.ok:
            return True, url
        return False, f"Serveur {url} a répondu {r.status_code}"
    except Exception as e:
        return False, f"Serveur injoignable à {url} : {e}"


def get_technicien_by_nom(nom: str) -> Optional[Dict]:
    if not nom:
        return None
    for t in get_techniciens():
        if (t.get("nom") or "").strip().lower() == nom.strip().lower():
            return t
    return None


# ═══════════════════════════════════════════════════════════════════════════
#   Clients
# ═══════════════════════════════════════════════════════════════════════════

def get_clients(search: str = "") -> List[Dict]:
    return _client.get("/clients", search=search)


def get_client(client_id: str) -> Optional[Dict]:
    if not client_id:
        return None
    try:
        return _client.get(f"/clients/{client_id}")
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def find_client_by_nom(nom: str) -> Optional[Dict]:
    """Retourne le premier client dont le nom correspond exactement (insensible à la casse)."""
    if not nom:
        return None
    results = get_clients(search=nom.strip())
    nom_norm = nom.strip().lower()
    for c in results:
        if (c.get("nom") or "").strip().lower() == nom_norm:
            return c
    return None


def upsert_client(data: Dict, client_id: Optional[str] = None) -> str:
    """Si client_id fourni -> PUT ; sinon POST (upsert par nom)."""
    if client_id:
        _client.put(f"/clients/{client_id}", json=data)
        return client_id
    return _client.post("/clients", json=data)["id"]


def update_client(client_id: str, data: Dict) -> Dict:
    return _client.put(f"/clients/{client_id}", json=data)


def delete_client(client_id: str) -> None:
    _client.delete(f"/clients/{client_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Moteurs
# ═══════════════════════════════════════════════════════════════════════════

def get_moteurs(search: str = "", serie_only: bool = False) -> List[Dict]:
    return _client.get("/moteurs",
                        search=search,
                        serie_only=str(bool(serie_only)).lower())


def get_moteur(moteur_id: str) -> Optional[Dict]:
    if not moteur_id:
        return None
    try:
        return _client.get(f"/moteurs/{moteur_id}")
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def find_moteur_by_serie(num_serie: str) -> Optional[Dict]:
    if not num_serie:
        return None
    return _client.get(f"/moteurs/by-serie/{num_serie}")


def upsert_moteur(data: Dict, moteur_id: Optional[str] = None) -> str:
    if moteur_id:
        _client.put(f"/moteurs/{moteur_id}", json=data)
        return moteur_id
    return _client.post("/moteurs", json=data)["id"]


def update_moteur(moteur_id: str, data: Dict) -> Dict:
    return _client.put(f"/moteurs/{moteur_id}", json=data)


def delete_moteur(moteur_id: str) -> None:
    _client.delete(f"/moteurs/{moteur_id}")


def get_moteurs_garantie_expirante(jours_max: int = 90) -> List[Dict]:
    """Retourne [{'moteur': {...}, 'jours_restants': N}, ...]"""
    moteurs = _client.get("/moteurs/garantie-expirante", jours_max=jours_max)
    res = []
    for m in moteurs:
        _, jours = garantie_status(m.get("date_mise_service", ""),
                                     m.get("duree_garantie", ""))
        res.append({"moteur": m, "jours_restants": jours})
    return res


# ═══════════════════════════════════════════════════════════════════════════
#   Techniciens
# ═══════════════════════════════════════════════════════════════════════════

def get_techniciens() -> List[Dict]:
    return _client.get("/techniciens")


def get_technicien(tech_id: str) -> Optional[Dict]:
    if not tech_id:
        return None
    try:
        return _client.get(f"/techniciens/{tech_id}")
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def upsert_technicien(data: Dict, tech_id: Optional[str] = None) -> str:
    if tech_id:
        _client.put(f"/techniciens/{tech_id}", json=data)
        return tech_id
    return _client.post("/techniciens", json=data)["id"]


def delete_technicien(tech_id: str) -> None:
    _client.delete(f"/techniciens/{tech_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Types intervention & Statuts garantie (parametrage)
# ═══════════════════════════════════════════════════════════════════════════

def get_types_intervention() -> List[str]:
    items = _client.get("/types-intervention")
    return [it["libelle"] for it in items]


def add_type_intervention(libelle: str) -> bool:
    """Retourne True si ajoute, False si doublon."""
    try:
        _client.post("/types-intervention", json={"libelle": libelle})
        return True
    except APIError as e:
        if e.status_code == 409:
            return False
        raise


def update_type_intervention(old_libelle: str, new_libelle: str) -> bool:
    """Retourne True si OK, False si le nouveau nom existe deja."""
    try:
        _client.put("/types-intervention",
                     json={"old": old_libelle, "new": new_libelle})
        return True
    except APIError as e:
        if e.status_code in (404, 409):
            return False
        raise


def delete_type_intervention(libelle: str) -> None:
    _client.delete(f"/types-intervention/{libelle}")


def get_marques() -> List[str]:
    items = _client.get("/marques-moteur")
    return [it["libelle"] for it in items]


def add_marque(libelle: str) -> bool:
    try:
        _client.post("/marques-moteur", json={"libelle": libelle})
        return True
    except APIError as e:
        if e.status_code == 409:
            return False
        raise


def update_marque(old: str, new: str) -> bool:
    try:
        _client.put("/marques-moteur", json={"old": old, "new": new})
        return True
    except APIError as e:
        if e.status_code in (404, 409):
            return False
        raise


def delete_marque(libelle: str) -> None:
    _client.delete(f"/marques-moteur/{libelle}")


def get_statuts_garantie() -> List[str]:
    items = _client.get("/statuts-garantie")
    return [it["libelle"] for it in items]


def add_statut_garantie(libelle: str) -> bool:
    """Retourne True si ajoute, False si doublon."""
    try:
        _client.post("/statuts-garantie", json={"libelle": libelle})
        return True
    except APIError as e:
        if e.status_code == 409:
            return False
        raise


def update_statut_garantie(old_libelle: str, new_libelle: str) -> bool:
    """Retourne True si OK, False si le nouveau nom existe deja."""
    try:
        _client.put("/statuts-garantie",
                     json={"old": old_libelle, "new": new_libelle})
        return True
    except APIError as e:
        if e.status_code in (404, 409):
            return False
        raise


def delete_statut_garantie(libelle: str) -> None:
    _client.delete(f"/statuts-garantie/{libelle}")


# ═══════════════════════════════════════════════════════════════════════════
#   Interventions
# ═══════════════════════════════════════════════════════════════════════════

def get_interventions(statut: Optional[str] = None,
                       search: str = "",
                       urgence: Optional[str] = None) -> List[Dict]:
    if statut in ("Tous", "tous", ""):
        statut = None
    if urgence in ("Toutes", "toutes", ""):
        urgence = None
    return _client.get("/interventions", statut=statut,
                        urgence=urgence, search=search)


def get_intervention(inv_id: Optional[str] = None,
                      num_bon: Optional[str] = None) -> Optional[Dict]:
    try:
        if inv_id:
            return _client.get(f"/interventions/{inv_id}")
        if num_bon:
            return _client.get(f"/interventions/by-num/{num_bon}")
        return None
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def get_interventions_for_moteur(moteur_id: str) -> List[Dict]:
    if not moteur_id:
        return []
    return _client.get(f"/interventions/by-moteur/{moteur_id}")


def get_interventions_urgentes(limit: int = 10) -> List[Dict]:
    return _client.get("/interventions/urgentes", limit=limit)


def get_non_notifies(limit: int = 50) -> List[Dict]:
    return _client.get("/interventions/non-notifies", limit=limit)


def create_intervention(data: Dict) -> Tuple[str, str]:
    r = _client.post("/interventions", json=data)
    return r["id"], r["num_bon"]


def update_intervention(inv_id: str, data: Dict) -> Dict:
    return _client.put(f"/interventions/{inv_id}", json=data)


def delete_intervention(inv_id: str) -> None:
    _client.delete(f"/interventions/{inv_id}")


def enregistrer_signature(inv_id: str, signature_b64: str,
                           signature_nom: str, role: str = "client") -> str:
    r = _client.post(f"/interventions/{inv_id}/signature",
                      json={"signature_b64": signature_b64,
                            "signature_nom": signature_nom,
                            "role": role})
    if role == "technicien":
        return r.get("signature_tech_date", "")
    return r.get("signature_date", "")


def mark_notifie(inv_id: str, kind: str) -> None:
    """kind = 'client' ou 'tech'."""
    _client.post(f"/interventions/{inv_id}/notifie/{kind}", json={})


# ═══════════════════════════════════════════════════════════════════════════
#   Garanties
# ═══════════════════════════════════════════════════════════════════════════

def get_garanties(statut: Optional[str] = None,
                   search: str = "",
                   attribution: Optional[str] = None) -> List[Dict]:
    if statut in ("Tous", "tous", ""):
        statut = None
    if attribution in ("Toutes", "toutes", "Tous", ""):
        attribution = None
    return _client.get("/garanties", statut=statut, search=search,
                        attribution=attribution)


def get_garantie(garantie_id: Optional[str] = None,
                  num_ems: Optional[str] = None) -> Optional[Dict]:
    try:
        if garantie_id:
            return _client.get(f"/garanties/{garantie_id}")
        if num_ems:
            return _client.get(f"/garanties/by-num/{num_ems}")
        return None
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def get_garanties_moteur(moteur_id: str) -> List[Dict]:
    if not moteur_id:
        return []
    return _client.get(f"/garanties/by-moteur/{moteur_id}")


def get_attributions_garantie() -> List[str]:
    return _client.get("/garanties/attributions")


def create_garantie(data: Dict) -> Tuple[str, str]:
    r = _client.post("/garanties", json=data)
    return r["id"], r["num_ems"]


def update_garantie(garantie_id: str, data: Dict) -> Dict:
    return _client.put(f"/garanties/{garantie_id}", json=data)


def delete_garantie(garantie_id: str) -> None:
    _client.delete(f"/garanties/{garantie_id}")


def get_stats_garanties() -> Dict:
    """
    Stats calculees en local. Retourne :
      {Total, Ouvertes, Cloturees, 'Clôturées' (avec accent),
       par_attribution: {...}, par_statut: {...}}
    """
    par_statut = Counter()
    par_attrib = Counter()
    total = 0
    for g in get_garanties():
        total += 1
        s = g.get("statut") or "Inconnu"
        par_statut[s] += 1
        a = g.get("attribution") or "Non assignee"
        par_attrib[a] += 1
    cloturees = (par_statut.get("Cloturee", 0)
                  + par_statut.get("Cloturees", 0)
                  + par_statut.get("Clôturée", 0)
                  + par_statut.get("Clôturées", 0))
    return {
        "Total":           total,
        "Ouvertes":        total - cloturees,
        "Cloturees":       cloturees,
        "Clôturées":       cloturees,
        "par_attribution": dict(par_attrib),
        "par_statut":      dict(par_statut),
    }


# ═══════════════════════════════════════════════════════════════════════════
#   Ameliorations
# ═══════════════════════════════════════════════════════════════════════════

def get_ameliorations(statut: Optional[str] = None,
                       priorite: Optional[str] = None,
                       search: str = "") -> List[Dict]:
    if statut in ("Tous", "tous", ""):
        statut = None
    if priorite in ("Toutes", "toutes", ""):
        priorite = None
    return _client.get("/ameliorations", statut=statut,
                        priorite=priorite, search=search)


def get_amelioration(amelio_id: Optional[str] = None,
                      num_ticket: Optional[str] = None) -> Optional[Dict]:
    try:
        if amelio_id:
            return _client.get(f"/ameliorations/{amelio_id}")
        if num_ticket:
            return _client.get(f"/ameliorations/by-num/{num_ticket}")
        return None
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def create_amelioration(data: Dict) -> Tuple[str, str]:
    r = _client.post("/ameliorations", json=data)
    return r["id"], r["num_ticket"]


def update_amelioration(amelio_id: str, data: Dict) -> Dict:
    return _client.put(f"/ameliorations/{amelio_id}", json=data)


def delete_amelioration(amelio_id: str) -> None:
    _client.delete(f"/ameliorations/{amelio_id}")


def get_stats_ameliorations() -> Dict:
    return _client.get("/ameliorations/stats")


# ═══════════════════════════════════════════════════════════════════════════
#   Pieces detachees (catalogue stock)
# ═══════════════════════════════════════════════════════════════════════════

def get_pieces(search: str = "", ref_only: bool = False,
                limit: int = 500) -> List[Dict]:
    """Retourne jusqu'a `limit` pieces (500 par defaut, max 5000)."""
    return _client.get("/pieces",
                        search=search,
                        ref_only=str(bool(ref_only)).lower(),
                        limit=limit)


def get_piece(piece_id: str) -> Optional[Dict]:
    if not piece_id:
        return None
    try:
        return _client.get(f"/pieces/{piece_id}")
    except APIError as e:
        if e.status_code == 404:
            return None
        raise


def find_piece_by_reference(reference: str) -> Optional[Dict]:
    if not reference:
        return None
    return _client.get(f"/pieces/by-reference/{reference}")


def count_pieces() -> int:
    return _client.get("/pieces/count").get("total", 0)


def upsert_piece(data: Dict, piece_id: Optional[str] = None) -> str:
    if piece_id:
        _client.put(f"/pieces/{piece_id}", json=data)
        return piece_id
    return _client.post("/pieces", json=data)["id"]


def update_piece(piece_id: str, data: Dict) -> Dict:
    return _client.put(f"/pieces/{piece_id}", json=data)


def delete_piece(piece_id: str) -> None:
    _client.delete(f"/pieces/{piece_id}")


def bulk_import_pieces(pieces: List[Dict],
                         skip_doublons: bool = True) -> Dict:
    """Import en masse. Retourne {importees, mises_a_jour, ignorees, erreurs, details_erreurs}."""
    return _client.post("/pieces/bulk",
                         json={"pieces": pieces,
                               "skip_doublons": skip_doublons})


# ═══════════════════════════════════════════════════════════════════════════
#   Stats globales & config dashboard
# ═══════════════════════════════════════════════════════════════════════════

def get_stats() -> Dict:
    return _client.get("/stats")


def get_stats_par_technicien() -> List[Dict]:
    return _client.get("/stats/par-technicien")


def get_stats_par_type() -> List[Dict]:
    return _client.get("/stats/par-type")


def get_activite_recente(limit: int = 20) -> List[Dict]:
    return _client.get("/stats/activite-recente", limit=limit)


def get_dashboard_widgets() -> List[str]:
    return _client.get("/config/dashboard-widgets")


def set_dashboard_widgets(widgets: List[str]) -> None:
    _client.post("/config/dashboard-widgets", json=widgets)


def get_dashboard_cards() -> List[str]:
    return _client.get("/config/dashboard-cards")


def set_dashboard_cards(cards: List[str]) -> None:
    _client.post("/config/dashboard-cards", json=cards)


# ═══════════════════════════════════════════════════════════════════════════
#   Constantes (compat ancien database.py)
# ═══════════════════════════════════════════════════════════════════════════

GARANTIE_STATUT_DEFAULT      = "Suivi EMS"
GARANTIE_ATTRIBUTION_DEFAULT = "Constructeur"
STATUTS_GARANTIE = ["Suivi EMS", "Expertise en cours",
                    "En attente infos Constructeur",
                    "En attente infos EMS",
                    "Acceptée par Constructeur",
                    "Facture transmise au Constructeur",
                    "Non pris en garantie", "Clôturée"]

AMELIO_STATUT_DEFAULT   = "Nouveau"
AMELIO_PRIORITE_DEFAULT = "Moyenne"
AMELIO_STATUTS    = ["Nouveau", "À étudier", "En cours", "Résolu", "Refusé"]
AMELIO_PRIORITES  = ["Basse", "Moyenne", "Haute", "Critique"]
PRIORITES_AMELIORATION = AMELIO_PRIORITES   # alias

# Dossiers de stockage (modifiables a chaud par les apps)
def _data_dir(name: str) -> _Path:
    """Retourne le chemin du dossier de donnees, cote exe ou cote sources."""
    import sys as _sys
    if getattr(_sys, "frozen", False):
        base = _Path(_sys.executable).parent   # a cote du .exe
    else:
        base = _Path(__file__).resolve().parent.parent  # racine projet en dev
    p = base / name
    p.mkdir(parents=True, exist_ok=True)
    return p

GARANTIE_DIR = _data_dir("garanties")
AMELIO_DIR   = _data_dir("ameliorations")


# ═══════════════════════════════════════════════════════════════════════════
#   Affaires
# ═══════════════════════════════════════════════════════════════════════════

def get_affaires(statut: str = "", search: str = "") -> List[Dict]:
    return _client.get("/affaires", statut=statut, search=search)


def get_affaire(affaire_id: str) -> Optional[Dict]:
    if not affaire_id:
        return None
    try:
        return _client.get(f"/affaires/{affaire_id}")
    except APIError:
        return None


def create_affaire(data: Dict) -> Dict:
    return _client.post("/affaires", json=data)


def update_affaire(affaire_id: str, data: Dict) -> Dict:
    return _client.put(f"/affaires/{affaire_id}", json=data)


def delete_affaire(affaire_id: str) -> None:
    _client.delete(f"/affaires/{affaire_id}")


# ─── Items d'affaire ─────────────────────────────────────────────────────────

def get_affaire_items(affaire_id: str) -> List[Dict]:
    return _client.get(f"/affaires/{affaire_id}/items")


def create_affaire_item(affaire_id: str, data: Dict) -> Dict:
    return _client.post(f"/affaires/{affaire_id}/items", json=data)


def update_affaire_item(affaire_id: str, item_id: str, data: Dict) -> Dict:
    return _client.put(f"/affaires/{affaire_id}/items/{item_id}", json=data)


def delete_affaire_item(affaire_id: str, item_id: str) -> None:
    _client.delete(f"/affaires/{affaire_id}/items/{item_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Init (no-op)
# ═══════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """Compat ancien database.py. L'API gere sa propre base."""
    pass

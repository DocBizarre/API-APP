"""
═══════════════════════════════════════════════════════════════════════════════
  EMS CLIENT — Wrapper API pour les apps Tkinter
═══════════════════════════════════════════════════════════════════════════════

Expose la même interface que l'ancien `database.py` mais s'appuie sur
l'API REST. Pour migrer une app, remplacer :

    import database as db

par :

    from ems_client import api as db

Configuration via variables d'environnement :
    EMS_API_URL   (défaut : http://127.0.0.1:8765)
    EMS_API_KEY   (vide = pas d'authentification)
═══════════════════════════════════════════════════════════════════════════════
"""
from __future__ import annotations
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, List, Dict
import requests


class APIError(Exception):
    """Erreur retournée par l'API EMS."""
    def __init__(self, message: str, status_code: int = 0, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


class EMSClient:
    """Client REST minimaliste pour l'API EMS."""

    def __init__(self, base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 timeout: float = 15.0):
        self.base_url = (base_url or
                         os.environ.get("EMS_API_URL",
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
            raise APIError(f"Connexion à l'API impossible : {e}") from e
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
    """Reconfigure le client à chaud (ex: changer de serveur)."""
    global _client
    _client = EMSClient(base_url=base_url, api_key=api_key)


# ═══════════════════════════════════════════════════════════════════════════
#   Constantes (identiques à l'ancien database.py)
# ═══════════════════════════════════════════════════════════════════════════

AMELIO_PRIORITES        = ["Basse", "Moyenne", "Haute"]
AMELIO_PRIORITE_DEFAULT = "Moyenne"
AMELIO_STATUTS          = ["À étudier", "En cours", "Terminé", "Annulé"]
AMELIO_STATUT_DEFAULT   = "À étudier"

GARANTIE_ATTRIBUTION_DEFAULT = "Constructeur"
GARANTIE_STATUT_DEFAULT      = "Suivi EMS"

# Fuseau Paris (UTC+1 hiver, UTC+2 été) — approximation sans dépendance externe
_PARIS = timezone(timedelta(hours=1))


# ═══════════════════════════════════════════════════════════════════════════
#   Utilitaires locaux (pas d'appel API)
# ═══════════════════════════════════════════════════════════════════════════

def parse_techniciens(csv: str) -> List[str]:
    """'A, B, C' → ['A', 'B', 'C']"""
    if not csv:
        return []
    return [t.strip() for t in csv.split(",") if t.strip()]


def format_techniciens(noms: List[str]) -> str:
    """['A', 'B'] → 'A, B'"""
    return ", ".join(n.strip() for n in noms if n.strip())


def email_looks_valid(email: str) -> bool:
    """Validation légère, non bloquante (comme l'ancien database.py)."""
    if not email:
        return True
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def fmt_paris_short(dt_str: str) -> str:
    """Convertit une chaîne ISO ou JJ/MM/AAAA HH:MM en format court 'JJ/MM HH:MM'."""
    if not dt_str:
        return ""
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f",
                "%d/%m/%Y %H:%M", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(dt_str[:19], fmt[:len(dt_str[:19])])
            return dt.strftime("%d/%m %H:%M")
        except ValueError:
            continue
    return dt_str[:11]


def garantie_status(moteur: Dict) -> str:
    """Retourne 'active', 'expiree' ou 'aucune' selon le moteur."""
    date_str = moteur.get("date_mise_service", "")
    duree_str = moteur.get("duree_garantie", "")
    if not date_str or not duree_str:
        return "aucune"
    try:
        duree = int(duree_str)
        for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
            try:
                debut = datetime.strptime(date_str, fmt)
                break
            except ValueError:
                continue
        else:
            return "aucune"
        fin = debut + timedelta(days=duree * 30)
        return "active" if datetime.now() <= fin else "expiree"
    except (ValueError, TypeError):
        return "aucune"


def get_technicien_by_nom(nom: str) -> Optional[Dict]:
    """Recherche un technicien par son nom exact."""
    techs = get_techniciens()
    for t in techs:
        if t.get("nom", "").lower() == nom.lower():
            return t
    return None


# ═══════════════════════════════════════════════════════════════════════════
#   Clients
# ═══════════════════════════════════════════════════════════════════════════

def get_clients(search: str = "") -> List[Dict]:
    return _client.get("/clients", search=search)


def get_client(client_id: str) -> Optional[Dict]:
    try:
        return _client.get(f"/clients/{client_id}")
    except APIError as e:
        if e.status_code == 404: return None
        raise


def upsert_client(data: Dict) -> str:
    return _client.post("/clients", json=data)["id"]


def update_client(client_id: str, data: Dict) -> Dict:
    return _client.put(f"/clients/{client_id}", json=data)


def delete_client(client_id: str) -> None:
    _client.delete(f"/clients/{client_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Moteurs
# ═══════════════════════════════════════════════════════════════════════════

def get_moteurs(search: str = "", serie_only: bool = False) -> List[Dict]:
    return _client.get("/moteurs", search=search,
                        serie_only=str(serie_only).lower())


def get_moteur(moteur_id: str) -> Optional[Dict]:
    try:
        return _client.get(f"/moteurs/{moteur_id}")
    except APIError as e:
        if e.status_code == 404: return None
        raise


def find_moteur_by_serie(num_serie: str) -> Optional[Dict]:
    try:
        return _client.get(f"/moteurs/by-serie/{num_serie}")
    except APIError as e:
        if e.status_code == 404: return None
        raise


def upsert_moteur(data: Dict) -> str:
    return _client.post("/moteurs", json=data)["id"]


def update_moteur(moteur_id: str, data: Dict) -> Dict:
    return _client.put(f"/moteurs/{moteur_id}", json=data)


def delete_moteur(moteur_id: str) -> None:
    _client.delete(f"/moteurs/{moteur_id}")


def get_moteurs_garantie_expirante(jours_max: int = 90) -> List[Dict]:
    return _client.get("/moteurs/garantie-expirante", jours_max=jours_max)


# ═══════════════════════════════════════════════════════════════════════════
#   Techniciens
# ═══════════════════════════════════════════════════════════════════════════

def get_techniciens() -> List[Dict]:
    return _client.get("/techniciens")


def get_technicien(tech_id: str) -> Optional[Dict]:
    try:
        return _client.get(f"/techniciens/{tech_id}")
    except APIError as e:
        if e.status_code == 404: return None
        raise


def upsert_technicien(data: Dict) -> str:
    return _client.post("/techniciens", json=data)["id"]


def delete_technicien(tech_id: str) -> None:
    _client.delete(f"/techniciens/{tech_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Types d'intervention
# ═══════════════════════════════════════════════════════════════════════════

def get_types_intervention() -> List[str]:
    """Retourne la liste des libellés triés par ordre."""
    try:
        items = _client.get("/types-intervention")
        return [i["libelle"] for i in items]
    except APIError:
        return []


def add_type_intervention(libelle: str) -> None:
    _client.post("/types-intervention", json={"libelle": libelle})


def update_type_intervention(old_libelle: str, new_libelle: str) -> None:
    _client.put("/types-intervention", json={"old": old_libelle,
                                              "new": new_libelle})


def delete_type_intervention(libelle: str) -> None:
    _client.delete(f"/types-intervention/{libelle}")


# ═══════════════════════════════════════════════════════════════════════════
#   Statuts de garantie
# ═══════════════════════════════════════════════════════════════════════════

def get_statuts_garantie() -> List[str]:
    try:
        items = _client.get("/statuts-garantie")
        return [i["libelle"] for i in items]
    except APIError:
        return []


def add_statut_garantie(libelle: str) -> None:
    _client.post("/statuts-garantie", json={"libelle": libelle})


def update_statut_garantie(old_libelle: str, new_libelle: str) -> None:
    _client.put("/statuts-garantie", json={"old": old_libelle,
                                            "new": new_libelle})


def delete_statut_garantie(libelle: str) -> None:
    _client.delete(f"/statuts-garantie/{libelle}")


# ═══════════════════════════════════════════════════════════════════════════
#   Interventions
# ═══════════════════════════════════════════════════════════════════════════

def get_interventions(statut: Optional[str] = None,
                       search: str = "",
                       urgence: Optional[str] = None) -> List[Dict]:
    return _client.get("/interventions", statut=statut,
                        search=search, urgence=urgence)


def get_intervention(inv_id: Optional[str] = None,
                      num_bon: Optional[str] = None) -> Optional[Dict]:
    try:
        if inv_id:
            return _client.get(f"/interventions/{inv_id}")
        if num_bon:
            return _client.get(f"/interventions/by-num/{num_bon}")
        return None
    except APIError as e:
        if e.status_code == 404: return None
        raise


def get_interventions_for_moteur(moteur_id: str) -> List[Dict]:
    return _client.get(f"/interventions/by-moteur/{moteur_id}")


def get_interventions_urgentes(limit: int = 10) -> List[Dict]:
    return _client.get("/interventions/urgentes", limit=limit)


def create_intervention(data: Dict) -> tuple[str, str]:
    """Retourne (id, num_bon)."""
    r = _client.post("/interventions", json=data)
    return r["id"], r["num_bon"]


def update_intervention(inv_id: str, data: Dict) -> Dict:
    return _client.put(f"/interventions/{inv_id}", json=data)


def delete_intervention(inv_id: str) -> None:
    _client.delete(f"/interventions/{inv_id}")


def enregistrer_signature(inv_id: str, signature_b64: str,
                           signature_nom: str, role: str = "client") -> str:
    """Retourne l'horodatage."""
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


def get_non_notifies(limit: int = 50) -> List[Dict]:
    """Interventions en cours dont client ou technicien n'a pas été notifié."""
    try:
        return _client.get("/interventions/non-notifies", limit=limit)
    except APIError:
        interventions = get_interventions(statut="En cours")
        res = [i for i in interventions
               if not i.get("client_notifie") or not i.get("tech_notifie")]
        return res[:limit]


# ═══════════════════════════════════════════════════════════════════════════
#   Garanties
# ═══════════════════════════════════════════════════════════════════════════

def get_garanties(statut: Optional[str] = None,
                   search: str = "") -> List[Dict]:
    return _client.get("/garanties", statut=statut, search=search)


def get_garantie(garantie_id: Optional[str] = None,
                  num_ems: Optional[str] = None) -> Optional[Dict]:
    try:
        if garantie_id:
            return _client.get(f"/garanties/{garantie_id}")
        if num_ems:
            return _client.get(f"/garanties/by-num/{num_ems}")
        return None
    except APIError as e:
        if e.status_code == 404: return None
        raise


def get_garanties_moteur(moteur_id: str) -> List[Dict]:
    if not moteur_id:
        return []
    return _client.get(f"/garanties/by-moteur/{moteur_id}")


def get_attributions_garantie() -> List[str]:
    try:
        return _client.get("/garanties/attributions")
    except APIError:
        return ["Constructeur", "EMS"]


def create_garantie(data: Dict) -> tuple[str, str]:
    r = _client.post("/garanties", json=data)
    return r["id"], r["num_ems"]


def update_garantie(garantie_id: str, data: Dict) -> Dict:
    return _client.put(f"/garanties/{garantie_id}", json=data)


def delete_garantie(garantie_id: str) -> None:
    _client.delete(f"/garanties/{garantie_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Améliorations
# ═══════════════════════════════════════════════════════════════════════════

def get_ameliorations(statut: Optional[str] = None,
                       priorite: Optional[str] = None,
                       search: str = "") -> List[Dict]:
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
        if e.status_code == 404: return None
        raise


def create_amelioration(data: Dict) -> tuple[str, str]:
    r = _client.post("/ameliorations", json=data)
    return r["id"], r["num_ticket"]


def update_amelioration(amelio_id: str, data: Dict) -> Dict:
    return _client.put(f"/ameliorations/{amelio_id}", json=data)


def delete_amelioration(amelio_id: str) -> None:
    _client.delete(f"/ameliorations/{amelio_id}")


# ═══════════════════════════════════════════════════════════════════════════
#   Statistiques & tableau de bord
# ═══════════════════════════════════════════════════════════════════════════

def get_stats() -> Dict:
    """Statistiques globales pour les cartes du tableau de bord."""
    try:
        return _client.get("/stats")
    except APIError:
        return {}


def get_stats_par_technicien() -> List[Dict]:
    try:
        return _client.get("/stats/par-technicien")
    except APIError:
        return []


def get_stats_par_type() -> List[Dict]:
    try:
        return _client.get("/stats/par-type")
    except APIError:
        return []


def get_activite_recente(limit: int = 20) -> List[Dict]:
    try:
        return _client.get("/stats/activite-recente", limit=limit)
    except APIError:
        return []


def get_dashboard_widgets() -> List[str]:
    """Retourne la liste ordonnée des widgets actifs."""
    try:
        r = _client.get("/config/dashboard-widgets")
        return r if isinstance(r, list) else []
    except APIError:
        return []


def set_dashboard_widgets(widgets: List[str]) -> None:
    try:
        _client.post("/config/dashboard-widgets", json=widgets)
    except APIError:
        pass


def get_dashboard_cards() -> List[str]:
    """Retourne la liste ordonnée des cartes statistiques actives."""
    try:
        r = _client.get("/config/dashboard-cards")
        return r if isinstance(r, list) else []
    except APIError:
        return []


def set_dashboard_cards(cards: List[str]) -> None:
    try:
        _client.post("/config/dashboard-cards", json=cards)
    except APIError:
        pass


# ═══════════════════════════════════════════════════════════════════════════
#   Initialisation (no-op : l'API gère elle-même)
# ═══════════════════════════════════════════════════════════════════════════

def init_db() -> None:
    """Compat ancien database.py. L'API initialise sa propre base."""
    pass

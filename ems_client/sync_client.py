"""
Synchronisation côté client (tablette).

Fonction principale : exporter_bon(inv_id)
  Pousse UN bon depuis la base locale (cache tablette) vers le serveur central.

Workflow :
  1. Lit le bon dans l'API LOCALE (127.0.0.1) — la version travaillee en terrain.
  2. L'envoie au serveur CENTRAL via POST /sync/push/bons.
  3. Analyse le resultat :
       - applique          -> succes
       - conflit detecte   -> retourne le conflit pour que l'UI demande
                              confirmation (puis re-appel avec force=True)
       - erreur reseau     -> retourne un statut "hors-ligne"

Le bon reste modifiable localement apres export (on pose juste un marqueur
visuel "exporte le ..." cote UI).
"""
from __future__ import annotations
from datetime import datetime
from typing import Dict, Any, Optional

import requests

from . import sync_config


# Resultats possibles d'un export
EXPORT_OK        = "ok"            # bon applique sur le serveur central
EXPORT_CONFLIT   = "conflit"      # le bon a ete modifie au bureau entre-temps
EXPORT_HORS_LIGNE = "hors_ligne"  # serveur central injoignable
EXPORT_ERREUR    = "erreur"       # autre erreur


def _get_local_bon(inv_id: str, timeout: float = 10.0) -> Optional[Dict[str, Any]]:
    """Recupere le bon depuis l'API locale (cache tablette)."""
    url = f"{sync_config.local_url()}/interventions/{inv_id}"
    r = requests.get(url, timeout=timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def exporter_bon(inv_id: str, force: bool = False,
                 timeout: float = 15.0) -> Dict[str, Any]:
    """
    Exporte un bon de la base locale vers le serveur central.

    Retourne un dict :
      {
        "status": EXPORT_OK | EXPORT_CONFLIT | EXPORT_HORS_LIGNE | EXPORT_ERREUR,
        "num_bon": "...",
        "message": "texte lisible",
        "conflit": {...} | None,    # presente si status == EXPORT_CONFLIT
      }
    """
    device = sync_config.device_id()

    # 1. Lire le bon localement
    try:
        bon = _get_local_bon(inv_id)
    except requests.RequestException as e:
        return {"status": EXPORT_ERREUR, "num_bon": "",
                "message": f"Impossible de lire le bon en local : {e}",
                "conflit": None}
    if not bon:
        return {"status": EXPORT_ERREUR, "num_bon": "",
                "message": f"Bon {inv_id} introuvable dans le cache local.",
                "conflit": None}

    num_bon = bon.get("num_bon", "")
    base_version = bon.get("version", 0)

    # 2. Pousser vers le serveur central
    payload = {
        "device": device,
        "bons": [{
            "data": bon,
            "base_version": base_version,
            "force": force,
        }],
    }
    url = f"{sync_config.server_url()}/sync/push/bons"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
    except requests.RequestException:
        return {"status": EXPORT_HORS_LIGNE, "num_bon": num_bon,
                "message": "Serveur central injoignable. "
                           "Vous pourrez exporter ce bon une fois "
                           "le réseau atelier disponible.",
                "conflit": None}

    if not r.ok:
        return {"status": EXPORT_ERREUR, "num_bon": num_bon,
                "message": f"Erreur serveur ({r.status_code}) : {r.text[:200]}",
                "conflit": None}

    res = r.json()

    # 3. Analyser
    if res.get("conflits"):
        cf = res["conflits"][0]
        return {"status": EXPORT_CONFLIT, "num_bon": num_bon,
                "message": (f"Le bon {num_bon} a aussi été modifié au bureau "
                            f"(version serveur {cf.get('serveur_version')} "
                            f"vs votre version {cf.get('base_version')}). "
                            "Voulez-vous écraser la version du bureau ?"),
                "conflit": cf}

    if res.get("appliques", 0) >= 1:
        return {"status": EXPORT_OK, "num_bon": num_bon,
                "message": f"Bon {num_bon} exporté vers la base centrale "
                           f"le {datetime.now().strftime('%d/%m/%Y à %H:%M')}.",
                "conflit": None}

    erreurs = res.get("erreurs", [])
    return {"status": EXPORT_ERREUR, "num_bon": num_bon,
            "message": "Export non appliqué : "
                       + ("; ".join(erreurs) if erreurs else "raison inconnue"),
            "conflit": None}


def serveur_central_joignable(timeout: float = 4.0) -> bool:
    """Teste rapidement si le serveur central repond (pour l'UI)."""
    try:
        r = requests.get(f"{sync_config.server_url()}/health", timeout=timeout)
        return r.ok
    except requests.RequestException:
        return False

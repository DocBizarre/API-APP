"""Indicateur « envoyé » des bons de commande / intentions d'achat."""
import pytest


@pytest.mark.parametrize("route,statut_envoye", [("/bons-commande", "Envoyé"),
                                                 ("/intentions-achat", "Envoyée")])
def test_marquer_envoye_puis_annuler(client, route, statut_envoye):
    r = client.post(route, json={"fournisseur_nom": "SCANIA", "lignes": []})
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["envoye_le"] == "" and b["statut"] == "Brouillon"

    r = client.post(f"{route}/{b['id']}/envoi", json={"envoye": True, "envoye_a": "a@scania.com"})
    assert r.status_code == 200, r.text
    b2 = r.json()
    assert b2["envoye_le"] and b2["envoye_a"] == "a@scania.com"
    assert b2["statut"] == statut_envoye            # Brouillon → Envoyé(e)
    assert client.get(f"{route}/{b['id']}").json()["envoye_le"] == b2["envoye_le"]

    r = client.post(f"{route}/{b['id']}/envoi", json={"envoye": False})
    assert r.json()["envoye_le"] == "" and r.json()["statut"] == statut_envoye   # statut conservé


def test_statut_avance_non_modifie(client):
    b = client.post("/bons-commande", json={"fournisseur_nom": "ZF", "statut": "Confirmé",
                                            "lignes": []}).json()
    r = client.post(f"/bons-commande/{b['id']}/envoi", json={"envoye": True})
    assert r.json()["statut"] == "Confirmé"

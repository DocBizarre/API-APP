"""Réceptions (totales ou partielles) des bons de commande fournisseur."""


def _bc(client, **kw):
    body = {"fournisseur_nom": "SCANIA", "statut": "Confirmé", "lignes": [
        {"reference": "FILTRE-1", "libelle": "Filtre à huile", "quantite": 10, "prix_unitaire": 5},
        {"reference": "JOINT-2", "libelle": "Joint culasse", "quantite": 2, "prix_unitaire": 40},
    ]}
    body.update(kw)
    r = client.post("/bons-commande", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _ids(bc):
    return [l["id"] for l in bc["lignes"]]


def test_reception_partielle_puis_complete(client):
    bc = _bc(client)
    l1, l2 = _ids(bc)
    assert bc["etat_reception"] == "" and bc["lignes"][0]["quantite_restante"] == 10

    r = client.post(f"/bons-commande/{bc['id']}/receptions", json={
        "date_reception": "03/11/2026", "numero_bl": "BL-001",
        "lignes": [{"ligne_id": l1, "quantite_recue": 6}, {"ligne_id": l2, "quantite_recue": 2}],
    })
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["statut"] == "Reçu partiellement" and b["etat_reception"] == "partielle"
    assert b["lignes"][0]["quantite_recue"] == 6 and b["lignes"][0]["quantite_restante"] == 4
    assert b["lignes"][1]["quantite_restante"] == 0
    assert b["date_livraison_reelle"] == ""
    assert len(b["receptions"]) == 1 and b["receptions"][0]["numero_bl"] == "BL-001"

    r = client.post(f"/bons-commande/{bc['id']}/receptions", json={
        "date_reception": "05/11/2026", "lignes": [{"ligne_id": l1, "quantite_recue": 4}],
    })
    b = r.json()
    assert b["statut"] == "Reçu" and b["etat_reception"] == "complete"
    assert b["date_livraison_reelle"] == "05/11/2026"
    assert len(client.get(f"/bons-commande/{bc['id']}/receptions").json()) == 2


def test_sur_reception_et_saisie_vide_refusees(client):
    bc = _bc(client)
    l1, _ = _ids(bc)
    url = f"/bons-commande/{bc['id']}/receptions"
    assert client.post(url, json={"lignes": [{"ligne_id": l1, "quantite_recue": 11}]}).status_code == 422
    assert client.post(url, json={"lignes": [{"ligne_id": l1, "quantite_recue": 0}]}).status_code == 422
    assert client.post(url, json={"lignes": [{"ligne_id": "inconnue", "quantite_recue": 1}]}).status_code == 422
    assert client.get(f"/bons-commande/{bc['id']}").json()["receptions"] == []


def test_bon_annule_non_receptionnable(client):
    bc = _bc(client, statut="Annulé")
    r = client.post(f"/bons-commande/{bc['id']}/receptions",
                    json={"lignes": [{"ligne_id": _ids(bc)[0], "quantite_recue": 1}]})
    assert r.status_code == 409


def test_annuler_reception_revient_au_statut_precedent(client):
    bc = _bc(client)
    l1, l2 = _ids(bc)
    url = f"/bons-commande/{bc['id']}/receptions"
    b = client.post(url, json={"date_reception": "01/11/2026", "lignes": [
        {"ligne_id": l1, "quantite_recue": 10}, {"ligne_id": l2, "quantite_recue": 2}]}).json()
    assert b["statut"] == "Reçu" and b["date_livraison_reelle"] == "01/11/2026"

    r = client.delete(f"{url}/{b['receptions'][0]['id']}")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["statut"] == "Confirmé" and b["date_livraison_reelle"] == "" and b["receptions"] == []


def test_modifier_le_bon_conserve_les_receptions(client):
    bc = _bc(client)
    l1, l2 = _ids(bc)
    client.post(f"/bons-commande/{bc['id']}/receptions",
                json={"lignes": [{"ligne_id": l1, "quantite_recue": 10}, {"ligne_id": l2, "quantite_recue": 2}]})

    # Ré-enregistrement avec les ids (front) + ajout d'une ligne : le bon
    # repasse en réception partielle, les quantités déjà reçues sont gardées.
    lignes = [{"id": l["id"], "reference": l["reference"], "libelle": l["libelle"],
               "quantite": l["quantite"], "prix_unitaire": l["prix_unitaire"], "ordre": i}
              for i, l in enumerate(bc["lignes"])]
    lignes.append({"reference": "VIS-3", "libelle": "Vis", "quantite": 4, "prix_unitaire": 1, "ordre": 2})
    b = client.put(f"/bons-commande/{bc['id']}", json={"lignes": lignes}).json()
    assert _ids(b)[:2] == [l1, l2]
    assert [l["quantite_recue"] for l in b["lignes"]] == [10, 2, 0]
    assert b["statut"] == "Reçu partiellement"

    # Client sans ids : rapprochement par référence + désignation
    sans_id = [{k: v for k, v in l.items() if k != "id"} for l in lignes]
    b = client.put(f"/bons-commande/{bc['id']}", json={"lignes": sans_id}).json()
    assert _ids(b)[:2] == [l1, l2]
    assert [l["quantite_recue"] for l in b["lignes"]] == [10, 2, 0]


def test_suppression_du_bon_supprime_ses_receptions(client):
    bc = _bc(client)
    client.post(f"/bons-commande/{bc['id']}/receptions",
                json={"lignes": [{"ligne_id": _ids(bc)[0], "quantite_recue": 1}]})
    assert client.delete(f"/bons-commande/{bc['id']}").status_code == 204
    assert client.get(f"/bons-commande/{bc['id']}").status_code == 404

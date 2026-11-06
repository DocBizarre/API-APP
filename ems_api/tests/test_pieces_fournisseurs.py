"""Liens références produits ↔ fournisseurs."""


def _piece(client, ref, **kw):
    r = client.post("/pieces", json={"reference": ref, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def test_bon_commande_lie_ses_lignes_au_fournisseur(client):
    p = _piece(client, "FLT-001", libelle="Filtre")
    r = client.post("/bons-commande", json={
        "fournisseur_nom": "SCANIA", "date_commande": "05/11/2026",
        "lignes": [{"piece_id": p["id"], "reference": "FLT-001", "quantite": 2, "prix_unitaire": 12.5},
                   {"reference": "INCONNUE", "quantite": 1, "prix_unitaire": 3}]})
    assert r.status_code == 201, r.text
    liens = client.get(f"/pieces/{p['id']}/fournisseurs").json()
    assert [(l["nom"], l["prix_achat"], l["date_dernier_achat"]) for l in liens] == \
        [("SCANIA", 12.5, "05/11/2026")]
    f = [x for x in client.get("/fournisseurs").json() if x["nom"] == "SCANIA"][0]
    assert f["nb_references"] == 1
    assert client.get(f"/fournisseurs/{f['id']}/pieces").json()[0]["reference"] == "FLT-001"


def test_recherche_par_fournisseur(client):
    a = _piece(client, "AAA-1", fournisseur="BAUDOUIN", ref_fournisseur="BD-77", prix_achat=40)
    _piece(client, "AAA-0")
    # ses références d'abord, avec son prix et sa référence
    res = client.get("/pieces?search=AAA&fournisseur=baudouin").json()
    assert res[0]["id"] == a["id"] and res[0]["chez_fournisseur"]
    assert res[0]["prix_fournisseur"] == 40 and res[0]["ref_fournisseur"] == "BD-77"
    assert len(client.get("/pieces?fournisseur=BAUDOUIN&only_fournisseur=true").json()) == 1
    # recherche par la référence fournisseur
    assert client.get("/pieces?search=BD-77&ref_only=true").json()[0]["id"] == a["id"]


def test_bulk_fournisseur_par_defaut_et_suppression(client):
    client.post("/pieces/bulk", json={"fournisseur": "ZF", "pieces": [
        {"reference": "Z1", "prix_achat": 5}, {"reference": "Z2", "fournisseur": "FPT"}]})
    z1 = client.get("/pieces?search=Z1").json()[0]
    z2 = client.get("/pieces?search=Z2").json()[0]
    assert [l["nom"] for l in z1["fournisseurs"]] == ["ZF"]
    assert [l["nom"] for l in z2["fournisseurs"]] == ["FPT"]
    # saisie manuelle puis suppression du lien
    r = client.put(f"/pieces/{z1['id']}/fournisseurs",
                   json={"fournisseur_nom": "PERKINS", "ref_fournisseur": "P-9", "prix_achat": 7})
    assert r.status_code == 200 and r.json()["ref_fournisseur"] == "P-9"
    fid = r.json()["fournisseur_id"]
    assert client.delete(f"/pieces/{z1['id']}/fournisseurs/{fid}").status_code == 204
    assert [l["nom"] for l in client.get(f"/pieces/{z1['id']}/fournisseurs").json()] == ["ZF"]
    # supprimer la pièce supprime ses liens
    assert client.delete(f"/pieces/{z1['id']}").status_code == 204
    zf = [x for x in client.get("/fournisseurs").json() if x["nom"] == "ZF"][0]
    assert zf["nb_references"] == 0

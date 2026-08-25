"""Vérifie que la numérotation (affaires, interventions) repart bien à 0001
au changement d'année civile."""
import sys
import datetime as real_datetime


class _FakeDateTime(real_datetime.datetime):
    _fixed_year = 2026

    @classmethod
    def now(cls, tz=None):
        return real_datetime.datetime(cls._fixed_year, 6, 15)


def _set_year(monkeypatch, year):
    # Le fixture `client` recharge les modules ems_api.* à chaque test :
    # on doit donc récupérer le module fraîchement importé (pas une
    # référence obtenue avant le rechargement) avant de le patcher.
    num_svc = sys.modules["ems_api.services.numerotation"]
    _FakeDateTime._fixed_year = year
    monkeypatch.setattr(num_svc, "datetime", _FakeDateTime)


def test_num_affaire_reset_nouvelle_annee(client, monkeypatch, client_id):
    _set_year(monkeypatch, 2026)
    a1 = client.post("/affaires", json={"client_id": client_id}).json()
    a2 = client.post("/affaires", json={"client_id": client_id}).json()
    assert a1["num_affaire"] == "AMOT20260001"
    assert a2["num_affaire"] == "AMOT20260002"

    _set_year(monkeypatch, 2027)
    a3 = client.post("/affaires", json={"client_id": client_id}).json()
    assert a3["num_affaire"] == "AMOT20270001"


def test_num_bon_reset_nouvelle_annee(client, monkeypatch, client_id, moteur_id):
    _set_year(monkeypatch, 2026)
    i1 = client.post("/interventions", json={"client_id": client_id,
                                               "moteur_id": moteur_id}).json()
    i2 = client.post("/interventions", json={"client_id": client_id,
                                              "moteur_id": moteur_id}).json()
    assert i1["num_bon"] == "BON-2026-0001"
    assert i2["num_bon"] == "BON-2026-0002"

    _set_year(monkeypatch, 2027)
    i3 = client.post("/interventions", json={"client_id": client_id,
                                              "moteur_id": moteur_id}).json()
    assert i3["num_bon"] == "BON-2027-0001"

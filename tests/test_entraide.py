import copy
from datetime import date

import pytest

from app.routes import solidarite as route_solidarite
from app.services.entraide import (
    CHAMPS,
    EntraideInvalide,
    charger_entraide,
    grouper_par_jour,
    nom_du_jour,
    valider_entraide,
)

ENTREE = {
    "nom": "Association de test",
    "type": "aide_alimentaire",
    "description": "Une distribution.",
    "jour_semaine": "mardi",
    "frequence": "chaque semaine",
    "horaires": "",
    "adresse": "",
    "conditions": "",
    "lien_inscription": "",
    "verifie_le": "",
    "a_verifier": True,
}


def entree(**changements):
    return {**copy.deepcopy(ENTREE), **changements}


def test_entraide_json_se_charge_et_est_valide():
    entrees = charger_entraide()
    noms = [e["nom"] for e in entrees]
    for attendu in ("Linkee Lille", "Cop1 Lille", "AGORAé Cité Scientifique", "Repas à 1 euro du Crous"):
        assert attendu in noms
    assert all(set(CHAMPS) <= e.keys() for e in entrees)
    assert all(e["a_verifier"] is True for e in entrees)


def test_entree_valide_acceptee():
    assert valider_entraide([entree()]) == [entree()]


def test_champ_manquant_refuse():
    incomplete = entree()
    del incomplete["horaires"]
    with pytest.raises(EntraideInvalide, match="champs manquants horaires"):
        valider_entraide([incomplete])


@pytest.mark.parametrize(
    "changements, message",
    [
        ({"nom": ""}, "champs vides nom"),
        ({"type": "autre"}, "type inconnu"),
        ({"jour_semaine": "Lundi"}, "jour_semaine"),
        ({"frequence": "tous les jours"}, "fréquence inconnue"),
        ({"lien_inscription": "http://exemple.fr"}, "https://"),
        ({"verifie_le": "hier"}, "AAAA-MM-JJ"),
        ({"a_verifier": 1}, "true ou false"),
    ],
)
def test_valeurs_invalides_refusees(changements, message):
    with pytest.raises(EntraideInvalide, match=message):
        valider_entraide([entree(**changements)])


def test_grouper_par_jour():
    semaine, sans_jour = grouper_par_jour(
        [entree(nom="A"), entree(nom="B", jour_semaine=""), entree(nom="C")]
    )
    assert list(semaine) == ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    assert [e["nom"] for e in semaine["mardi"]] == ["A", "C"]
    assert [e["nom"] for e in sans_jour] == ["B"]


def test_nom_du_jour():
    assert nom_du_jour(date(2026, 11, 23)) == "lundi"
    assert nom_du_jour(date(2026, 11, 29)) == "dimanche"


def test_page_solidarite(app, client, monkeypatch):
    monkeypatch.setattr(route_solidarite, "aujourd_hui", lambda: date(2026, 11, 24))  # un mardi
    app.extensions["entraide"] = [entree(nom="Distribution du mardi")]
    texte = client.get("/solidarite").get_data(as_text=True)
    assert "Cette semaine à Lille" in texte
    assert 'class="carte jour jour-courant"' in texte
    assert texte.index("jour-courant") < texte.index("Distribution du mardi")
    assert "jeveuxaider.gouv.fr/missions-benevolat" in texte
    assert "city=Lille" in texte
    assert "Les horaires changent souvent, vérifie sur le site de l'association." in texte


def test_entrees_sans_jour_listees_a_part(client):
    texte = client.get("/solidarite").get_data(as_text=True)
    assert "Jour à confirmer" in texte
    assert "Linkee Lille" in texte

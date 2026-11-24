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
    prochains_creneaux,
    valider_entraide,
)

ENTREE = {
    "nom": "Association de test",
    "sigle": "At",
    "type": "aide_alimentaire",
    "theme": "entraide",
    "description": "Une distribution.",
    "creneaux": [{"jour_semaine": "mardi", "horaires": "", "adresse": ""}],
    "frequence": "chaque semaine",
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


def creneau(jour="mardi", horaires="", adresse=""):
    return {"jour_semaine": jour, "horaires": horaires, "adresse": adresse}


def test_champ_manquant_refuse():
    incomplete = entree()
    del incomplete["creneaux"]
    with pytest.raises(EntraideInvalide, match="champs manquants creneaux"):
        valider_entraide([incomplete])


@pytest.mark.parametrize(
    "changements, message",
    [
        ({"nom": ""}, "champs vides nom"),
        ({"type": "autre"}, "type inconnu"),
        ({"creneaux": [creneau("Lundi")]}, "jour_semaine"),
        ({"creneaux": [{"jour_semaine": "lundi"}]}, "un créneau a jour_semaine, horaires et adresse"),
        ({"creneaux": "mardi"}, "creneaux doit être une liste"),
        ({"frequence": "tous les jours"}, "fréquence inconnue"),
        ({"lien_inscription": "http://exemple.fr"}, "https://"),
        ({"verifie_le": "hier"}, "AAAA-MM-JJ"),
        ({"a_verifier": 1}, "true ou false"),
    ],
)
def test_valeurs_invalides_refusees(changements, message):
    with pytest.raises(EntraideInvalide, match=message):
        valider_entraide([entree(**changements)])


def test_grouper_par_jour_avec_creneaux_multiples():
    deux = entree(nom="Deux", creneaux=[creneau("mardi", "18 h"), creneau("mercredi", "19 h")])
    sans = entree(nom="Sans", creneaux=[])
    adresse_seule = entree(nom="Adresse", creneaux=[creneau("", "", "Maison des Associations")])
    semaine, sans_jour = grouper_par_jour([deux, sans, adresse_seule])
    assert list(semaine) == ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    assert [(e["nom"], c["horaires"]) for e, c in semaine["mardi"]] == [("Deux", "18 h")]
    assert [(e["nom"], c["horaires"]) for e, c in semaine["mercredi"]] == [("Deux", "19 h")]
    assert [e["nom"] for e in sans_jour] == ["Sans", "Adresse"]


def test_prochains_creneaux_a_partir_d_aujourd_hui():
    entrees = [
        entree(nom="Lundi", creneaux=[creneau("lundi")]),
        entree(nom="Jeudi", creneaux=[creneau("jeudi")]),
        entree(nom="Mercredi", creneaux=[creneau("mercredi")]),
        entree(nom="Sans jour", creneaux=[]),
    ]
    rdv = prochains_creneaux(entrees, date(2026, 11, 25), limite=3)  # un mercredi
    assert [(r["nom"], r["aujourd_hui"]) for r in rdv] == [
        ("Mercredi", True),
        ("Jeudi", False),
        ("Lundi", False),
    ]


def test_donnees_linkee_et_cop1():
    entrees = {e["nom"]: e for e in charger_entraide()}
    linkee = entrees["Linkee Lille"]
    assert [c["jour_semaine"] for c in linkee["creneaux"]] == ["mardi", "mercredi"]
    assert linkee["creneaux"][0]["adresse"] == "Bazaar St-So, 292 rue Camille Guérin, Lille"
    assert linkee["lien_inscription"] == "https://linkee.fillout.com/inscriptions"
    cop1 = entrees["Cop1 Lille"]
    assert cop1["frequence"] == "une semaine sur deux"
    assert cop1["creneaux"][0]["jour_semaine"] == "jeudi"
    assert all(e["a_verifier"] is True for e in entrees.values())


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


def test_linkee_sous_ses_deux_jours(client):
    texte = client.get("/solidarite").get_data(as_text=True)
    mardi = texte[texte.index('id="jour-mardi"') : texte.index('id="jour-mercredi"')]
    mercredi = texte[texte.index('id="jour-mercredi"') : texte.index('id="jour-jeudi"')]
    assert "Linkee Lille" in mardi and "Bazaar St-So" in mardi
    assert "Linkee Lille" in mercredi and "Chaud Bouillon" in mercredi
    assert "Chaud Bouillon" not in mardi


def test_entrees_sans_jour_listees_a_part(client):
    texte = client.get("/solidarite").get_data(as_text=True)
    a_confirmer = texte[texte.index("Jour à confirmer") : texte.index("Devenir bénévole")]
    assert "AGORAé Cité Scientifique" in a_confirmer
    assert "Linkee Lille" not in a_confirmer


def test_accueil_et_laterale_seulement_les_rendez_vous_dates(client):
    texte = client.get("/").get_data(as_text=True)
    bloc = texte[texte.index('id="titre-semaine"') :]
    assert "Linkee Lille" in bloc
    assert "AGORAé" not in bloc
    assert "Jour à confirmer" not in bloc


def test_bloc_masque_sans_rendez_vous_date(app, client):
    app.extensions["entraide"] = [entree(nom="Sans jour", creneaux=[])]
    assert "titre-semaine" not in client.get("/").get_data(as_text=True)
    assert "titre-semaine" not in client.get("/lille/se-loger").get_data(as_text=True)
    assert "Jour à confirmer" in client.get("/solidarite").get_data(as_text=True)

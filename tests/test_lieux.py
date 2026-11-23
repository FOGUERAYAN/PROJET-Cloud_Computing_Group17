import copy

import pytest

from app.services.lieux import (
    CHAMPS,
    LieuInvalide,
    charger_lieux,
    filtrer_decouvrir,
    par_categorie,
    premiere_phrase,
    valider_lieux,
)

LIEU = {
    "id": "test",
    "nom": "Lieu de test",
    "sigle": "",
    "categorie": "decouverte",
    "sous_categorie": "a_voir",
    "theme": "bons-plans",
    "description": "Première phrase. Deuxième phrase.",
    "adresse": "",
    "metro": "",
    "lien_officiel": "",
    "lien_carte": "https://www.openstreetmap.org/search?query=Lille",
    "photo": "",
    "credit_photo": "",
    "prix_indicatif": "",
    "verifie_le": "",
    "a_verifier": True,
}


def lieu(**changements):
    return {**copy.deepcopy(LIEU), **changements}


def test_lieux_json_se_charge_et_est_valide():
    lieux = charger_lieux()
    ids = {x["id"] for x in lieux}
    for attendu in ("cpam", "caf", "crous", "office_tourisme", "grand_place", "vieille_bourse"):
        assert attendu in ids
    for attendu in ("citadelle", "vieux_lille", "marche_wazemmes", "crous_logement", "lokaviz"):
        assert attendu in ids
    assert all(set(CHAMPS) <= x.keys() for x in lieux)
    assert all(x["a_verifier"] is True for x in lieux)


def test_lieu_valide_accepte():
    assert valider_lieux([lieu()]) == [lieu()]


def test_champ_manquant_refuse():
    incomplet = lieu()
    del incomplet["metro"]
    with pytest.raises(LieuInvalide, match="champs manquants metro"):
        valider_lieux([incomplet])


def test_champ_obligatoire_vide_refuse():
    with pytest.raises(LieuInvalide, match="champs vides nom"):
        valider_lieux([lieu(nom="  ")])


def test_photo_sans_credit_refusee():
    with pytest.raises(LieuInvalide, match="crédit photo"):
        valider_lieux([lieu(photo="grand-place.jpg")])


def test_photo_avec_credit_acceptee():
    valider_lieux([lieu(photo="grand-place.jpg", credit_photo="Auteur, CC BY-SA 4.0")])


@pytest.mark.parametrize(
    "changements, message",
    [
        ({"categorie": "inconnue"}, "catégorie inconnue"),
        ({"lien_carte": "https://exemple.com/carte"}, "OpenStreetMap"),
        ({"verifie_le": "01/09/2026"}, "AAAA-MM-JJ"),
        ({"a_verifier": "oui"}, "true ou false"),
    ],
)
def test_valeurs_invalides_refusees(changements, message):
    with pytest.raises(LieuInvalide, match=message):
        valider_lieux([lieu(**changements)])


def test_identifiant_en_double_refuse():
    with pytest.raises(LieuInvalide, match="en double"):
        valider_lieux([lieu(), lieu()])


LIEUX = [
    lieu(id="u", categorie="utile", sous_categorie="sante"),
    lieu(id="v", categorie="decouverte", sous_categorie="a_voir"),
    lieu(id="s", categorie="decouverte", sous_categorie="sortir"),
    lieu(id="m", categorie="manger", sous_categorie="marche"),
    lieu(id="l", categorie="logement", sous_categorie="site"),
]


def ids(lieux):
    return [x["id"] for x in lieux]


def test_filtre_par_categorie():
    assert ids(par_categorie(LIEUX, "utile")) == ["u"]
    assert ids(par_categorie(LIEUX, "logement")) == ["l"]


@pytest.mark.parametrize(
    "filtre, attendus",
    [
        ("a-voir", ["v"]),
        ("manger", ["m"]),
        ("sortir", ["s"]),
        (None, ["v", "s", "m"]),
        ("inconnu", ["v", "s", "m"]),
    ],
)
def test_filtres_decouvrir(filtre, attendus):
    assert ids(filtrer_decouvrir(LIEUX, filtre)) == attendus


def test_premiere_phrase():
    assert premiere_phrase("Une. Deux.") == "Une."
    assert premiere_phrase("Seule phrase.") == "Seule phrase."


def test_pages_lille_repondent(client):
    for chemin in ("/lille/", "/lille/lieux-utiles", "/lille/se-loger", "/lille/decouvrir"):
        assert client.get(chemin).status_code == 200


def test_page_lieux_utiles_affiche_carte_et_adresse(client):
    texte = client.get("/lille/lieux-utiles").get_data(as_text=True)
    assert "2 rue d&#39;Iéna, Lille" in texte
    assert "Voir sur la carte" in texte
    assert 'target="_blank"' in texte


def test_page_se_loger_affiche_fiche_arnaques(client):
    texte = client.get("/lille/se-loger").get_data(as_text=True)
    assert "Éviter les arnaques" in texte
    assert "Ne paie jamais avant la visite." in texte
    assert "https://trouverunlogement.lescrous.fr" in texte


def test_page_decouvrir_filtree(client):
    texte = client.get("/lille/decouvrir?filtre=manger").get_data(as_text=True)
    assert "Marché de Wazemmes" in texte
    assert "Grand Place" not in texte


def test_detail_lieu(client):
    assert client.get("/lille/decouvrir/grand_place").status_code == 200
    assert client.get("/lille/decouvrir/inconnu").status_code == 404
    assert client.get("/lille/decouvrir/cpam").status_code == 404


def test_photo_absente_affiche_bloc_icone(client):
    texte = client.get("/lille/decouvrir/citadelle").get_data(as_text=True)
    assert 'class="photo-absente"' in texte
    assert "<img" not in texte

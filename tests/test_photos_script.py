"""Script de photos : traitement d'une réponse d'API simulée, sans réseau."""

import pytest

from scripts.telecharger_photos import (
    candidats_valides,
    choisir_image,
    credit,
    licence_acceptee,
    nettoyer_texte,
    parametres_recherche,
)


def page(index, titre, largeur, hauteur, licence, auteur, mime="image/jpeg"):
    return {
        "index": index,
        "title": titre,
        "imageinfo": [
            {
                "thumburl": f"https://upload.wikimedia.org/{titre}-1200px.jpg",
                "thumbwidth": largeur,
                "thumbheight": hauteur,
                "mime": mime,
                "descriptionurl": f"https://commons.wikimedia.org/wiki/{titre}",
                "extmetadata": {
                    "Artist": {"value": auteur},
                    "LicenseShortName": {"value": licence},
                },
            }
        ],
    }


REPONSE = {
    "query": {
        "pages": [
            page(
                4,
                "File:Bonne.jpg",
                1200,
                800,
                "CC BY-SA 4.0",
                '<a href="//commons.wikimedia.org/wiki/User:Jean">Jean&nbsp;Dupont</a>',
            ),
            page(1, "File:Portrait.jpg", 800, 1200, "CC BY-SA 4.0", "Auteur A"),
            page(2, "File:NonCommercial.jpg", 1200, 800, "CC BY-NC 2.0", "Auteur B"),
            page(3, "File:Schema.png", 1200, 800, "CC0", "Auteur C", mime="image/png"),
            page(5, "File:Suivante.jpg", 1200, 800, "CC BY 4.0", "Auteur D"),
        ]
    }
}


def test_propositions_valides_dans_l_ordre():
    valides = candidats_valides(REPONSE)
    assert [c["titre"] for c in valides] == ["File:Bonne.jpg", "File:Suivante.jpg"]
    assert choisir_image(REPONSE, 2)["titre"] == "File:Suivante.jpg"
    assert choisir_image(REPONSE, 3) is None


def test_choisit_la_premiere_image_paysage_avec_licence_libre():
    choix = choisir_image(REPONSE)
    assert choix["titre"] == "File:Bonne.jpg"
    assert choix["url"].endswith("-1200px.jpg")
    assert choix["page_commons"] == "https://commons.wikimedia.org/wiki/File:Bonne.jpg"


def test_credit_nettoye_du_html():
    choix = choisir_image(REPONSE)
    assert choix["auteur"] == "Jean Dupont"
    assert credit(choix) == "Jean Dupont, CC BY-SA 4.0, via Wikimedia Commons"


@pytest.mark.parametrize(
    "brut, propre",
    [
        ('<span class="fn"><a href="x">Marie  Curie</a></span>', "Marie Curie"),
        ("Pierre &amp; Paul", "Pierre & Paul"),
        ("© Pierre André", "Pierre André"),
        ("<bdi>Inconnu</bdi>\n", "Inconnu"),
        ("", ""),
    ],
)
def test_nettoyer_texte(brut, propre):
    assert nettoyer_texte(brut) == propre


@pytest.mark.parametrize(
    "licence, acceptee",
    [
        ("CC0", True),
        ("Public domain", True),
        ("PD-old-70", True),
        ("CC BY 4.0", True),
        ("CC BY-SA 3.0", True),
        ("CC BY-SA 2.0 fr", True),
        ("CC BY-NC 2.0", False),
        ("CC BY-NC-SA 4.0", False),
        ("CC BY-ND 4.0", False),
        ("GFDL", False),
        ("", False),
    ],
)
def test_licences(licence, acceptee):
    assert licence_acceptee(licence) is acceptee


def test_aucune_image_valable():
    reponse = {"query": {"pages": [page(1, "File:Portrait.jpg", 800, 1200, "CC BY 4.0", "A")]}}
    assert choisir_image(reponse) is None
    assert choisir_image({}) is None


def test_auteur_obligatoire_sauf_domaine_public():
    sans_auteur = {"query": {"pages": [page(1, "File:A.jpg", 1200, 800, "CC BY 4.0", "")]}}
    assert choisir_image(sans_auteur) is None
    public = {"query": {"pages": [page(1, "File:B.jpg", 1200, 800, "Public domain", "")]}}
    assert credit(choisir_image(public)) == "Auteur inconnu, Public domain, via Wikimedia Commons"


def test_parametres_de_recherche():
    parametres = parametres_recherche("Grand Place Lille")
    assert parametres["gsrsearch"] == "Grand Place Lille"
    assert parametres["gsrnamespace"] == "6"
    assert parametres["iiurlwidth"] == "1200"
    assert "extmetadata" in parametres["iiprop"]

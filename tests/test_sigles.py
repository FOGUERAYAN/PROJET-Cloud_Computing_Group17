"""Pastilles de monogramme, photos de bandeau des modules et mention d'indépendance."""

import pytest

from app.services.modules import ModuleInvalide, photo_du_module, valider_modules
from app.services.sigles import erreur_sigle, famille_du_theme


@pytest.mark.parametrize(
    "sigle, obligatoire, erreur",
    [
        ("CPAM", True, None),
        ("Crous", True, None),
        ("Lk", True, None),
        ("", False, None),
        ("", True, "le sigle est obligatoire"),
        ("X", True, "le sigle doit faire 2 à 5 caractères"),
        ("TROPLONG", True, "le sigle doit faire 2 à 5 caractères"),
    ],
)
def test_validation_du_sigle(sigle, obligatoire, erreur):
    assert erreur_sigle(sigle, obligatoire) == erreur


def test_famille_selon_le_theme():
    assert famille_du_theme("logement") == "logement"
    assert famille_du_theme("entraide") == "entraide"
    assert famille_du_theme("papiers") == "demarche"


def test_catalogues_ont_des_sigles(app):
    lieux = {lieu["id"]: lieu for lieu in app.extensions["lieux"]}
    assert lieux["cpam"]["sigle"] == "CPAM"
    assert lieux["lokaviz"]["sigle"] == "Lv"
    assert lieux["grand_place"]["sigle"] == ""
    assert all(e["sigle"] for e in app.extensions["entraide"])
    assert all(lien["sigle"] for lien in app.extensions["liens"])


def test_pastilles_par_famille(client):
    texte = client.get("/lille/lieux-utiles").get_data(as_text=True)
    assert '<span class="pastille-sigle pastille-demarche" aria-hidden="true">CPAM</span>' in texte
    texte = client.get("/lille/se-loger").get_data(as_text=True)
    assert '<span class="pastille-sigle pastille-logement" aria-hidden="true">Lv</span>' in texte
    texte = client.get("/solidarite").get_data(as_text=True)
    assert '<span class="pastille-sigle pastille-entraide" aria-hidden="true">Lk</span>' in texte


def test_pastille_remplace_le_bloc_de_secours(client):
    texte = client.get("/lille/lieux-utiles").get_data(as_text=True)
    carte_cpam = texte[texte.index('id="cpam"') : texte.index('id="caf"')]
    assert "photo-absente" not in carte_cpam
    assert "pastille-sigle" in carte_cpam


def test_mention_independance_en_pied_de_page(client):
    texte = client.get("/").get_data(as_text=True)
    assert "Cap90 est un projet étudiant indépendant, sans lien avec les organismes cités." in texte


def test_decouvrir_colonne_laterale_sans_suivi(client):
    client.post(
        "/profil",
        data={"statut": "etudiant", "ville": "lille", "date_arrivee": "2026-09-01", "langue": "wo"},
    )
    texte = client.get("/lille/decouvrir").get_data(as_text=True)
    laterale = texte[texte.index('class="laterale"') :]
    assert "Cette semaine à Lille" in laterale
    assert "Liens utiles" in laterale
    assert "Ta progression" not in laterale


def test_photo_de_bandeau_des_modules():
    modules = {"decouvrir": {"photo_bandeau": "bandeau-decouvrir.jpg", "credit_photo": "Auteur, CC BY 4.0"}}
    photo = photo_du_module(valider_modules(modules), "decouvrir", "Découvrir Lille")
    assert photo["photo"] == "bandeau-decouvrir.jpg"
    assert photo_du_module(modules, "planning", "Planning") is None
    with pytest.raises(ModuleInvalide, match="crédit"):
        valider_modules({"decouvrir": {"photo_bandeau": "a.jpg", "credit_photo": ""}})

"""Corrections avant le premier push : profil, migration, WebP, ressources locales."""

import io
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from app.services.referentiels import (
    charger_communes,
    charger_langues,
    migrer_commune,
    migrer_langue,
    nom_langue,
    normaliser,
)
from scripts import charger_medias
from scripts.migrer_profils import migrer

RACINE = Path(__file__).resolve().parent.parent
FORMULAIRE = {
    "pseudo": "Awa",
    "statut": "etudiant",
    "ville": "roubaix",
    "date_arrivee": "2026-09-01",
    "langue": "wo",
}


def id_session(client):
    with client.session_transaction() as session:
        return session.get("id_utilisateur")


# Formulaire de profil


def test_listes_de_reference():
    langues = charger_langues()
    codes = [langue["code"] for langue in langues]
    assert len(codes) == 25
    assert codes[0] == "fr" and codes[-1] == "autre"
    assert {"ar", "fa", "ps", "ti", "wo", "bm", "ln", "sw"} <= set(codes)
    assert all(len(code) == 2 for code in codes if code != "autre")
    communes = [commune["nom"] for commune in charger_communes()]
    assert communes[0] == "Lille"
    assert "Marcq-en-Barœul" in communes and communes[-1] == "Autre commune de la métropole"


def test_formulaire_avec_listes(client):
    texte = client.get("/profil").get_data(as_text=True)
    assert '<option value="" disabled selected>Choisis ta langue</option>' in texte
    assert "Arabe (العربية)" in texte
    assert '<option value="lille" selected>Lille</option>' in texte
    assert 'id="langue_precision"' in texte


def test_creation_avec_codes(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    profil = stockage.lire_profil(id_session(client))
    assert (profil["ville"], profil["langue"], profil["langue_precision"]) == ("roubaix", "wo", "")
    texte = client.get("/profil").get_data(as_text=True)
    assert "<dd>Roubaix</dd>" in texte
    assert "<dd>Wolof</dd>" in texte


@pytest.mark.parametrize(
    "changements, erreur",
    [
        ({"langue": "klingon"}, "Choisis ta langue maternelle dans la liste."),
        ({"langue": ""}, "Choisis ta langue maternelle dans la liste."),
        ({"ville": "paris"}, "Choisis ta commune dans la liste."),
        ({"langue": "autre", "langue_precision": "  "}, "Précise ta langue maternelle."),
    ],
)
def test_validation_serveur(client, stockage, changements, erreur):
    reponse = client.post("/profil", data={**FORMULAIRE, **changements})
    assert reponse.status_code == 400
    assert erreur in reponse.get_data(as_text=True)
    assert stockage.lister_profils() == []


def test_autre_langue_avec_precision(client, stockage):
    client.post("/profil", data={**FORMULAIRE, "langue": "autre", "langue_precision": "  Soninké "})
    profil = stockage.lire_profil(id_session(client))
    assert (profil["langue"], profil["langue_precision"]) == ("autre", "Soninké")
    assert "<dd>Soninké</dd>" in client.get("/profil").get_data(as_text=True)


def test_precision_ignoree_si_langue_de_la_liste(client, stockage):
    client.post("/profil", data={**FORMULAIRE, "langue_precision": "texte inutile"})
    assert stockage.lire_profil(id_session(client))["langue_precision"] == ""


def test_precision_affichee_en_css_sans_javascript():
    css = (RACINE / "app/static/css/app.css").read_text(encoding="utf-8")
    assert '.champ-langue:has(option[value="autre"]:checked) .langue-precision' in css


# Migration des profils existants


def test_normalisation_et_migration_unitaire():
    langues, communes = charger_langues(), charger_communes()
    assert normaliser("Marcq-en-Barœul") == "marcq en baroeul"
    assert migrer_langue(langues, "wolof") == ("wo", "")
    assert migrer_langue(langues, "English") == ("en", "")
    assert migrer_langue(langues, "Soninké") == ("autre", "Soninké")
    assert migrer_langue(langues, "wo") == ("wo", "")
    assert migrer_commune(communes, "villeneuve d'ascq") == "villeneuve-d-ascq"
    assert migrer_commune(communes, "Paris") == "autre"
    assert nom_langue(langues, "autre", "") == "Autre langue"


def test_migration_des_profils(stockage):
    stockage.initialiser()
    stockage.enregistrer_profil("a", {"ville": "Lille", "langue": "Wolof"})
    stockage.enregistrer_profil("b", {"ville": "Lens", "langue": "Soninké"})
    stockage.enregistrer_profil("c", {"ville": "lille", "langue": "fr", "langue_precision": ""})

    apercu = migrer(stockage, dry_run=True)
    assert [identifiant for identifiant, _ in apercu] == ["a", "b"]
    assert stockage.lire_profil("a")["langue"] == "Wolof"  # rien n'est écrit en dry-run

    migrer(stockage, dry_run=False)
    assert stockage.lire_profil("a")["ville"] == "lille"
    assert stockage.lire_profil("a")["langue"] == "wo"
    b = stockage.lire_profil("b")
    assert (b["ville"], b["langue"], b["langue_precision"]) == ("autre", "autre", "Soninké")
    assert migrer(stockage, dry_run=True) == []


# Conversion WebP


def image_jpeg(largeur, hauteur):
    tampon = io.BytesIO()
    image = Image.new("RGB", (largeur, hauteur))
    pixels = image.load()
    for x in range(largeur):
        for y in range(hauteur):
            pixels[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    image.save(tampon, "JPEG", quality=95)
    return tampon.getvalue()


def test_conversion_webp_redimensionne(tmp_path):
    (tmp_path / "grand.jpg").write_bytes(image_jpeg(1600, 900))
    (tmp_path / "petit.jpg").write_bytes(image_jpeg(400, 300))
    (tmp_path / "README.md").write_text("ignoré", encoding="utf-8")

    resultats = {r["nouveau"]: r for r in charger_medias.convertir_dossier(tmp_path)}

    assert set(resultats) == {"grand.webp", "petit.webp"}
    assert not (tmp_path / "grand.jpg").exists()
    assert (tmp_path / "README.md").exists()
    grand = resultats["grand.webp"]
    assert grand["largeur"] <= 1200
    assert grand["apres"] <= 150 * 1024
    assert grand["apres"] < grand["avant"]
    with Image.open(tmp_path / "grand.webp") as image:
        assert image.format == "WEBP"
        assert image.size == (grand["largeur"], grand["hauteur"])
        assert round(image.width / image.height, 2) == round(1600 / 900, 2)
    assert resultats["petit.webp"]["largeur"] == 400  # jamais agrandie


def test_mise_a_jour_des_references(tmp_path):
    (tmp_path / "lieu.jpg").write_bytes(image_jpeg(300, 200))
    charger_medias.convertir_dossier(tmp_path)
    fiches = [{"photo": "lieu.jpg"}, {"photo": ""}]
    assert charger_medias.mettre_a_jour_references(fiches, "photo", tmp_path) is True
    assert fiches[0] == {"photo": "lieu.webp", "photo_largeur": 300, "photo_hauteur": 200}
    assert charger_medias.mettre_a_jour_references(fiches, "photo", tmp_path) is False


def test_tableau_avant_apres():
    lignes = charger_medias.tableau(
        [
            {
                "nouveau": "a.webp",
                "avant": 300 * 1024,
                "apres": 100 * 1024,
                "largeur": 1200,
                "hauteur": 800,
                "qualite": 80,
            }
        ]
    )
    assert "300 Ko" in lignes and "100 Ko" in lignes and "67 %" in lignes


def test_donnees_en_webp_avec_dimensions():
    lieux = json.loads((RACINE / "app/data/lieux.json").read_text(encoding="utf-8"))
    for lieu in lieux:
        if lieu["photo"]:
            assert lieu["photo"].endswith(".webp")
            assert (RACINE / "medias" / lieu["photo"]).stat().st_size <= 150 * 1024
            assert lieu["photo_largeur"] <= 1200 and lieu["photo_hauteur"] > 0


def test_images_avec_dimensions_et_priorite(client):
    texte = client.get("/lille/decouvrir").get_data(as_text=True)
    images = re.findall(r"<img\b[^>]*>", texte, flags=re.S)
    assert images
    assert all('width="' in img and 'height="' in img for img in images)
    bandeau = [img for img in images if "bandeau-decouvrir" in img]
    assert bandeau and 'loading="eager"' in bandeau[0] and 'fetchpriority="high"' in bandeau[0]
    autres = [img for img in images if "bandeau-decouvrir" not in img]
    assert all('loading="lazy"' in img for img in autres)


# Aucune ressource externe


def references_externes(texte: str) -> list[str]:
    motifs = [
        r"<link\b[^>]*\bhref=[\"']\s*(?:https?:)?//[^\"']*",
        r"<script\b[^>]*\bsrc=[\"']\s*(?:https?:)?//[^\"']*",
        r"url\(\s*[\"']?\s*(?:https?:)?//[^)]*",
        r"@import\s+[^;]*(?:https?:)?//[^;]*",
    ]
    return [m for motif in motifs for m in re.findall(motif, texte, flags=re.I)]


def test_aucune_ressource_externe_dans_les_gabarits_et_le_css():
    fichiers = list((RACINE / "app/templates").glob("*.html")) + list((RACINE / "app/static").rglob("*.css"))
    trouvees = {f.name: references_externes(f.read_text(encoding="utf-8")) for f in fichiers}
    assert {nom: refs for nom, refs in trouvees.items() if refs} == {}


def test_le_detecteur_repere_bien_un_lien_externe():
    assert references_externes('<link rel="stylesheet" href="https://cdn.exemple.com/a.css">')
    assert references_externes('<script src="//cdn.exemple.com/a.js"></script>')
    assert references_externes("@font-face { src: url('https://fonts.exemple.com/a.woff2') }")
    assert not references_externes('<a href="https://www.caf.fr" target="_blank">CAF</a>')


def test_polices_et_icones_locales_avec_licences(client):
    texte = client.get("/").get_data(as_text=True)
    assert "/static/vendor/tabler-icons/tabler-icons.min.css" in texte
    assert "/static/vendor/fonts/fonts.css" in texte
    vendor = RACINE / "app/static/vendor"
    assert (vendor / "tabler-icons/LICENSE").exists()
    assert (vendor / "tabler-icons/fonts/tabler-icons.woff2").exists()
    assert "SIL Open Font License" in (vendor / "fonts/LICENSE-Inter.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in (vendor / "fonts/LICENSE-Poppins.txt").read_text(encoding="utf-8")
    assert client.get("/static/vendor/fonts/inter-latin-400-normal.woff2").status_code == 200

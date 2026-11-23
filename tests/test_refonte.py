"""Refonte : liens utiles, suivi du planning, profil, suppression des données."""

from datetime import date

import pytest

from app.routes import planning as route_planning
from app.routes.commun import initiales, majuscule_initiale
from app.services.liens import LienInvalide, charger_liens, filtrer_par_themes, valider_liens
from app.services.planning import charger_catalogue
from app.services.storage import TABLE_ETAPES, TABLE_HEURES, TABLE_PROFILS
from app.services.suivi import (
    badges_obtenus,
    basculer_piece,
    grouper,
    message_validation,
    prochaine_etape,
    recalculer,
    resume_recalcul,
)

FORMULAIRE = {
    "pseudo": "Awa Diop",
    "statut": "etudiant",
    "ville": "lille",
    "date_arrivee": "2026-09-01",
    "langue": "wolof",
}


def id_session(client):
    with client.session_transaction() as session:
        return session.get("id_utilisateur")


# Liens utiles


def test_liens_utiles_valides_et_complets():
    liens = charger_liens()
    assert len(liens) == 9
    assert all(lien["url"].startswith("https://") for lien in liens)
    assert any(lien["url"].endswith("/F2713") for lien in liens)


def test_liens_filtres_par_theme():
    liens = charger_liens()
    logement = filtrer_par_themes(liens, ["logement"])
    assert {lien["titre"] for lien in logement} == {"CAF", "Trouver un logement Crous", "Lokaviz"}
    assert all(lien["theme"] == "travail" for lien in filtrer_par_themes(liens, ["travail"]))
    assert len(filtrer_par_themes(liens, ["logement", "sante"], limite=2)) == 2
    assert all(lien["theme"] == "papiers" for lien in filtrer_par_themes(liens, []))


@pytest.mark.parametrize(
    "lien, message",
    [
        (
            {"titre": "A", "sigle": "Ab", "url": "http://a.fr", "description": "d", "theme": "papiers"},
            "https://",
        ),
        (
            {"titre": "A", "sigle": "Ab", "url": "https://a.fr", "description": "d", "theme": "inconnu"},
            "thème inconnu",
        ),
        ({"titre": "A", "sigle": "Ab", "url": "https://a.fr", "theme": "papiers"}, "description"),
    ],
)
def test_lien_invalide_refuse(lien, message):
    with pytest.raises(LienInvalide, match=message):
        valider_liens([lien])


def test_page_liens_par_theme(client):
    texte = client.get("/liens-utiles?theme=logement").get_data(as_text=True)
    assert "Lokaviz" in texte
    assert "Ameli" not in texte
    assert 'rel="noopener noreferrer"' in texte


def test_colonne_laterale_filtree_selon_la_page(client):
    texte = client.get("/lille/se-loger").get_data(as_text=True)
    assert "Créer mon profil" in texte[texte.index('class="laterale"') :]
    client.post("/profil", data=FORMULAIRE)
    texte = client.get("/lille/se-loger").get_data(as_text=True)
    laterale = texte[texte.index('class="laterale"') :]
    assert "Lokaviz" in laterale
    assert "Travailler pendant tes études" not in laterale


# Suivi du planning


def etape(code, date_limite, statut="a_faire", fait_le="", ordre=1):
    return {
        "RowKey": code,
        "titre": code,
        "date_limite": date_limite,
        "statut": statut,
        "fait_le": fait_le,
        "ordre": ordre,
    }


def test_groupes_selon_la_date_du_jour():
    aujourd_hui = date(2026, 9, 10)
    etapes = [
        etape("retard", "2026-09-05"),
        etape("semaine", "2026-09-16"),
        etape("mois", "2026-09-17"),
        etape("tard", "2026-10-10"),
        etape("faite", "2026-09-01", "fait", "2026-08-30"),
    ]
    groupes = {code: [e["RowKey"] for e in contenu] for code, _, contenu in grouper(etapes, aujourd_hui)}
    assert groupes == {
        "en_retard": ["retard"],
        "cette_semaine": ["semaine"],
        "ce_mois": ["mois"],
        "plus_tard": ["tard"],
        "faites": ["faite"],
    }


def test_groupes_vides_non_affiches():
    groupes = grouper([etape("tard", "2026-12-01")], date(2026, 9, 1))
    assert [code for code, _, _ in groupes] == ["plus_tard"]


def test_prochaine_etape_et_badges():
    etapes = [
        etape("b", "2026-09-20"),
        etape("a", "2026-09-15", "fait", "2026-09-10"),
        etape("c", "2026-09-18"),
    ]
    assert prochaine_etape(etapes)["RowKey"] == "c"
    assert badges_obtenus(etapes) == {"premier_pas", "a_l_heure"}
    etapes[0].update(statut="fait", fait_le="2026-09-25")  # faite en retard
    assert badges_obtenus(etapes) == {"premier_pas", "mi_parcours"}


def test_message_de_validation_avec_badge():
    avant = [etape("a", "2026-09-15"), etape("b", "2026-09-20"), etape("c", "2026-09-25")]
    apres = [etape("a", "2026-09-15", "fait", "2026-09-10"), *avant[1:]]
    assert message_validation(avant, apres) == (
        "Étape validée, plus que 2. Badge débloqué : Premier pas, À l'heure."
    )


def test_basculer_piece():
    assert basculer_piece("", 2) == "2"
    assert basculer_piece("0,2", 1) == "0,1,2"
    assert basculer_piece("0,2", 0) == "2"


# Recalcul du planning


def test_recalcul_garde_les_etapes_faites():
    catalogue = charger_catalogue()
    existantes = [
        etape("visa", "2026-10-31", "fait", "2026-10-01", 6),
        etape("securite_sociale", "2026-10-01", ordre=3),
        etape("assurance_habitation", "2026-09-08", "fait", "2026-09-05", 1),
    ]
    existantes[1]["pieces_pretes"] = "0,1"
    # Le statut passe à réfugié et la date d'arrivée change.
    a_ecrire, a_supprimer = recalculer(catalogue, existantes, "refugie", date(2026, 9, 15))
    par_code = {e["code"]: e for e in a_ecrire}

    assert "visa" not in par_code  # ne concerne plus le statut...
    assert a_supprimer == []  # ...mais elle était faite : elle est conservée telle quelle
    assert par_code["assurance_habitation"]["statut"] == "fait"
    assert par_code["assurance_habitation"]["fait_le"] == "2026-09-05"
    assert par_code["assurance_habitation"]["date_limite"] == "2026-09-08"
    assert par_code["securite_sociale"]["statut"] == "a_faire"
    assert par_code["securite_sociale"]["date_limite"] == "2026-10-15"
    assert par_code["securite_sociale"]["pieces_pretes"] == "0,1"
    resume = resume_recalcul(existantes, a_ecrire, a_supprimer)
    assert "S'inscrire à la sécurité sociale" in resume["deplacees"]


def test_recalcul_retire_les_etapes_non_faites_qui_ne_concernent_plus():
    a_ecrire, a_supprimer = recalculer(
        charger_catalogue(), [etape("visa", "2026-10-31")], "refugie", date(2026, 9, 1)
    )
    assert a_supprimer == ["visa"]
    assert "visa" not in {e["code"] for e in a_ecrire}


def test_modification_du_profil_avec_confirmation(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    id_utilisateur = id_session(client)
    client.post("/planning/assurance_habitation/fait")

    nouveau = {**FORMULAIRE, "statut": "refugie", "date_arrivee": "2026-09-15"}
    page = client.post("/profil/modifier", data=nouveau)
    assert page.status_code == 200
    texte = page.get_data(as_text=True)
    assert "Étapes retirées" in texte
    assert stockage.lire_profil(id_utilisateur)["statut"] == "etudiant"  # rien n'est encore enregistré

    client.post("/profil/modifier/confirmer", data=nouveau)
    assert stockage.lire_profil(id_utilisateur)["statut"] == "refugie"
    etapes = {e["RowKey"]: e for e in stockage.lister_etapes(id_utilisateur)}
    assert "visa" not in etapes
    assert etapes["assurance_habitation"]["statut"] == "fait"
    assert etapes["securite_sociale"]["date_limite"] == "2026-10-15"


# Suppression des données


def test_suppression_des_donnees(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    id_utilisateur = id_session(client)
    client.post("/travailler", data={"mois": "2026-10", "heures": "20"})
    stockage.coffre[f"{id_utilisateur}/passeport.pdf"] = b"pdf"
    stockage.coffre["autre-utilisateur/bail.pdf"] = b"pdf"

    assert client.get("/profil/supprimer").status_code == 200
    reponse = client.post("/profil/supprimer")
    assert reponse.headers["Location"].endswith("/")

    assert stockage.lire_profil(id_utilisateur) is None
    assert not [k for k in stockage.tables[TABLE_ETAPES] if k[0] == id_utilisateur]
    assert not [k for k in stockage.tables[TABLE_HEURES] if k[0] == id_utilisateur]
    assert not [k for k in stockage.tables[TABLE_PROFILS] if k[1] == id_utilisateur]
    assert list(stockage.coffre) == ["autre-utilisateur/bail.pdf"]
    assert id_session(client) is None
    assert client.get("/planning").headers["Location"].endswith("/profil")


# Pages


def test_ville_et_initiales():
    assert majuscule_initiale("lille") == "Lille"
    assert majuscule_initiale("villeneuve-d'Ascq") == "Villeneuve-d'Ascq"
    assert initiales({"pseudo": "awa diop"}) == "AD"
    assert initiales({"pseudo": ""}) == ""
    assert initiales(None) == ""


def test_ville_enregistree_avec_majuscule(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    assert stockage.lire_profil(id_session(client))["ville"] == "Lille"


def test_accueil_sans_et_avec_profil(client):
    texte = client.get("/").get_data(as_text=True)
    assert "Bienvenue à Lille" in texte
    assert "Créer mon profil" in texte
    assert texte.count('class="tuile"') == 8

    client.post("/profil", data=FORMULAIRE)
    texte = client.get("/").get_data(as_text=True)
    assert "Voir mon planning" in texte
    assert ">AD<" in texte.replace("\n", "").replace(" ", "")
    assert "Ta prochaine étape" in texte
    assert "Cette semaine à Lille" in texte


def test_planning_toast_et_pieces(client, monkeypatch):
    monkeypatch.setattr(route_planning, "aujourd_hui", lambda: date(2026, 9, 3))
    client.post("/profil", data=FORMULAIRE)

    client.post("/planning/assurance_habitation/pieces/0")
    texte = client.get("/planning").get_data(as_text=True)
    assert "1 sur 2 prête" in texte
    assert client.post("/planning/assurance_habitation/pieces/9").status_code == 404

    client.post("/planning/assurance_habitation/fait")
    texte = client.get("/planning").get_data(as_text=True)
    assert 'class="toast"' in texte
    assert "Étape validée, plus que 5. Badge débloqué : Premier pas, À l&#39;heure." in texte
    # Le message ne s'affiche qu'une fois.
    assert 'class="toast"' not in client.get("/planning").get_data(as_text=True)


def test_planning_groupe_de_la_prochaine_etape_ouvert(client, monkeypatch):
    monkeypatch.setattr(route_planning, "aujourd_hui", lambda: date(2026, 9, 3))
    client.post("/profil", data=FORMULAIRE)
    texte = client.get("/planning").get_data(as_text=True)
    assert '<details class="groupe groupe-cette_semaine" open>' in texte
    assert '<details class="groupe groupe-plus_tard" >' in texte
    assert "groupe-en_retard" not in texte
    assert "Mes badges" in texte


def test_boutons_site_officiel(client):
    client.post("/profil", data=FORMULAIRE)
    for chemin in ("/planning", "/lille/lieux-utiles", "/solidarite", "/travailler"):
        texte = client.get(chemin).get_data(as_text=True)
        assert "Site officiel" in texte, chemin
        assert 'target="_blank" rel="noopener noreferrer"' in texte, chemin

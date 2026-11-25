"""Améliorations : Mes démarches, liens officiels précis, notifications."""

import re
from datetime import date

import pytest

from app.routes import commun
from app.services.notifications import (
    calculer,
    notification_pieces,
    notifications_echeances,
    notifications_entraide,
)
from app.services.planning import charger_catalogue
from scripts import verifier_liens
from scripts.verifier_liens import est_accueil, evaluer, titre_de_page

PROFIL = {"statut": "etudiant", "ville": "lille", "date_arrivee": "2026-09-01", "langue": "fr"}


# 1. Mes démarches


def test_redirection_mes_demarches(client):
    reponse = client.get("/mes-demarches")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/planning")


def test_libelles_mes_demarches(client):
    client.post("/profil", data=PROFIL)
    texte = client.get("/planning").get_data(as_text=True)
    assert "<title>Mes démarches | Cap90</title>" in texte
    assert texte.count("<span>Mes démarches</span>") == 1  # barre du bas
    assert "Planning" not in texte
    accueil = client.get("/").get_data(as_text=True)
    assert "Voir mes démarches" in accueil
    assert "planning" not in re.sub(r'(href|class|id|aria-labelledby)="[^"]*"', "", accueil).lower()


# 2. Liens officiels


@pytest.mark.parametrize(
    "demande, statut, finale, titre, attendu",
    [
        ("https://a.fr/fiche/F1", 200, "https://a.fr/fiche/F1", "Fiche F1 | Service", (True, "ok")),
        ("https://a.fr/fiche/F1", 404, "https://a.fr/fiche/F1", "", (False, "erreur 404")),
        ("https://a.fr/fiche/F1", 403, "https://a.fr/fiche/F1", "", (False, "erreur 403")),
        ("https://a.fr/fiche/F1", 200, "https://a.fr/", "Accueil", (False, "redirection vers l'accueil")),
        (
            "https://a.fr/fiche/F1",
            200,
            "https://a.fr/fr/",
            "Bienvenue",
            (False, "redirection vers l'accueil"),
        ),
        (
            "https://a.fr/fiche/F1",
            200,
            "https://a.fr/fiche/F1",
            "Page introuvable",
            (False, "page introuvable (titre)"),
        ),
        (
            "https://a.fr/f",
            200,
            "https://a.fr/f",
            "Ce formulaire n'est plus actif",
            (False, "page introuvable (titre)"),
        ),
        (
            "https://a.fr/f",
            200,
            "https://a.fr/f",
            "Radware Bot Manager Block",
            (False, "non vérifiable (protection anti-robot)"),
        ),
        (
            "https://a.fr/f",
            200,
            "https://a.fr/f",
            "Accueil | Site",
            (False, "redirection vers l'accueil (titre)"),
        ),
        (
            "https://a.fr/app/#/vls-ts",
            200,
            "https://a.fr/app/",
            "Application",
            (False, "non vérifiable (adresse après #)"),
        ),
        ("https://a.fr", 200, "https://a.fr/", "Accueil", (True, "ok")),
    ],
)
def test_evaluation_des_liens(demande, statut, finale, titre, attendu):
    assert evaluer(demande, statut, finale, titre) == attendu


def test_verification_avec_reponses_simulees(monkeypatch):
    reponses = {
        "https://bon.fr/page": (200, "https://bon.fr/page", "Une fiche utile"),
        "https://casse.fr/page": (404, "https://casse.fr/page", ""),
        "https://renvoi.fr/page": (200, "https://renvoi.fr/", "Accueil"),
    }
    monkeypatch.setattr(verifier_liens, "interroger", lambda url, delai=20: reponses[url])
    assert verifier_liens.verifier("https://bon.fr/page") == (True, "ok, titre : Une fiche utile", 200)
    assert verifier_liens.verifier("https://casse.fr/page")[:2] == (False, "erreur 404")
    assert verifier_liens.verifier("https://renvoi.fr/page")[:2] == (False, "redirection vers l'accueil")


def test_outils_de_verification():
    assert (
        est_accueil("https://a.fr/") and est_accueil("https://a.fr/fr") and not est_accueil("https://a.fr/F1")
    )
    assert titre_de_page("<html><title> Fiche &amp; droits\n</title></html>") == "Fiche & droits"
    assert verifier_liens.accueil_du_site("https://a.fr/x/y?z=1") == "https://a.fr"


def test_les_liens_des_donnees_sont_precis():
    urls = verifier_liens.liens_des_donnees()
    accueils_autorises = {
        "https://www.caf.fr",
        "https://www.lokaviz.fr",
        "https://trouverunlogement.lescrous.fr",
        "https://etudiant-etranger.ameli.fr",  # site dédié aux étudiants étrangers
        "https://www.linkee.co",  # repli : le formulaire d'inscription Linkee n'est plus actif
    }
    for url in urls:
        assert url.startswith("https://")
        assert not est_accueil(url) or url in accueils_autorises, url
    assert "https://linkee.fillout.com/inscriptions" not in urls  # formulaire désactivé
    assert not [u for u in urls if u.startswith("https://www.service-public.fr/")]  # ancien domaine


def test_liens_externes_ouvrent_un_nouvel_onglet(client):
    client.post("/profil", data=PROFIL)
    pages = [
        "/",
        "/planning",
        "/lille/lieux-utiles",
        "/lille/se-loger",
        "/lille/decouvrir",
        "/lille/decouvrir/grand_place",
        "/travailler",
        "/solidarite",
        "/liens-utiles?theme=logement",
        "/coffre",
        "/notifications",
    ]
    for page in pages:
        texte = client.get(page).get_data(as_text=True)
        for lien in re.findall(r"<a\b[^>]*\bhref=\"https?://[^\"]+\"[^>]*>", texte):
            assert 'target="_blank"' in lien and 'rel="noopener noreferrer"' in lien, (page, lien)


# 3. Notifications


def etape(code, date_limite, statut="a_faire", pieces_pretes=""):
    return {
        "RowKey": code,
        "titre": f"Démarche {code}",
        "date_limite": date_limite,
        "statut": statut,
        "ordre": 1,
        "fait_le": "",
        "pieces_pretes": pieces_pretes,
    }


def entree(nom, *jours):
    return {
        "nom": nom,
        "sigle": "Ab",
        "type": "aide_alimentaire",
        "creneaux": [{"jour_semaine": j, "horaires": "18 h", "adresse": "Lille"} for j in jours],
    }


AUJOURD_HUI = date(2026, 11, 25)  # un mercredi


def test_echeances_proches_et_depassees():
    etapes = [
        etape("retard", "2026-11-23"),
        etape("jour_j", "2026-11-25"),
        etape("six_jours", "2026-12-01"),
        etape("sept_jours", "2026-12-02"),
        etape("faite", "2026-11-20", statut="fait"),
    ]
    resultat = notifications_echeances(etapes, AUJOURD_HUI)
    assert [n["ancre"] for n in resultat] == ["retard", "jour_j", "six_jours"]
    assert resultat[0]["texte"] == "En retard de 2 jours : Démarche retard"
    assert resultat[0]["niveau"] == "retard"
    assert resultat[1]["texte"] == "Dernier jour pour : Démarche jour_j"
    assert resultat[2]["texte"] == "Plus que 6 jours pour : Démarche six_jours"


def test_entraide_aujourd_hui_et_demain_seulement():
    entrees = [
        entree("Mercredi", "mercredi"),
        entree("Jeudi", "jeudi"),
        entree("Vendredi", "vendredi"),
        entree("Sans", ""),
    ]
    resultat = notifications_entraide(entrees, AUJOURD_HUI)
    assert [n["texte"] for n in resultat] == [
        "Aujourd'hui : 18 h, Mercredi, Lille",
        "Demain : 18 h, Jeudi, Lille",
    ]
    assert resultat[0]["ancre"] == "jour-mercredi" and resultat[0]["page"] == "solidarite"


def test_pieces_manquantes_de_la_prochaine_demarche():
    catalogue = charger_catalogue()
    etapes = [etape("assurance_habitation", "2026-12-10", pieces_pretes="1"), etape("visa", "2027-01-01")]
    resultat = notification_pieces(etapes, catalogue)
    assert len(resultat) == 1
    assert (
        resultat[0]["texte"]
        == "1 pièce à préparer pour Démarche assurance_habitation : Bail ou contrat de location"
    )
    etapes[0]["pieces_pretes"] = "0,1"
    assert notification_pieces(etapes, catalogue) == []


def test_tu_es_a_jour(client, app, monkeypatch):
    app.extensions["entraide"] = []
    texte = client.get("/notifications").get_data(as_text=True)
    assert "Tu es à jour." in texte
    assert "Les notifications par e-mail arriveront dans une prochaine version." in texte
    assert 'class="compteur"' not in texte


def test_page_et_pastille_avec_alertes(client, app, monkeypatch):
    monkeypatch.setattr(commun, "aujourd_hui", lambda: date(2026, 9, 5))
    app.extensions["entraide"] = [entree("Linkee Lille", "samedi")]  # le 5 septembre 2026 est un samedi
    client.post("/profil", data=PROFIL)
    texte = client.get("/notifications").get_data(as_text=True)
    attendu = calculer(
        app.extensions["stockage"].lister_etapes(_id(client)),
        app.extensions["catalogue"],
        app.extensions["entraide"],
        date(2026, 9, 5),
    )
    assert len(attendu) == 3  # assurance habitation à 3 jours, ses pièces, Linkee aujourd'hui
    assert "Plus que 3 jours pour : Souscrire une assurance habitation" in texte
    assert "2 pièces à préparer pour Souscrire une assurance habitation" in texte
    assert (
        "Aujourd&#39;hui : 18 h, Linkee Lille, Lille" in texte
        or "Aujourd'hui : 18 h, Linkee Lille, Lille" in texte
    )
    assert '<span class="compteur" aria-hidden="true">3</span>' in client.get("/").get_data(as_text=True)
    assert 'aria-label="Notifications, 3 alertes"' in texte


def _id(client):
    with client.session_transaction() as session:
        return session["id_utilisateur"]


def test_sans_profil_seulement_l_entraide(client, app, monkeypatch):
    monkeypatch.setattr(commun, "aujourd_hui", lambda: date(2026, 11, 24))  # un mardi : Linkee
    texte = client.get("/notifications").get_data(as_text=True)
    assert "Linkee Lille" in texte
    assert "Crée ton profil pour recevoir aussi les alertes sur tes démarches." in texte

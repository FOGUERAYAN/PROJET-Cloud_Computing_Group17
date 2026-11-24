from datetime import date

import pytest

from app.routes import planning as route_planning
from app.routes import travail as route_travail
from app.services.travail import (
    PLAFOND_HEURES,
    ajouter_annees,
    heures_restantes,
    mois_de_la_periode,
    niveau_jauge,
    periode_en_cours,
    total_periode,
)

VALIDATION = date(2025, 9, 1)


@pytest.mark.parametrize(
    "aujourd_hui, debut, fin",
    [
        (date(2025, 9, 1), date(2025, 9, 1), date(2026, 8, 31)),
        (date(2026, 8, 31), date(2025, 9, 1), date(2026, 8, 31)),
        (date(2026, 9, 1), date(2026, 9, 1), date(2027, 8, 31)),
        (date(2028, 1, 15), date(2027, 9, 1), date(2028, 8, 31)),
        (date(2025, 6, 1), date(2025, 9, 1), date(2026, 8, 31)),
    ],
)
def test_periode_annuelle_depuis_validation(aujourd_hui, debut, fin):
    assert periode_en_cours(VALIDATION, aujourd_hui) == (debut, fin)


def test_periode_validation_un_29_fevrier():
    assert ajouter_annees(date(2028, 2, 29), 1) == date(2029, 2, 28)
    assert periode_en_cours(date(2028, 2, 29), date(2028, 6, 1)) == (date(2028, 2, 29), date(2029, 2, 27))


def test_mois_de_la_periode():
    mois = mois_de_la_periode(date(2025, 9, 1))
    assert len(mois) == 12
    assert mois[0] == "2025-09"
    assert mois[3] == "2025-12"
    assert mois[4] == "2026-01"
    assert mois[-1] == "2026-08"


def test_total_sur_la_periode_ignore_les_autres_mois():
    heures = {
        "2025-08": 100,  # avant la validation
        "2025-09": 60,
        "2026-01": 80.5,
        "2026-08": 40,
        "2026-09": 200,  # période suivante
    }
    assert total_periode(heures, date(2025, 9, 1)) == 180.5
    assert total_periode(heures, date(2026, 9, 1)) == 200


def test_validation_en_milieu_de_mois_compte_ce_mois():
    assert total_periode({"2025-09": 30, "2026-09": 50}, date(2025, 9, 15)) == 30


@pytest.mark.parametrize(
    "total, niveau",
    [
        (0, "normal"),
        (771, "normal"),  # 79,98 %
        (771.2, "alerte"),  # exactement 80 %
        (900, "alerte"),
        (964, "alerte"),  # exactement 100 %
        (964.5, "retard"),
        (1200, "retard"),
    ],
)
def test_seuils_de_couleur(total, niveau):
    assert niveau_jauge(total) == niveau


def test_heures_restantes():
    assert heures_restantes(0) == PLAFOND_HEURES
    assert heures_restantes(900) == 64
    assert heures_restantes(1000) == 0


FORMULAIRE = {
    "statut": "etudiant",
    "ville": "lille",
    "date_arrivee": "2025-08-20",
    "langue": "wo",
}


def test_page_travailler_sans_profil_redirige(client):
    assert client.get("/travailler").headers["Location"].endswith("/profil")


def test_jauge_avec_validation_du_visa(client, monkeypatch):
    monkeypatch.setattr(route_planning, "aujourd_hui", lambda: date(2025, 9, 1))
    monkeypatch.setattr(route_travail, "aujourd_hui", lambda: date(2026, 3, 10))
    client.post("/profil", data=FORMULAIRE)
    client.post("/planning/visa/fait")

    for mois, heures in (("2025-10", "300"), ("2025-11", "300"), ("2025-12", "100")):
        assert client.post("/travailler", data={"mois": mois, "heures": heures}).status_code == 302
    assert client.post("/travailler", data={"mois": "2026-02", "heures": "100,5"}).status_code == 302

    texte = client.get("/travailler").get_data(as_text=True)
    assert "Il te reste 163,5 heures de travail autorisées sur ta période" in texte
    assert "Période en cours : du 01/09/2025 au 31/08/2026." in texte
    assert "jauge-alerte" in texte
    assert "/vosdroits/F2713" in texte


def test_jauge_en_retard(client, monkeypatch):
    monkeypatch.setattr(route_travail, "aujourd_hui", lambda: date(2025, 12, 1))
    client.post("/profil", data=FORMULAIRE)
    client.post("/travailler", data={"mois": "2025-09", "heures": "300"})
    client.post("/travailler", data={"mois": "2025-10", "heures": "300"})
    client.post("/travailler", data={"mois": "2025-11", "heures": "300"})
    client.post("/travailler", data={"mois": "2025-12", "heures": "100"})

    texte = client.get("/travailler").get_data(as_text=True)
    # Visa non coché : la période part de la date d'arrivée (20 août 2025).
    assert "Période en cours : du 20/08/2025 au 19/08/2026." in texte
    assert "jauge-retard" in texte
    assert "Il te reste 0 heures" in texte
    assert "Tu as dépassé la limite de 36 heures." in texte


def test_saisie_invalide_refusee(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    reponse = client.post("/travailler", data={"mois": "2025-13", "heures": "-2"})
    assert reponse.status_code == 400
    texte = reponse.get_data(as_text=True)
    assert "Choisis un mois." in texte
    assert "Indique un nombre d&#39;heures entre 0 et 300." in texte


def test_saisie_remplace_le_mois(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    client.post("/travailler", data={"mois": "2025-10", "heures": "20"})
    client.post("/travailler", data={"mois": "2025-10", "heures": "35"})
    with client.session_transaction() as session:
        assert stockage.lister_heures(session["id_utilisateur"]) == {"2025-10": 35.0}


def test_pas_de_jauge_pour_un_salarie(client):
    client.post("/profil", data={**FORMULAIRE, "statut": "salarie"})
    texte = client.get("/travailler").get_data(as_text=True)
    assert "jauge-" not in texte
    assert "Elle ne s'applique pas à ton statut." in texte


def test_libelle_mois():
    assert route_travail.libelle_mois("2026-02") == "février 2026"
    assert route_travail.libelle_mois("2026-12") == "décembre 2026"

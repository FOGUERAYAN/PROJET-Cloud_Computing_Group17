from datetime import date

from app.services.planning import (
    calculer_etapes,
    charger_catalogue,
    est_urgente,
    jour_courant,
    jours_restants,
)

ARRIVEE = date(2026, 9, 1)

CATALOGUE_TEST = [
    {"code": "b", "titre": "Étape B", "statuts": ["etudiant"], "delai_jours": 30},
    {"code": "a", "titre": "Étape A", "statuts": ["etudiant", "salarie"], "delai_jours": 10},
    {"code": "c", "titre": "Étape C", "statuts": ["salarie"], "delai_jours": 5},
]


def test_calcul_des_dates_depuis_une_arrivee_fixe():
    etapes = calculer_etapes(CATALOGUE_TEST, "etudiant", ARRIVEE)
    assert [e["code"] for e in etapes] == ["a", "b"]
    assert etapes[0]["date_limite"] == date(2026, 9, 11)
    assert etapes[1]["date_limite"] == date(2026, 10, 1)
    assert [e["ordre"] for e in etapes] == [1, 2]
    assert all(e["statut"] == "a_faire" for e in etapes)


def test_calcul_filtre_par_statut():
    etapes = calculer_etapes(CATALOGUE_TEST, "salarie", ARRIVEE)
    assert [e["code"] for e in etapes] == ["c", "a"]


def test_jour_courant_borne_entre_1_et_90():
    assert jour_courant(ARRIVEE, ARRIVEE) == 1
    assert jour_courant(ARRIVEE, date(2026, 9, 12)) == 12
    assert jour_courant(ARRIVEE, date(2026, 8, 20)) == 1
    assert jour_courant(ARRIVEE, date(2027, 1, 1)) == 90


def test_jours_restants():
    assert jours_restants(date(2026, 9, 11), date(2026, 9, 1)) == 10
    assert jours_restants(date(2026, 9, 1), date(2026, 9, 3)) == -2


def test_etape_a_moins_de_7_jours_est_urgente():
    aujourd_hui = date(2026, 9, 5)
    assert est_urgente(date(2026, 9, 11), "a_faire", aujourd_hui) is True
    assert est_urgente(date(2026, 9, 12), "a_faire", aujourd_hui) is False


def test_etape_depassee_est_urgente_mais_pas_si_faite():
    aujourd_hui = date(2026, 9, 20)
    assert est_urgente(date(2026, 9, 11), "a_faire", aujourd_hui) is True
    assert est_urgente(date(2026, 9, 11), "fait", aujourd_hui) is False


def test_catalogue_reel_bien_forme():
    catalogue = charger_catalogue()
    assert 5 <= len(catalogue) <= 6
    champs = {"code", "titre", "statuts", "delai_jours", "pieces", "lien_officiel", "conseil", "a_verifier"}
    for demarche in catalogue:
        assert champs <= demarche.keys()
        assert demarche["a_verifier"] is True
        assert demarche["lien_officiel"].startswith("https://")

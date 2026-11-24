from datetime import date, timedelta

from app.routes import planning as route_planning
from app.services.storage import TABLE_ANNONCES, TABLE_ETAPES, TABLE_PROFILS

FORMULAIRE = {
    "pseudo": "Awa",
    "statut": "etudiant",
    "ville": "lille",
    "date_arrivee": "2026-09-01",
    "langue": "wo",
    "interets": ["sport", "cuisine"],
}


def test_tables_creees_au_demarrage(stockage, app):
    assert {TABLE_PROFILS, TABLE_ETAPES, TABLE_ANNONCES} <= stockage.tables.keys()


def test_creation_profil_enregistre_profil_et_etapes(client, stockage):
    reponse = client.post("/profil", data=FORMULAIRE)
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/planning")

    with client.session_transaction() as session:
        id_utilisateur = session["id_utilisateur"]

    profil = stockage.lire_profil(id_utilisateur)
    assert profil["statut"] == "etudiant"
    assert profil["ville"] == "lille"
    assert profil["date_arrivee"] == "2026-09-01"
    assert profil["interets"] == "sport,cuisine"
    assert profil["cree_le"]

    etapes = stockage.lister_etapes(id_utilisateur)
    codes = [e["RowKey"] for e in etapes]
    assert len(etapes) == 6
    assert "visa" in codes
    assert all(e["statut"] == "a_faire" for e in etapes)
    assert etapes[0]["date_limite"] == "2026-09-08"


def test_refugie_sans_etape_visa(client, stockage):
    client.post("/profil", data={**FORMULAIRE, "statut": "refugie"})
    with client.session_transaction() as session:
        id_utilisateur = session["id_utilisateur"]
    codes = [e["RowKey"] for e in stockage.lister_etapes(id_utilisateur)]
    assert "visa" not in codes


def test_profil_invalide_refuse(client, stockage):
    reponse = client.post("/profil", data={**FORMULAIRE, "statut": "inconnu", "date_arrivee": "pas-une-date"})
    assert reponse.status_code == 400
    texte = reponse.get_data(as_text=True)
    assert "Choisis un statut." in texte
    assert "Indique une date d&#39;arrivée valide." in texte
    assert stockage.tables[TABLE_PROFILS] == {}


def test_planning_sans_profil_redirige(client):
    reponse = client.get("/planning")
    assert reponse.status_code == 302
    assert reponse.headers["Location"].endswith("/profil")


def test_planning_affiche_jour_et_alerte(client, monkeypatch):
    arrivee = date(2026, 9, 1)
    monkeypatch.setattr(route_planning, "aujourd_hui", lambda: arrivee + timedelta(days=3))
    client.post("/profil", data=FORMULAIRE)

    texte = client.get("/planning").get_data(as_text=True)
    assert "Jour 4 sur 90" in texte
    # Assurance habitation : 7 jours après l'arrivée, il en reste 4, donc urgente.
    assert 'class="carte etape urgente"' in texte
    assert "4 jours restants" in texte


def test_case_fait_bascule_le_statut(client, stockage):
    client.post("/profil", data=FORMULAIRE)
    with client.session_transaction() as session:
        id_utilisateur = session["id_utilisateur"]

    client.post("/planning/visa/fait")
    etapes = {e["RowKey"]: e for e in stockage.lister_etapes(id_utilisateur)}
    assert etapes["visa"]["statut"] == "fait"

    client.post("/planning/visa/fait")
    etapes = {e["RowKey"]: e for e in stockage.lister_etapes(id_utilisateur)}
    assert etapes["visa"]["statut"] == "a_faire"

    assert client.post("/planning/inconnu/fait").status_code == 404


def test_planning_affiche_ou_aller(client):
    client.post("/profil", data=FORMULAIRE)
    texte = client.get("/planning").get_data(as_text=True)
    assert texte.count("Où aller") == 1  # seule la sécurité sociale a un lieu avec adresse
    assert "CPAM de Lille-Douai, 2 rue d&#39;Iéna, Lille" in texte

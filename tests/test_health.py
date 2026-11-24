def test_health_repond_200(client):
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.get_json() == {"status": "ok"}


def test_pages_publiques_repondent(client):
    for chemin in ("/", "/profil", "/coffre", "/solidarite"):
        assert client.get(chemin).status_code == 200


def test_pages_attente_affichent_le_message(client):
    assert "Disponible très bientôt" in client.get("/coffre").get_data(as_text=True)
    assert "Disponible prochainement." in client.get("/solidarite").get_data(as_text=True)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def test_media_servi_depuis_le_stockage(client, stockage):
    stockage.envoyer_media("grand-place.png", PNG, "image/png")
    reponse = client.get("/medias/grand-place.png")
    assert reponse.status_code == 200
    assert reponse.data == PNG
    assert reponse.mimetype == "image/png"
    assert reponse.headers["Cache-Control"] == "public, max-age=86400"
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"


def test_media_absent_404(client):
    assert client.get("/medias/absente.jpg").status_code == 404


def test_nom_de_media_refuse(client, stockage):
    stockage.envoyer_media("script.html", b"<script></script>", "text/html")
    assert client.get("/medias/script.html").status_code == 404
    assert client.get("/medias/..%2Fsecret.jpg").status_code == 404
    assert client.get("/medias/.cache.jpg").status_code == 404


def test_type_non_image_remplace(client, stockage):
    stockage.envoyer_media("photo.jpg", PNG, "text/html")
    assert client.get("/medias/photo.jpg").mimetype == "image/jpeg"


def test_photo_presente_affiche_image_et_credit(app, client):
    grand_place = next(x for x in app.extensions["lieux"] if x["id"] == "grand_place")
    grand_place.update(photo="grand-place.jpg", credit_photo="Auteur, CC BY-SA 4.0")
    texte = client.get("/lille/decouvrir/grand_place").get_data(as_text=True)
    assert 'src="/medias/grand-place.jpg"' in texte
    assert "Auteur, CC BY-SA 4.0" in texte
    assert 'class="photo-absente"' in texte  # reste dessous, visible si le fichier manque

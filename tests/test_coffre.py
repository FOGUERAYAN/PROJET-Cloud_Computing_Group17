"""Coffre-fort : dépôt, isolation entre utilisateurs, liens de partage, suppression des données."""

import base64
import io
import re
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import itsdangerous.timed
import pytest

from app import create_app
from app.config import Config
from app.services.coffre import (
    TAILLE_MAX,
    FichierRefuse,
    LienExpire,
    LienInvalide,
    SignataireLiens,
    nettoyer_nom,
    taille_lisible,
    valider_fichier,
)
from app.services.storage import StockageAzure

PDF = b"%PDF-1.4\n% faux document de test\n"
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PROFIL = {"statut": "etudiant", "ville": "lille", "date_arrivee": "2026-09-01", "langue": "fr"}


def id_session(client):
    with client.session_transaction() as session:
        return session.get("id_utilisateur")


def deposer(client, contenu, nom):
    return client.post(
        "/coffre/deposer",
        data={"fichier": (io.BytesIO(contenu), nom)},
        content_type="multipart/form-data",
    )


@pytest.fixture
def connecte(client):
    client.post("/profil", data=PROFIL)
    return client


@pytest.fixture
def autre_client(app):
    autre = app.test_client()
    autre.post("/profil", data=PROFIL)
    return autre


# Contrôle des fichiers


@pytest.mark.parametrize(
    "nom, contenu, attendu",
    [
        ("passeport.pdf", PDF, ("pdf", "application/pdf")),
        ("photo.JPG", JPG, ("jpg", "image/jpeg")),
        ("photo.jpeg", JPG, ("jpg", "image/jpeg")),
        ("scan.png", PNG, ("png", "image/png")),
    ],
)
def test_types_acceptes(nom, contenu, attendu):
    assert valider_fichier(nom, contenu) == attendu


@pytest.mark.parametrize(
    "nom, contenu, message",
    [
        ("notes.txt", b"bonjour", "Seuls les fichiers PDF, JPG et PNG"),
        ("programme.exe", b"MZ\x90\x00", "Seuls les fichiers PDF, JPG et PNG"),
        ("faux.pdf", b"MZ\x90\x00 programme renomme", "ne correspond pas"),
        ("image.png", JPG, "ne correspond pas"),
        ("vide.pdf", b"", "vide"),
        ("gros.pdf", PDF + b"0" * TAILLE_MAX, "dépasse 10 Mo"),
    ],
)
def test_fichiers_refuses(nom, contenu, message):
    with pytest.raises(FichierRefuse, match=message):
        valider_fichier(nom, contenu)


def test_taille_et_nom_lisibles():
    assert taille_lisible(512) == "512 o"
    assert taille_lisible(2048) == "2 Ko"
    assert taille_lisible(int(1.5 * 1024 * 1024)) == "1,5 Mo"
    assert taille_lisible(TAILLE_MAX) == "10 Mo"
    assert nettoyer_nom("C:\\Users\\moi\\passeport été.pdf") == "passeport été.pdf"
    assert nettoyer_nom("../../etc/passwd.pdf") == "passwd.pdf"
    assert nettoyer_nom("") == "document"


# Pages et routes


def test_coffre_reserve_aux_profils(client):
    assert client.get("/coffre").headers["Location"].endswith("/profil")


def test_avertissement_demonstration(connecte):
    texte = connecte.get("/coffre").get_data(as_text=True)
    assert (
        "Pour la démonstration, n&#39;utilise que de faux documents, jamais tes vrais papiers." in texte
        or ("Pour la démonstration, n'utilise que de faux documents, jamais tes vrais papiers." in texte)
    )


@pytest.mark.parametrize("nom, contenu", [("passeport.pdf", PDF), ("photo.jpg", JPG), ("scan.png", PNG)])
def test_depot_accepte(connecte, stockage, nom, contenu):
    reponse = deposer(connecte, contenu, nom)
    assert reponse.status_code == 302
    fichiers = stockage.lister_fichiers(id_session(connecte))
    assert [f["nom"] for f in fichiers] == [nom]
    assert re.fullmatch(r"[0-9a-f]{32}\.(pdf|jpg|png)", fichiers[0]["identifiant"])


@pytest.mark.parametrize(
    "nom, contenu, message",
    [
        ("notes.txt", b"bonjour", "Seuls les fichiers PDF, JPG et PNG sont acceptés."),
        ("faux.pdf", b"MZ programme", "Le contenu du fichier ne correspond pas"),
        ("gros.pdf", PDF + b"0" * TAILLE_MAX, "Le fichier dépasse 10 Mo."),
    ],
)
def test_depot_refuse(connecte, stockage, nom, contenu, message):
    reponse = deposer(connecte, contenu, nom)
    assert reponse.status_code == 400
    assert message in reponse.get_data(as_text=True)
    assert stockage.lister_fichiers(id_session(connecte)) == []


def test_envoi_trop_gros_arrete_avec_message_clair(connecte):
    reponse = deposer(connecte, PDF + b"0" * (TAILLE_MAX + 600 * 1024), "enorme.pdf")
    assert reponse.status_code == 413
    assert "Le fichier dépasse 10 Mo." in reponse.get_data(as_text=True)


def test_liste_avec_taille_lisible(connecte):
    deposer(connecte, PDF + b"0" * 3000, "bail.pdf")
    texte = connecte.get("/coffre").get_data(as_text=True)
    assert "bail.pdf" in texte
    assert "PDF, 3 Ko, déposé le" in texte


def test_telechargement_avec_nom_d_origine(connecte, stockage):
    deposer(connecte, PDF, "passeport été.pdf")
    fichier = stockage.lister_fichiers(id_session(connecte))[0]
    reponse = connecte.get(f"/coffre/fichier/{fichier['identifiant']}")
    assert reponse.status_code == 200
    assert reponse.data == PDF
    disposition = reponse.headers["Content-Disposition"]
    assert disposition.startswith("attachment")
    assert "filename*=UTF-8''passeport%20%C3%A9t%C3%A9.pdf" in disposition
    assert fichier["identifiant"] not in disposition
    assert reponse.headers["Cache-Control"] == "private, no-store"
    assert reponse.headers["X-Content-Type-Options"] == "nosniff"


def test_un_utilisateur_ne_voit_que_ses_fichiers(connecte, autre_client, stockage):
    deposer(connecte, PDF, "a-moi.pdf")
    identifiant = stockage.lister_fichiers(id_session(connecte))[0]["identifiant"]

    assert "a-moi.pdf" not in autre_client.get("/coffre").get_data(as_text=True)
    assert stockage.lister_fichiers(id_session(autre_client)) == []
    assert autre_client.get(f"/coffre/fichier/{identifiant}").status_code == 404
    assert autre_client.post(f"/coffre/fichier/{identifiant}/partager").status_code == 404
    assert autre_client.post(f"/coffre/fichier/{identifiant}/supprimer").status_code == 404
    assert len(stockage.lister_fichiers(id_session(connecte))) == 1


@pytest.mark.parametrize("identifiant", ["..%2F..%2Fautre.pdf", "inconnu.pdf", "0" * 32 + ".exe"])
def test_identifiants_invalides(connecte, identifiant):
    assert connecte.get(f"/coffre/fichier/{identifiant}").status_code == 404


def test_suppression_d_un_fichier(connecte, stockage):
    deposer(connecte, PDF, "bail.pdf")
    identifiant = stockage.lister_fichiers(id_session(connecte))[0]["identifiant"]
    assert connecte.post(f"/coffre/fichier/{identifiant}/supprimer").status_code == 302
    assert stockage.lister_fichiers(id_session(connecte)) == []


# Liens de partage signés (mode local)


def creer_lien(client, stockage, nom="bail.pdf"):
    deposer(client, PDF, nom)
    identifiant = stockage.lister_fichiers(id_session(client))[0]["identifiant"]
    assert client.post(f"/coffre/fichier/{identifiant}/partager").status_code == 302
    texte = client.get("/coffre").get_data(as_text=True)
    url = re.search(r'id="champ-lien" type="text" value="([^"]+)"', texte).group(1)
    return identifiant, url, texte


def test_lien_signe_affiche_avec_expiration(connecte, stockage):
    _, url, texte = creer_lien(connecte, stockage)
    assert "/partage/" in url
    assert "Copier le lien" in texte
    assert "Valable jusqu&#39;au" in texte or "Valable jusqu'au" in texte
    assert "pourra voir le fichier pendant 24 h" in texte
    # Le lien ne s'affiche qu'une fois.
    assert 'id="champ-lien"' not in connecte.get("/coffre").get_data(as_text=True)


def test_lien_valide_sans_session(app, connecte, stockage):
    _, url, _ = creer_lien(connecte, stockage)
    visiteur = app.test_client()
    reponse = visiteur.get(urlsplit(url).path)
    assert reponse.status_code == 200
    assert reponse.data == PDF
    assert reponse.headers["Content-Disposition"].startswith("inline")
    assert reponse.headers["X-Robots-Tag"] == "noindex, nofollow"


def test_lien_modifie_refuse(app, connecte, stockage):
    _, url, _ = creer_lien(connecte, stockage)
    chemin = urlsplit(url).path
    modifie = chemin[:-3] + ("aaa" if not chemin.endswith("aaa") else "bbb")
    reponse = app.test_client().get(modifie)
    assert reponse.status_code == 404
    assert "Ce lien n&#39;est pas valide" in reponse.get_data(as_text=True) or "Ce lien n'est pas valide" in (
        reponse.get_data(as_text=True)
    )


def test_lien_expire_refuse(app, connecte, stockage, monkeypatch):
    _, url, _ = creer_lien(connecte, stockage)
    maintenant = time.time()
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: maintenant + 24 * 3600 + 60)
    reponse = app.test_client().get(urlsplit(url).path)
    assert reponse.status_code == 410
    assert "Ce lien a expiré" in reponse.get_data(as_text=True)


def test_lien_d_un_fichier_supprime(app, connecte, stockage):
    identifiant, url, _ = creer_lien(connecte, stockage)
    connecte.post(f"/coffre/fichier/{identifiant}/supprimer")
    assert app.test_client().get(urlsplit(url).path).status_code == 404


def test_signataire_unitaire(monkeypatch):
    signataire = SignataireLiens("cle-de-test")
    jeton = signataire.signer("u1", "0" * 32 + ".pdf")
    assert signataire.verifier(jeton) == ("u1", "0" * 32 + ".pdf")
    with pytest.raises(LienInvalide):
        SignataireLiens("autre-cle").verifier(jeton)
    with pytest.raises(LienInvalide):
        signataire.verifier(SignataireLiens("cle-de-test").serialiseur.dumps({"u": "u1", "f": "../x"}))
    maintenant = time.time()
    monkeypatch.setattr(itsdangerous.timed.time, "time", lambda: maintenant + 25 * 3600)
    with pytest.raises(LienExpire):
        signataire.verifier(jeton)


def test_secret_key_obligatoire_pour_signer():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        SignataireLiens("")


# User Delegation SAS (Azure), avec un faux client : aucun réseau, aucune clé de compte


class FauxBlob:
    def __init__(self, conteneur, chemin):
        self.url = f"https://cap90test.blob.core.windows.net/{conteneur}/{chemin}"


class FauxServiceBlob:
    def __init__(self):
        self.demandes = []

    def get_user_delegation_key(self, key_start_time, key_expiry_time):
        from azure.storage.blob import UserDelegationKey

        self.demandes.append((key_start_time, key_expiry_time))
        cle = UserDelegationKey()
        cle.signed_oid = "00000000-0000-0000-0000-000000000001"
        cle.signed_tid = "00000000-0000-0000-0000-000000000002"
        cle.signed_start = key_start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        cle.signed_expiry = key_expiry_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        cle.signed_service = "b"
        cle.signed_version = "2025-01-05"
        cle.value = base64.b64encode(b"cle-de-delegation-factice").decode()
        return cle

    def get_blob_client(self, conteneur, chemin):
        return FauxBlob(conteneur, chemin)


def test_user_delegation_sas_lecture_seule_24_h():
    service = FauxServiceBlob()
    stockage = StockageAzure(None, service, nom_compte="cap90test")
    maintenant = datetime.now(UTC)
    url = stockage._lien_sas(
        "u1/" + "a" * 32 + ".pdf", "passeport.pdf", maintenant, maintenant + timedelta(hours=24)
    )

    debut, fin = service.demandes[0]
    assert fin - debut == timedelta(hours=24)
    assert url.startswith("https://cap90test.blob.core.windows.net/coffre/u1/")
    parametres = parse_qs(urlsplit(url).query)
    assert parametres["sp"] == ["r"]  # lecture seule
    assert parametres["spr"] == ["https"]
    assert parametres["skoid"] == ["00000000-0000-0000-0000-000000000001"]  # signée par délégation
    assert "sig" in parametres
    expire = datetime.strptime(parametres["se"][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    assert abs(expire - (maintenant + timedelta(hours=24))) < timedelta(seconds=2)


def test_azurite_utilise_le_lien_interne():
    stockage = StockageAzure(None, FauxServiceBlob())  # chaîne de connexion : pas de nom de compte
    assert stockage._lien_sas("u1/x.pdf", "x.pdf", datetime.now(UTC), datetime.now(UTC)) is None


def test_mode_memoire_renvoie_un_lien_interne(stockage):
    stockage.initialiser()
    fichier = stockage.deposer_fichier("u1", "bail.pdf", PDF, "application/pdf")
    lien = stockage.generer_lien_partage("u1", fichier["identifiant"])
    assert lien["mode"] == "interne" and lien["url"] is None
    assert timedelta(hours=23, minutes=59) < lien["expire_le"] - datetime.now(UTC) <= timedelta(hours=24)
    assert stockage.generer_lien_partage("u2", fichier["identifiant"]) is None


# RGPD


def test_supprimer_mes_donnees_efface_le_coffre(connecte, autre_client, stockage):
    deposer(connecte, PDF, "passeport.pdf")
    deposer(connecte, PNG, "scan.png")
    deposer(autre_client, PDF, "autre.pdf")
    id_utilisateur = id_session(connecte)
    assert len(stockage.lister_fichiers(id_utilisateur)) == 2

    connecte.post("/profil/supprimer")

    assert stockage.lister_fichiers(id_utilisateur) == []
    assert not [chemin for chemin in stockage.coffre if chemin.startswith(f"{id_utilisateur}/")]
    assert len(stockage.lister_fichiers(id_session(autre_client))) == 1


def test_conteneur_coffre_cree_au_demarrage():
    class FauxService:
        def __init__(self):
            self.conteneurs = []

        def create_container(self, nom):
            self.conteneurs.append(nom)

    class FausseTable:
        def create_table_if_not_exists(self, nom):
            pass

    service = FauxService()
    StockageAzure(FausseTable(), service).initialiser()
    assert "coffre" in service.conteneurs


def test_application_cree_le_signataire():
    application = create_app(Config({"SECRET_KEY": "cle-de-test", "STORAGE_MODE": "memoire"}))
    assert isinstance(application.extensions["signataire"], SignataireLiens)
    assert application.config["MAX_CONTENT_LENGTH"] > TAILLE_MAX

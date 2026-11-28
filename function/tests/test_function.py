"""Function de Cap90 : logique pure des tâches nocturnes, sans réseau ni Azure."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from rappels import CanalEmail, CanalJournal, choisir_canal, resume
from stockage import StockageFunction
from taches import (
    annonces_a_purger,
    executer_purge,
    executer_rappels,
    id_court,
    lire_moment,
    rappels_a_envoyer,
)

MAINTENANT = datetime(2026, 11, 28, 3, 0, tzinfo=UTC)
AUJOURD_HUI = MAINTENANT.date()


def annonce(ligne, expire_le=None, cree_le=None, photo=""):
    fiche = {"PartitionKey": "lille", "RowKey": ligne, "photo_blob": photo}
    if expire_le is not None:
        fiche["expire_le"] = expire_le
    if cree_le is not None:
        fiche["cree_le"] = cree_le
    return fiche


# Dates


@pytest.mark.parametrize(
    "valeur, attendu",
    [
        ("2026-11-27", datetime(2026, 11, 28, tzinfo=UTC)),  # une date seule vaut jusqu'à la fin du jour
        ("2026-11-27T10:00:00+00:00", datetime(2026, 11, 27, 10, tzinfo=UTC)),
        ("2026-11-27T10:00:00Z", datetime(2026, 11, 27, 10, tzinfo=UTC)),
        ("2026-11-27T10:00:00", datetime(2026, 11, 27, 10, tzinfo=UTC)),
        ("", None),
        ("pas une date", None),
        (None, None),
    ],
)
def test_lire_moment(valeur, attendu):
    assert lire_moment(valeur) == attendu


# Tâche 1 : choix des annonces à purger


def test_choix_des_annonces_a_purger():
    annonces = [
        annonce("hier", expire_le="2026-11-27"),
        annonce("aujourd_hui", expire_le="2026-11-28"),  # expire ce soir : on garde
        annonce("demain", expire_le="2026-11-29"),
        annonce("heure_passee", expire_le="2026-11-28T02:59:00+00:00"),
        annonce("pile_maintenant", expire_le="2026-11-28T03:00:00+00:00"),
        annonce("heure_future", expire_le="2026-11-28T03:01:00+00:00"),
        annonce("creee_il_y_a_31_jours", cree_le="2026-10-28"),
        annonce("creee_il_y_a_29_jours", cree_le="2026-10-30"),
        annonce("creation_precise_expiree", cree_le="2026-10-29T02:00:00+00:00"),
        annonce("sans_date"),
        annonce("date_illisible", expire_le="bientot"),
    ]
    a_purger, ignorees = annonces_a_purger(annonces, MAINTENANT)
    assert [f["ligne"] for f in a_purger] == [
        "hier",
        "heure_passee",
        "pile_maintenant",
        "creee_il_y_a_31_jours",
        "creation_precise_expiree",
    ]
    assert [f["ligne"] for f in ignorees] == ["sans_date", "date_illisible"]


def test_fiche_de_purge_avec_photo():
    a_purger, _ = annonces_a_purger(
        [annonce("a", expire_le="2026-01-01", photo="  lille/a.webp ")], MAINTENANT
    )
    assert a_purger == [{"partition": "lille", "ligne": "a", "photo_blob": "lille/a.webp"}]


class FauxStockage:
    def __init__(self, annonces=(), etapes=(), photos=(), photo_en_panne=None):
        self.annonces = {a["RowKey"]: a for a in annonces}
        self.etapes = list(etapes)
        self.photos = set(photos)
        self.photo_en_panne = photo_en_panne
        self.ordre = []

    def lister_annonces(self):
        return list(self.annonces.values())

    def supprimer_photo(self, nom):
        if nom == self.photo_en_panne:
            raise OSError("panne réseau simulée")
        self.ordre.append(("photo", nom))
        if nom in self.photos:
            self.photos.remove(nom)
            return True
        return False

    def supprimer_annonce(self, partition, ligne):
        self.ordre.append(("annonce", ligne))
        del self.annonces[ligne]

    def lister_etapes_non_faites(self):
        return [e for e in self.etapes if e.get("statut") != "fait"]


def test_purge_supprime_la_photo_puis_l_annonce():
    stockage = FauxStockage(
        annonces=[
            annonce("expiree", expire_le="2026-11-01", photo="a.webp"),
            annonce("photo_deja_absente", expire_le="2026-11-01", photo="b.webp"),
            annonce("valide", expire_le="2026-12-20", photo="c.webp"),
        ],
        photos={"a.webp", "c.webp"},
    )
    bilan = executer_purge(stockage, MAINTENANT)
    assert bilan == {"examinees": 3, "purgees": 2, "photos": 1, "echecs": 0, "ignorees": 0}
    assert stockage.ordre[:2] == [("photo", "a.webp"), ("annonce", "expiree")]
    assert set(stockage.annonces) == {"valide"}
    assert stockage.photos == {"c.webp"}


def test_echec_photo_garde_l_annonce_pour_la_nuit_suivante(caplog):
    stockage = FauxStockage(
        annonces=[
            annonce("bloquee", expire_le="2026-11-01", photo="x.webp"),
            annonce("ok", expire_le="2026-11-01"),
        ],
        photo_en_panne="x.webp",
    )
    with caplog.at_level(logging.ERROR):
        bilan = executer_purge(stockage, MAINTENANT)
    assert bilan["echecs"] == 1 and bilan["purgees"] == 1
    assert "bloquee" in stockage.annonces
    assert "Échec de la purge" in caplog.text


def test_table_vide_rien_a_purger(caplog):
    with caplog.at_level(logging.INFO):
        bilan = executer_purge(FauxStockage(), MAINTENANT)
    assert bilan["purgees"] == 0
    assert "rien à purger" in caplog.text


# Tâche 2 : choix des démarches à rappeler


def etape(utilisateur, code, date_limite, statut="a_faire", titre="Titre"):
    return {
        "PartitionKey": utilisateur,
        "RowKey": code,
        "date_limite": date_limite,
        "statut": statut,
        "titre": titre,
    }


def test_choix_des_demarches_a_rappeler():
    etapes = [
        etape("u1", "six_jours", (AUJOURD_HUI + timedelta(days=6)).isoformat()),
        etape("u1", "sept_jours", (AUJOURD_HUI + timedelta(days=7)).isoformat()),  # limite : pas de rappel
        etape("u1", "en_retard", (AUJOURD_HUI - timedelta(days=2)).isoformat()),
        etape("u1", "aujourd_hui", AUJOURD_HUI.isoformat()),
        etape("u1", "faite", (AUJOURD_HUI - timedelta(days=5)).isoformat(), statut="fait"),
        etape("u2", "bientot", (AUJOURD_HUI + timedelta(days=1)).isoformat()),
        etape("u3", "tard", (AUJOURD_HUI + timedelta(days=40)).isoformat()),
        etape("u4", "illisible", "un jour"),
    ]
    rappels = rappels_a_envoyer(etapes, AUJOURD_HUI)
    assert list(rappels) == ["u1", "u2"]  # u3 et u4 n'ont rien à rappeler
    assert [(r["code"], r["jours_restants"]) for r in rappels["u1"]] == [
        ("en_retard", -2),
        ("aujourd_hui", 0),
        ("six_jours", 6),
    ]
    assert rappels["u2"][0]["code"] == "bientot"


def test_canal_journal_sans_donnee_personnelle(caplog):
    identifiant = "8f627020-aaaa-bbbb-cccc-1234567890ab"
    rappels = {
        identifiant: [
            {"code": "visa", "titre": "Valider son visa", "date_limite": "2026-11-26", "jours_restants": -2},
            {
                "code": "assurance_habitation",
                "titre": "Assurance",
                "date_limite": "2026-12-01",
                "jours_restants": 3,
            },
        ]
    }
    with caplog.at_level(logging.INFO):
        assert CanalJournal().envoyer(rappels) == 1
    assert (
        "Rappel pour l'utilisateur 8f627020 : visa (en retard de 2 j), assurance_habitation (3 j)"
        in caplog.text
    )
    assert identifiant not in caplog.text
    assert "Valider son visa" not in caplog.text


def test_resume_et_identifiant_court():
    assert resume([{"code": "a", "jours_restants": 0}]) == "a (0 j)"
    assert id_court("1234567890") == "12345678"
    assert id_court("") == "inconnu"


def test_point_d_extension_email():
    assert isinstance(choisir_canal(), CanalJournal)
    with pytest.raises(NotImplementedError, match="prochaine version"):
        CanalEmail().envoyer({"u1": []})


def test_executer_rappels_passe_par_le_canal():
    class CanalTest:
        def __init__(self):
            self.recus = None

        def envoyer(self, rappels):
            self.recus = rappels
            return len(rappels)

    canal = CanalTest()
    stockage = FauxStockage(etapes=[etape("u1", "a", AUJOURD_HUI.isoformat())])
    assert executer_rappels(stockage, AUJOURD_HUI, canal) == 1
    assert list(canal.recus) == ["u1"]


# Function et configuration


def test_une_tache_en_echec_n_empeche_pas_l_autre(caplog):
    import function_app

    class StockageCasse(FauxStockage):
        def lister_annonces(self):
            raise OSError("table indisponible")

    stockage = StockageCasse(etapes=[etape("u1", "a", AUJOURD_HUI.isoformat())])
    with caplog.at_level(logging.INFO):
        bilan = function_app.executer_taches(stockage, CanalJournal(), MAINTENANT)
    assert bilan["purge"] is None
    assert bilan["rappels"] == 1
    assert "La purge des annonces a échoué." in caplog.text


def test_minuteur_a_3_h_utc():
    import function_app

    fonctions = function_app.app.get_functions()
    assert [f.get_function_name() for f in fonctions] == ["taches_nocturnes"]
    declencheur = fonctions[0].get_trigger()
    assert declencheur.schedule == "0 0 3 * * *"
    secondes, minutes, heures, *_ = declencheur.schedule.split()
    assert (secondes, minutes, heures) == ("0", "0", "3")
    assert declencheur.run_on_startup is False


@pytest.mark.parametrize(
    "environ, message",
    [
        ({"STORAGE_MODE": "azure"}, "AZURE_STORAGE_ACCOUNT_NAME est obligatoire"),
        ({"STORAGE_MODE": "memoire"}, "azure ou azurite"),
    ],
)
def test_configuration_invalide(environ, message):
    with pytest.raises(ValueError, match=message):
        StockageFunction.depuis_environnement(environ)


def test_configuration_azurite_sans_cle():
    stockage = StockageFunction.depuis_environnement({"STORAGE_MODE": "azurite"})
    assert stockage.service_blobs.account_name == "devstoreaccount1"


def test_configuration_azure_par_identite(monkeypatch):
    import azure.identity

    class IdentiteFactice:
        def get_token(self, *scopes, **kwargs):
            raise AssertionError("aucun appel réseau dans ce test")

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", IdentiteFactice)
    stockage = StockageFunction.depuis_environnement(
        {"STORAGE_MODE": "azure", "AZURE_STORAGE_ACCOUNT_NAME": "stcap90"}
    )
    assert stockage.service_blobs.url.startswith("https://stcap90.blob.core.windows.net")
    assert isinstance(stockage.service_blobs.credential, IdentiteFactice)

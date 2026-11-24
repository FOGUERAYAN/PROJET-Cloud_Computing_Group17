"""Accès aux données. Une interface commune et deux implémentations.

- StockageMemoire : dictionnaires en mémoire, utilisé par les tests.
- StockageAzure : Azure Table Storage et Blob Storage (ou l'émulateur Azurite en local).

La logique métier (profils, étapes) est écrite une seule fois dans la classe de base.
Chaque implémentation ne fournit que les opérations élémentaires.
"""

import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta
from urllib.parse import quote, unquote

from app.services.coffre import DUREE_PARTAGE_HEURES, IDENTIFIANT_VALIDE

TABLE_PROFILS = "profils"
TABLE_ETAPES = "etapes"
TABLE_ANNONCES = "annonces"
TABLE_HEURES = "heures"
TABLES = (TABLE_PROFILS, TABLE_ETAPES, TABLE_ANNONCES, TABLE_HEURES)

CONTENEUR_MEDIAS = "medias-lille"
# Coffre-fort : conteneur privé, un préfixe par utilisateur ("<id utilisateur>/<identifiant du fichier>").
CONTENEUR_COFFRE = "coffre"

PARTITION_PROFIL = "profil"


class Stockage(ABC):
    """Interface commune d'accès aux données."""

    # Opérations élémentaires à fournir par chaque implémentation.

    @abstractmethod
    def initialiser(self) -> None:
        """Crée les tables et le conteneur de médias s'ils n'existent pas."""

    @abstractmethod
    def _ecrire(self, table: str, entite: dict) -> None:
        """Insère ou met à jour une entité (fusion des champs)."""

    @abstractmethod
    def _lire(self, table: str, partition: str, ligne: str) -> dict | None:
        """Retourne une entité, ou None si elle n'existe pas."""

    @abstractmethod
    def _lister(self, table: str, partition: str) -> list[dict]:
        """Retourne toutes les entités d'une partition."""

    @abstractmethod
    def _supprimer(self, table: str, partition: str, ligne: str) -> None:
        """Supprime une entité (sans erreur si elle n'existe pas)."""

    @abstractmethod
    def supprimer_coffre(self, id_utilisateur: str) -> int:
        """Supprime les fichiers du coffre-fort d'un utilisateur. Retourne le nombre de fichiers supprimés."""

    @abstractmethod
    def _ecrire_blob_coffre(self, chemin: str, contenu: bytes, type_contenu: str, metadonnees: dict) -> None:
        """Écrit un fichier du coffre (sans écraser un fichier existant)."""

    @abstractmethod
    def _lister_blobs_coffre(self, prefixe: str) -> list[dict]:
        """Fichiers sous un préfixe : chemin, taille, type, date, métadonnées."""

    @abstractmethod
    def _lire_blob_coffre(self, chemin: str) -> dict | None:
        """Contenu, type et métadonnées d'un fichier, ou None."""

    @abstractmethod
    def _supprimer_blob_coffre(self, chemin: str) -> bool:
        """Supprime un fichier. Retourne False s'il n'existait pas."""

    def _lien_sas(self, chemin: str, nom: str, debut: datetime, expiration: datetime) -> str | None:
        """Lien direct en lecture seule (Azure uniquement). None quand il faut un lien interne signé."""
        return None

    @abstractmethod
    def envoyer_media(self, nom: str, contenu: bytes, type_contenu: str) -> None:
        """Enregistre un fichier dans le conteneur de médias (remplace s'il existe)."""

    @abstractmethod
    def lire_media(self, nom: str) -> tuple[bytes, str] | None:
        """Retourne (contenu, type) d'un média, ou None s'il n'existe pas."""

    # Opérations métier communes.

    def enregistrer_profil(self, id_utilisateur: str, profil: dict) -> None:
        entite = {"PartitionKey": PARTITION_PROFIL, "RowKey": id_utilisateur, **profil}
        self._ecrire(TABLE_PROFILS, entite)

    def lire_profil(self, id_utilisateur: str) -> dict | None:
        return self._lire(TABLE_PROFILS, PARTITION_PROFIL, id_utilisateur)

    def lister_profils(self) -> list[dict]:
        return self._lister(TABLE_PROFILS, PARTITION_PROFIL)

    def enregistrer_etapes(self, id_utilisateur: str, etapes: list[dict]) -> None:
        for etape in etapes:
            entite = {
                "PartitionKey": id_utilisateur,
                "RowKey": etape["code"],
                "titre": etape["titre"],
                "date_limite": etape["date_limite"],
                "statut": etape["statut"],
                "ordre": etape["ordre"],
                "fait_le": etape.get("fait_le", ""),
                "pieces_pretes": etape.get("pieces_pretes", ""),
            }
            self._ecrire(TABLE_ETAPES, entite)

    def supprimer_etape(self, id_utilisateur: str, code: str) -> None:
        self._supprimer(TABLE_ETAPES, id_utilisateur, code)

    def changer_pieces_pretes(self, id_utilisateur: str, code: str, valeur: str) -> None:
        self._ecrire(TABLE_ETAPES, {"PartitionKey": id_utilisateur, "RowKey": code, "pieces_pretes": valeur})

    def lister_etapes(self, id_utilisateur: str) -> list[dict]:
        etapes = self._lister(TABLE_ETAPES, id_utilisateur)
        return sorted(etapes, key=lambda e: e["ordre"])

    def lire_etape(self, id_utilisateur: str, code: str) -> dict | None:
        return self._lire(TABLE_ETAPES, id_utilisateur, code)

    def changer_statut_etape(self, id_utilisateur: str, code: str, statut: str, fait_le: str = "") -> bool:
        """Change le statut d'une étape. fait_le garde la date (AAAA-MM-JJ) où elle a été cochée."""
        if self._lire(TABLE_ETAPES, id_utilisateur, code) is None:
            return False
        entite = {"PartitionKey": id_utilisateur, "RowKey": code, "statut": statut, "fait_le": fait_le}
        self._ecrire(TABLE_ETAPES, entite)
        return True

    def enregistrer_heures(self, id_utilisateur: str, mois: str, heures: float) -> None:
        """Heures travaillées pendant un mois (AAAA-MM). Remplace la valeur précédente."""
        self._ecrire(TABLE_HEURES, {"PartitionKey": id_utilisateur, "RowKey": mois, "heures": float(heures)})

    def lister_heures(self, id_utilisateur: str) -> dict[str, float]:
        return {e["RowKey"]: float(e["heures"]) for e in self._lister(TABLE_HEURES, id_utilisateur)}

    # Coffre-fort. Le chemin d'un fichier est toujours "<id utilisateur>/<identifiant>",
    # avec un identifiant tiré au hasard : l'utilisateur ne choisit jamais le chemin.

    @staticmethod
    def _chemin(id_utilisateur: str, identifiant: str) -> str:
        if not id_utilisateur or "/" in id_utilisateur or ".." in id_utilisateur:
            raise ValueError("Identifiant d'utilisateur invalide.")
        if not IDENTIFIANT_VALIDE.match(identifiant or ""):
            raise ValueError("Identifiant de fichier invalide.")
        return f"{id_utilisateur}/{identifiant}"

    @staticmethod
    def _fiche(chemin: str, taille: int, type_contenu: str, metadonnees: dict, date: datetime | None) -> dict:
        depose_le = metadonnees.get("depose_le") or (date.isoformat() if date else "")
        return {
            "identifiant": chemin.split("/", 1)[1],
            "nom": unquote(metadonnees.get("nom_original", "")) or chemin.split("/", 1)[1],
            "type": type_contenu,
            "taille": taille,
            "depose_le": depose_le,
        }

    def deposer_fichier(self, id_utilisateur: str, nom: str, contenu: bytes, type_contenu: str) -> dict:
        """Dépose un fichier déjà contrôlé. Le nom d'origine est gardé dans les métadonnées."""
        extension = "jpg" if type_contenu == "image/jpeg" else type_contenu.rsplit("/", 1)[-1]
        identifiant = f"{uuid.uuid4().hex}.{extension}"
        chemin = self._chemin(id_utilisateur, identifiant)
        metadonnees = {
            # Les métadonnées Blob n'acceptent que l'ASCII : le nom est encodé.
            "nom_original": quote(nom, safe=""),
            "depose_le": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self._ecrire_blob_coffre(chemin, contenu, type_contenu, metadonnees)
        return self._fiche(chemin, len(contenu), type_contenu, metadonnees, None)

    def lister_fichiers(self, id_utilisateur: str) -> list[dict]:
        """Fichiers de l'utilisateur, du plus récent au plus ancien."""
        prefixe = f"{self._chemin(id_utilisateur, '0' * 32 + '.pdf').split('/')[0]}/"
        fiches = [
            self._fiche(b["chemin"], b["taille"], b["type"], b["metadonnees"], b["date"])
            for b in self._lister_blobs_coffre(prefixe)
            if IDENTIFIANT_VALIDE.match(b["chemin"].split("/", 1)[1])
        ]
        return sorted(fiches, key=lambda f: f["depose_le"], reverse=True)

    def lire_fichier(self, id_utilisateur: str, identifiant: str) -> dict | None:
        """Contenu, type et nom d'origine d'un fichier de l'utilisateur, ou None."""
        try:
            chemin = self._chemin(id_utilisateur, identifiant)
        except ValueError:
            return None
        blob = self._lire_blob_coffre(chemin)
        if blob is None:
            return None
        fiche = self._fiche(chemin, len(blob["contenu"]), blob["type"], blob["metadonnees"], None)
        return {**fiche, "contenu": blob["contenu"]}

    def supprimer_fichier(self, id_utilisateur: str, identifiant: str) -> bool:
        try:
            chemin = self._chemin(id_utilisateur, identifiant)
        except ValueError:
            return False
        return self._supprimer_blob_coffre(chemin)

    def generer_lien_partage(
        self, id_utilisateur: str, identifiant: str, duree_heures: int = DUREE_PARTAGE_HEURES
    ) -> dict | None:
        """Lien de lecture seule valable duree_heures, ou None si le fichier n'existe pas.

        Retourne {"mode": "sas", "url": ...} sur Azure (User Delegation SAS),
        ou {"mode": "interne", "url": None} : l'application crée alors un lien signé vers /partage.
        """
        fichier = self.lire_fichier(id_utilisateur, identifiant)
        if fichier is None:
            return None
        maintenant = datetime.now(UTC)
        expiration = maintenant + timedelta(hours=duree_heures)
        # Début légèrement dans le passé pour tolérer un décalage d'horloge.
        url = self._lien_sas(
            self._chemin(id_utilisateur, identifiant),
            fichier["nom"],
            maintenant - timedelta(minutes=5),
            expiration,
        )
        return {
            "mode": "sas" if url else "interne",
            "url": url,
            "expire_le": expiration,
            "nom": fichier["nom"],
        }

    def supprimer_utilisateur(self, id_utilisateur: str) -> None:
        """Efface le profil, les étapes, les heures et les fichiers du coffre-fort."""
        for table in (TABLE_ETAPES, TABLE_HEURES):
            for entite in self._lister(table, id_utilisateur):
                self._supprimer(table, id_utilisateur, entite["RowKey"])
        self.supprimer_coffre(id_utilisateur)
        self._supprimer(TABLE_PROFILS, PARTITION_PROFIL, id_utilisateur)


class StockageMemoire(Stockage):
    """Implémentation en mémoire, sans dépendance externe."""

    def __init__(self):
        self.tables: dict[str, dict[tuple[str, str], dict]] = {}
        self.medias: dict[str, tuple[bytes, str]] = {}
        # Coffre : chemin -> {"contenu", "type", "metadonnees", "date"}.
        self.coffre: dict[str, dict] = {}

    def initialiser(self) -> None:
        for nom in TABLES:
            self.tables.setdefault(nom, {})

    def _ecrire(self, table, entite):
        cle = (entite["PartitionKey"], entite["RowKey"])
        existante = self.tables[table].get(cle, {})
        self.tables[table][cle] = {**existante, **entite}

    def _lire(self, table, partition, ligne):
        entite = self.tables[table].get((partition, ligne))
        return dict(entite) if entite else None

    def _lister(self, table, partition):
        return [dict(e) for (pk, _), e in self.tables[table].items() if pk == partition]

    def _supprimer(self, table, partition, ligne):
        self.tables[table].pop((partition, ligne), None)

    def supprimer_coffre(self, id_utilisateur):
        noms = [nom for nom in self.coffre if nom.startswith(f"{id_utilisateur}/")]
        for nom in noms:
            del self.coffre[nom]
        return len(noms)

    def _ecrire_blob_coffre(self, chemin, contenu, type_contenu, metadonnees):
        if chemin in self.coffre:
            raise FileExistsError(chemin)
        self.coffre[chemin] = {
            "contenu": contenu,
            "type": type_contenu,
            "metadonnees": dict(metadonnees),
            "date": datetime.now(UTC),
        }

    def _lister_blobs_coffre(self, prefixe):
        return [
            {
                "chemin": chemin,
                "taille": len(b["contenu"]),
                "type": b["type"],
                "metadonnees": b["metadonnees"],
                "date": b["date"],
            }
            for chemin, b in self.coffre.items()
            if chemin.startswith(prefixe)
        ]

    def _lire_blob_coffre(self, chemin):
        blob = self.coffre.get(chemin)
        return dict(blob) if blob else None

    def _supprimer_blob_coffre(self, chemin):
        return self.coffre.pop(chemin, None) is not None

    def envoyer_media(self, nom, contenu, type_contenu):
        self.medias[nom] = (contenu, type_contenu)

    def lire_media(self, nom):
        return self.medias.get(nom)


class StockageAzure(Stockage):
    """Implémentation Azure Table Storage et Blob Storage (ou Azurite)."""

    def __init__(self, service_tables, service_blobs, nom_compte: str | None = None):
        self.service_tables = service_tables
        self.service_blobs = service_blobs
        # Renseigné seulement avec la Managed Identity : active les liens User Delegation SAS.
        self.nom_compte = nom_compte

    @classmethod
    def depuis_chaine_connexion(cls, chaine: str) -> "StockageAzure":
        """Connexion locale, par exemple avec UseDevelopmentStorage=true (Azurite)."""
        from azure.data.tables import TableServiceClient
        from azure.storage.blob import BlobServiceClient

        return cls(
            TableServiceClient.from_connection_string(chaine),
            BlobServiceClient.from_connection_string(chaine),
        )

    @classmethod
    def depuis_identite(cls, nom_compte: str) -> "StockageAzure":
        """Connexion sur Azure avec la Managed Identity, sans aucune clé."""
        from azure.data.tables import TableServiceClient
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        identite = DefaultAzureCredential()
        return cls(
            TableServiceClient(endpoint=f"https://{nom_compte}.table.core.windows.net", credential=identite),
            BlobServiceClient(account_url=f"https://{nom_compte}.blob.core.windows.net", credential=identite),
            nom_compte=nom_compte,
        )

    def initialiser(self) -> None:
        from azure.core.exceptions import ResourceExistsError

        for nom in TABLES:
            self.service_tables.create_table_if_not_exists(nom)
        # Conteneurs privés (aucun niveau d'accès public) : les images passent par /medias,
        # les fichiers du coffre par /coffre ou par un lien de partage limité dans le temps.
        for conteneur in (CONTENEUR_MEDIAS, CONTENEUR_COFFRE):
            try:
                self.service_blobs.create_container(conteneur)
            except ResourceExistsError:
                pass

    def _ecrire(self, table, entite):
        from azure.data.tables import UpdateMode

        self.service_tables.get_table_client(table).upsert_entity(entite, mode=UpdateMode.MERGE)

    def _lire(self, table, partition, ligne):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return dict(self.service_tables.get_table_client(table).get_entity(partition, ligne))
        except ResourceNotFoundError:
            return None

    def _lister(self, table, partition):
        client = self.service_tables.get_table_client(table)
        entites = client.query_entities("PartitionKey eq @pk", parameters={"pk": partition})
        return [dict(e) for e in entites]

    def _supprimer(self, table, partition, ligne):
        self.service_tables.get_table_client(table).delete_entity(partition, ligne)

    def supprimer_coffre(self, id_utilisateur):
        from azure.core.exceptions import ResourceNotFoundError

        conteneur = self.service_blobs.get_container_client(CONTENEUR_COFFRE)
        try:
            noms = [b.name for b in conteneur.list_blobs(name_starts_with=f"{id_utilisateur}/")]
        except ResourceNotFoundError:
            return 0  # conteneur absent : rien à supprimer
        for nom in noms:
            conteneur.delete_blob(nom)
        return len(noms)

    def _ecrire_blob_coffre(self, chemin, contenu, type_contenu, metadonnees):
        from azure.storage.blob import ContentSettings

        blob = self.service_blobs.get_blob_client(CONTENEUR_COFFRE, chemin)
        blob.upload_blob(
            contenu,
            overwrite=False,
            content_settings=ContentSettings(content_type=type_contenu),
            metadata=metadonnees,
        )

    def _lister_blobs_coffre(self, prefixe):
        conteneur = self.service_blobs.get_container_client(CONTENEUR_COFFRE)
        return [
            {
                "chemin": b.name,
                "taille": b.size,
                "type": b.content_settings.content_type,
                "metadonnees": b.metadata or {},
                "date": b.creation_time or b.last_modified,
            }
            for b in conteneur.list_blobs(name_starts_with=prefixe, include=["metadata"])
        ]

    def _lire_blob_coffre(self, chemin):
        from azure.core.exceptions import ResourceNotFoundError

        blob = self.service_blobs.get_blob_client(CONTENEUR_COFFRE, chemin)
        try:
            telechargement = blob.download_blob()
        except ResourceNotFoundError:
            return None
        proprietes = telechargement.properties
        return {
            "contenu": telechargement.readall(),
            "type": proprietes.content_settings.content_type,
            "metadonnees": proprietes.metadata or {},
        }

    def _supprimer_blob_coffre(self, chemin):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self.service_blobs.get_blob_client(CONTENEUR_COFFRE, chemin).delete_blob()
        except ResourceNotFoundError:
            return False
        return True

    def _lien_sas(self, chemin, nom, debut, expiration):
        """User Delegation SAS en lecture seule : clé de délégation obtenue avec la Managed Identity.

        Aucune clé de compte n'est utilisée. Rôles nécessaires : Storage Blob Data Contributor
        et Storage Blob Delegator. Avec Azurite (pas de délégation AAD), retourne None.
        """
        if not self.nom_compte:
            return None
        from azure.storage.blob import BlobSasPermissions, generate_blob_sas

        cle = self.service_blobs.get_user_delegation_key(key_start_time=debut, key_expiry_time=expiration)
        sas = generate_blob_sas(
            account_name=self.nom_compte,
            container_name=CONTENEUR_COFFRE,
            blob_name=chemin,
            user_delegation_key=cle,
            permission=BlobSasPermissions(read=True),
            start=debut,
            expiry=expiration,
            protocol="https",
            content_disposition=f"inline; filename*=UTF-8''{quote(nom, safe='')}",
        )
        return f"{self.service_blobs.get_blob_client(CONTENEUR_COFFRE, chemin).url}?{sas}"

    def envoyer_media(self, nom, contenu, type_contenu):
        from azure.storage.blob import ContentSettings

        blob = self.service_blobs.get_blob_client(CONTENEUR_MEDIAS, nom)
        blob.upload_blob(contenu, overwrite=True, content_settings=ContentSettings(content_type=type_contenu))

    def lire_media(self, nom):
        from azure.core.exceptions import ResourceNotFoundError

        blob = self.service_blobs.get_blob_client(CONTENEUR_MEDIAS, nom)
        try:
            telechargement = blob.download_blob()
        except ResourceNotFoundError:
            return None
        return telechargement.readall(), telechargement.properties.content_settings.content_type


def creer_stockage(config) -> Stockage:
    """Choisit l'implémentation selon STORAGE_MODE."""
    if config.STORAGE_MODE == "memoire":
        return StockageMemoire()
    if config.STORAGE_MODE == "azurite":
        if not config.AZURE_STORAGE_CONNECTION_STRING:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING est obligatoire en mode azurite.")
        return StockageAzure.depuis_chaine_connexion(config.AZURE_STORAGE_CONNECTION_STRING)
    if not config.AZURE_STORAGE_ACCOUNT_NAME:
        raise ValueError("AZURE_STORAGE_ACCOUNT_NAME est obligatoire en mode azure.")
    return StockageAzure.depuis_identite(config.AZURE_STORAGE_ACCOUNT_NAME)

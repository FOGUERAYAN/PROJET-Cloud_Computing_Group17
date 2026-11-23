"""Accès aux tables. Une interface commune et deux implémentations.

- StockageMemoire : dictionnaires en mémoire, utilisé par les tests.
- StockageAzureTables : Azure Table Storage (ou l'émulateur Azurite en local).

La logique métier (profils, étapes) est écrite une seule fois dans la classe de base.
Chaque implémentation ne fournit que trois opérations élémentaires.
"""

from abc import ABC, abstractmethod

TABLE_PROFILS = "profils"
TABLE_ETAPES = "etapes"
TABLE_ANNONCES = "annonces"
TABLES = (TABLE_PROFILS, TABLE_ETAPES, TABLE_ANNONCES)

PARTITION_PROFIL = "profil"


class Stockage(ABC):
    """Interface commune d'accès aux données."""

    # Opérations élémentaires à fournir par chaque implémentation.

    @abstractmethod
    def creer_tables(self) -> None:
        """Crée les tables si elles n'existent pas."""

    @abstractmethod
    def _ecrire(self, table: str, entite: dict) -> None:
        """Insère ou met à jour une entité (fusion des champs)."""

    @abstractmethod
    def _lire(self, table: str, partition: str, ligne: str) -> dict | None:
        """Retourne une entité, ou None si elle n'existe pas."""

    @abstractmethod
    def _lister(self, table: str, partition: str) -> list[dict]:
        """Retourne toutes les entités d'une partition."""

    # Opérations métier communes.

    def enregistrer_profil(self, id_utilisateur: str, profil: dict) -> None:
        entite = {"PartitionKey": PARTITION_PROFIL, "RowKey": id_utilisateur, **profil}
        self._ecrire(TABLE_PROFILS, entite)

    def lire_profil(self, id_utilisateur: str) -> dict | None:
        return self._lire(TABLE_PROFILS, PARTITION_PROFIL, id_utilisateur)

    def enregistrer_etapes(self, id_utilisateur: str, etapes: list[dict]) -> None:
        for etape in etapes:
            entite = {
                "PartitionKey": id_utilisateur,
                "RowKey": etape["code"],
                "titre": etape["titre"],
                "date_limite": etape["date_limite"],
                "statut": etape["statut"],
                "ordre": etape["ordre"],
            }
            self._ecrire(TABLE_ETAPES, entite)

    def lister_etapes(self, id_utilisateur: str) -> list[dict]:
        etapes = self._lister(TABLE_ETAPES, id_utilisateur)
        return sorted(etapes, key=lambda e: e["ordre"])

    def changer_statut_etape(self, id_utilisateur: str, code: str, statut: str) -> bool:
        if self._lire(TABLE_ETAPES, id_utilisateur, code) is None:
            return False
        self._ecrire(TABLE_ETAPES, {"PartitionKey": id_utilisateur, "RowKey": code, "statut": statut})
        return True


class StockageMemoire(Stockage):
    """Implémentation en mémoire, sans dépendance externe."""

    def __init__(self):
        self.tables: dict[str, dict[tuple[str, str], dict]] = {}

    def creer_tables(self) -> None:
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


class StockageAzureTables(Stockage):
    """Implémentation Azure Table Storage (ou Azurite)."""

    def __init__(self, service):
        self.service = service

    @classmethod
    def depuis_chaine_connexion(cls, chaine: str) -> "StockageAzureTables":
        """Connexion locale, par exemple avec UseDevelopmentStorage=true (Azurite)."""
        from azure.data.tables import TableServiceClient

        return cls(TableServiceClient.from_connection_string(chaine))

    @classmethod
    def depuis_identite(cls, nom_compte: str) -> "StockageAzureTables":
        """Connexion sur Azure avec la Managed Identity, sans aucune clé."""
        from azure.data.tables import TableServiceClient
        from azure.identity import DefaultAzureCredential

        point_acces = f"https://{nom_compte}.table.core.windows.net"
        return cls(TableServiceClient(endpoint=point_acces, credential=DefaultAzureCredential()))

    def creer_tables(self) -> None:
        for nom in TABLES:
            self.service.create_table_if_not_exists(nom)

    def _ecrire(self, table, entite):
        from azure.data.tables import UpdateMode

        self.service.get_table_client(table).upsert_entity(entite, mode=UpdateMode.MERGE)

    def _lire(self, table, partition, ligne):
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return dict(self.service.get_table_client(table).get_entity(partition, ligne))
        except ResourceNotFoundError:
            return None

    def _lister(self, table, partition):
        client = self.service.get_table_client(table)
        entites = client.query_entities("PartitionKey eq @pk", parameters={"pk": partition})
        return [dict(e) for e in entites]


def creer_stockage(config) -> Stockage:
    """Choisit l'implémentation selon STORAGE_MODE."""
    if config.STORAGE_MODE == "memoire":
        return StockageMemoire()
    if config.STORAGE_MODE == "azurite":
        if not config.AZURE_STORAGE_CONNECTION_STRING:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING est obligatoire en mode azurite.")
        return StockageAzureTables.depuis_chaine_connexion(config.AZURE_STORAGE_CONNECTION_STRING)
    if not config.AZURE_STORAGE_ACCOUNT_NAME:
        raise ValueError("AZURE_STORAGE_ACCOUNT_NAME est obligatoire en mode azure.")
    return StockageAzureTables.depuis_identite(config.AZURE_STORAGE_ACCOUNT_NAME)

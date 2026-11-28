"""Accès au stockage pour la Function : seulement ce dont les tâches nocturnes ont besoin.

- STORAGE_MODE=azure   : AZURE_STORAGE_ACCOUNT_NAME et DefaultAzureCredential (identité managée), sans clé.
- STORAGE_MODE=azurite : émulateur local, chaîne UseDevelopmentStorage=true (aucune clé écrite).
"""

import os

TABLE_ANNONCES = "annonces"
TABLE_ETAPES = "etapes"
CONTENEUR_PHOTOS = "annonces-photos"
CHAINE_AZURITE = "UseDevelopmentStorage=true"


class StockageFunction:
    def __init__(self, service_tables, service_blobs):
        self.service_tables = service_tables
        self.service_blobs = service_blobs

    @classmethod
    def depuis_environnement(cls, environ=None) -> "StockageFunction":
        from azure.data.tables import TableServiceClient
        from azure.storage.blob import BlobServiceClient

        env = os.environ if environ is None else environ
        mode = env.get("STORAGE_MODE", "azure").strip().lower()
        if mode == "azurite":
            return cls(
                TableServiceClient.from_connection_string(CHAINE_AZURITE),
                BlobServiceClient.from_connection_string(CHAINE_AZURITE),
            )
        if mode != "azure":
            raise ValueError("STORAGE_MODE doit valoir azure ou azurite pour la Function.")
        compte = env.get("AZURE_STORAGE_ACCOUNT_NAME", "").strip()
        if not compte:
            raise ValueError("AZURE_STORAGE_ACCOUNT_NAME est obligatoire en mode azure.")
        from azure.identity import DefaultAzureCredential

        identite = DefaultAzureCredential()
        return cls(
            TableServiceClient(endpoint=f"https://{compte}.table.core.windows.net", credential=identite),
            BlobServiceClient(account_url=f"https://{compte}.blob.core.windows.net", credential=identite),
        )

    def lister_annonces(self) -> list[dict]:
        """Toutes les annonces (champs utiles seulement). Table absente : liste vide."""
        from azure.core.exceptions import ResourceNotFoundError

        client = self.service_tables.get_table_client(TABLE_ANNONCES)
        champs = ["PartitionKey", "RowKey", "expire_le", "cree_le", "photo_blob"]
        try:
            return [dict(e) for e in client.list_entities(select=champs)]
        except ResourceNotFoundError:
            return []

    def supprimer_photo(self, nom: str) -> bool:
        """Supprime une photo d'annonce. Retourne False si elle n'existait déjà plus."""
        from azure.core.exceptions import ResourceNotFoundError

        try:
            self.service_blobs.get_blob_client(CONTENEUR_PHOTOS, nom).delete_blob()
        except ResourceNotFoundError:
            return False
        return True

    def supprimer_annonce(self, partition: str, ligne: str) -> None:
        self.service_tables.get_table_client(TABLE_ANNONCES).delete_entity(partition, ligne)

    def lister_etapes_non_faites(self) -> list[dict]:
        """Étapes de tous les utilisateurs dont le statut n'est pas "fait". Table absente : liste vide."""
        from azure.core.exceptions import ResourceNotFoundError

        client = self.service_tables.get_table_client(TABLE_ETAPES)
        champs = ["PartitionKey", "RowKey", "titre", "date_limite", "statut"]
        try:
            return [dict(e) for e in client.query_entities("statut ne 'fait'", select=champs)]
        except ResourceNotFoundError:
            return []

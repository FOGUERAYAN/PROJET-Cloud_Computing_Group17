"""Lecture de la configuration depuis les variables d'environnement (facteur III)."""

import os

MODES_STOCKAGE = ("memoire", "azurite", "azure")


class Config:
    """Configuration de l'application, lue uniquement dans l'environnement."""

    def __init__(self, environ=None):
        env = os.environ if environ is None else environ

        self.SECRET_KEY = env.get("SECRET_KEY", "")
        self.STORAGE_MODE = env.get("STORAGE_MODE", "memoire").strip().lower()
        self.AZURE_STORAGE_CONNECTION_STRING = env.get("AZURE_STORAGE_CONNECTION_STRING", "")
        self.AZURE_STORAGE_ACCOUNT_NAME = env.get("AZURE_STORAGE_ACCOUNT_NAME", "")
        self.TESTING = False

        if self.STORAGE_MODE not in MODES_STOCKAGE:
            raise ValueError(
                f"STORAGE_MODE doit valoir {', '.join(MODES_STOCKAGE)} (reçu : {self.STORAGE_MODE})."
            )
        if not self.SECRET_KEY:
            raise ValueError("La variable d'environnement SECRET_KEY est obligatoire.")

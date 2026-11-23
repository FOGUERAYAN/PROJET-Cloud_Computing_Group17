"""Envoie les images du dossier medias/ dans le conteneur Blob medias-lille.

Utilisation locale (Azurite lancé avec docker compose) :
    python scripts/charger_medias.py

Variables d'environnement lues (mêmes noms que l'application) :
    STORAGE_MODE                     azurite (par défaut) ou azure
    AZURE_STORAGE_CONNECTION_STRING  UseDevelopmentStorage=true par défaut en mode azurite
    AZURE_STORAGE_ACCOUNT_NAME       en mode azure (authentification par DefaultAzureCredential)
"""

import argparse
import mimetypes
import os
import sys
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.routes.medias import NOM_VALIDE  # noqa: E402
from app.services.lieux import charger_lieux  # noqa: E402
from app.services.storage import creer_stockage  # noqa: E402


def lire_config():
    mode = os.environ.get("STORAGE_MODE", "azurite")
    chaine = os.environ.get("AZURE_STORAGE_CONNECTION_STRING", "")
    if mode == "azurite" and not chaine:
        chaine = "UseDevelopmentStorage=true"
    return SimpleNamespace(
        STORAGE_MODE=mode,
        AZURE_STORAGE_CONNECTION_STRING=chaine,
        AZURE_STORAGE_ACCOUNT_NAME=os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dossier", type=Path, default=RACINE / "medias", help="dossier des images")
    args = parser.parse_args()

    config = lire_config()
    if config.STORAGE_MODE == "memoire":
        print("STORAGE_MODE=memoire : rien à envoyer.")
        return 1

    fichiers = sorted(f for f in args.dossier.iterdir() if f.is_file() and NOM_VALIDE.match(f.name))
    if not fichiers:
        print(f"Aucune image dans {args.dossier}.")

    stockage = creer_stockage(config)
    stockage.initialiser()
    for fichier in fichiers:
        type_contenu = mimetypes.guess_type(fichier.name)[0] or "application/octet-stream"
        stockage.envoyer_media(fichier.name, fichier.read_bytes(), type_contenu)
        print(f"Envoyé : {fichier.name}")

    # Contrôle de cohérence avec lieux.json.
    presents = {f.name for f in fichiers}
    for lieu in charger_lieux():
        if lieu["photo"] and lieu["photo"] not in presents:
            print(
                f"Attention : {lieu['photo']} est cité dans lieux.json mais absent de {args.dossier.name}/."
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Essai local des tâches nocturnes contre Azurite, sans les Azure Functions Core Tools.

Crée deux annonces de test (une expirée, une valide) avec leurs photos, lance les deux tâches
comme le ferait le minuteur, vérifie le résultat, puis nettoie ce qu'il a créé.

Utilisation (Azurite lancé avec docker compose, depuis la racine du dépôt) :
    python function/essai_local.py
"""

import logging
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from rappels import CanalJournal  # noqa: E402
from stockage import CONTENEUR_PHOTOS, TABLE_ANNONCES, StockageFunction  # noqa: E402

PARTITION_ESSAI = "essai-local"


def preparer(stockage) -> dict:
    """Crée la table et le conteneur s'ils manquent (Terraform les crée sur Azure), puis deux annonces."""
    from azure.core.exceptions import ResourceExistsError

    stockage.service_tables.create_table_if_not_exists(TABLE_ANNONCES)
    try:
        stockage.service_blobs.create_container(CONTENEUR_PHOTOS)
    except ResourceExistsError:
        pass
    maintenant = datetime.now(UTC)
    annonces = {
        "expiree": (maintenant - timedelta(days=31), maintenant - timedelta(days=1)),
        "valide": (maintenant - timedelta(days=2), maintenant + timedelta(days=28)),
    }
    creees = {}
    table = stockage.service_tables.get_table_client(TABLE_ANNONCES)
    for nom, (cree_le, expire_le) in annonces.items():
        identifiant = uuid.uuid4().hex
        photo = f"{PARTITION_ESSAI}/{identifiant}.webp"
        stockage.service_blobs.get_blob_client(CONTENEUR_PHOTOS, photo).upload_blob(
            b"RIFF essai", overwrite=True
        )
        table.upsert_entity(
            {
                "PartitionKey": PARTITION_ESSAI,
                "RowKey": identifiant,
                "titre": f"Annonce de test {nom}",
                "cree_le": cree_le.isoformat(timespec="seconds"),
                "expire_le": expire_le.isoformat(timespec="seconds"),
                "photo_blob": photo,
            }
        )
        creees[nom] = (identifiant, photo)
    return creees


def existe(stockage, identifiant, photo) -> tuple[bool, bool]:
    annonce = any(a["RowKey"] == identifiant for a in stockage.lister_annonces())
    blob = stockage.service_blobs.get_blob_client(CONTENEUR_PHOTOS, photo).exists()
    return annonce, blob


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s : %(message)s", stream=sys.stdout)
    logging.getLogger("azure").setLevel(logging.WARNING)

    stockage = StockageFunction.depuis_environnement({"STORAGE_MODE": "azurite"})
    creees = preparer(stockage)

    import function_app

    function_app.executer_taches(stockage, CanalJournal(), datetime.now(UTC))

    expiree, valide = existe(stockage, *creees["expiree"]), existe(stockage, *creees["valide"])
    print(f"\nAnnonce expirée : annonce={expiree[0]}, photo={expiree[1]} (attendu : False, False)")
    print(f"Annonce valide  : annonce={valide[0]}, photo={valide[1]} (attendu : True, True)")

    # Nettoyage de l'annonce valide créée pour l'essai.
    identifiant, photo = creees["valide"]
    stockage.supprimer_photo(photo)
    stockage.supprimer_annonce(PARTITION_ESSAI, identifiant)

    reussi = expiree == (False, False) and valide == (True, True)
    print("Essai réussi." if reussi else "Essai en échec.")
    return 0 if reussi else 1


if __name__ == "__main__":
    sys.exit(main())

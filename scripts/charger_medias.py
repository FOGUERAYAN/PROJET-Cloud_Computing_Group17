"""Convertit les images du dossier medias/ en WebP, puis les envoie dans le conteneur Blob medias-lille.

Conversion (Pillow) : largeur maximale 1200 px, qualité 80. Si le fichier dépasse 150 Ko,
la qualité baisse par paliers jusqu'à 60, puis la largeur jusqu'à 900 px.
Le fichier d'origine est remplacé par le .webp,
et les noms de fichiers sont mis à jour dans app/data/lieux.json et app/data/modules.json,
avec la largeur et la hauteur de chaque image.

Utilisation locale (Azurite lancé avec docker compose, Pillow installé par requirements-dev.txt) :
    python scripts/charger_medias.py
    python scripts/charger_medias.py --sans-envoi     conversion seulement

Variables d'environnement lues (mêmes noms que l'application) :
    STORAGE_MODE                     azurite (par défaut) ou azure
    AZURE_STORAGE_CONNECTION_STRING  UseDevelopmentStorage=true par défaut en mode azurite
    AZURE_STORAGE_ACCOUNT_NAME       en mode azure (authentification par DefaultAzureCredential)
"""

import argparse
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.routes.medias import NOM_VALIDE  # noqa: E402
from app.services.storage import creer_stockage  # noqa: E402

CHEMIN_LIEUX = RACINE / "app" / "data" / "lieux.json"
CHEMIN_MODULES = RACINE / "app" / "data" / "modules.json"
LARGEUR_MAX = 1200
LARGEURS = (LARGEUR_MAX, 1100, 1000, 900)
QUALITE = 80
QUALITE_MIN = 60
POIDS_CIBLE = 150 * 1024
EXTENSIONS_A_CONVERTIR = (".jpg", ".jpeg", ".png")
TYPES = {".webp": "image/webp", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


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


def encoder_webp(contenu: bytes) -> dict:
    """Image (octets) vers WebP. Retourne les octets, les dimensions et la qualité retenue.

    On essaie la qualité 80 puis on baisse jusqu'à 60. Si l'image dépasse toujours 150 Ko,
    on réduit la largeur par paliers (1100, 1000 puis 900 px) et on recommence.
    """
    from PIL import Image

    with Image.open(io.BytesIO(contenu)) as originale:
        originale = originale.convert("RGB")
        meilleur = None
        for largeur_max in LARGEURS:
            image = originale
            if originale.width > largeur_max:
                hauteur = round(originale.height * largeur_max / originale.width)
                image = originale.resize((largeur_max, hauteur), Image.LANCZOS)
            for qualite in range(QUALITE, QUALITE_MIN - 1, -5):
                tampon = io.BytesIO()
                image.save(tampon, "WEBP", quality=qualite, method=6)
                meilleur = {
                    "octets": tampon.getvalue(),
                    "largeur": image.width,
                    "hauteur": image.height,
                    "qualite": qualite,
                }
                if tampon.tell() <= POIDS_CIBLE:
                    return meilleur
            if originale.width <= largeur_max:
                break  # inutile de réduire une image déjà plus étroite
        return meilleur


def dimensions(contenu: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(contenu)) as image:
        return image.width, image.height


def convertir_dossier(dossier: Path) -> list[dict]:
    """Convertit chaque image JPG ou PNG du dossier en WebP et supprime l'original."""
    resultats = []
    for source in sorted(dossier.iterdir()):
        if source.suffix.lower() not in EXTENSIONS_A_CONVERTIR or not NOM_VALIDE.match(source.name):
            continue
        avant = source.read_bytes()
        webp = encoder_webp(avant)
        destination = source.with_suffix(".webp")
        destination.write_bytes(webp["octets"])
        source.unlink()
        resultats.append(
            {
                "ancien": source.name,
                "nouveau": destination.name,
                "avant": len(avant),
                "apres": len(webp["octets"]),
                "largeur": webp["largeur"],
                "hauteur": webp["hauteur"],
                "qualite": webp["qualite"],
            }
        )
    return resultats


def mettre_a_jour_references(fiches: list[dict], champ: str, dossier: Path) -> bool:
    """Remplace les anciens noms par les .webp et renseigne largeur et hauteur. Retourne True si modifié."""
    modifie = False
    for fiche in fiches:
        nom = fiche.get(champ, "")
        if not nom:
            continue
        webp = Path(nom).with_suffix(".webp").name
        if (dossier / webp).exists():
            largeur, hauteur = dimensions((dossier / webp).read_bytes())
            nouveau = {champ: webp, "photo_largeur": largeur, "photo_hauteur": hauteur}
            if any(fiche.get(cle) != valeur for cle, valeur in nouveau.items()):
                fiche.update(nouveau)
                modifie = True
    return modifie


def ecrire_json(chemin: Path, donnees) -> None:
    chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def tableau(resultats: list[dict]) -> str:
    lignes = [f"{'Fichier':<28} {'Avant':>9} {'Après':>9} {'Gain':>6}  Dimensions  Qualité"]
    for r in resultats:
        gain = 100 - round(r["apres"] * 100 / r["avant"]) if r["avant"] else 0
        lignes.append(
            f"{r['nouveau']:<28} {r['avant'] / 1024:>6.0f} Ko {r['apres'] / 1024:>6.0f} Ko {gain:>5} %"
            f"  {r['largeur']}x{r['hauteur']:<6} {r['qualite']}"
        )
    total_avant = sum(r["avant"] for r in resultats)
    total_apres = sum(r["apres"] for r in resultats)
    lignes.append(f"{'Total':<28} {total_avant / 1024:>6.0f} Ko {total_apres / 1024:>6.0f} Ko")
    return "\n".join(lignes)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Conversion WebP et envoi des photos.")
    parser.add_argument("--dossier", type=Path, default=RACINE / "medias", help="dossier des images")
    parser.add_argument("--sans-envoi", action="store_true", help="convertit sans envoyer dans le stockage")
    args = parser.parse_args()

    resultats = convertir_dossier(args.dossier)
    if resultats:
        print(tableau(resultats))

    lieux = json.loads(CHEMIN_LIEUX.read_text(encoding="utf-8"))
    if mettre_a_jour_references(lieux, "photo", args.dossier):
        ecrire_json(CHEMIN_LIEUX, lieux)
    modules = json.loads(CHEMIN_MODULES.read_text(encoding="utf-8"))
    if mettre_a_jour_references(list(modules.values()), "photo_bandeau", args.dossier):
        ecrire_json(CHEMIN_MODULES, modules)

    references = {x["photo"] for x in lieux if x["photo"]} | {
        m["photo_bandeau"] for m in modules.values() if m["photo_bandeau"]
    }
    for nom in sorted(references):
        if not (args.dossier / nom).exists():
            print(f"Attention : {nom} est cité dans les données mais absent de {args.dossier.name}/.")

    if args.sans_envoi:
        return 0
    config = lire_config()
    if config.STORAGE_MODE == "memoire":
        print("STORAGE_MODE=memoire : rien à envoyer.")
        return 1
    stockage = creer_stockage(config)
    stockage.initialiser()
    fichiers = sorted(f for f in args.dossier.iterdir() if f.is_file() and NOM_VALIDE.match(f.name))
    for fichier in fichiers:
        stockage.envoyer_media(fichier.name, fichier.read_bytes(), TYPES[fichier.suffix.lower()])
    print(f"{len(fichiers)} image(s) envoyée(s) dans le stockage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

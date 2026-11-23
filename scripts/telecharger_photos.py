"""Récupère sur Wikimedia Commons une photo libre pour chaque lieu de lieux.json qui n'en a pas.

Utilisation :
    python scripts/telecharger_photos.py --dry-run     affiche les choix sans rien télécharger
    python scripts/telecharger_photos.py               télécharge et met à jour lieux.json
    python scripts/telecharger_photos.py --lieux grand_place,citadelle

Le contact de l'équipe (User-Agent exigé par Wikimedia) est lu dans la variable d'environnement
PHOTOS_CONTACT, ou à défaut dans le fichier .env à la racine du projet. Aucune adresse n'est écrite ici.

Les lieux de la catégorie "logement" sont des sites web, pas des lieux physiques : ils sont ignorés.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
CHEMIN_LIEUX = RACINE / "app" / "data" / "lieux.json"
DOSSIER_MEDIAS = RACINE / "medias"
API = "https://commons.wikimedia.org/w/api.php"
LARGEUR = 1200
CATEGORIES_IGNOREES = ("logement",)
PAUSE_SECONDES = 1.0


# Fonctions pures, testées sans réseau.


def nettoyer_texte(valeur: str) -> str:
    """Retire les balises HTML et les entités, et compacte les espaces."""
    sans_balises = re.sub(r"<[^>]+>", " ", valeur or "")
    return re.sub(r"\s+", " ", html.unescape(sans_balises)).strip()


def licence_acceptee(licence: str) -> bool:
    """CC0, domaine public, CC BY et CC BY-SA. Refuse NC, ND et les autres licences."""
    texte = licence.strip().lower()
    if not texte or re.search(r"\b(nc|nd)\b", texte):
        return False
    if est_domaine_public(texte):
        return True
    return re.match(r"^cc[ -]by(-sa)?( \d(\.\d)?)?( [a-z]{2,3})?$", texte) is not None


def est_domaine_public(licence: str) -> bool:
    texte = licence.strip().lower()
    return (
        texte.startswith("cc0") or texte.startswith("public domain") or re.match(r"^pd\b", texte) is not None
    )


def lire_candidat(page: dict) -> dict | None:
    """Extrait les informations utiles d'une page de la réponse de l'API."""
    infos = (page.get("imageinfo") or [None])[0]
    if not infos:
        return None
    meta = infos.get("extmetadata") or {}
    return {
        "titre": page.get("title", ""),
        "rang": page.get("index", 0),
        "url": infos.get("thumburl") or infos.get("url", ""),
        "largeur": infos.get("thumbwidth") or infos.get("width", 0),
        "hauteur": infos.get("thumbheight") or infos.get("height", 0),
        "mime": infos.get("mime", ""),
        "page_commons": infos.get("descriptionurl", ""),
        "auteur": nettoyer_texte(meta.get("Artist", {}).get("value", "")),
        "licence": nettoyer_texte(meta.get("LicenseShortName", {}).get("value", "")),
    }


def choisir_image(reponse: dict) -> dict | None:
    """Première image (dans l'ordre de la recherche) en paysage, en JPEG, avec une licence acceptée."""
    pages = (reponse.get("query") or {}).get("pages") or []
    candidats = [c for c in (lire_candidat(p) for p in pages) if c]
    for candidat in sorted(candidats, key=lambda c: c["rang"]):
        if candidat["mime"] != "image/jpeg" or not candidat["url"]:
            continue
        if candidat["largeur"] <= candidat["hauteur"]:
            continue
        if not licence_acceptee(candidat["licence"]):
            continue
        if not candidat["auteur"] and not est_domaine_public(candidat["licence"]):
            continue  # attribution impossible sans auteur
        return candidat
    return None


def credit(candidat: dict) -> str:
    auteur = candidat["auteur"] or "Auteur inconnu"
    return f"{auteur}, {candidat['licence']}, via Wikimedia Commons"


def parametres_recherche(nom: str) -> dict:
    return {
        "action": "query",
        "format": "json",
        "formatversion": "2",
        "generator": "search",
        "gsrsearch": f"{nom} Lille",
        "gsrnamespace": "6",
        "gsrlimit": "15",
        "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata",
        "iiurlwidth": str(LARGEUR),
        "iiextmetadatafilter": "Artist|LicenseShortName",
    }


def tableau(lignes: list[tuple]) -> str:
    """Tableau texte aligné."""
    entetes = ("Lieu", "Fichier", "Auteur", "Licence", "Page Commons")
    toutes = [entetes, *lignes]
    largeurs = [min(max(len(str(x[i])) for x in toutes), 60) for i in range(len(entetes))]
    sortie = []
    for numero, ligne in enumerate(toutes):
        sortie.append(" | ".join(str(v)[:60].ljust(largeurs[i]) for i, v in enumerate(ligne)))
        if numero == 0:
            sortie.append("-+-".join("-" * x for x in largeurs))
    return "\n".join(sortie)


# Accès réseau et fichiers.


def lire_contact() -> str:
    contact = os.environ.get("PHOTOS_CONTACT", "").strip()
    fichier_env = RACINE / ".env"
    if not contact and fichier_env.exists():
        for ligne in fichier_env.read_text(encoding="utf-8").splitlines():
            if ligne.startswith("PHOTOS_CONTACT="):
                contact = ligne.split("=", 1)[1].strip().strip('"').strip("'")
    return contact


def requete(url: str, user_agent: str) -> bytes:
    demande = urllib.request.Request(url, headers={"User-Agent": user_agent})
    with urllib.request.urlopen(demande, timeout=30) as reponse:
        return reponse.read()


def rechercher(nom: str, user_agent: str) -> dict | None:
    url = f"{API}?{urllib.parse.urlencode(parametres_recherche(nom))}"
    return choisir_image(json.loads(requete(url, user_agent)))


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Photos libres depuis Wikimedia Commons.")
    parser.add_argument("--dry-run", action="store_true", help="affiche les choix sans rien télécharger")
    parser.add_argument("--lieux", default="", help="identifiants séparés par des virgules")
    args = parser.parse_args()

    contact = lire_contact()
    if not contact:
        print("PHOTOS_CONTACT est vide. Renseigne-le dans .env (contact de l'équipe pour Wikimedia).")
        return 1
    user_agent = f"Cap90-projet-etudiant/1.0 (contact : {contact})"

    lieux = json.loads(CHEMIN_LIEUX.read_text(encoding="utf-8"))
    filtre = {x.strip() for x in args.lieux.split(",") if x.strip()}
    a_traiter = [
        lieu
        for lieu in lieux
        if not lieu["photo"]
        and lieu["categorie"] not in CATEGORIES_IGNOREES
        and (not filtre or lieu["id"] in filtre)
    ]

    lignes = []
    for lieu in a_traiter:
        try:
            candidat = rechercher(lieu["nom"], user_agent)
        except OSError as erreur:
            print(f"{lieu['id']} : erreur réseau ({erreur}).")
            continue
        time.sleep(PAUSE_SECONDES)
        if candidat is None:
            lignes.append((lieu["id"], "aucune image retenue", "", "", ""))
            continue
        fichier = f"{lieu['id']}.jpg"
        lignes.append(
            (lieu["id"], fichier, candidat["auteur"], candidat["licence"], candidat["page_commons"])
        )
        if args.dry_run:
            continue
        DOSSIER_MEDIAS.mkdir(exist_ok=True)
        (DOSSIER_MEDIAS / fichier).write_bytes(requete(candidat["url"], user_agent))
        lieu["photo"] = fichier
        lieu["credit_photo"] = credit(candidat)
        time.sleep(PAUSE_SECONDES)

    if not args.dry_run and any(x[1].endswith(".jpg") for x in lignes):
        CHEMIN_LIEUX.write_text(json.dumps(lieux, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(tableau(lignes) if lignes else "Aucun lieu à traiter.")
    if args.dry_run:
        print("\nMode --dry-run : rien n'a été téléchargé ni modifié.")
    else:
        print("\nPense à lancer python scripts/charger_medias.py pour envoyer les photos dans le stockage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

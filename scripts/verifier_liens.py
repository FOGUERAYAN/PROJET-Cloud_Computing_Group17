"""Vérifie les liens officiels des fichiers de données (liens utiles, lieux, démarches, entraide).

Un lien est accepté s'il répond 200 et que la page d'arrivée n'est pas l'accueil du site.
Il est refusé en cas d'erreur (403, 404...), de redirection vers l'accueil, ou de fausse page
(réponse 200 avec "page introuvable" dans le titre).

Utilisation :
    python scripts/verifier_liens.py                 vérifie tous les liens des données
    python scripts/verifier_liens.py URL [URL...]    vérifie des adresses candidates
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from html import unescape
from pathlib import Path
from urllib.parse import urlsplit

RACINE = Path(__file__).resolve().parent.parent
DONNEES = RACINE / "app" / "data"
SOURCES = (
    ("liens_utiles.json", "titre", "url"),
    ("lieux.json", "id", "lien_officiel"),
    ("demarches.json", "code", "lien_officiel"),
    ("entraide.json", "nom", "lien_inscription"),
)
USER_AGENT = "Mozilla/5.0 (compatible; Cap90-verification-liens/1.0)"
CHEMINS_ACCUEIL = {"", "fr", "accueil", "index.html", "index.php", "home"}
MOTS_PAGE_INTROUVABLE = ("introuvable", "page not found", "404", "n'existe pas", "erreur", "n'est plus actif")
# Pages de protection anti-robot : elles répondent 200 quelle que soit l'adresse demandée.
MOTS_ANTI_ROBOT = ("robot", "bot manager", "captcha", "access denied", "just a moment", "attention required")


# Fonctions pures, testées sans réseau.


def chemin_normalise(url: str) -> str:
    return urlsplit(url).path.strip("/").lower()


def est_accueil(url: str) -> bool:
    return chemin_normalise(url) in CHEMINS_ACCUEIL


def titre_de_page(html: str) -> str:
    trouve = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.I | re.S)
    return " ".join(unescape(trouve.group(1)).split()) if trouve else ""


def evaluer(url_demandee: str, statut: int, url_finale: str, titre: str = "") -> tuple[bool, str]:
    """Décide si un lien précis est utilisable. Retourne (accepté, raison)."""
    if urlsplit(url_demandee).fragment.startswith("/"):
        # Application à une seule page : le serveur ne voit jamais ce qui suit le #.
        return False, "non vérifiable (adresse après #)"
    if statut >= 400:
        return False, f"erreur {statut}"
    if statut >= 300:
        return False, f"redirection {statut} non suivie"
    if est_accueil(url_finale) and not est_accueil(url_demandee):
        return False, "redirection vers l'accueil"
    titre_min = titre.lower()
    if any(mot in titre_min for mot in MOTS_ANTI_ROBOT):
        return False, "non vérifiable (protection anti-robot)"
    if any(mot in titre_min for mot in MOTS_PAGE_INTROUVABLE):
        return False, "page introuvable (titre)"
    if titre_min.startswith("accueil") and not est_accueil(url_demandee):
        return False, "redirection vers l'accueil (titre)"
    return True, "ok"


def accueil_du_site(url: str) -> str:
    morceaux = urlsplit(url)
    return f"{morceaux.scheme}://{morceaux.netloc}"


def tableau(lignes: list[tuple]) -> str:
    entetes = ("Statut", "Lien", "Raison")
    toutes = [entetes, *lignes]
    largeur = max(len(str(ligne[0])) for ligne in toutes)
    return "\n".join(f"{str(a):<{largeur}}  {b}  ({c})" for a, b, c in toutes)


# Réseau.


def interroger(url: str, delai: int = 20) -> tuple[int, str, str]:
    """(statut, url finale après redirections, titre de la page)."""
    demande = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "fr"})
    try:
        with urllib.request.urlopen(demande, timeout=delai) as reponse:
            html = reponse.read(300_000).decode("utf-8", errors="replace")
            return reponse.status, reponse.geturl(), titre_de_page(html)
    except urllib.error.HTTPError as erreur:
        return erreur.code, url, ""
    except (urllib.error.URLError, TimeoutError, OSError) as erreur:
        return 599, url, str(getattr(erreur, "reason", erreur))


def verifier(url: str) -> tuple[bool, str, int]:
    """(accepté, raison avec le titre de la page, statut)."""
    statut, finale, titre = interroger(url)
    accepte, raison = evaluer(url, statut, finale, titre)
    if accepte and titre:
        raison = f"ok, titre : {titre[:90]}"
    return accepte, raison, statut


def liens_des_donnees() -> list[str]:
    urls = []
    for fichier, _, champ in SOURCES:
        for element in json.loads((DONNEES / fichier).read_text(encoding="utf-8")):
            if element.get(champ) and element[champ] not in urls:
                urls.append(element[champ])
    return urls


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Vérification des liens officiels.")
    parser.add_argument(
        "urls", nargs="*", help="adresses à vérifier (par défaut : toutes celles des données)"
    )
    args = parser.parse_args()

    urls = args.urls or liens_des_donnees()
    lignes, echecs = [], 0
    for url in urls:
        accepte, raison, statut = verifier(url)
        echecs += not accepte
        lignes.append((statut, url, raison))
    print(tableau(lignes))
    print(f"\n{len(urls) - echecs} lien(s) valable(s), {echecs} à revoir.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(main())

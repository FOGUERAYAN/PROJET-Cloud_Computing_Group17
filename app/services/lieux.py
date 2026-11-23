"""Catalogue des lieux de la Métropole Européenne de Lille : chargement, validation et filtres."""

import json
from datetime import date
from pathlib import Path

CHEMIN_LIEUX = Path(__file__).resolve().parent.parent / "data" / "lieux.json"

CATEGORIES = ("utile", "logement", "decouverte", "manger")
CHAMPS = (
    "id",
    "nom",
    "categorie",
    "sous_categorie",
    "description",
    "adresse",
    "metro",
    "lien_officiel",
    "lien_carte",
    "photo",
    "credit_photo",
    "prix_indicatif",
    "verifie_le",
    "a_verifier",
)
CHAMPS_NON_VIDES = ("id", "nom", "categorie", "description")
PREFIXE_CARTE = "https://www.openstreetmap.org/"

# Icône Tabler affichée quand un lieu n'a pas de photo.
ICONES = {
    "utile": "building-community",
    "logement": "home",
    "decouverte": "building-castle",
    "manger": "tools-kitchen-2",
}

# Filtres de la page Découvrir : code dans l'URL, libellé, fonction de sélection.
FILTRES_DECOUVRIR = {
    "a-voir": ("À voir", lambda x: x["categorie"] == "decouverte" and x["sous_categorie"] != "sortir"),
    "manger": ("Manger pas cher", lambda x: x["categorie"] == "manger"),
    "sortir": ("Sortir", lambda x: x["sous_categorie"] == "sortir"),
}


class LieuInvalide(ValueError):
    """Erreur levée quand lieux.json ne respecte pas le format attendu."""


def valider_lieux(lieux: list) -> list:
    """Vérifie chaque lieu et retourne la liste. Lève LieuInvalide au premier problème."""
    if not isinstance(lieux, list):
        raise LieuInvalide("lieux.json doit contenir une liste.")
    vus = set()
    for position, lieu in enumerate(lieux, start=1):
        nom = lieu.get("id") or f"numéro {position}"
        manquants = [c for c in CHAMPS if c not in lieu]
        if manquants:
            raise LieuInvalide(f"Lieu {nom} : champs manquants {', '.join(manquants)}.")
        vides = [c for c in CHAMPS_NON_VIDES if not str(lieu[c]).strip()]
        if vides:
            raise LieuInvalide(f"Lieu {nom} : champs vides {', '.join(vides)}.")
        if lieu["id"] in vus:
            raise LieuInvalide(f"Lieu {nom} : identifiant en double.")
        vus.add(lieu["id"])
        if lieu["categorie"] not in CATEGORIES:
            raise LieuInvalide(f"Lieu {nom} : catégorie inconnue {lieu['categorie']}.")
        if lieu["photo"] and not lieu["credit_photo"].strip():
            raise LieuInvalide(f"Lieu {nom} : le crédit photo est obligatoire quand il y a une photo.")
        if lieu["lien_carte"] and not lieu["lien_carte"].startswith(PREFIXE_CARTE):
            raise LieuInvalide(f"Lieu {nom} : le lien de carte doit pointer vers OpenStreetMap.")
        if lieu["verifie_le"]:
            try:
                date.fromisoformat(lieu["verifie_le"])
            except ValueError as erreur:
                raise LieuInvalide(f"Lieu {nom} : verifie_le doit être au format AAAA-MM-JJ.") from erreur
        if not isinstance(lieu["a_verifier"], bool):
            raise LieuInvalide(f"Lieu {nom} : a_verifier doit valoir true ou false.")
    return lieux


def charger_lieux(chemin=CHEMIN_LIEUX) -> list:
    with open(chemin, encoding="utf-8") as fichier:
        return valider_lieux(json.load(fichier))


def par_categorie(lieux: list, categorie: str) -> list:
    return [lieu for lieu in lieux if lieu["categorie"] == categorie]


def filtrer_decouvrir(lieux: list, filtre: str | None) -> list:
    """Lieux de la page Découvrir. Sans filtre connu : tout ce qui est à voir, manger ou sortir."""
    if filtre in FILTRES_DECOUVRIR:
        selection = FILTRES_DECOUVRIR[filtre][1]
        return [lieu for lieu in lieux if selection(lieu)]
    return [lieu for lieu in lieux if lieu["categorie"] in ("decouverte", "manger")]


def premiere_phrase(texte: str) -> str:
    """Première phrase d'une description, pour les cartes."""
    fin = texte.find(". ")
    return texte if fin == -1 else texte[: fin + 1]


def trouver(lieux: list, identifiant: str) -> dict | None:
    return next((lieu for lieu in lieux if lieu["id"] == identifiant), None)

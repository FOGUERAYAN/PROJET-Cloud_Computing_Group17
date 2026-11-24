"""Photo de bandeau de chaque module (app/data/modules.json)."""

import json
from pathlib import Path

CHEMIN_MODULES = Path(__file__).resolve().parent.parent / "data" / "modules.json"


def dimensions_valides(fiche: dict) -> bool:
    """Largeur et hauteur facultatives, mais des entiers positifs quand elles sont présentes."""
    return all(
        isinstance(fiche.get(cle, 1), int) and fiche.get(cle, 1) > 0
        for cle in ("photo_largeur", "photo_hauteur")
    )


class ModuleInvalide(ValueError):
    """Erreur levée quand modules.json ne respecte pas le format attendu."""


def valider_modules(modules: dict) -> dict:
    if not isinstance(modules, dict):
        raise ModuleInvalide("modules.json doit contenir un objet.")
    for nom, module in modules.items():
        manquants = [c for c in ("photo_bandeau", "credit_photo") if c not in module]
        if manquants:
            raise ModuleInvalide(f"Module {nom} : champs manquants {', '.join(manquants)}.")
        if not dimensions_valides(module):
            raise ModuleInvalide(
                f"Module {nom} : photo_largeur et photo_hauteur doivent être des entiers positifs."
            )
        if module["photo_bandeau"] and not module["credit_photo"].strip():
            raise ModuleInvalide(f"Module {nom} : le crédit photo est obligatoire quand il y a une photo.")
    return modules


def charger_modules(chemin=CHEMIN_MODULES) -> dict:
    with open(chemin, encoding="utf-8") as fichier:
        return valider_modules(json.load(fichier))


def photo_du_module(modules: dict, nom: str, titre: str) -> dict | None:
    """Photo de bandeau au format attendu par la macro photo(), ou None s'il n'y en a pas."""
    module = modules.get(nom) or {}
    if not module.get("photo_bandeau"):
        return None
    return {
        "nom": titre,
        "photo": module["photo_bandeau"],
        "credit_photo": module["credit_photo"],
        "photo_largeur": module.get("photo_largeur", 0),
        "photo_hauteur": module.get("photo_hauteur", 0),
        "categorie": "decouverte",
    }

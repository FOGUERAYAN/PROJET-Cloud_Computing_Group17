"""Photo de bandeau de chaque module (app/data/modules.json)."""

import json
from pathlib import Path

CHEMIN_MODULES = Path(__file__).resolve().parent.parent / "data" / "modules.json"


class ModuleInvalide(ValueError):
    """Erreur levée quand modules.json ne respecte pas le format attendu."""


def valider_modules(modules: dict) -> dict:
    if not isinstance(modules, dict):
        raise ModuleInvalide("modules.json doit contenir un objet.")
    for nom, module in modules.items():
        manquants = [c for c in ("photo_bandeau", "credit_photo") if c not in module]
        if manquants:
            raise ModuleInvalide(f"Module {nom} : champs manquants {', '.join(manquants)}.")
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
        "categorie": "decouverte",
    }

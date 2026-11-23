"""Liens officiels utiles : chargement, validation et filtre par thème."""

import json
from pathlib import Path

from app.services.sigles import erreur_sigle
from app.services.themes import THEMES

CHEMIN_LIENS = Path(__file__).resolve().parent.parent / "data" / "liens_utiles.json"
CHAMPS = ("titre", "sigle", "url", "description", "theme")


class LienInvalide(ValueError):
    """Erreur levée quand liens_utiles.json ne respecte pas le format attendu."""


def valider_liens(liens: list) -> list:
    if not isinstance(liens, list):
        raise LienInvalide("liens_utiles.json doit contenir une liste.")
    for position, lien in enumerate(liens, start=1):
        nom = lien.get("titre") or f"numéro {position}"
        manquants = [c for c in CHAMPS if not str(lien.get(c, "")).strip()]
        if manquants:
            raise LienInvalide(f"Lien {nom} : champs manquants ou vides {', '.join(manquants)}.")
        if not lien["url"].startswith("https://"):
            raise LienInvalide(f"Lien {nom} : l'adresse doit commencer par https://.")
        probleme = erreur_sigle(lien["sigle"], obligatoire=True)
        if probleme:
            raise LienInvalide(f"Lien {nom} : {probleme}.")
        if lien["theme"] not in THEMES:
            raise LienInvalide(f"Lien {nom} : thème inconnu {lien['theme']}.")
    return liens


def charger_liens(chemin=CHEMIN_LIENS) -> list:
    with open(chemin, encoding="utf-8") as fichier:
        return valider_liens(json.load(fichier))


def filtrer_par_themes(liens: list, themes, limite: int | None = None) -> list:
    """Liens des thèmes demandés, dans l'ordre du fichier. Sans thème : les liens généraux (papiers)."""
    themes = set(themes or ()) or {"papiers"}
    selection = [lien for lien in liens if lien["theme"] in themes]
    return selection[:limite] if limite else selection

"""Agenda de l'entraide à Lille : chargement, validation et regroupement par jour."""

import json
from datetime import date
from pathlib import Path

from app.services.sigles import erreur_sigle
from app.services.themes import THEMES

CHEMIN_ENTRAIDE = Path(__file__).resolve().parent.parent / "data" / "entraide.json"

JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
TYPES = {
    "aide_alimentaire": ("Aide alimentaire", "basket"),
    "epicerie": ("Épicerie solidaire", "building-store"),
    "benevolat": ("Bénévolat", "heart-handshake"),
}
FREQUENCES = ("chaque semaine", "une semaine sur deux", "variable")
CHAMPS = (
    "nom",
    "sigle",
    "type",
    "theme",
    "description",
    "jour_semaine",
    "frequence",
    "horaires",
    "adresse",
    "conditions",
    "lien_inscription",
    "verifie_le",
    "a_verifier",
)
CHAMPS_NON_VIDES = ("nom", "type", "description", "frequence")


class EntraideInvalide(ValueError):
    """Erreur levée quand entraide.json ne respecte pas le format attendu."""


def valider_entraide(entrees: list) -> list:
    if not isinstance(entrees, list):
        raise EntraideInvalide("entraide.json doit contenir une liste.")
    for position, entree in enumerate(entrees, start=1):
        nom = entree.get("nom") or f"numéro {position}"
        manquants = [c for c in CHAMPS if c not in entree]
        if manquants:
            raise EntraideInvalide(f"Entrée {nom} : champs manquants {', '.join(manquants)}.")
        vides = [c for c in CHAMPS_NON_VIDES if not str(entree[c]).strip()]
        if vides:
            raise EntraideInvalide(f"Entrée {nom} : champs vides {', '.join(vides)}.")
        if entree["type"] not in TYPES:
            raise EntraideInvalide(f"Entrée {nom} : type inconnu {entree['type']}.")
        probleme = erreur_sigle(entree["sigle"], obligatoire=True)
        if probleme:
            raise EntraideInvalide(f"Entrée {nom} : {probleme}.")
        if entree["theme"] not in THEMES:
            raise EntraideInvalide(f"Entrée {nom} : thème inconnu {entree['theme']}.")
        if entree["jour_semaine"] and entree["jour_semaine"] not in JOURS:
            raise EntraideInvalide(f"Entrée {nom} : jour_semaine doit être un jour en minuscules ou vide.")
        if entree["frequence"] not in FREQUENCES:
            raise EntraideInvalide(f"Entrée {nom} : fréquence inconnue {entree['frequence']}.")
        if entree["lien_inscription"] and not entree["lien_inscription"].startswith("https://"):
            raise EntraideInvalide(f"Entrée {nom} : le lien d'inscription doit commencer par https://.")
        if entree["verifie_le"]:
            try:
                date.fromisoformat(entree["verifie_le"])
            except ValueError as erreur:
                raise EntraideInvalide(
                    f"Entrée {nom} : verifie_le doit être au format AAAA-MM-JJ."
                ) from erreur
        if not isinstance(entree["a_verifier"], bool):
            raise EntraideInvalide(f"Entrée {nom} : a_verifier doit valoir true ou false.")
    return entrees


def charger_entraide(chemin=CHEMIN_ENTRAIDE) -> list:
    with open(chemin, encoding="utf-8") as fichier:
        return valider_entraide(json.load(fichier))


def nom_du_jour(jour: date) -> str:
    return JOURS[jour.weekday()]


def grouper_par_jour(entrees: list) -> tuple[dict[str, list], list]:
    """Retourne les entrées rangées par jour (lundi à dimanche) et celles dont le jour est à confirmer."""
    semaine = {jour: [] for jour in JOURS}
    sans_jour = []
    for entree in entrees:
        if entree["jour_semaine"]:
            semaine[entree["jour_semaine"]].append(entree)
        else:
            sans_jour.append(entree)
    return semaine, sans_jour

"""Calcul du rétroplanning. Uniquement des fonctions pures, faciles à tester."""

import json
from datetime import date, timedelta
from pathlib import Path

DUREE_PARCOURS = 90
SEUIL_URGENCE_JOURS = 7
CHEMIN_CATALOGUE = Path(__file__).resolve().parent.parent / "data" / "demarches.json"


def charger_catalogue(chemin=CHEMIN_CATALOGUE):
    """Lit le catalogue des démarches au format JSON."""
    with open(chemin, encoding="utf-8") as fichier:
        return json.load(fichier)


def jour_courant(date_arrivee: date, aujourd_hui: date) -> int:
    """Numéro du jour dans le parcours (le jour d'arrivée est le jour 1), borné entre 1 et 90."""
    numero = (aujourd_hui - date_arrivee).days + 1
    return max(1, min(numero, DUREE_PARCOURS))


def calculer_etapes(catalogue: list, statut: str, date_arrivee: date) -> list:
    """Retourne les étapes qui concernent le statut, triées par date limite."""
    concernees = [d for d in catalogue if statut in d["statuts"]]
    concernees.sort(key=lambda d: (d["delai_jours"], d["code"]))
    return [
        {
            "code": d["code"],
            "titre": d["titre"],
            "date_limite": date_arrivee + timedelta(days=d["delai_jours"]),
            "statut": "a_faire",
            "ordre": ordre,
        }
        for ordre, d in enumerate(concernees, start=1)
    ]


def jours_restants(date_limite: date, aujourd_hui: date) -> int:
    """Nombre de jours avant la date limite (négatif si elle est dépassée)."""
    return (date_limite - aujourd_hui).days


def est_urgente(date_limite: date, statut: str, aujourd_hui: date) -> bool:
    """Une étape non faite est urgente s'il reste moins de 7 jours."""
    return statut != "fait" and jours_restants(date_limite, aujourd_hui) < SEUIL_URGENCE_JOURS

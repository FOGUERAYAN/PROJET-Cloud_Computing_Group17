"""Suivi des heures de travail des étudiants étrangers. Uniquement des fonctions pures.

La limite est de 964 heures par période d'un an. Chaque période commence à la date de
validation du visa et recommence à chaque anniversaire de cette date (exemple : validation
le 1er septembre 2025, période du 1er septembre 2025 au 31 août 2026).

Les heures sont saisies par mois (AAAA-MM). Une période compte donc les 12 mois qui
commencent au mois de son premier jour : chaque mois appartient à une seule période.
"""

from datetime import date, timedelta

PLAFOND_HEURES = 964
SEUIL_ALERTE = 0.8


def ajouter_annees(jour: date, annees: int) -> date:
    """Même jour, n années plus tard. Un 29 février devient un 28 février si besoin."""
    try:
        return jour.replace(year=jour.year + annees)
    except ValueError:
        return jour.replace(year=jour.year + annees, day=28)


def periode_en_cours(date_validation: date, aujourd_hui: date) -> tuple[date, date]:
    """Début et fin (inclus) de la période d'un an qui contient aujourd'hui."""
    annees = 0
    while ajouter_annees(date_validation, annees + 1) <= aujourd_hui:
        annees += 1
    debut = ajouter_annees(date_validation, annees)
    fin = ajouter_annees(date_validation, annees + 1) - timedelta(days=1)
    return debut, fin


def mois_de_la_periode(debut: date) -> list[str]:
    """Les 12 mois (AAAA-MM) comptés dans la période qui commence à cette date."""
    mois = []
    annee, numero = debut.year, debut.month
    for _ in range(12):
        mois.append(f"{annee:04d}-{numero:02d}")
        numero += 1
        if numero == 13:
            annee, numero = annee + 1, 1
    return mois


def total_periode(heures_par_mois: dict[str, float], debut: date) -> float:
    return sum(heures_par_mois.get(mois, 0) for mois in mois_de_la_periode(debut))


def heures_restantes(total: float) -> float:
    return max(0.0, PLAFOND_HEURES - total)


def niveau_jauge(total: float) -> str:
    """normal sous 80 %, alerte de 80 à 100 % inclus, retard au-delà de 100 %."""
    if total > PLAFOND_HEURES:
        return "retard"
    if total >= PLAFOND_HEURES * SEUIL_ALERTE:
        return "alerte"
    return "normal"


def pourcentage(total: float) -> float:
    return round(total / PLAFOND_HEURES * 100, 1)

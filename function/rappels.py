"""Canaux d'envoi des rappels. Point d'extension pour l'e-mail (V2).

Pour ajouter un canal : écrire une classe avec une méthode envoyer(rappels) -> int,
puis la choisir dans choisir_canal(). Rien d'autre ne change dans la Function.
"""

import logging
from typing import Protocol

from taches import id_court

journal = logging.getLogger("cap90.rappels")


class CanalRappel(Protocol):
    def envoyer(self, rappels: dict[str, list[dict]]) -> int:
        """Envoie les rappels {id utilisateur: [démarches]} et retourne le nombre d'utilisateurs traités."""
        ...


def resume(demarches: list[dict]) -> str:
    """Résumé sans donnée personnelle : codes des démarches et jours restants."""
    morceaux = []
    for d in demarches:
        if d["jours_restants"] < 0:
            morceaux.append(f"{d['code']} (en retard de {-d['jours_restants']} j)")
        else:
            morceaux.append(f"{d['code']} ({d['jours_restants']} j)")
    return ", ".join(morceaux)


class CanalJournal:
    """V1 : écrit une ligne par utilisateur dans les journaux (sortie standard et Application Insights).

    Seuls l'identifiant tronqué et les codes des démarches sont écrits : ni pseudo, ni ville, ni titre.
    """

    def __init__(self, logger: logging.Logger = journal):
        self.logger = logger

    def envoyer(self, rappels: dict[str, list[dict]]) -> int:
        for utilisateur, demarches in rappels.items():
            self.logger.info("Rappel pour l'utilisateur %s : %s", id_court(utilisateur), resume(demarches))
        return len(rappels)


class CanalEmail:
    """V2, pas encore disponible.

    Prérequis avant de l'activer :
    1. Ajouter une adresse e-mail facultative au profil, avec le consentement de l'utilisateur.
    2. Choisir un service d'envoi (par exemple Azure Communication Services) et lui donner accès
       par identité managée, sans clé dans le code.
    3. Implémenter envoyer() : un e-mail par utilisateur qui a donné son adresse.
    """

    def envoyer(self, rappels: dict[str, list[dict]]) -> int:
        raise NotImplementedError("Les rappels par e-mail arriveront dans une prochaine version.")


def choisir_canal() -> CanalRappel:
    """Point unique de choix du canal. V1 : journaux."""
    return CanalJournal()

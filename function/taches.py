"""Tâches nocturnes de Cap90 : purge des annonces expirées et rappels des démarches.

La logique de choix (quelles annonces purger, quelles démarches rappeler) est faite de fonctions
pures, testées sans réseau. Les fonctions executer_* reçoivent le stockage et le canal de rappel
en paramètre, ce qui permet de les tester avec des doubles en mémoire.
"""

import logging
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

DUREE_ANNONCE = timedelta(days=30)  # une annonce expire 30 jours après sa création (J+30)
SEUIL_RAPPEL_JOURS = 7  # même seuil que la page Notifications de l'application

journal = logging.getLogger("cap90.function")


# Dates


def lire_moment(valeur) -> datetime | None:
    """Date (AAAA-MM-JJ) ou date et heure ISO vers un datetime UTC. None si la valeur est illisible.

    Une date seule vaut jusqu'à la fin de ce jour : elle est donc convertie en minuit du lendemain.
    """
    if isinstance(valeur, datetime):
        return valeur if valeur.tzinfo else valeur.replace(tzinfo=UTC)
    if not isinstance(valeur, str) or not valeur.strip():
        return None
    texte = valeur.strip()
    try:
        if len(texte) == 10:
            jour = date.fromisoformat(texte)
            return datetime(jour.year, jour.month, jour.day, tzinfo=UTC) + timedelta(days=1)
        moment = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def lire_debut(valeur) -> datetime | None:
    """Comme lire_moment, mais une date seule compte dès minuit (date de création)."""
    moment = lire_moment(valeur)
    if moment is not None and isinstance(valeur, str) and len(valeur.strip()) == 10:
        moment -= timedelta(days=1)
    return moment


def id_court(id_utilisateur: str) -> str:
    """Identifiant tronqué pour les journaux : jamais d'identifiant complet dans Application Insights."""
    return (id_utilisateur or "inconnu")[:8]


# Tâche 1 : purge des annonces


def annonces_a_purger(annonces: list[dict], maintenant: datetime) -> tuple[list[dict], list[dict]]:
    """Retourne (annonces à purger, annonces ignorées faute de date lisible).

    Une annonce est purgée quand expire_le est dépassé. Sans expire_le, on prend cree_le + 30 jours.
    Une annonce dont aucune date n'est lisible n'est jamais supprimée : elle est signalée.
    """
    a_purger, ignorees = [], []
    for annonce in annonces:
        expiration = lire_moment(annonce.get("expire_le"))
        if expiration is None:
            creation = lire_debut(annonce.get("cree_le"))
            expiration = creation + DUREE_ANNONCE if creation else None
        fiche = {
            "partition": annonce.get("PartitionKey", ""),
            "ligne": annonce.get("RowKey", ""),
            "photo_blob": (annonce.get("photo_blob") or "").strip(),
        }
        if expiration is None:
            ignorees.append(fiche)
        elif expiration <= maintenant:
            a_purger.append(fiche)
    return a_purger, ignorees


def executer_purge(stockage, maintenant: datetime) -> dict:
    """Supprime les annonces expirées et leurs photos. La photo d'abord, l'annonce ensuite :
    si la photo ne peut pas être supprimée, l'annonce reste et sera reprise la nuit suivante."""
    annonces = stockage.lister_annonces()
    a_purger, ignorees = annonces_a_purger(annonces, maintenant)
    bilan = {"examinees": len(annonces), "purgees": 0, "photos": 0, "echecs": 0, "ignorees": len(ignorees)}
    for fiche in ignorees:
        journal.warning("Annonce %s ignorée : date d'expiration illisible.", fiche["ligne"][:8])
    for fiche in a_purger:
        try:
            if fiche["photo_blob"] and stockage.supprimer_photo(fiche["photo_blob"]):
                bilan["photos"] += 1
            stockage.supprimer_annonce(fiche["partition"], fiche["ligne"])
            bilan["purgees"] += 1
        except Exception:  # une erreur sur une annonce ne doit pas arrêter la purge
            bilan["echecs"] += 1
            journal.exception("Échec de la purge de l'annonce %s.", fiche["ligne"][:8])
    if not a_purger:
        journal.info("Purge : rien à purger (%s annonce(s) examinée(s)).", bilan["examinees"])
    else:
        journal.info(
            "Purge : %s annonce(s) et %s photo(s) supprimée(s), %s échec(s).",
            bilan["purgees"],
            bilan["photos"],
            bilan["echecs"],
        )
    return bilan


# Tâche 2 : rappels des démarches


def rappels_a_envoyer(
    etapes: list[dict], aujourd_hui: date, seuil: int = SEUIL_RAPPEL_JOURS
) -> dict[str, list[dict]]:
    """Démarches non faites dont la date limite est à moins de `seuil` jours ou dépassée,
    regroupées par utilisateur (PartitionKey) et triées de la plus urgente à la moins urgente."""
    rappels = defaultdict(list)
    for etape in etapes:
        if etape.get("statut") == "fait":
            continue
        try:
            date_limite = date.fromisoformat(str(etape.get("date_limite", "")))
        except ValueError:
            continue
        restants = (date_limite - aujourd_hui).days
        if restants < seuil:
            rappels[etape.get("PartitionKey", "")].append(
                {
                    "code": etape.get("RowKey", ""),
                    "titre": etape.get("titre", ""),
                    "date_limite": date_limite.isoformat(),
                    "jours_restants": restants,
                }
            )
    return {
        utilisateur: sorted(liste, key=lambda r: (r["jours_restants"], r["code"]))
        for utilisateur, liste in sorted(rappels.items())
    }


def executer_rappels(stockage, aujourd_hui: date, canal) -> int:
    """Calcule les rappels et les confie au canal (journaux en V1, e-mail en V2)."""
    rappels = rappels_a_envoyer(stockage.lister_etapes_non_faites(), aujourd_hui)
    envoyes = canal.envoyer(rappels)
    journal.info("Rappels : %s utilisateur(s) concerné(s).", envoyes)
    return envoyes

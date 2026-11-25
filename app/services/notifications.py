"""Notifications calculées à l'affichage, sans base de données ni service externe.

Trois sources :
- les démarches non faites dont l'échéance est dans moins de 7 jours ou dépassée ;
- les distributions d'entraide qui ont lieu aujourd'hui ou demain ;
- les pièces encore à préparer pour la prochaine démarche (une seule notification).
"""

from datetime import date, timedelta

from app.services.entraide import JOURS, TYPES, grouper_par_jour
from app.services.planning import SEUIL_URGENCE_JOURS, jours_restants
from app.services.suivi import est_faite, lire_pieces_pretes, prochaine_etape, trier


def pluriel(nombre: int, mot: str) -> str:
    return f"{nombre} {mot}{'s' if nombre > 1 else ''}"


def notifications_echeances(etapes: list, aujourd_hui: date) -> list[dict]:
    resultat = []
    for etape in trier(etapes):
        if est_faite(etape):
            continue
        restants = jours_restants(date.fromisoformat(etape["date_limite"]), aujourd_hui)
        if restants >= SEUIL_URGENCE_JOURS:
            continue
        if restants < 0:
            texte, icone, niveau = (
                f"En retard de {pluriel(-restants, 'jour')} : {etape['titre']}",
                "alert-octagon",
                "retard",
            )
        elif restants == 0:
            texte, icone, niveau = f"Dernier jour pour : {etape['titre']}", "alarm", "alerte"
        else:
            texte, icone, niveau = (
                f"Plus que {pluriel(restants, 'jour')} pour : {etape['titre']}",
                "alarm",
                "alerte",
            )
        resultat.append(
            {
                "categorie": "echeance",
                "niveau": niveau,
                "icone": icone,
                "texte": texte,
                "page": "planning",
                "ancre": etape["RowKey"],
            }
        )
    return resultat


def notification_pieces(etapes: list, catalogue: list) -> list[dict]:
    prochaine = prochaine_etape(etapes)
    if prochaine is None:
        return []
    pieces = next((d.get("pieces", []) for d in catalogue if d["code"] == prochaine["RowKey"]), [])
    pretes = lire_pieces_pretes(prochaine.get("pieces_pretes"))
    manquantes = [nom for indice, nom in enumerate(pieces) if indice not in pretes]
    if not manquantes:
        return []
    texte = (
        f"{pluriel(len(manquantes), 'pièce')} à préparer pour {prochaine['titre']} : {', '.join(manquantes)}"
    )
    return [
        {
            "categorie": "pieces",
            "niveau": "info",
            "icone": "list-check",
            "texte": texte,
            "page": "planning",
            "ancre": prochaine["RowKey"],
        }
    ]


def notifications_entraide(entrees: list, aujourd_hui: date) -> list[dict]:
    semaine, _ = grouper_par_jour(entrees)
    resultat = []
    for decalage, quand in ((0, "Aujourd'hui"), (1, "Demain")):
        jour = JOURS[(aujourd_hui + timedelta(days=decalage)).weekday()]
        for entree, creneau in semaine[jour]:
            details = ", ".join(x for x in (creneau["horaires"], entree["nom"], creneau["adresse"]) if x)
            resultat.append(
                {
                    "categorie": "entraide",
                    "niveau": "info",
                    "icone": TYPES[entree["type"]][1],
                    "texte": f"{quand} : {details}",
                    "page": "solidarite",
                    "ancre": f"jour-{jour}",
                }
            )
    return resultat


def calculer(etapes: list, catalogue: list, entraide: list, aujourd_hui: date) -> list[dict]:
    """Toutes les notifications, des plus urgentes aux plus informatives."""
    return (
        notifications_echeances(etapes, aujourd_hui)
        + notification_pieces(etapes, catalogue)
        + notifications_entraide(entraide, aujourd_hui)
    )

"""Suivi du planning : groupes par échéance, prochaine étape, badges, pièces prêtes, recalcul.

Uniquement des fonctions pures. Les étapes sont des dictionnaires tels qu'enregistrés :
RowKey (code), titre, date_limite (AAAA-MM-JJ), statut, ordre, fait_le, pieces_pretes.
"""

from datetime import date

from app.services.planning import calculer_etapes, jours_restants

GROUPES = (
    ("en_retard", "En retard"),
    ("cette_semaine", "Cette semaine"),
    ("ce_mois", "Ce mois-ci"),
    ("plus_tard", "Plus tard"),
    ("faites", "Déjà faites"),
)

BADGES = (
    ("premier_pas", "Premier pas", "shoe", "Une première démarche faite."),
    ("mi_parcours", "Mi-parcours", "flag", "La moitié des démarches faites."),
    ("tout_en_ordre", "Tout est en ordre", "trophy", "Toutes les démarches faites."),
    ("a_l_heure", "À l'heure", "clock-check", "Aucune démarche faite après sa date limite."),
)


def est_faite(etape: dict) -> bool:
    return etape.get("statut") == "fait"


def groupe_de(etape: dict, aujourd_hui: date) -> str:
    """Groupe d'une étape selon sa date limite et la date du jour."""
    if est_faite(etape):
        return "faites"
    restants = jours_restants(date.fromisoformat(etape["date_limite"]), aujourd_hui)
    if restants < 0:
        return "en_retard"
    if restants < 7:
        return "cette_semaine"
    if restants < 30:
        return "ce_mois"
    return "plus_tard"


def trier(etapes: list) -> list:
    return sorted(etapes, key=lambda e: (e["date_limite"], e.get("ordre", 0)))


def prochaine_etape(etapes: list) -> dict | None:
    """Première étape à faire, par date limite."""
    return next((e for e in trier(etapes) if not est_faite(e)), None)


def grouper(etapes: list, aujourd_hui: date) -> list[tuple[str, str, list]]:
    """Groupes non vides, dans l'ordre : (code, libellé, étapes triées)."""
    ranges = {code: [] for code, _ in GROUPES}
    for etape in trier(etapes):
        ranges[groupe_de(etape, aujourd_hui)].append(etape)
    return [(code, libelle, ranges[code]) for code, libelle in GROUPES if ranges[code]]


def progression(etapes: list) -> tuple[int, int, int]:
    """(faites, total, pourcentage entier)."""
    total = len(etapes)
    faites = sum(1 for e in etapes if est_faite(e))
    return faites, total, round(faites * 100 / total) if total else 0


def badges_obtenus(etapes: list) -> set[str]:
    faites = [e for e in etapes if est_faite(e)]
    total = len(etapes)
    obtenus = set()
    if faites:
        obtenus.add("premier_pas")
        if all(e.get("fait_le") and e["fait_le"] <= e["date_limite"] for e in faites):
            obtenus.add("a_l_heure")
    if total and len(faites) * 2 >= total:
        obtenus.add("mi_parcours")
    if total and len(faites) == total:
        obtenus.add("tout_en_ordre")
    return obtenus


def liste_badges(etapes: list) -> list[dict]:
    obtenus = badges_obtenus(etapes)
    return [
        {"code": code, "titre": titre, "icone": icone, "description": texte, "obtenu": code in obtenus}
        for code, titre, icone, texte in BADGES
    ]


def nouveaux_badges(avant: list, apres: list) -> list[str]:
    """Titres des badges débloqués entre deux états du planning."""
    gagnes = badges_obtenus(apres) - badges_obtenus(avant)
    return [titre for code, titre, _, _ in BADGES if code in gagnes]


def message_validation(avant: list, apres: list) -> str:
    """Message affiché après "C'est fait"."""
    restantes = sum(1 for e in apres if not est_faite(e))
    if restantes == 0:
        message = "Étape validée, toutes tes démarches sont faites."
    elif restantes == 1:
        message = "Étape validée, plus qu'une."
    else:
        message = f"Étape validée, plus que {restantes}."
    badges = nouveaux_badges(avant, apres)
    if badges:
        message += f" Badge débloqué : {', '.join(badges)}."
    return message


# Pièces à préparer : indices des pièces cochées, enregistrés sous la forme "0,2".


def lire_pieces_pretes(valeur: str | None) -> set[int]:
    if not valeur:
        return set()
    return {int(x) for x in valeur.split(",") if x.strip().isdigit()}


def ecrire_pieces_pretes(indices: set[int]) -> str:
    return ",".join(str(i) for i in sorted(indices))


def basculer_piece(valeur: str | None, indice: int) -> str:
    indices = lire_pieces_pretes(valeur)
    indices ^= {indice}
    return ecrire_pieces_pretes(indices)


# Recalcul après modification du profil.


def recalculer(catalogue: list, existantes: list, statut: str, date_arrivee: date) -> tuple[list, list]:
    """Compare le planning existant au nouveau profil.

    Retourne (a_ecrire, a_supprimer) :
    - les étapes faites restent faites, avec leur date et leurs pièces ;
    - les étapes à faire prennent la nouvelle date limite ;
    - une étape qui ne concerne plus le statut est supprimée seulement si elle n'est pas faite.
    """
    nouvelles = {e["code"]: e for e in calculer_etapes(catalogue, statut, date_arrivee)}
    anciennes = {e["RowKey"]: e for e in existantes}

    a_ecrire = []
    for code, nouvelle in nouvelles.items():
        ancienne = anciennes.get(code)
        etape = {
            "code": code,
            "titre": nouvelle["titre"],
            "date_limite": nouvelle["date_limite"].isoformat(),
            "statut": "a_faire",
            "ordre": nouvelle["ordre"],
            "fait_le": "",
            "pieces_pretes": "",
        }
        if ancienne:
            etape["pieces_pretes"] = ancienne.get("pieces_pretes", "")
            if est_faite(ancienne):
                etape.update(
                    statut="fait",
                    fait_le=ancienne.get("fait_le", ""),
                    date_limite=ancienne["date_limite"],
                )
        a_ecrire.append(etape)

    a_supprimer = [code for code, e in anciennes.items() if code not in nouvelles and not est_faite(e)]
    return a_ecrire, a_supprimer


def resume_recalcul(existantes: list, a_ecrire: list, a_supprimer: list) -> dict:
    """Résumé lisible des changements, pour la page de confirmation."""
    anciennes = {e["RowKey"]: e for e in existantes}
    ajoutees = [e["titre"] for e in a_ecrire if e["code"] not in anciennes]
    deplacees = [
        e["titre"]
        for e in a_ecrire
        if e["code"] in anciennes
        and e["statut"] != "fait"
        and anciennes[e["code"]]["date_limite"] != e["date_limite"]
    ]
    retirees = [anciennes[code]["titre"] for code in a_supprimer]
    gardees = [e["titre"] for e in a_ecrire if e["statut"] == "fait"]
    return {"ajoutees": ajoutees, "deplacees": deplacees, "retirees": retirees, "gardees": gardees}

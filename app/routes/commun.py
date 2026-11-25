"""Aides communes aux pages : utilisateur courant, colonne latérale, filtres de templates."""

from datetime import date

from flask import current_app, g, session

from app.services.entraide import prochains_creneaux
from app.services.liens import filtrer_par_themes
from app.services.notifications import calculer as calculer_notifications
from app.services.planning import jour_courant, jours_restants
from app.services.referentiels import nom_commune, nom_langue
from app.services.sigles import famille_du_theme
from app.services.suivi import prochaine_etape, progression
from app.services.themes import THEMES


def aujourd_hui() -> date:
    return date.today()


def stockage():
    return current_app.extensions["stockage"]


def profil_courant() -> dict | None:
    """Profil de la session, lu une seule fois par requête."""
    if "profil" not in g:
        id_utilisateur = session.get("id_utilisateur")
        g.profil = stockage().lire_profil(id_utilisateur) if id_utilisateur else None
    return g.profil


def etapes_courantes() -> list:
    if "etapes" not in g:
        profil = profil_courant()
        g.etapes = stockage().lister_etapes(session["id_utilisateur"]) if profil else []
    return g.etapes


def majuscule_initiale(texte: str) -> str:
    texte = (texte or "").strip()
    return texte[:1].upper() + texte[1:]


def initiales(profil: dict | None) -> str:
    """Deux lettres au plus, tirées du pseudo. Vide s'il n'y a pas de pseudo."""
    if not profil or not profil.get("pseudo"):
        return ""
    mots = profil["pseudo"].replace("-", " ").split()
    return "".join(m[0] for m in mots[:2]).upper()


def resume_progression() -> dict | None:
    """Progression et prochaine étape de l'utilisateur, ou None sans profil."""
    profil = profil_courant()
    if profil is None:
        return None
    etapes = etapes_courantes()
    faites, total, pourcentage = progression(etapes)
    jour = aujourd_hui()
    prochaine = prochaine_etape(etapes)
    detail = None
    if prochaine:
        catalogue = {d["code"]: d for d in current_app.extensions["catalogue"]}
        pieces = catalogue.get(prochaine["RowKey"], {}).get("pieces", [])
        pretes = [
            i for i in range(len(pieces)) if str(i) in (prochaine.get("pieces_pretes") or "").split(",")
        ]
        date_limite = date.fromisoformat(prochaine["date_limite"])
        detail = {
            "code": prochaine["RowKey"],
            "titre": prochaine["titre"],
            "date_limite": date_limite.strftime("%d/%m/%Y"),
            "jours_restants": jours_restants(date_limite, jour),
            "pieces_total": len(pieces),
            "pieces_pretes": len(pretes),
        }
    return {
        "faites": faites,
        "total": total,
        "pourcentage": pourcentage,
        "jour": jour_courant(date.fromisoformat(profil["date_arrivee"]), jour),
        "prochaine": detail,
    }


def semaine_a_lille(limite: int = 3) -> list:
    """Prochains rendez-vous d'entraide dont le jour est connu (liste vide sinon)."""
    return prochains_creneaux(current_app.extensions["entraide"], aujourd_hui(), limite)


def notifications_courantes() -> list[dict]:
    """Notifications de l'utilisateur courant, calculées une seule fois par requête."""
    if "notifications" not in g:
        g.notifications = calculer_notifications(
            etapes_courantes(),
            current_app.extensions["catalogue"],
            current_app.extensions["entraide"],
            aujourd_hui(),
        )
    return g.notifications


def donnees_laterales(themes=()) -> dict:
    """Contenu de la colonne latérale des pages de module."""
    return {
        "progression": resume_progression(),
        "semaine": semaine_a_lille(),
        "liens": filtrer_par_themes(current_app.extensions["liens"], themes, limite=5),
    }


def installer(app) -> None:
    """Enregistre les fonctions et filtres utilisés par les templates."""
    app.jinja_env.globals.update(
        donnees_laterales=donnees_laterales,
        libelles_themes=THEMES,
        famille_du_theme=famille_du_theme,
        libelle_commune=lambda code: nom_commune(current_app.extensions["communes"], code),
        libelle_langue=lambda code, precision="": nom_langue(
            current_app.extensions["langues"], code, precision
        ),
    )
    app.jinja_env.filters["majuscule_initiale"] = majuscule_initiale

    @app.context_processor
    def utilisateur():
        profil = profil_courant()
        return {
            "profil_connecte": profil,
            "initiales": initiales(profil),
            "nb_notifications": len(notifications_courantes()),
        }

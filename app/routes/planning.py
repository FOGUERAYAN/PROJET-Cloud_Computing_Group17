"""Rétroplanning : étapes groupées par échéance, pièces à préparer, validation des étapes."""

from datetime import date

from flask import Blueprint, abort, current_app, flash, redirect, render_template, session, url_for

from app.routes.commun import majuscule_initiale
from app.services.lieux import trouver
from app.services.planning import DUREE_PARCOURS, est_urgente, jour_courant, jours_restants
from app.services.suivi import (
    basculer_piece,
    groupe_de,
    grouper,
    lire_pieces_pretes,
    liste_badges,
    message_validation,
    prochaine_etape,
    progression,
)

bp = Blueprint("planning", __name__)


def aujourd_hui() -> date:
    return date.today()


def vue_etape(etape: dict, details: dict, lieux: list, jour: date) -> dict:
    """Prépare une étape pour l'affichage."""
    date_limite = date.fromisoformat(etape["date_limite"])
    detail = details.get(etape["RowKey"], {})
    pieces = detail.get("pieces", [])
    pretes = lire_pieces_pretes(etape.get("pieces_pretes"))
    return {
        "code": etape["RowKey"],
        "titre": etape["titre"],
        "theme": detail.get("theme", ""),
        "date_limite": date_limite.strftime("%d/%m/%Y"),
        "jours_restants": jours_restants(date_limite, jour),
        "fait": etape["statut"] == "fait",
        "urgente": est_urgente(date_limite, etape["statut"], jour),
        "pieces": [{"indice": i, "nom": nom, "prete": i in pretes} for i, nom in enumerate(pieces)],
        "pieces_pretes": sum(1 for i in range(len(pieces)) if i in pretes),
        "lien_officiel": detail.get("lien_officiel", ""),
        "conseil": detail.get("conseil", ""),
        "lieu": trouver(lieux, detail.get("lieu_id", "")),
    }


@bp.get("/planning")
def index():
    id_utilisateur = session.get("id_utilisateur")
    stockage = current_app.extensions["stockage"]
    profil = stockage.lire_profil(id_utilisateur) if id_utilisateur else None
    if profil is None:
        return redirect(url_for("profil.formulaire"))

    jour = aujourd_hui()
    details = {d["code"]: d for d in current_app.extensions["catalogue"]}
    lieux = current_app.extensions["lieux"]
    etapes = stockage.lister_etapes(id_utilisateur)
    prochaine = prochaine_etape(etapes)
    groupe_ouvert = groupe_de(prochaine, jour) if prochaine else None
    faites, total, pourcentage = progression(etapes)

    groupes = [
        {
            "code": code,
            "libelle": libelle,
            "ouvert": code == groupe_ouvert,
            "etapes": [vue_etape(e, details, lieux, jour) for e in contenu],
        }
        for code, libelle, contenu in grouper(etapes, jour)
    ]

    return render_template(
        "planning.html",
        profil=profil,
        ville=majuscule_initiale(profil["ville"]),
        jour=jour_courant(date.fromisoformat(profil["date_arrivee"]), jour),
        duree=DUREE_PARCOURS,
        prochaine=vue_etape(prochaine, details, lieux, jour) if prochaine else None,
        groupes=groupes,
        faites=faites,
        total=total,
        pourcentage=pourcentage,
        badges=liste_badges(etapes),
    )


@bp.post("/planning/<code>/fait")
def basculer(code):
    id_utilisateur = session.get("id_utilisateur")
    if not id_utilisateur:
        return redirect(url_for("profil.formulaire"))

    stockage = current_app.extensions["stockage"]
    etape = stockage.lire_etape(id_utilisateur, code)
    if etape is None:
        abort(404)
    if etape["statut"] == "fait":
        stockage.changer_statut_etape(id_utilisateur, code, "a_faire")
        return redirect(url_for("planning.index") + f"#{code}")

    avant = stockage.lister_etapes(id_utilisateur)
    stockage.changer_statut_etape(id_utilisateur, code, "fait", aujourd_hui().isoformat())
    apres = stockage.lister_etapes(id_utilisateur)
    flash(message_validation(avant, apres), "succes")
    return redirect(url_for("planning.index"))


@bp.post("/planning/<code>/pieces/<int:indice>")
def basculer_piece_prete(code, indice):
    id_utilisateur = session.get("id_utilisateur")
    if not id_utilisateur:
        return redirect(url_for("profil.formulaire"))

    stockage = current_app.extensions["stockage"]
    etape = stockage.lire_etape(id_utilisateur, code)
    details = {d["code"]: d for d in current_app.extensions["catalogue"]}
    pieces = details.get(code, {}).get("pieces", [])
    if etape is None or not 0 <= indice < len(pieces):
        abort(404)
    stockage.changer_pieces_pretes(id_utilisateur, code, basculer_piece(etape.get("pieces_pretes"), indice))
    return redirect(url_for("planning.index") + f"#{code}")

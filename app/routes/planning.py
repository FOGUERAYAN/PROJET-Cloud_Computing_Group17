"""Affichage du rétroplanning et suivi des étapes faites."""

from datetime import date

from flask import Blueprint, abort, current_app, redirect, render_template, session, url_for

from app.services.lieux import trouver
from app.services.planning import DUREE_PARCOURS, est_urgente, jour_courant, jours_restants

bp = Blueprint("planning", __name__)


def aujourd_hui() -> date:
    return date.today()


@bp.get("/planning")
def index():
    id_utilisateur = session.get("id_utilisateur")
    stockage = current_app.extensions["stockage"]
    profil = stockage.lire_profil(id_utilisateur) if id_utilisateur else None
    if profil is None:
        return redirect(url_for("profil.formulaire"))

    jour = aujourd_hui()
    details = {d["code"]: d for d in current_app.extensions["catalogue"]}
    etapes = []
    for etape in stockage.lister_etapes(id_utilisateur):
        date_limite = date.fromisoformat(etape["date_limite"])
        detail = details.get(etape["RowKey"], {})
        etapes.append(
            {
                "code": etape["RowKey"],
                "titre": etape["titre"],
                "date_limite": date_limite.strftime("%d/%m/%Y"),
                "jours_restants": jours_restants(date_limite, jour),
                "fait": etape["statut"] == "fait",
                "urgente": est_urgente(date_limite, etape["statut"], jour),
                "pieces": detail.get("pieces", []),
                "lien_officiel": detail.get("lien_officiel", ""),
                "conseil": detail.get("conseil", ""),
                "lieu": trouver(current_app.extensions["lieux"], detail.get("lieu_id", "")),
            }
        )

    return render_template(
        "planning.html",
        profil=profil,
        jour=jour_courant(date.fromisoformat(profil["date_arrivee"]), jour),
        duree=DUREE_PARCOURS,
        etapes=etapes,
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
    else:
        stockage.changer_statut_etape(id_utilisateur, code, "fait", aujourd_hui().isoformat())
    return redirect(url_for("planning.index") + f"#{code}")

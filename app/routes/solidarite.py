"""Solidarité : agenda de l'entraide à Lille, bénévolat, et bientôt les dons entre habitants."""

from datetime import date

from flask import Blueprint, current_app, render_template

from app.services.entraide import JOURS, TYPES, grouper_par_jour, nom_du_jour

bp = Blueprint("solidarite", __name__)

LIEN_JEVEUXAIDER = (
    "https://www.jeveuxaider.gouv.fr/missions-benevolat"
    "?type=Mission%20en%20pr%C3%A9sentiel&aroundLatLng=50.632,3.05749&city=Lille"
)


def aujourd_hui() -> date:
    return date.today()


@bp.get("/solidarite")
def index():
    semaine, sans_jour = grouper_par_jour(current_app.extensions["entraide"])
    return render_template(
        "solidarite.html",
        jours=JOURS,
        semaine=semaine,
        sans_jour=sans_jour,
        jour_courant=nom_du_jour(aujourd_hui()),
        types=TYPES,
        lien_jeveuxaider=LIEN_JEVEUXAIDER,
    )

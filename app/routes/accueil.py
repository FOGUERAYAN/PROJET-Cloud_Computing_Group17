from flask import Blueprint, current_app, render_template

from app.routes.commun import resume_progression, semaine_a_lille
from app.services.lieux import trouver

bp = Blueprint("accueil", __name__)


@bp.get("/")
def index():
    return render_template(
        "accueil.html",
        grand_place=trouver(current_app.extensions["lieux"], "grand_place"),
        suivi=resume_progression(),
        semaine=semaine_a_lille(4),
    )

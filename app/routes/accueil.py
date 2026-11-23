from flask import Blueprint, current_app, render_template

from app.services.lieux import trouver

bp = Blueprint("accueil", __name__)


@bp.get("/")
def index():
    grand_place = trouver(current_app.extensions["lieux"], "grand_place")
    return render_template("accueil.html", grand_place=grand_place)

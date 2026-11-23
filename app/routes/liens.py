"""Page des liens officiels par thème (cible des étiquettes de thème)."""

from flask import Blueprint, current_app, render_template, request

from app.services.liens import filtrer_par_themes
from app.services.themes import THEMES

bp = Blueprint("liens", __name__)


@bp.get("/liens-utiles")
def index():
    theme = request.args.get("theme")
    if theme not in THEMES:
        theme = None
    liens = current_app.extensions["liens"]
    selection = filtrer_par_themes(liens, [theme]) if theme else liens
    demarches = [
        d for d in current_app.extensions["catalogue"] if theme and d["theme"] == theme and d["lien_officiel"]
    ]
    lieux = [
        lieu
        for lieu in current_app.extensions["lieux"]
        if theme and lieu["theme"] == theme and lieu["lien_officiel"]
    ]
    return render_template(
        "liens.html", theme=theme, liens=selection, demarches=demarches, lieux=lieux, themes=THEMES
    )

"""Page Notifications : alertes calculées à partir des données déjà présentes."""

from flask import Blueprint, render_template

from app.routes.commun import notifications_courantes, profil_courant

bp = Blueprint("notifications", __name__)


@bp.get("/notifications")
def index():
    return render_template(
        "notifications.html",
        notifications=notifications_courantes(),
        avec_profil=profil_courant() is not None,
    )

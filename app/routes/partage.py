"""Lien de partage interne (Azurite et stockage en mémoire) : lecture seule pendant 24 h, sans session."""

import io

from flask import Blueprint, current_app, render_template, send_file

from app.services.coffre import LienExpire, LienInvalide

bp = Blueprint("partage", __name__)


@bp.get("/partage/<jeton>")
def lire(jeton):
    try:
        id_utilisateur, identifiant = current_app.extensions["signataire"].verifier(jeton)
    except LienExpire:
        return render_template("partage_indisponible.html", expire=True), 410
    except LienInvalide:
        return render_template("partage_indisponible.html", expire=False), 404

    fichier = current_app.extensions["stockage"].lire_fichier(id_utilisateur, identifiant)
    if fichier is None:  # fichier supprimé depuis la création du lien
        return render_template("partage_indisponible.html", expire=False), 404

    reponse = send_file(
        io.BytesIO(fichier["contenu"]),
        mimetype=fichier["type"],
        as_attachment=False,
        download_name=fichier["nom"],
    )
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    reponse.headers["X-Robots-Tag"] = "noindex, nofollow"
    reponse.headers["Referrer-Policy"] = "no-referrer"
    return reponse

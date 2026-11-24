"""Diffusion des photos stockées dans le conteneur Blob privé medias-lille."""

import mimetypes
import re

from flask import Blueprint, Response, abort, current_app

bp = Blueprint("medias", __name__)

NOM_VALIDE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*\.(jpg|jpeg|png|webp)$", re.IGNORECASE)
DUREE_CACHE = 86400  # un jour, en secondes


@bp.get("/medias/<nom>")
def lire(nom):
    if not NOM_VALIDE.match(nom):
        abort(404)
    media = current_app.extensions["stockage"].lire_media(nom)
    if media is None:
        abort(404)
    contenu, type_contenu = media
    if not type_contenu or not type_contenu.startswith("image/"):
        type_contenu = mimetypes.guess_type(nom)[0] or "application/octet-stream"

    reponse = Response(contenu, mimetype=type_contenu)
    reponse.headers["Cache-Control"] = f"public, max-age={DUREE_CACHE}"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse

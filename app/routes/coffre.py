"""Coffre-fort : dépôt, liste, téléchargement, partage de 24 h et suppression des fichiers.

Tout passe par l'application : l'utilisateur ne lit jamais le conteneur directement,
et chaque accès vérifie que le fichier se trouve bien sous son propre préfixe.
"""

import io
from datetime import datetime

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from app.routes.commun import profil_courant
from app.services.coffre import (
    TAILLE_MAX,
    FichierRefuse,
    date_lisible,
    libelle_type,
    nettoyer_nom,
    taille_lisible,
    valider_fichier,
)

bp = Blueprint("coffre", __name__)


def stockage():
    return current_app.extensions["stockage"]


def en_tetes_prives(reponse):
    reponse.headers["Cache-Control"] = "private, no-store"
    reponse.headers["X-Content-Type-Options"] = "nosniff"
    return reponse


def vue_fichier(fiche: dict) -> dict:
    depose = datetime.fromisoformat(fiche["depose_le"]) if fiche["depose_le"] else None
    return {
        **fiche,
        "type_lisible": libelle_type(fiche["type"]),
        "taille_lisible": taille_lisible(fiche["taille"]),
        "depose_lisible": date_lisible(depose) if depose else "",
    }


def page_coffre(erreur: str = "", code: int = 200):
    id_utilisateur = session["id_utilisateur"]
    fichiers = [vue_fichier(f) for f in stockage().lister_fichiers(id_utilisateur)]
    lien = session.pop("dernier_lien", None)
    return (
        render_template(
            "coffre.html",
            fichiers=fichiers,
            erreur=erreur,
            lien=lien,
            taille_max=taille_lisible(TAILLE_MAX),
        ),
        code,
    )


def exiger_profil():
    if profil_courant() is None:
        return redirect(url_for("profil.formulaire"))
    return None


@bp.get("/coffre")
def index():
    return exiger_profil() or page_coffre()


@bp.post("/coffre/deposer")
def deposer():
    if (redirection := exiger_profil()) is not None:
        return redirection
    envoi = request.files.get("fichier")
    if envoi is None or not envoi.filename:
        return page_coffre("Choisis un fichier à déposer.", 400)
    contenu = envoi.read(TAILLE_MAX + 1)
    nom = nettoyer_nom(envoi.filename)
    try:
        _, type_mime = valider_fichier(nom, contenu)
    except FichierRefuse as refus:
        return page_coffre(str(refus), 400)
    stockage().deposer_fichier(session["id_utilisateur"], nom, contenu, type_mime)
    return redirect(url_for("coffre.index"))


@bp.get("/coffre/fichier/<identifiant>")
def telecharger(identifiant):
    if (redirection := exiger_profil()) is not None:
        return redirection
    fichier = stockage().lire_fichier(session["id_utilisateur"], identifiant)
    if fichier is None:
        abort(404)
    reponse = send_file(
        io.BytesIO(fichier["contenu"]),
        mimetype=fichier["type"],
        as_attachment=True,
        download_name=fichier["nom"],
    )
    return en_tetes_prives(reponse)


@bp.post("/coffre/fichier/<identifiant>/partager")
def partager(identifiant):
    if (redirection := exiger_profil()) is not None:
        return redirection
    id_utilisateur = session["id_utilisateur"]
    lien = stockage().generer_lien_partage(id_utilisateur, identifiant)
    if lien is None:
        abort(404)
    url = lien["url"]
    if lien["mode"] == "interne":
        jeton = current_app.extensions["signataire"].signer(id_utilisateur, identifiant)
        url = url_for("partage.lire", jeton=jeton, _external=True)
    session["dernier_lien"] = {
        "identifiant": identifiant,
        "nom": lien["nom"],
        "url": url,
        "expire": date_lisible(lien["expire_le"]),
        "mode": lien["mode"],
    }
    return redirect(url_for("coffre.index") + "#lien-partage")


@bp.post("/coffre/fichier/<identifiant>/supprimer")
def supprimer(identifiant):
    if (redirection := exiger_profil()) is not None:
        return redirection
    if not stockage().supprimer_fichier(session["id_utilisateur"], identifiant):
        abort(404)
    return redirect(url_for("coffre.index"))


def trop_volumineux(_erreur):
    """Envoi arrêté par MAX_CONTENT_LENGTH : message clair au lieu d'une erreur 413 brute."""
    if request.path.startswith("/coffre") and session.get("id_utilisateur") and profil_courant():
        return page_coffre(f"Le fichier dépasse {taille_lisible(TAILLE_MAX)}.", 413)
    return "Fichier trop volumineux.", 413

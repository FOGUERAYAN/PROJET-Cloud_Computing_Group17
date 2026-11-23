"""Création du profil en 5 questions, puis calcul et enregistrement des étapes."""

import uuid
from datetime import UTC, date, datetime

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app.services.planning import calculer_etapes

bp = Blueprint("profil", __name__)

STATUTS = {"etudiant": "Étudiant", "salarie": "Salarié", "refugie": "Réfugié"}
INTERETS = {
    "sport": "Sport",
    "culture": "Culture",
    "cuisine": "Cuisine",
    "benevolat": "Bénévolat",
    "langues": "Échanges de langues",
    "numerique": "Numérique",
}


def valider(formulaire) -> tuple[dict, list[str]]:
    """Vérifie les réponses. Retourne le profil nettoyé et la liste des erreurs."""
    erreurs = []
    pseudo = formulaire.get("pseudo", "").strip()[:40]
    statut = formulaire.get("statut", "")
    ville = formulaire.get("ville", "").strip()[:80]
    langue = formulaire.get("langue", "").strip()[:40]
    interets = [i for i in formulaire.getlist("interets") if i in INTERETS]

    if statut not in STATUTS:
        erreurs.append("Choisissez un statut.")
    if not ville:
        erreurs.append("Indiquez votre ville.")
    if not langue:
        erreurs.append("Indiquez votre langue maternelle.")
    try:
        date_arrivee = date.fromisoformat(formulaire.get("date_arrivee", ""))
    except ValueError:
        date_arrivee = None
        erreurs.append("Indiquez une date d'arrivée valide.")

    profil = {
        "pseudo": pseudo,
        "statut": statut,
        "ville": ville,
        "date_arrivee": date_arrivee.isoformat() if date_arrivee else "",
        "langue": langue,
        "interets": ",".join(interets),
    }
    return profil, erreurs


@bp.get("/profil")
def formulaire():
    return render_template("profil.html", statuts=STATUTS, interets=INTERETS, valeurs={}, erreurs=[])


@bp.post("/profil")
def creer():
    profil, erreurs = valider(request.form)
    if erreurs:
        valeurs = {**profil, "interets": request.form.getlist("interets")}
        return (
            render_template(
                "profil.html", statuts=STATUTS, interets=INTERETS, valeurs=valeurs, erreurs=erreurs
            ),
            400,
        )

    id_utilisateur = str(uuid.uuid4())
    profil["cree_le"] = datetime.now(UTC).isoformat(timespec="seconds")

    stockage = current_app.extensions["stockage"]
    catalogue = current_app.extensions["catalogue"]
    etapes = calculer_etapes(catalogue, profil["statut"], date.fromisoformat(profil["date_arrivee"]))
    for etape in etapes:
        etape["date_limite"] = etape["date_limite"].isoformat()

    stockage.enregistrer_profil(id_utilisateur, profil)
    stockage.enregistrer_etapes(id_utilisateur, etapes)

    session["id_utilisateur"] = id_utilisateur
    return redirect(url_for("planning.index"))

"""Profil : création en 5 questions, page Mon profil, modification et suppression des données."""

import uuid
from datetime import UTC, date, datetime

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.routes.commun import majuscule_initiale, profil_courant
from app.services.planning import calculer_etapes
from app.services.suivi import liste_badges, recalculer, resume_recalcul

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
    ville = majuscule_initiale(formulaire.get("ville", ""))[:80]
    langue = majuscule_initiale(formulaire.get("langue", ""))[:40]
    interets = [i for i in formulaire.getlist("interets") if i in INTERETS]

    if statut not in STATUTS:
        erreurs.append("Choisis un statut.")
    if not ville:
        erreurs.append("Indique ta ville.")
    if not langue:
        erreurs.append("Indique ta langue maternelle.")
    try:
        date_arrivee = date.fromisoformat(formulaire.get("date_arrivee", ""))
    except ValueError:
        date_arrivee = None
        erreurs.append("Indique une date d'arrivée valide.")

    profil = {
        "pseudo": pseudo,
        "statut": statut,
        "ville": ville,
        "date_arrivee": date_arrivee.isoformat() if date_arrivee else "",
        "langue": langue,
        "interets": ",".join(interets),
    }
    return profil, erreurs


def stockage():
    return current_app.extensions["stockage"]


def formulaire_profil(valeurs, erreurs, action, titre, code=200):
    return (
        render_template(
            "profil_formulaire.html",
            statuts=STATUTS,
            interets=INTERETS,
            valeurs=valeurs,
            erreurs=erreurs,
            action=action,
            titre=titre,
        ),
        code,
    )


def valeurs_du_formulaire(profil):
    return {**profil, "interets": request.form.getlist("interets")}


@bp.get("/profil")
def formulaire():
    """Mon profil si un profil existe, sinon le formulaire de création."""
    profil = profil_courant()
    if profil is None:
        return formulaire_profil({}, [], url_for("profil.creer"), "Créer mon profil")

    etapes = stockage().lister_etapes(session["id_utilisateur"])
    return render_template(
        "profil.html",
        profil=profil,
        statut=STATUTS.get(profil["statut"], profil["statut"]),
        interets=[INTERETS[i] for i in (profil.get("interets") or "").split(",") if i in INTERETS],
        date_arrivee=date.fromisoformat(profil["date_arrivee"]).strftime("%d/%m/%Y"),
        badges=liste_badges(etapes),
    )


@bp.post("/profil")
def creer():
    profil, erreurs = valider(request.form)
    if erreurs:
        return formulaire_profil(
            valeurs_du_formulaire(profil), erreurs, url_for("profil.creer"), "Créer mon profil", 400
        )

    id_utilisateur = str(uuid.uuid4())
    profil["cree_le"] = datetime.now(UTC).isoformat(timespec="seconds")

    catalogue = current_app.extensions["catalogue"]
    etapes = calculer_etapes(catalogue, profil["statut"], date.fromisoformat(profil["date_arrivee"]))
    for etape in etapes:
        etape["date_limite"] = etape["date_limite"].isoformat()

    stockage().enregistrer_profil(id_utilisateur, profil)
    stockage().enregistrer_etapes(id_utilisateur, etapes)

    session["id_utilisateur"] = id_utilisateur
    return redirect(url_for("planning.index"))


@bp.get("/profil/modifier")
def modifier():
    profil = profil_courant()
    if profil is None:
        return redirect(url_for("profil.formulaire"))
    valeurs = {**profil, "interets": (profil.get("interets") or "").split(",")}
    return formulaire_profil(valeurs, [], url_for("profil.verifier"), "Modifier mes réponses")


@bp.post("/profil/modifier")
def verifier():
    """Affiche l'effet des nouvelles réponses sur le planning avant de les enregistrer."""
    if profil_courant() is None:
        return redirect(url_for("profil.formulaire"))
    nouveau, erreurs = valider(request.form)
    if erreurs:
        return formulaire_profil(
            valeurs_du_formulaire(nouveau), erreurs, url_for("profil.verifier"), "Modifier mes réponses", 400
        )
    existantes = stockage().lister_etapes(session["id_utilisateur"])
    a_ecrire, a_supprimer = recalculer(
        current_app.extensions["catalogue"],
        existantes,
        nouveau["statut"],
        date.fromisoformat(nouveau["date_arrivee"]),
    )
    return render_template(
        "profil_confirmer.html",
        nouveau=nouveau,
        interets=nouveau["interets"].split(",") if nouveau["interets"] else [],
        resume=resume_recalcul(existantes, a_ecrire, a_supprimer),
    )


@bp.post("/profil/modifier/confirmer")
def confirmer():
    profil = profil_courant()
    if profil is None:
        return redirect(url_for("profil.formulaire"))
    nouveau, erreurs = valider(request.form)
    if erreurs:
        return formulaire_profil(
            valeurs_du_formulaire(nouveau), erreurs, url_for("profil.verifier"), "Modifier mes réponses", 400
        )

    id_utilisateur = session["id_utilisateur"]
    a_ecrire, a_supprimer = recalculer(
        current_app.extensions["catalogue"],
        stockage().lister_etapes(id_utilisateur),
        nouveau["statut"],
        date.fromisoformat(nouveau["date_arrivee"]),
    )
    stockage().enregistrer_profil(id_utilisateur, {**nouveau, "cree_le": profil.get("cree_le", "")})
    stockage().enregistrer_etapes(id_utilisateur, a_ecrire)
    for code in a_supprimer:
        stockage().supprimer_etape(id_utilisateur, code)

    flash("Ton profil est à jour et ton planning a été recalculé.", "succes")
    return redirect(url_for("planning.index"))


@bp.get("/profil/supprimer")
def supprimer_confirmation():
    if profil_courant() is None:
        return redirect(url_for("profil.formulaire"))
    return render_template("profil_supprimer.html")


@bp.post("/profil/supprimer")
def supprimer():
    id_utilisateur = session.get("id_utilisateur")
    if id_utilisateur:
        stockage().supprimer_utilisateur(id_utilisateur)
    session.clear()
    flash("Tes données ont été supprimées.", "succes")
    return redirect(url_for("accueil.index"))

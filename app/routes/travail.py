"""Module Travailler : saisie des heures et jauge des 964 heures."""

import re
from datetime import date

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

from app.services.travail import (
    PLAFOND_HEURES,
    heures_restantes,
    mois_de_la_periode,
    niveau_jauge,
    periode_en_cours,
    pourcentage,
    total_periode,
)

bp = Blueprint("travail", __name__)

MOIS_VALIDE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
HEURES_MAX_PAR_MOIS = 300
LIEN_F2713 = "https://www.service-public.gouv.fr/particuliers/vosdroits/F2713"


def aujourd_hui() -> date:
    return date.today()


def nombre(valeur: float) -> str:
    """Affiche 12 ou 12,5 selon le cas."""
    return f"{valeur:g}".replace(".", ",")


NOMS_MOIS = (
    "janvier",
    "février",
    "mars",
    "avril",
    "mai",
    "juin",
    "juillet",
    "août",
    "septembre",
    "octobre",
    "novembre",
    "décembre",
)


def libelle_mois(mois: str) -> str:
    """2026-11 devient novembre 2026."""
    annee, numero = mois.split("-")
    return f"{NOMS_MOIS[int(numero) - 1]} {annee}"


def date_de_validation(stockage, id_utilisateur: str, profil: dict) -> tuple[date, bool]:
    """Date de validation du visa (étape cochée), ou date d'arrivée à défaut.

    Le booléen indique si la date de validation est connue.
    """
    visa = stockage.lire_etape(id_utilisateur, "visa")
    if visa and visa.get("statut") == "fait" and visa.get("fait_le"):
        return date.fromisoformat(visa["fait_le"]), True
    return date.fromisoformat(profil["date_arrivee"]), False


def valider_saisie(formulaire) -> tuple[str, float | None, list[str]]:
    erreurs = []
    mois = formulaire.get("mois", "")
    if not MOIS_VALIDE.match(mois):
        erreurs.append("Choisis un mois.")
    try:
        heures = float(formulaire.get("heures", "").replace(",", "."))
    except ValueError:
        heures = None
    if heures is None or not 0 <= heures <= HEURES_MAX_PAR_MOIS:
        erreurs.append(f"Indique un nombre d'heures entre 0 et {HEURES_MAX_PAR_MOIS}.")
        heures = None
    return mois, heures, erreurs


def contexte_jauge(stockage, id_utilisateur: str, profil: dict) -> dict:
    jour = aujourd_hui()
    validation, connue = date_de_validation(stockage, id_utilisateur, profil)
    debut, fin = periode_en_cours(validation, jour)
    heures = stockage.lister_heures(id_utilisateur)
    total = total_periode(heures, debut)
    mois_periode = mois_de_la_periode(debut)
    return {
        "validation_connue": connue,
        "debut": debut.strftime("%d/%m/%Y"),
        "fin": fin.strftime("%d/%m/%Y"),
        "total": nombre(total),
        "restantes": nombre(heures_restantes(total)),
        "depassement": nombre(total - PLAFOND_HEURES) if total > PLAFOND_HEURES else "",
        "niveau": niveau_jauge(total),
        "pourcentage": pourcentage(total),
        "largeur": min(pourcentage(total), 100),
        "plafond": PLAFOND_HEURES,
        "saisies": [(libelle_mois(m), nombre(heures[m])) for m in mois_periode if m in heures],
        "mois_defaut": jour.strftime("%Y-%m"),
    }


def page(profil, erreurs=None, code=200):
    stockage = current_app.extensions["stockage"]
    jauge = None
    if profil["statut"] == "etudiant":
        jauge = contexte_jauge(stockage, session["id_utilisateur"], profil)
    contexte = {"profil": profil, "jauge": jauge, "erreurs": erreurs or [], "lien_f2713": LIEN_F2713}
    return render_template("travailler.html", **contexte), code


def profil_courant():
    id_utilisateur = session.get("id_utilisateur")
    if not id_utilisateur:
        return None
    return current_app.extensions["stockage"].lire_profil(id_utilisateur)


@bp.get("/travailler")
def index():
    profil = profil_courant()
    if profil is None:
        return redirect(url_for("profil.formulaire"))
    return page(profil)


@bp.post("/travailler")
def saisir():
    profil = profil_courant()
    if profil is None:
        return redirect(url_for("profil.formulaire"))
    mois, heures, erreurs = valider_saisie(request.form)
    if erreurs:
        return page(profil, erreurs, 400)
    current_app.extensions["stockage"].enregistrer_heures(session["id_utilisateur"], mois, heures)
    return redirect(url_for("travail.index"))

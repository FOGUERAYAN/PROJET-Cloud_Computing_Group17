"""Modules Lille : lieux utiles, se loger, découvrir."""

from flask import Blueprint, abort, current_app, render_template, request

from app.services.lieux import FILTRES_DECOUVRIR, filtrer_decouvrir, par_categorie, trouver

bp = Blueprint("lille", __name__, url_prefix="/lille")


def lieux():
    return current_app.extensions["lieux"]


@bp.get("/")
def index():
    return render_template("lille.html")


@bp.get("/lieux-utiles")
def lieux_utiles():
    return render_template("lieux_utiles.html", lieux=par_categorie(lieux(), "utile"))


@bp.get("/se-loger")
def se_loger():
    return render_template("se_loger.html", sites=par_categorie(lieux(), "logement"))


@bp.get("/decouvrir")
def decouvrir():
    filtre = request.args.get("filtre")
    if filtre not in FILTRES_DECOUVRIR:
        filtre = None
    return render_template(
        "decouvrir.html",
        lieux=filtrer_decouvrir(lieux(), filtre),
        filtres={code: libelle for code, (libelle, _) in FILTRES_DECOUVRIR.items()},
        filtre_actif=filtre,
    )


@bp.get("/decouvrir/<identifiant>")
def detail(identifiant):
    lieu = trouver(lieux(), identifiant)
    if lieu is None or lieu["categorie"] not in ("decouverte", "manger"):
        abort(404)
    return render_template("lieu_detail.html", lieu=lieu)

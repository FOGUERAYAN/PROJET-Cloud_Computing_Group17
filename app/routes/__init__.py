"""Enregistrement des blueprints et des aides de templates."""

from app.routes.accueil import bp as accueil_bp
from app.routes.coffre import bp as coffre_bp
from app.routes.health import bp as health_bp
from app.routes.lille import bp as lille_bp
from app.routes.medias import bp as medias_bp
from app.routes.planning import bp as planning_bp
from app.routes.profil import bp as profil_bp
from app.routes.solidarite import bp as solidarite_bp
from app.services.lieux import ICONES, premiere_phrase

BLUEPRINTS = (accueil_bp, profil_bp, planning_bp, lille_bp, medias_bp, coffre_bp, solidarite_bp, health_bp)


def enregistrer_routes(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint)
    app.jinja_env.globals["icones_categories"] = ICONES
    app.jinja_env.filters["premiere_phrase"] = premiere_phrase

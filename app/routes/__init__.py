"""Enregistrement des blueprints."""

from app.routes.accueil import bp as accueil_bp
from app.routes.coffre import bp as coffre_bp
from app.routes.health import bp as health_bp
from app.routes.planning import bp as planning_bp
from app.routes.profil import bp as profil_bp
from app.routes.solidarite import bp as solidarite_bp


def enregistrer_routes(app):
    for blueprint in (accueil_bp, profil_bp, planning_bp, coffre_bp, solidarite_bp, health_bp):
        app.register_blueprint(blueprint)

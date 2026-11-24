"""Point d'entrée de l'application Cap90."""

from flask import Flask

from app.config import Config
from app.routes import enregistrer_routes
from app.services.entraide import charger_entraide
from app.services.liens import charger_liens
from app.services.lieux import charger_lieux
from app.services.modules import charger_modules
from app.services.planning import charger_catalogue
from app.services.referentiels import charger_communes, charger_langues
from app.services.storage import creer_stockage


def create_app(config=None, stockage=None):
    """Crée l'application Flask.

    Les tests passent leur propre configuration et un stockage en mémoire.
    En production, tout vient des variables d'environnement.
    """
    app = Flask(__name__)
    config = config or Config()
    app.config.from_object(config)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

    if stockage is None:
        stockage = creer_stockage(config)
    stockage.initialiser()
    app.extensions["stockage"] = stockage
    app.extensions["catalogue"] = charger_catalogue()
    app.extensions["lieux"] = charger_lieux()
    app.extensions["entraide"] = charger_entraide()
    app.extensions["liens"] = charger_liens()
    app.extensions["modules"] = charger_modules()
    app.extensions["langues"] = charger_langues()
    app.extensions["communes"] = charger_communes()

    enregistrer_routes(app)
    return app

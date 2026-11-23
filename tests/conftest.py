import pytest

from app import create_app
from app.config import Config
from app.services.storage import StockageMemoire


@pytest.fixture
def stockage():
    return StockageMemoire()


@pytest.fixture
def app(stockage):
    # Clé de test générée pour les tests uniquement, aucun secret réel.
    config = Config({"SECRET_KEY": "cle-de-test", "STORAGE_MODE": "memoire"})
    config.TESTING = True
    return create_app(config=config, stockage=stockage)


@pytest.fixture
def client(app):
    return app.test_client()

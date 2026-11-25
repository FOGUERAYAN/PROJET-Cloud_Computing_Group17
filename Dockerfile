# Version exacte (Python 3.12.16, Debian 13 trixie) pour des constructions reproductibles.
# Pour monter de version : changer ce tag, reconstruire, relancer les tests.
FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Utilisateur sans privilèges pour exécuter l'application.
RUN useradd --create-home --uid 1000 cap90

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app

USER cap90

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"

CMD ["gunicorn", "-b", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-", "app:create_app()"]

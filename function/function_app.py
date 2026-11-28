"""Azure Function de Cap90 (modèle Python v2) : tâches nocturnes.

Chaque nuit à 03:00 UTC : purge des annonces expirées, puis rappels des démarches proches ou en retard.
Si une tâche échoue, l'erreur est journalisée et l'autre tâche s'exécute quand même.
"""

import logging
from datetime import UTC, datetime

import azure.functions as func
from rappels import choisir_canal
from stockage import StockageFunction
from taches import executer_purge, executer_rappels

# NCRONTAB (secondes minutes heures jour mois jour-semaine), toujours interprété en UTC sur Linux.
PLANNING_NOCTURNE = "0 0 3 * * *"

app = func.FunctionApp()
journal = logging.getLogger("cap90.function")


def executer_taches(stockage, canal, maintenant: datetime) -> dict:
    """Exécute les deux tâches de façon indépendante et retourne un bilan."""
    bilan = {"purge": None, "rappels": None}
    try:
        bilan["purge"] = executer_purge(stockage, maintenant)
    except Exception:
        journal.exception("La purge des annonces a échoué.")
    try:
        bilan["rappels"] = executer_rappels(stockage, maintenant.date(), canal)
    except Exception:
        journal.exception("Le calcul des rappels a échoué.")
    return bilan


@app.timer_trigger(schedule=PLANNING_NOCTURNE, arg_name="minuteur", run_on_startup=False, use_monitor=True)
def taches_nocturnes(minuteur: func.TimerRequest) -> None:
    if minuteur.past_due:
        journal.warning("Exécution en retard sur le planning prévu.")
    executer_taches(StockageFunction.depuis_environnement(), choisir_canal(), datetime.now(UTC))

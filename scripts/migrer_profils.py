"""Migre les profils enregistrés avant le passage aux listes fermées.

- La langue en texte libre devient un code ISO 639-1 si elle correspond à un nom de la liste,
  sinon "autre", avec le texte gardé dans langue_precision.
- La ville en texte libre devient un code de commune de la métropole, sinon "autre".

Utilisation locale (Azurite lancé avec docker compose) :
    python scripts/migrer_profils.py --dry-run
    python scripts/migrer_profils.py
"""

import argparse
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from app.services.referentiels import (  # noqa: E402
    charger_communes,
    charger_langues,
    migrer_commune,
    migrer_langue,
)
from app.services.storage import creer_stockage  # noqa: E402
from scripts.charger_medias import lire_config  # noqa: E402


def changements(profil: dict, langues: list, communes: list) -> dict:
    """Champs à modifier pour un profil (dictionnaire vide s'il est déjà migré)."""
    nouveau = {}
    codes = {langue["code"] for langue in langues}
    if profil.get("langue") not in codes:  # langue déjà codée : on garde aussi sa précision
        code, precision = migrer_langue(langues, profil.get("langue", ""))
        nouveau.update(langue=code, langue_precision=precision)
    elif "langue_precision" not in profil:
        nouveau["langue_precision"] = ""
    commune = migrer_commune(communes, profil.get("ville", ""))
    if commune != profil.get("ville"):
        nouveau["ville"] = commune
    return nouveau


def migrer(stockage, dry_run: bool) -> list[tuple[str, dict]]:
    langues, communes = charger_langues(), charger_communes()
    resultat = []
    for profil in stockage.lister_profils():
        nouveau = changements(profil, langues, communes)
        if not nouveau:
            continue
        resultat.append((profil["RowKey"], nouveau))
        if not dry_run:
            stockage.enregistrer_profil(profil["RowKey"], nouveau)
    return resultat


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Migration des profils vers les listes fermées.")
    parser.add_argument("--dry-run", action="store_true", help="affiche les changements sans les enregistrer")
    args = parser.parse_args()

    stockage = creer_stockage(lire_config())
    stockage.initialiser()
    resultat = migrer(stockage, args.dry_run)
    for identifiant, nouveau in resultat:
        print(f"{identifiant[:8]} : {nouveau}")
    print(f"{len(resultat)} profil(s) {'à migrer' if args.dry_run else 'migré(s)'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

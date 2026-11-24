"""Listes fermées du profil : langues (codes ISO 639-1) et communes de la Métropole Européenne de Lille."""

import json
import unicodedata
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent.parent / "data"
LANGUE_AUTRE = "autre"
COMMUNE_AUTRE = "autre"
COMMUNE_DEFAUT = "lille"


class ReferentielInvalide(ValueError):
    """Erreur levée quand langues.json ou communes.json ne respecte pas le format attendu."""


def _charger(nom: str) -> list:
    with open(DOSSIER / nom, encoding="utf-8") as fichier:
        return json.load(fichier)


def valider_langues(langues: list) -> list:
    codes = [langue.get("code", "") for langue in langues]
    if len(set(codes)) != len(codes):
        raise ReferentielInvalide("langues.json : code en double.")
    for langue in langues:
        code = langue.get("code", "")
        if code != LANGUE_AUTRE and (len(code) != 2 or not code.isalpha() or not code.islower()):
            raise ReferentielInvalide(f"langues.json : {code!r} n'est pas un code ISO 639-1.")
        if not langue.get("libelle") or langue.get("sens") not in ("ltr", "rtl"):
            raise ReferentielInvalide(f"langues.json : libellé ou sens manquant pour {code}.")
    if LANGUE_AUTRE not in codes:
        raise ReferentielInvalide("langues.json : l'entrée autre est obligatoire.")
    return langues


def valider_communes(communes: list) -> list:
    codes = [commune.get("code", "") for commune in communes]
    if len(set(codes)) != len(codes) or not all(c.get("code") and c.get("nom") for c in communes):
        raise ReferentielInvalide("communes.json : code en double ou nom manquant.")
    if COMMUNE_DEFAUT not in codes or COMMUNE_AUTRE not in codes:
        raise ReferentielInvalide("communes.json : lille et autre sont obligatoires.")
    return communes


def charger_langues() -> list:
    return valider_langues(_charger("langues.json"))


def charger_communes() -> list:
    return valider_communes(_charger("communes.json"))


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, sans ligature, avec des espaces à la place des tirets et apostrophes."""
    texte = (texte or "").strip().lower().replace("œ", "oe").replace("æ", "ae")
    texte = "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")
    for signe in ("-", "'", "’"):
        texte = texte.replace(signe, " ")
    return " ".join(texte.split())


def nom_langue(langues: list, code: str, precision: str = "") -> str:
    """Libellé affiché pour une langue enregistrée."""
    if code == LANGUE_AUTRE:
        return precision or "Autre langue"
    trouvee = next((langue for langue in langues if langue["code"] == code), None)
    return trouvee["libelle"] if trouvee else code


def nom_commune(communes: list, code: str) -> str:
    trouvee = next((commune for commune in communes if commune["code"] == code), None)
    return trouvee["nom"] if trouvee else code


def migrer_langue(langues: list, texte: str) -> tuple[str, str]:
    """Ancienne langue en texte libre vers (code, précision)."""
    if any(langue["code"] == texte for langue in langues):
        return texte, ""  # déjà migrée
    cible = normaliser(texte)
    for langue in langues:
        noms = {normaliser(langue["libelle"]), normaliser(langue["nom_local"])} - {""}
        if langue["code"] != LANGUE_AUTRE and cible in noms:
            return langue["code"], ""
    return LANGUE_AUTRE, (texte or "").strip()


def migrer_commune(communes: list, texte: str) -> str:
    """Ancienne ville en texte libre vers un code de commune."""
    if any(commune["code"] == texte for commune in communes):
        return texte
    cible = normaliser(texte)
    for commune in communes:
        if commune["code"] != COMMUNE_AUTRE and normaliser(commune["nom"]) == cible:
            return commune["code"]
    return COMMUNE_AUTRE

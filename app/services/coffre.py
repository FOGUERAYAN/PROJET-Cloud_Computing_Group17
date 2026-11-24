"""Coffre-fort : contrôle des fichiers déposés et liens de partage signés (mode local).

Sur Azure, le lien de partage est une User Delegation SAS (voir services/storage.py).
Avec Azurite ou le stockage en mémoire, qui ne gèrent pas la délégation, le lien pointe vers
la route /partage/<jeton> de l'application : le jeton est signé avec SECRET_KEY et expire au bout de 24 h.
"""

import re
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TAILLE_MAX = 10 * 1024 * 1024  # 10 Mo
DUREE_PARTAGE_HEURES = 24
FUSEAU = ZoneInfo("Europe/Paris")

# Extension acceptée : (type MIME, signature attendue au début du fichier).
TYPES_ACCEPTES = {
    "pdf": ("application/pdf", b"%PDF-"),
    "jpg": ("image/jpeg", b"\xff\xd8\xff"),
    "jpeg": ("image/jpeg", b"\xff\xd8\xff"),
    "png": ("image/png", b"\x89PNG\r\n\x1a\n"),
}
LIBELLES_TYPES = {"application/pdf": "PDF", "image/jpeg": "JPG", "image/png": "PNG"}

# Identifiant interne d'un fichier : 32 caractères hexadécimaux et l'extension.
IDENTIFIANT_VALIDE = re.compile(r"^[0-9a-f]{32}\.(pdf|jpg|png)$")


class FichierRefuse(ValueError):
    """Fichier refusé au dépôt. Le message est affiché tel quel à l'utilisateur."""


class LienInvalide(ValueError):
    """Jeton de partage modifié, mal formé ou visant un fichier inconnu."""


class LienExpire(ValueError):
    """Jeton de partage authentique mais plus valable."""


def extension(nom: str) -> str:
    return nom.rsplit(".", 1)[-1].lower() if "." in nom else ""


def valider_fichier(nom: str, contenu: bytes) -> tuple[str, str]:
    """Vérifie l'extension, la signature réelle et la taille. Retourne (extension, type MIME)."""
    ext = extension(nom)
    if ext not in TYPES_ACCEPTES:
        raise FichierRefuse("Seuls les fichiers PDF, JPG et PNG sont acceptés.")
    if not contenu:
        raise FichierRefuse("Le fichier est vide.")
    if len(contenu) > TAILLE_MAX:
        raise FichierRefuse("Le fichier dépasse 10 Mo.")
    type_mime, signature = TYPES_ACCEPTES[ext]
    if not contenu.startswith(signature):
        raise FichierRefuse("Le contenu du fichier ne correspond pas à un PDF, un JPG ou un PNG.")
    return ("jpg" if ext == "jpeg" else ext), type_mime


def nettoyer_nom(nom: str) -> str:
    """Nom d'origine affichable : sans chemin, sans caractère de contrôle, 120 caractères au plus."""
    nom = (nom or "").replace("\\", "/").rsplit("/", 1)[-1]
    nom = "".join(c for c in unicodedata.normalize("NFC", nom) if unicodedata.category(c)[0] != "C")
    nom = " ".join(nom.split()).strip(". ")
    if len(nom) > 120:
        base, _, ext = nom.rpartition(".")
        nom = f"{base[: 115 - len(ext)]}.{ext}" if base else nom[:120]
    return nom or "document"


def taille_lisible(octets: int) -> str:
    if octets < 1024:
        return f"{octets} o"
    if octets < 1024 * 1024:
        return f"{max(1, round(octets / 1024))} Ko"
    mega = f"{octets / (1024 * 1024):.1f}".removesuffix(".0")
    return f"{mega} Mo".replace(".", ",")


def date_lisible(moment: datetime) -> str:
    """Date et heure de Paris, par exemple 26/11/2026 à 10 h 05."""
    local = moment.astimezone(FUSEAU)
    return f"{local:%d/%m/%Y} à {local.hour} h {local:%M}"


def libelle_type(type_mime: str) -> str:
    return LIBELLES_TYPES.get(type_mime, type_mime)


class SignataireLiens:
    """Jetons de partage signés avec SECRET_KEY, valables 24 h (mode local)."""

    SEL = "cap90-coffre-partage"

    def __init__(self, secret_key: str, duree_heures: int = DUREE_PARTAGE_HEURES):
        if not secret_key:
            raise ValueError("SECRET_KEY est obligatoire pour signer les liens de partage.")
        self.serialiseur = URLSafeTimedSerializer(secret_key, salt=self.SEL)
        self.duree = timedelta(hours=duree_heures)

    def signer(self, id_utilisateur: str, identifiant: str) -> str:
        return self.serialiseur.dumps({"u": id_utilisateur, "f": identifiant})

    def verifier(self, jeton: str) -> tuple[str, str]:
        """Retourne (id utilisateur, identifiant du fichier) ou lève LienExpire ou LienInvalide."""
        try:
            donnees = self.serialiseur.loads(jeton, max_age=int(self.duree.total_seconds()))
        except SignatureExpired as erreur:
            raise LienExpire("Ce lien de partage a expiré.") from erreur
        except BadSignature as erreur:
            raise LienInvalide("Ce lien de partage n'est pas valide.") from erreur
        if not isinstance(donnees, dict) or not IDENTIFIANT_VALIDE.match(str(donnees.get("f", ""))):
            raise LienInvalide("Ce lien de partage n'est pas valide.")
        return str(donnees.get("u", "")), donnees["f"]

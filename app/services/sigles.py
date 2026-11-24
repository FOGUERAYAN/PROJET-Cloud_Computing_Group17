"""Monogrammes (sigles) affichés à la place des logos officiels, qui sont des marques protégées."""

FAMILLES = ("demarche", "entraide", "logement")


def erreur_sigle(sigle, obligatoire: bool) -> str | None:
    """Message d'erreur si le sigle est invalide, sinon None.

    Un sigle fait 2 à 5 caractères (5 pour "Crous").
    """
    if not isinstance(sigle, str):
        return "le sigle doit être un texte"
    sigle = sigle.strip()
    if not sigle:
        return "le sigle est obligatoire" if obligatoire else None
    if not 2 <= len(sigle) <= 5:
        return "le sigle doit faire 2 à 5 caractères"
    return None


def famille_du_theme(theme: str) -> str:
    """Couleur de la pastille : logement, entraide, ou démarche pour tout le reste."""
    if theme == "logement":
        return "logement"
    if theme in ("entraide",):
        return "entraide"
    return "demarche"

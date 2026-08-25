"""Normalisation des numéros de téléphone au format international (+XX ...)."""
import phonenumbers

DEFAULT_REGION = "FR"  # indicatif présumé pour un numéro saisi sans "+"


def format_telephone(raw: str, region: str = DEFAULT_REGION) -> str:
    """Reformate un numéro en format international lisible (+33 6 06 06 06 06).

    Chaîne vide → chaîne vide (téléphone optionnel). Lève ValueError si le
    numéro fourni n'est pas vide mais n'est pas un numéro valide reconnu.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as e:
        raise ValueError(f"Numéro de téléphone invalide : {raw!r}") from e
    if not phonenumbers.is_valid_number(parsed):
        raise ValueError(f"Numéro de téléphone invalide : {raw!r}")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)

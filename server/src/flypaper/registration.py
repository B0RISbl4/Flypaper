from flydenity import Parser

REGISTRATION_PARSER = Parser()


def registration_country(registration: str) -> tuple[str, str]:
    try:
        parsed = REGISTRATION_PARSER.parse(registration.strip().upper()) if registration else None
    except (TypeError, ValueError):
        parsed = None
    if not isinstance(parsed, dict):
        return "", ""

    name = str(parsed.get("nation") or "").strip()
    iso2 = str(parsed.get("iso2") or "").strip().upper()
    if len(iso2) != 2 or not iso2.isascii() or not iso2.isalpha():
        iso2 = ""
    return name, iso2

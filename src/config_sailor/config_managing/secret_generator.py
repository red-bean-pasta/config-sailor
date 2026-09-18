import secrets


def generate(length: int) -> str:
    return secrets.token_urlsafe(length)
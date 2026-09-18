from fastapi.security import HTTPAuthorizationCredentials, HTTPBasicCredentials


def parse_bearer(creds: HTTPAuthorizationCredentials) -> tuple[str, str] | None:
    split = creds.credentials.rsplit('~', 1)
    if len(split) != 2:
        return None
    return tuple(split)


def parse_basic(creds: HTTPBasicCredentials) -> tuple[str, str] | None:
    return creds.username, creds.password
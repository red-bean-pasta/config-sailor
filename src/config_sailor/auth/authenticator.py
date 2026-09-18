from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from fastapi.security import HTTPBasicCredentials, HTTPAuthorizationCredentials

from config_sailor.auth.credential_handler import parse_bearer, parse_basic
from config_sailor.hash import hasher


# Explicitly commented out to avoid I/O operations and inconsistent timing
# logger = logging.getLogger(__name__)


class Method(StrEnum):
    BASIC = "basic"
    BEARER = "bearer"


@dataclass(slots=True, frozen=True)
class AuthOutput:
    result: str | Literal[False] | None
    message: str


async def auth_bearer(
        rules: dict[str, dict[Method, str]],
        creds: HTTPAuthorizationCredentials | None
) -> AuthOutput:
    if creds is None:
        await _dummy_verify()
        return _no_cred_result(Method.BEARER)

    parsed = parse_bearer(creds)
    if not parsed:
        await _dummy_verify()
        return AuthOutput(False, f"Failed to split received bearer")

    user, token = parsed
    return await _auth(rules, user, token, Method.BEARER)


async def auth_basic(
        rules: dict[str, dict[Method, str]],
        creds: HTTPBasicCredentials | None
) -> AuthOutput:
    if creds is None:
        await _dummy_verify()
        return _no_cred_result(Method.BASIC)

    user, password = parse_basic(creds)
    return await _auth(rules, user, password, Method.BASIC)


async def _auth(
        rules: dict[str, dict[Method, str]],
        user: str,
        cred: str,
        method: Method
) -> AuthOutput:
    methods = rules.get(user)
    if not methods:
        await _dummy_verify()
        return _no_user_result(user)
    hashed = methods.get(method)
    if not hashed:
        await _dummy_verify()
        return _no_method_result(user, method)

    result = await _verify_hash(cred, hashed)
    return _verify_result(user, method, result)


async def _verify_hash(cred: str, hashed: str) -> bool:
    return await hasher.verify_hash(cred, hashed)


async def _dummy_verify() -> None:
    await hasher.dummy_verify() # to avoid timing attack


def _no_cred_result(method: Method) -> AuthOutput:
    return AuthOutput(None, f"No {method} credential provided. Skipping...")


def _no_user_result(user: str) -> AuthOutput:
    return AuthOutput(False, f"No auth rule defined for user '{user}'")


def _no_method_result(user: str, method: Method) -> AuthOutput:
    return AuthOutput(False, f"No {method} rules defined for user '{user}'")


def _verify_result(user: str, method: Method, result: bool) -> AuthOutput:
    return AuthOutput(
        user if result else False,
        f"{'Correct' if result else 'Invalid'} {method} credential from user '{user}'",
    )
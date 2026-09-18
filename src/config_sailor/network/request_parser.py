import re
from dataclasses import dataclass

from fastapi import Request
from fastapi.security import HTTPBasicCredentials, HTTPAuthorizationCredentials, HTTPBasic, HTTPBearer
from packaging.version import Version, InvalidVersion


BASIC = HTTPBasic(auto_error=False)
BEARER = HTTPBearer(auto_error=False)

VERSION_REGEX = re.compile(r'\d+(?:\.\d+)+(?:[-._][a-zA-Z0-9]+)*')


@dataclass(slots=True, frozen=True)
class ParsedRequest:
    encryption_key: str | None
    agent: str | None
    version: str | None
    basic_creds: HTTPBasicCredentials
    bearer_creds: HTTPAuthorizationCredentials


async def parse(request: Request) -> ParsedRequest:
    agent_header = request.headers.get("User-Agent")
    agent, version = _normalize_agent_header(agent_header)

    key = request.query_params.get("key") or request.headers.get("Encryption-Key")
    agent = request.query_params.get("agent") or agent
    version = request.query_params.get("version") or version

    version = _normalize_version(version)

    basic_creds = await BASIC(request)
    bearer_creds = await BEARER(request)

    return ParsedRequest(
        encryption_key=key,
        agent=agent,
        version=version,
        basic_creds=basic_creds,
        bearer_creds=bearer_creds,
    )


def _normalize_agent_header(header: str | None) -> tuple[str | None, str | None]:
    if not header or not header.strip():
        return None, None

    first_token = header.strip().split()[0]
    if '/' in first_token:
        agent, _, version = first_token.partition('/')
        return agent or None, version or None

    agent = first_token
    version_match = VERSION_REGEX.search(header)
    version = version_match.group(0) if version_match else None
    return agent, version


def _normalize_version(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(Version(value))
    except InvalidVersion:
        extracted = re.search(r'\d+(?:\.\d+)*', value)
        if extracted:
            try:
                return str(Version(extracted[0]))
            except InvalidVersion:
                return None
        return None

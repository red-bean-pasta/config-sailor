import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Any, Callable, Literal

from fastapi.security import HTTPAuthorizationCredentials, HTTPBasicCredentials

from config_sailor.utils import file_operator
from config_sailor.auth import credential_handler, authenticator
from config_sailor.auth.authenticator import Method
from config_sailor.file_managers.file_data import FileData


logger = logging.getLogger(__name__)


class AuthManager:
    def __init__(
            self,
            auth_rules_path: str | Path,
            revoke_record_path: str | Path,
    ) -> None:
        self._auth_rules = AuthRules(auth_rules_path)
        self._revoke_record = RevokeRecord(revoke_record_path)

    def revoke(self, credential: str | Iterable[str]) -> None:
        self._revoke_record.revoke(credential)

    async def auth(
            self,
            bearer: HTTPAuthorizationCredentials | None,
            basic: HTTPBasicCredentials | None,
    ) -> str | None:
        bearer_result = await self._auth_rules.auth_bearer(bearer)
        basic_result = await self._auth_rules.auth_basic(basic)
        authed = self._combine_auth_results(bearer_result, basic_result)

        bearer_revoked = self._is_revoked(bearer, credential_handler.parse_bearer)
        basic_revoked = self._is_revoked(basic, credential_handler.parse_basic)
        revoked = bearer_revoked or basic_revoked

        success = authed and not revoked
        state = "Valid" if success else "Revoked" if revoked else "Invalid"
        logger.info("Auth attempt completed: Success: %s; Credential: %s", success, state)
        if not success:
            return None
        return authed

    def _is_revoked(
            self,
            credential,
            parser: Callable[[Any], tuple[str, str]]
    ) -> bool:
        if not credential:
            return False
        secret = parser(credential)[1]
        return self._revoke_record.check_if_revoked(secret)

    @staticmethod
    def _combine_auth_results(*results: str | Literal[False] | None) -> str | None:
        not_none = [r for r in results if r is not None]
        if not not_none: # If all None
            return None
        if not all(not_none): # Any False
            return None
        strs = {r for r in not_none if isinstance(r, str)}
        return strs.pop() if len(strs) == 1 else None


@dataclass()
class AuthRules(FileData):
    _rules: dict[str, dict[Method, str]] = field(init=False) # User-Method-hash

    def _load(self) -> None:
        super()._load()
        self._rules = json.loads(self._payload)

    def _get_rules(self) -> dict[str, dict[Method, str]]:
        self._reload_on_change()
        return self._rules

    async def auth_bearer(self, creds: HTTPAuthorizationCredentials | None) -> str | Literal[False] | None:
        output = await authenticator.auth_bearer(self._get_rules(), creds)
        logger.info(output.message)
        return output.result

    async def auth_basic(self, creds: HTTPBasicCredentials | None) -> str | Literal[False] | None:
        output = await authenticator.auth_basic(self._get_rules(), creds)
        logger.info(output.message)
        return output.result


@dataclass(slots=True)
class RevokeRecord:
    path: Path
    _credentials: set[str] = field(init=False) # in hash

    def __post_init__(self) -> None:
        text = file_operator.read_text(self.path)
        self._credentials = {l.strip() for l in text.splitlines()} if text else set()

    def check_if_revoked(self, value: str) -> bool:
        return value in self._credentials

    def revoke(self, credential: str | Iterable[str]) -> None:
        len_before = len(self._credentials)
        self._credentials.update((credential,) if isinstance(credential, str) else credential)
        if len(self._credentials) != len_before:
            self._save()

    def _save(self) -> None:
        content = "\n".join(sorted(self._credentials))
        if content:
            content += "\n"
        file_operator.save(
            content.encode(encoding="utf-8"),
            self.path
        )
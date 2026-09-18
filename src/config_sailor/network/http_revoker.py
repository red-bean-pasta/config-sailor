import logging
from typing import Iterable, AsyncGenerator

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from config_sailor.auth import credential_handler
from config_sailor.file_managers.config_manager import ConfigManager
from config_sailor.network import request_parser
from config_sailor.file_managers.auth_manager import AuthManager, AuthRules
from config_sailor.utils import http_helper


logger = logging.getLogger(__name__)


class HttpAuthRevokeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.scheme == "https":
            return await call_next(request)

        if request.app.state.unsafe_mode:
            return await call_next(request)

        logger.warning("Received request sent in plaintext HTTP")

        auth_manager: AuthManager = request.app.state.auth_manager
        revocable = [c async for c in _validate_request_creds(request)]
        logger.warning("Revoking exposed credentials...")
        auth_manager.revoke(revocable)

        if await _validate_encryption_key(request):
            logger.warning("Encryption key LEAKED. Consider rotating it as soon as possible")

        return http_helper.get_uniform_reject()


async def _validate_request_creds(request: Request) -> AsyncGenerator[str, None]:
    parsed = await request_parser.parse(request)
    rules: AuthRules = request.app.state.auth_manager._auth_rules
    if await rules.auth_basic(parsed.basic_creds):
        yield credential_handler.parse_basic(parsed.basic_creds)[1]
    if await rules.auth_bearer(parsed.bearer_creds):
        yield credential_handler.parse_bearer(parsed.bearer_creds)[1]


async def _validate_encryption_key(request: Request) -> bool:
    parsed = await request_parser.parse(request)
    config_manager: ConfigManager = request.app.state.config_manager
    return config_manager.decrypt(parsed.encryption_key) is not None

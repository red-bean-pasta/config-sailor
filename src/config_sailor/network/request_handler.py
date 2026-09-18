import json
import logging

from fastapi import APIRouter, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBasicCredentials

from config_sailor.file_managers.auth_manager import AuthManager
from config_sailor.file_managers.config_manager import ConfigManager
from config_sailor.file_managers.patch_manager import PatchParam, PatchManager
from config_sailor.network import request_parser
from config_sailor.utils import http_helper, json_helper


router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/{full_path:path}")
async def auth_and_build_config(request: Request):
    parsed = await request_parser.parse(request)
    auth_result = await _auth(request.app.state.auth_manager, parsed.bearer_creds, parsed.basic_creds)
    decrypt_result = _decrypt(request.app.state.config_manager, parsed.encryption_key or "\0")
    if not auth_result:
        logger.info("Invalid request: Failed authentication")
        return http_helper.get_uniform_reject()
    logger.debug("Request passed authentication")
    if not decrypt_result:
        logger.info("Invalid request: Failed config decryption")
        return http_helper.get_uniform_reject()
    logger.debug("Request decrypted config")

    user = auth_result
    config = json.loads(decrypt_result)

    param = PatchParam(user, parsed.agent, parsed.version)
    patch_manager: PatchManager = request.app.state.patch_manager
    result = patch_manager.patch(param, config)

    return Response(
        content=json_helper.dump_readable(result),
        media_type="application/json",
    )


async def _auth(
        auth_manager: AuthManager,
        bearer_creds: HTTPAuthorizationCredentials,
        basic_creds: HTTPBasicCredentials,
) -> str | None:
    return await auth_manager.auth(bearer_creds, basic_creds)


def _decrypt(
        config_manager: ConfigManager,
        encryption_key: str
) -> bytes | None:
    return config_manager.decrypt(encryption_key)

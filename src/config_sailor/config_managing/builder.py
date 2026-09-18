import json
import logging
from pathlib import Path

from anyio.streams import file
from config_sailor import manager_helper
from config_sailor.file_managers.patch_manager import PatchParam


logger = logging.getLogger(__name__)


def build(
        spec_dir: str | Path,
        param: PatchParam,
        encryption_key: str
) -> dict | None:
    config_manager = manager_helper.build_config_manager(spec_dir)
    patch_manager = manager_helper.build_patch_manager(spec_dir)

    logger.info(f"Decrypting config...")
    decrypted = config_manager.decrypt(encryption_key)
    if not decrypted:
        logger.error(f"Failed to decrypt {file}")
        return None

    logger.info(f"Parsing config...")
    try:
        parsed = json.loads(decrypted)
    except json.decoder.JSONDecodeError as e:
        logger.error(f"Invalid base JSON config: {e}")
        return None

    logger.info(f"Patching config...")
    patched = patch_manager.patch(param, parsed)

    return patched
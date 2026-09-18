import logging
import shlex
import subprocess
import sys
from pathlib import Path

from config_sailor.utils import file_operator
from config_sailor.encrypt import encryptor
from config_sailor.file_managers.config_manager import ConfigManager


logger = logging.getLogger(__name__)


def edit(
        path: Path | str,
        decryption_key: str,
        editor_command: str = "nano",
) -> None:
    file = Path(path)
    folder = file.parent

    config_manager = ConfigManager(file)
    decrypted_bytes = config_manager.decrypt(decryption_key)
    if not decrypted_bytes:
        logger.error(f"Failed to decrypt {file}")
        sys.exit(1)

    decrypted = decrypted_bytes.decode("utf-8")

    try:
        tmp = file_operator.save_to_temp_file(folder, decrypted)
    except PermissionError:
        logger.error(f"Failed to save temporary decrypted result. Is permission granted?")
        sys.exit(1)

    logger.info(f"Editing with {editor_command}...")
    enc_tmp = tmp.with_name(tmp.name + ".enc")
    try:
        _edit_with_editor(tmp, editor_command)
        encryptor.encrypt_file(decryption_key, tmp, enc_tmp)
        file_operator.replace(enc_tmp, file)
        logger.info(f"Edit saved and encrypted")
    except (RuntimeError, FileNotFoundError) as e:
        logger.fatal("ERROR: " + str(e))
        sys.exit(1)
    finally:
        file_operator.clean_up(tmp, enc_tmp)


def _edit_with_editor(
        source_path: Path,
        editor_command: str,
) -> None:
    cmd = shlex.split(editor_command) + [str(source_path)]
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        logger.error(f"Command `{editor_command}` exited with code {proc.returncode}")
        sys.exit(1)

from enum import StrEnum
from pathlib import Path

from config_sailor.file_managers.auth_manager import AuthManager
from config_sailor.file_managers.config_manager import ConfigManager
from config_sailor.file_managers.patch_manager import PatchManager


class SpecFile(StrEnum):
    BASE = "base.enc"
    AUTH = "auth.json"
    USER = "user.json"
    AGENT = "agent.json"
    VERSION = "version.json"

class StateFile(StrEnum):
    REVOKED = "revoked_credentials.txt"


def build_config_manager(config_dir: str | Path) -> ConfigManager:
    return ConfigManager(Path(config_dir) / SpecFile.BASE)


def build_auth_manager(
        spec_dir: str | Path,
        state_dir: str | Path,
) -> AuthManager:
    return AuthManager(
        Path(spec_dir) / SpecFile.AUTH,
        Path(state_dir) / StateFile.REVOKED,
    )


def build_patch_manager(spec_dir: str | Path) -> PatchManager:
    parent = Path(spec_dir)
    return PatchManager(
        parent / SpecFile.USER,
        parent / SpecFile.AGENT,
        parent / SpecFile.VERSION,
    )

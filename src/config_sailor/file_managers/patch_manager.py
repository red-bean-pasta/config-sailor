import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from config_sailor.file_managers.file_data import FileData
from config_sailor.patch import user_patcher, agent_patcher, version_patcher
from config_sailor.utils.json_helper import JsonObject

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class PatchParam:
    user: str | None
    agent: str | None
    version: str | None


class PatchManager:
    _user_spec: FileData | None
    _agent_spec: FileData | None
    _version_spec: FileData | None

    _ordered_patcher = {
        "agent": agent_patcher.patch,
        "version": version_patcher.patch,
        "user": user_patcher.patch,
    }

    def __init__(
            self,
            user_spec_path: Path | str | None,
            agent_spec_path: Path | str | None,
            version_spec_path: Path | str | None
    ) -> None:
        self._user_spec = FileData(user_spec_path) if user_spec_path else None
        self._agent_spec = FileData(agent_spec_path) if agent_spec_path else None
        self._version_spec = FileData(version_spec_path) if version_spec_path else None

    def patch(
            self,
            param: PatchParam,
            target: JsonObject,
    ) -> JsonObject:
        result = target
        for key, patcher in self._ordered_patcher.items():
            data = getattr(self, f"_{key}_spec")
            content = data.get_content() if data else None
            result = _apply_spec(
                key,
                getattr(param, key),
                content,
                patcher,
                result,
            )
        return result


def _apply_spec(
        key: str,
        value: str,
        spec: str | bytes | None,
        patcher: Callable[[str, str | bytes, JsonObject], JsonObject],
        target: JsonObject,
) -> JsonObject:
    if not value:
        logger.info(f"Skipping applying {key} patch: No value provided")
        return target
    if not spec:
        logger.info(f"Skipping applying {key} patch: No spec available")
        return target
    logger.info(f"Applying {key} patch for '{value}'")
    return patcher(value, spec, target)

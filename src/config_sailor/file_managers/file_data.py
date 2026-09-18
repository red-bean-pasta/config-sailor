import logging
from dataclasses import dataclass, field
from pathlib import Path

from config_sailor.utils import file_operator


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FileData:
    path: Path
    _payload: bytes | None = field(init=False)
    _modified_time_ns: int | None = field(init=False)

    def __post_init__(self) -> None:
        self._load()

    def get_content(self) -> bytes | None:
        self._reload_on_change()
        return self._payload

    def _load(self) -> None:
        self._payload = file_operator.read_bytes(self.path)
        self._modified_time_ns = file_operator.read_modified_time_ns(self.path)

    # Future-prone: Scale bad
    def _reload_on_change(self) -> bool:
        new_modified_time = file_operator.read_modified_time_ns(self.path)
        if new_modified_time == self._modified_time_ns:
            return False
        logger.info(f"{self.path}: Change detected: Reloading...")
        self._load()
        return True
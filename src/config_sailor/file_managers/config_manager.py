import logging

from cryptography.fernet import InvalidToken

from config_sailor.encrypt import encryptor
from config_sailor.file_managers.file_data import FileData


logger = logging.getLogger(__name__)


class ConfigManager(FileData):
    def decrypt(self, encryption_key: str) -> bytes | None:
        encrypted = self.get_content()

        if not encrypted:
            logger.error(f"Base config not found: {self.path}")
            return None

        try:
            return encryptor.decrypt_file(
                encryption_key,
                encrypted
            )
        except InvalidToken:
            logger.error(f"Invalid encryption key or base ciphertext")
            return None
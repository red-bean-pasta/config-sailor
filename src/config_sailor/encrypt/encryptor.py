import base64
import hashlib
import logging
from pathlib import Path

from cryptography.fernet import Fernet


logger = logging.getLogger(__name__)


_DUMMY_KEY = Fernet.generate_key().decode()


def generate_key_and_encrypt_file(
        source_file: Path | str,
        output_file: Path | str | None
) -> str:
    key = generate_key()
    encrypt_file(key, source_file, output_file)
    return key


def generate_key() -> str:
    return Fernet.generate_key().decode()


def encrypt_file(
        key: str,
        source_file: Path | str,
        output_file: Path | str
) -> None:
    key_hash = hashlib.sha256(key.encode()).digest() # Hash as constant-time decrypt demands so
    work_key = base64.urlsafe_b64encode(key_hash)
    with open(source_file, "rb") as file:
        raw = file.read()
    encrypted = Fernet(work_key).encrypt(raw)
    with open(output_file, "wb") as file:
        file.write(encrypted)


def decrypt_file(key: str, data: bytes) -> bytes | None:
    # In case the key provided is not 32 bits or is malformed,
    # which Fernet skips, resulting in timing difference
    key_hash = hashlib.sha256(key.encode()).digest()
    work_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(work_key).decrypt(data)


def _dummy_decrypt(data: bytes) -> None:
    Fernet(_DUMMY_KEY.encode()).decrypt(data).decode()

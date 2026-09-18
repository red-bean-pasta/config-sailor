import anyio
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash, VerificationError


HASHER = PasswordHasher(
    memory_cost=65536,
    time_cost=3,
    parallelism=3,
)

DUMMY_HASH = HASHER.hash("this-is-a-dummy-password")


def hash_secret(secret: str) -> str:
    return HASHER.hash(secret)


def is_valid_hash(secret_hash: str) -> bool:
    if not isinstance(secret_hash, str) or not secret_hash.startswith("$argon2"):
        return False
    try:
        HASHER.verify(secret_hash, "")
        return True
    except VerifyMismatchError:
        return True
    except (InvalidHash, VerificationError, Exception):
        return False


async def verify_hash(secret: str, secret_hash: str) -> bool:
    return await anyio.to_thread.run_sync(_verify_hash_sync, secret, secret_hash)


async def dummy_verify() -> None:
    await verify_hash("", DUMMY_HASH)


def _verify_hash_sync(secret: str, secret_hash: str) -> bool:
    try:
        return HASHER.verify(secret_hash, secret)
    except (VerifyMismatchError, InvalidHash):
        return False

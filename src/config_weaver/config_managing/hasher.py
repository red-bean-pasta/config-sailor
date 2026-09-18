from config_weaver.hash.hasher import hash_secret, is_valid_hash


def hash(credential: str) -> str:
    return hash_secret(credential)

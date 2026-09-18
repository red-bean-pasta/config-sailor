import json
import logging
from pathlib import Path

from config_weaver import manager_helper
from config_weaver.auth.authenticator import Method
from config_weaver.config_managing import secret_generator, hasher
from config_weaver.utils import file_operator, json_helper


logger = logging.getLogger(__name__)


def get_auth_rules_path(
    spec_dir: str | Path | None = None,
    auth_rules_path: str | Path | None = None,
) -> Path | None:
    if auth_rules_path:
        return Path(auth_rules_path)
    if spec_dir:
        return Path(spec_dir) / manager_helper.SpecFile.AUTH
    return None


def add_user_credential(
    path: str | Path,
    user: str,
    method: Method | str,
    hashed: str | None = None,
) -> tuple[str, str | None]:
    """
    Add or update authentication credential for a user.

    :param path: Path to auth_rules.json
    :param user: Username
    :param method: 'basic' or 'bearer'
    :param hashed: Optional pre-computed Argon2 hash. If None, a random secret is generated.
    :return: (hash, secret). If ``hashed`` is provided, secret is None
    """
    method_enum = _convert_method(method)

    if hashed is not None:
        _verify_provided_hash(hashed)
        secret = None
    else:
        secret = secret_generator.generate(24)
        hashed = hasher.hash(secret)

    rules = _load_rules(path, assert_exists=False)
    _add_user_credential(rules, user, method_enum, hashed)
    _save_rules(rules, path)

    return hashed, secret

def _verify_provided_hash(value: str) -> None:
    if hasher.is_valid_hash(value):
        return
    raise ValueError(
        "Invalid Argon2 hash format. Plaintext credentials cannot be passed directly. "
        "To auto-generate a secret, omit the hash argument."
    )

def _add_user_credential(
    rules: dict[str, dict[str, str]],
    user: str,
    method: Method,
    hashed: str,
) -> None:
    if user not in rules or not isinstance(rules[user], dict):
        rules[user] = {}
    rules[user][method.value] = hashed


def remove_user_credential(
    path: str | Path,
    user: str,
    method: Method | str | None = None,
) -> None:
    """
    Remove a user or a specific credential method for a user.

    :param path: Path to auth_rules.json
    :param user: Username
    :param method: Optional method ('basic' or 'bearer'). If None, the entire user entry is removed.
    """
    rules = _load_rules(path)
    _remove_user_credential(rules, user, method)
    _save_rules(rules, path)

def _remove_user_credential(
    rules: dict[str, dict[str, str]],
    user: str,
    method: str | Method | None,
) -> None:
    if user not in rules:
        raise KeyError(f"User '{user}' not found")

    if method is None:
        del rules[user]
        return

    method_enum = _convert_method(method)
    user_methods = rules[user]
    if (
        not isinstance(user_methods, dict)
        or method_enum.value not in user_methods
    ):
        raise KeyError(f"Method '{method_enum.value}' not configured for user '{user}'")

    del user_methods[method_enum.value]
    if not user_methods:
        del rules[user]


def _convert_method(method: Method | str) -> Method:
    try:
        return Method(str(method).lower())
    except ValueError:
        raise ValueError(
            f"Unsupported authentication method '{method}'. "
            f"Allowed methods: {', '.join(m.value for m in Method)}"
        )

def _load_rules(
    path: Path | str,
    assert_exists: bool = True,
) -> dict:
    path = _verify_path(path, assert_exists)
    if not path.exists():
        return {}

    text = file_operator.read_text(path)
    if not text or not text.strip():
        return {}

    try:
        rules = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON in {path}: {e}")
    if not isinstance(rules, dict):
        raise ValueError(f"Expected root JSON object in {path}, got {type(rules).__name__}")
    return rules


def _save_rules(rules: dict, path: Path | str) -> None:
    path = _verify_path(path, assert_exists=False)
    content = json_helper.dump_readable(rules) + "\n"
    file_operator.save(content.encode("utf-8"), path)

def _verify_path(
    path: Path | str,
    assert_exists: bool = True,
) -> Path:
    path = Path(path)
    if path.exists():
        return path
    if assert_exists:
        raise FileNotFoundError(f"File not found: {path}")
    return path

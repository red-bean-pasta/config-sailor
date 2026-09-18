import argparse
import getpass
import logging
import sys
from pathlib import Path

from config_sailor.config_managing import secret_generator
from config_sailor.config_managing import encryptor, editor, hasher, builder, user_manager
from config_sailor.file_managers.patch_manager import PatchParam
from config_sailor.network import service_starter
from config_sailor.utils import json_helper, file_operator


logger = logging.getLogger(__name__)


def serve(
        args: argparse.Namespace,
        passthrough: list[str] | None = None
) -> None:
    service_starter.start(args, passthrough)


def build(args: argparse.Namespace) -> None:
    param = PatchParam(
        args.user,
        args.agent,
        args.version
    )

    try:
        key = getpass.getpass("Enter decryption key: ")
    except (KeyboardInterrupt, EOFError):
        print()
        return

    result = builder.build(args.spec_dir, param, key)

    if not result:
        return

    dump = json_helper.dump_readable(result)
    if args.output_path:
        file_operator.save(dump.encode("utf-8"), Path(args.output_path))
    else:
        print(dump)


def encrypt(args: argparse.Namespace) -> None:
    key = encryptor.encrypt(args.input_path, args.output_path)
    print(f"Encryption key: {key}")


def edit(args: argparse.Namespace) -> None:
    try:
        key = getpass.getpass("Enter decryption key: ")
    except (KeyboardInterrupt, EOFError):
        print()
        sys.exit(1)
    editor.edit(args.path, key, args.editor_command)


def hash(args: argparse.Namespace) -> None:
    for c in args.credentials:
        print(f"{c}: {hasher.hash(c)}")


def generate_secret(args: argparse.Namespace) -> None:
    print(secret_generator.generate(args.length))


def user_add(args: argparse.Namespace) -> None:
    auth_rules_path = user_manager.get_auth_rules_path(args.spec_dir, args.auth_rules)
    assert auth_rules_path is not None
    try:
        hashed, secret = user_manager.add_user_credential(
            path=auth_rules_path,
            user=args.user,
            method=args.method,
            hashed=args.hash,
        )
        if secret:
            print(f"Generated {args.method} secret for user '{args.user}'")
            print(f"Credential: {args.user}{':' if args.method == 'basic' else '~'}{secret}")
        else:
            print(f"Added {args.method} credential for user '{args.user}'")
    except Exception as e:
        logger.error(f"Failed to add user credential: {e}")
        sys.exit(1)


def user_remove(args: argparse.Namespace) -> None:
    auth_rules_path = user_manager.get_auth_rules_path(args.spec_dir, args.auth_rules)
    assert auth_rules_path is not None
    try:
        user_manager.remove_user_credential(
            path=auth_rules_path,
            user=args.user,
            method=args.method,
        )
        if args.method:
            print(f"Removed {args.method} credential for user '{args.user}'")
        else:
            print(f"Removed user '{args.user}'")
    except Exception as e:
        logger.error(f"Failed to remove user credential: {e}")
        sys.exit(1)
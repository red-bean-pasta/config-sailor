import argparse
import os
from pathlib import Path
from typing import Callable

from config_sailor import meta
from config_sailor import arg_funcs


_SPEC_DIR_ENV = "SPEC_DIR"
_env_spec_dir = os.getenv(_SPEC_DIR_ENV)

_STATE_DIR_ENV = "STATE_DIR"
_env_state_dir = os.getenv(_STATE_DIR_ENV)


def parse_args() -> argparse.Namespace:
    parser = _setup_parser()
    args = parser.parse_args()
    _validate_args(args, parser.error)
    return args


def _validate_args(
        args: argparse.Namespace,
        error_raiser: Callable[[str], None],
) -> None:
    if args.command == "serve" and any(not d for d in (args.spec_dir, args.state_dir)):
        error_raiser(f"{args.command}: Parameters --spec-dir and --state-dir are required")


def _setup_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=meta.MODULE_NAME,
        epilog="Use '%(prog)s <command> --help' for more information on a specific command")
    subparsers = parser.add_subparsers(
        title="Available commands",
        dest="command",
        required=True)

    _setup_secret_generate_parser(subparsers)
    _setup_hash_parser(subparsers)
    _setup_encrypt_parsers(subparsers)
    _setup_build_parser(subparsers)
    _setup_serve_parser(subparsers)
    _setup_user_parser(subparsers)

    return parser


def _setup_user_parser(subparsers):
    user_parser = subparsers.add_parser(
        "user",
        help="Manage users and authentication credentials in auth.json",
        epilog="Use '%(prog)s <action> --help' for more information on a specific action")

    user_subparsers = user_parser.add_subparsers(
        title="User actions",
        dest="user_action",
        required=True)

    _setup_user_add_parser(user_subparsers)
    _setup_user_remove_parser(user_subparsers)


def _setup_user_add_parser(subparsers):
    add_parser = subparsers.add_parser(
        "add",
        help="Add or update a verification credential for a user")
    add_parser.add_argument(
        "user",
        metavar="USER",
        help="Name of the user to add or update")
    add_parser.add_argument(
        "method",
        type=str.lower,
        choices=["basic", "bearer"],
        help="Verification method: 'basic' or 'bearer'")
    add_parser.add_argument(
        "path",
        type=Path,
        metavar="PATH",
        help="Path to auth.json or the directory containing it")
    add_parser.add_argument(
        "hash",
        nargs="?",
        default=None,
        metavar="HASH",
        help="Pre-computed Argon2 hash. If omitted, a random secret is generated automatically and its plaintext is printed")
    add_parser.set_defaults(func=arg_funcs.user_add)


def _setup_user_remove_parser(subparsers):
    remove_parser = subparsers.add_parser(
        "remove",
        help="Remove a user or a specific verification method for a user")
    remove_parser.add_argument(
        "user",
        metavar="USER",
        help="Name of the user to remove")
    remove_parser.add_argument(
        "method",
        nargs="?",
        default=None,
        type=str.lower,
        choices=["basic", "bearer"],
        help="Verification method to remove ('basic' or 'bearer'). If omitted, the entire user entry is removed")
    remove_parser.add_argument(
        "path",
        type=Path,
        metavar="PATH",
        help="Path to auth.json or the directory containing it")
    remove_parser.set_defaults(func=arg_funcs.user_remove)


def _setup_serve_parser(subparsers):
    parser = subparsers.add_parser(
        "serve",
        help="Start the config patching service over HTTP or HTTPS",
    )
    _add_serve_config_args(parser)
    _add_serve_network_args(parser)
    _add_log_arg(parser)
    parser.set_defaults(func=arg_funcs.serve)


def _add_serve_config_args(parser):
    config = parser.add_argument_group("Configuration")
    config.add_argument(
        "-d", "--spec-dir",
        metavar="PATH",
        default=_env_spec_dir,
        help=f"""Path to the spec directory
This directory must contain:
  - base.enc
  - auth.json
It may also contain:
  - user.json
  - agent.json
  - version.json
Defaults to ${_SPEC_DIR_ENV}""")
    config.add_argument(
        "-s", "--state-dir",
        metavar="PATH",
        default=_env_state_dir,
        help=f"""Directory for files created and managed by the service
This currently only includes the revoked-credentials record
Defaults to ${_STATE_DIR_ENV}""")


def _add_serve_network_args(parser):
    network = parser.add_argument_group("Network")
    network.add_argument(
        "--host",
        default=os.getenv("HOST") or "127.0.0.1",
        help="Interface to bind to. Defaults to $HOST else 127.0.0.1")
    network.add_argument(
        "--port",
        type=_port_type,
        default=_port_type(os.getenv("PORT") or 9443),
        help="Port to listen on. Defaults to $PORT else 9443")
    network.add_argument(
        "--forwarded-allow-ips",
        metavar="IP",
        default=os.getenv("FORWARDED_ALLOW_IPS") or "127.0.0.1",
        help="""Comma-separated list of proxy IPs whose forwarded headers are trusted
Warning: Should only be used when running behind reverse proxies, such as Nginx or Caddy
Defaults to FORWARDED_ALLOW_IPS else 127.0.0.1""")
    network.add_argument(
        "--ssl-keyfile",
        default=os.getenv("SSL_KEYFILE"),
        metavar="PATH",
        help="Path to SSL key file for HTTPS. Defaults to $SSL_KEYFILE")
    network.add_argument(
        "--ssl-certfile",
        default=os.getenv("SSL_CERTFILE"),
        metavar="PATH",
        help="Path to SSL certificate file for HTTPS. Defaults to $SSL_CERTFILE")
    network.add_argument(
        "--unsafe-mode",
        action='store_true', default=False,
        help="""Allow plaintext HTTP request and disable exposed credentials revoking
Warning: Enable this only in trusted development environments""")


def _setup_build_parser(subparsers):
    parser = subparsers.add_parser(
        "build",
        help="Generate config from your spec directory. It reads and decrypts the encrypted base config and applies optional rules based on user, agent, and version settings.")
    parser.add_argument(
        "-d", "--spec-dir",
        default=_env_spec_dir,
        help=f"Path to the spec directory. Required files: [base.enc]. Optional files: [user.json, agent.json, version.json]. Defaults to ${_SPEC_DIR_ENV}"
    )
    parser.add_argument(
        "-o", "--output-path",
        default=None,
        help="Path to save patched config. Omit to print to stdout")
    parser.add_argument(
        "-u", "--user",
        default=None,
        help="Name of the user to build for")
    parser.add_argument(
        "-a", "--agent",
        default=None,
        help="Client agent to build for")
    parser.add_argument(
        "-v", "--version",
        default=None,
        help="Client version to build for")
    _add_log_arg(parser)
    parser.set_defaults(func=arg_funcs.build)


def _setup_encrypt_parsers(subparsers):
    enc = subparsers.add_parser(
        "encrypt",
        help="Encrypt config file for secure storage")
    enc.add_argument(
        "input_path",
        type=Path,
        metavar="INPUT",
        help="Path to the file to encrypt")
    enc.add_argument(
        "output_path",
        type=Path,
        nargs="?",
        metavar="OUTPUT",
        help="Destination path. Defaults to INPUT with extension replaced with '.enc'")
    enc.set_defaults(func=arg_funcs.encrypt)

    edit = subparsers.add_parser(
        "edit",
        help="Decrypt and edit encrypted config file then re-encrypt")
    edit.add_argument(
        "path",
        type=Path,
        metavar="PATH",
        help="Path to the encrypted file")
    edit.add_argument(
        "-e", "--editor-command",
        metavar="COMMAND",
        default="nano",
        help="Editor command to run, such as 'vim' or 'code --wait'. Defaults to 'nano'")
    edit.set_defaults(func=arg_funcs.edit)


def _setup_hash_parser(subparsers):
    parser = subparsers.add_parser(
        "hash",
        help="Hash authentication credentials for secure storage")
    parser.add_argument(
        "credentials",
        nargs="+",
        metavar="CREDENTIAL",
        help="One or more credentials to hash")
    parser.set_defaults(func=arg_funcs.hash)


def _setup_secret_generate_parser(subparsers):
    parser = subparsers.add_parser(
        "generate",
        help="Generate random URL-safe secret")
    parser.add_argument(
        "length",
        nargs="?", type=int, default=24,
        help="Number of random bytes to generate. Every 4 bytes output 6 characters. Default to 24")
    parser.set_defaults(func=arg_funcs.generate_secret)


def _add_log_arg(parser):
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error", "critical"],
        default=os.getenv("LOG_LEVEL") or "info",
        help="Defaults to $LOG_LEVEL else 'info'")


def _port_type(value: str) -> int:
    port = int(value)
    if 1 <= port <= 65535: return port
    raise ValueError(f"Port overflow: {value} not within 1 and 65535")

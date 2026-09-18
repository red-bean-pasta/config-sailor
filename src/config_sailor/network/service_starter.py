import argparse
import logging
import os
import shlex
import sys

from config_sailor.meta import MODULE_NAME
from config_sailor.network import app

logger = logging.getLogger(__name__)


def start(
        args,
        passthrough: list[str] | None
) -> None:
    _env_persistent_args(args)

    argv = [
        sys.executable,
        "-m", "uvicorn",
        f"{MODULE_NAME}.network.app:create",
        "--factory",
        "--proxy-headers",
        "--no-server-header",
        *_get_env_uvicorn_args(),
        "--host", args.host,
        "--port", str(args.port),
        "--forwarded-allow-ips", args.forwarded_allow_ips,
        *(passthrough or [])
    ]
    logger.info(f"Starting uvicorn process: {' '.join(argv)}")
    os.execvp(argv[0], argv)


def _env_persistent_args(args: argparse.Namespace) -> None:
    os.environ[app.SPEC_DIR_ENV] = args.spec_dir
    os.environ[app.STATE_DIR_ENV] = args.state_dir
    os.environ[app.UNSAFE_MODE_ENV] = "1" if args.unsafe_mode else "0"
    os.environ[app.LOG_LEVEL_ENV] = args.log_level


def _get_env_uvicorn_args() -> list[str]:
    env = os.getenv("UVICORN_ARGS")
    args = shlex.split(env) if env else []
    return args
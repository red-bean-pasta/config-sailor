import logging

from fastapi import FastAPI

from config_sailor import manager_helper
from config_sailor.network import request_handler
from config_sailor.network.http_revoker import HttpAuthRevokeMiddleware
from config_sailor.utils import logging_helper

logger = logging.getLogger(__name__)


def create(
        spec_dir: str,
        state_dir: str,
        unsafe_mode: bool = False,
        log_level: str = "info",
) -> FastAPI:
    try:
        return _create(spec_dir, state_dir, unsafe_mode, log_level)
    except Exception:
        logger.exception("Failed to create ASGI app")
        raise


def _create(
        spec_dir: str,
        state_dir: str,
        unsafe_mode: bool = False,
        log_level: str = "info",
) -> FastAPI:
    _initialize_logging(log_level)

    app = FastAPI()
    app.include_router(request_handler.router)
    app.add_middleware(HttpAuthRevokeMiddleware)

    app.state.config_manager = manager_helper.build_config_manager(spec_dir)
    app.state.auth_manager = manager_helper.build_auth_manager(spec_dir, state_dir)
    app.state.patch_manager = manager_helper.build_patch_manager(spec_dir)
    app.state.unsafe_mode = unsafe_mode

    return app


def _initialize_logging(log_level: str = "info") -> None:
    logging_helper.initialize(log_level)
    _add_logger_filter()


def _add_logger_filter() -> None:
    uvicorn_logger = logging.getLogger("uvicorn.access")
    for h in uvicorn_logger.handlers:
        h.addFilter(_strip_path)


def _strip_path(record: logging.LogRecord) -> bool:
    if len(record.args) >= 3:
        record.args = record.args[:2] + ("REDACTED",) + record.args[3:]
    return True

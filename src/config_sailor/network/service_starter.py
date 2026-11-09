import argparse
import logging
import uvicorn

from config_sailor.network import app

logger = logging.getLogger(__name__)


def start(args: argparse.Namespace) -> None:
    asgi_app = app.create(
        spec_dir=args.spec_dir,
        state_dir=args.state_dir,
        unsafe_mode=args.unsafe_mode,
        log_level=args.log_level,
    )

    logger.info(f"Starting uvicorn server on {args.host}:{args.port}")
    uvicorn.run(
        asgi_app,
        host=args.host,
        port=args.port,
        proxy_headers=True,
        server_header=False,
        forwarded_allow_ips=args.forwarded_allow_ips,
        log_level=args.log_level.lower(),
        ssl_keyfile=getattr(args, "ssl_keyfile", None),
        ssl_certfile=getattr(args, "ssl_certfile", None),
    )

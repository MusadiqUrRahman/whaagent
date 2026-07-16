"""FastAPI-based REST API for whaagent."""

from whaagent.api.server import create_app, run_server

__all__ = ["create_app", "run_server"]

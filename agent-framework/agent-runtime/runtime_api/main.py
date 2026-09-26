"""Default ASGI entry point for the persisted Runtime API."""

from .app import create_app


app = create_app()

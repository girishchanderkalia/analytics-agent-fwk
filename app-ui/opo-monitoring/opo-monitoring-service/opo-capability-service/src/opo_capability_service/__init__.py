"""Deployable application-owned OPO capability service."""
from .app import create_app
from .service import OpoCapabilityService
__all__ = ["OpoCapabilityService", "create_app"]

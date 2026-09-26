"""FastAPI factory for trusted prebuilt-agent registration."""
from fastapi import FastAPI
from .agent_registration_routes import router
from .error_mapping import install_error_handlers

def create_app(agent_registration_service=None) -> FastAPI:
    app = FastAPI(title="Application Agent Runtime API", version="3.0.0")
    app.state.agent_registration_service = agent_registration_service
    install_error_handlers(app)
    app.include_router(router)
    return app

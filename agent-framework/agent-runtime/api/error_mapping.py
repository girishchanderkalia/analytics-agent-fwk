from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from agent_registration import AgentAlreadyRegisteredError, AgentRegistrationValidationError

def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AgentRegistrationValidationError)
    async def invalid(request: Request, exc: AgentRegistrationValidationError):
        del request
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"code":"agent_registration_invalid","message":str(exc)})

    @app.exception_handler(AgentAlreadyRegisteredError)
    async def conflict(request: Request, exc: AgentAlreadyRegisteredError):
        del request
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"code":"agent_registration_conflict","message":str(exc)})

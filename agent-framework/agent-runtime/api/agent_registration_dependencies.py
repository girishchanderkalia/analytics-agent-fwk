from fastapi import HTTPException, Request, status
from agent_registration.service import AgentRegistrationService

def get_agent_registration_service(request: Request) -> AgentRegistrationService:
    service = getattr(request.app.state, "agent_registration_service", None)
    if service is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Agent Registration Service is not configured")
    return service

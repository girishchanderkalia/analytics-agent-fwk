from pathlib import Path
from typing import Annotated
from fastapi import APIRouter, Depends, status
from agent_registration import AgentRegistrationRequest, AgentRegistrationService, BulkAgentRegistrationRequest
from .agent_registration_dependencies import get_agent_registration_service
from .agent_registration_models import BulkAgentRegistrationRequestModel, BulkAgentRegistrationResponse, AgentRegistrationListResponse

router = APIRouter(prefix="/v1/applications/{application_id}/agents", tags=["agent-registration"])

def payload(record):
    return {"applicationId":record.key.application_id,"agentId":record.key.agent_id,"version":record.key.version,"packageRoot":str(record.definition_root),"definitionFingerprint":record.definition_fingerprint,"registeredAt":record.registered_at}

@router.post(":bulk-register", response_model=BulkAgentRegistrationResponse, response_model_by_alias=True, status_code=status.HTTP_201_CREATED)
def bulk_register(application_id: str, body: BulkAgentRegistrationRequestModel, service: Annotated[AgentRegistrationService, Depends(get_agent_registration_service)]):
    result = service.register_bulk(BulkAgentRegistrationRequest(application_id=application_id, agents=tuple(AgentRegistrationRequest(agent_id=item.agent_id, version=item.version, definition_root=Path(item.package_root)) for item in body.agents)))
    return {"applicationId":result.application_id,"status":result.status.value,"agents":[payload(record) for record in result.registrations]}

@router.get("", response_model=AgentRegistrationListResponse, response_model_by_alias=True)
def list_agents(application_id: str, service: Annotated[AgentRegistrationService, Depends(get_agent_registration_service)]):
    return {"applicationId":application_id,"agents":[payload(record) for record in service.list_for_application(application_id)]}

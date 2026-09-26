from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

class AgentRegistrationItemRequest(ApiModel):
    agent_id: str = Field(alias="agentId", min_length=1)
    version: str = Field(min_length=1)
    package_root: str = Field(alias="packageRoot", min_length=1)

class BulkAgentRegistrationRequestModel(ApiModel):
    agents: list[AgentRegistrationItemRequest] = Field(min_length=1)

class AgentRegistrationRecordModel(ApiModel):
    application_id: str = Field(alias="applicationId")
    agent_id: str = Field(alias="agentId")
    version: str
    package_root: str = Field(alias="packageRoot")
    definition_fingerprint: str = Field(alias="definitionFingerprint")
    registered_at: datetime = Field(alias="registeredAt")

class BulkAgentRegistrationResponse(ApiModel):
    application_id: str = Field(alias="applicationId")
    status: str
    agents: list[AgentRegistrationRecordModel]

class AgentRegistrationListResponse(ApiModel):
    application_id: str = Field(alias="applicationId")
    agents: list[AgentRegistrationRecordModel]

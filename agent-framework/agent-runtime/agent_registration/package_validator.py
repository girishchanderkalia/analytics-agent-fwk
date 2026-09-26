"""Registration validator for generic declarative packages."""
from hashlib import sha256
from definitions import AgentPackageError, load_agent_package
from .errors import AgentRegistrationValidationError
class GenericAgentPackageRegistrationValidator:
    def validate(self,*,application_id,request):
        del application_id
        try:package=load_agent_package(request.definition_root)
        except AgentPackageError as exc:raise AgentRegistrationValidationError(str(exc)) from exc
        if package.manifest.agent_id != request.agent_id:raise AgentRegistrationValidationError("Registered agent ID does not match agent-package.yaml")
        if package.manifest.version != request.version:raise AgentRegistrationValidationError("Registered agent version does not match agent-package.yaml")
        return fingerprint_agent_package(package)
def fingerprint_agent_package(package):
    digest=sha256(); files=(("manifest",package.manifest_path),)+tuple(sorted(package.resolved_sources))
    for role,path in files:
        digest.update(role.encode());digest.update(b"\0");digest.update(path.relative_to(package.package_root).as_posix().encode());digest.update(b"\0")
        digest.update(path.read_text(encoding="utf-8").replace("\r\n","\n").replace("\r","\n").encode());digest.update(b"\0")
    return digest.hexdigest()

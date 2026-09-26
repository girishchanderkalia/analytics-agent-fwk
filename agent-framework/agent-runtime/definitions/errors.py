"""Errors for generic declarative agent packages."""
class AgentPackageError(ValueError):
    """Base package error."""
class AgentPackageManifestError(AgentPackageError):
    """Invalid package manifest."""

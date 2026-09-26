class FoundationServiceError(RuntimeError): pass
class DatasetConfigurationError(FoundationServiceError, ValueError): pass
class WorkspaceNotFoundError(FoundationServiceError, LookupError): pass
class RegistrationNotFoundError(FoundationServiceError, LookupError): pass

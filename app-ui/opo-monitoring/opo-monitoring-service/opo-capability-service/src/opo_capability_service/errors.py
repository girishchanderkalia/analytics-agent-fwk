class CapabilityInputError(ValueError):
    """Invalid tool input supplied by the runtime."""

class UnknownCapabilityError(LookupError):
    """Unknown OPO capability requested."""

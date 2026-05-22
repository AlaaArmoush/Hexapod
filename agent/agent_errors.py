"""Custom errors for agent plan parsing and validation."""


class AgentPlanError(Exception):
    """Base class for all agent plan errors."""


class AgentPlanParseError(AgentPlanError):
    """Raised when model output cannot be parsed as one JSON object."""


class AgentPlanValidationError(AgentPlanError):
    """Raised when a parsed plan fails schema or safety validation."""


class UnknownToolError(AgentPlanValidationError):
    """Raised when a tool name is not in the allowed tool list."""


class UnknownActionError(AgentPlanValidationError):
    """Raised when a robot action name is not in the allowed action list."""


class UnsafeAgentPlanError(AgentPlanValidationError):
    """Raised when unsafe content appears anywhere in an agent plan."""


class AmbiguousCommandError(AgentPlanValidationError):
    """Raised when a command contains mutually exclusive choices."""


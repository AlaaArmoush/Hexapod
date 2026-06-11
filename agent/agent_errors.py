class AgentPlanError(Exception):
    pass


class AgentPlanParseError(AgentPlanError):
    pass


class AgentPlanValidationError(AgentPlanError):
    pass


class UnknownToolError(AgentPlanValidationError):
    pass


class UnknownActionError(AgentPlanValidationError):
    pass


class UnsafeAgentPlanError(AgentPlanValidationError):
    pass


class AmbiguousCommandError(AgentPlanValidationError):
    pass


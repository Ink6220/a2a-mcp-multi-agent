"""
Mock Agent for Executor Testing

This mock agent is designed to return predictable, A2A-compliant ResponseFormat
objects for testing the GenericAgentExecutor's handling of state transitions,
event streaming, and artifact creation.
"""
from typing import Dict, Any, Optional

# --- Mock BaseModel and ResponseFormat for testing ---
# This simulates Pydantic's BaseModel without requiring Pydantic for the test.
class MockBaseModel:
    def __init__(self, **kwargs: Any):
        # Set default values for all annotated fields
        for name, _ in self.__annotations__.items():
            # In a real BaseModel, this would handle type casting etc.
            # For the mock, we just set the value.
            setattr(self, name, kwargs.get(name))

class ResponseFormat(MockBaseModel):
    """ Mocks the agent's ResponseFormat(BaseModel) for consistent testing """
    action: str  # Literal["answer", "call_next_agent"]
    status: str  # Literal["input_required", "completed", "failed"]
    message: str
    
    # Optional fields
    custom_status: Optional[str] = None
    agent_name: Optional[str] = None
    next_agent_instruction: Optional[str] = None
    next_agent_schema: Optional[Dict[str, Any]] = None
    artifacts: Optional[str] = None


class MockAgent:
    """
    A fully A2A-compliant mock agent that returns predictable ResponseFormat
    objects for testing the executor.
    """
    agent_name = "mock-agent"

    def __init__(self, response_data: Dict[str, Any]):
        """
        Initializes the mock agent with the data to be returned.
        
        Args:
            response_data: A dictionary of attributes for the ResponseFormat.
        """
        self.response_to_return = ResponseFormat(**response_data)

    async def invoke(
        self,
        query: str,
        context_id: str,
        task_id: str | None = None,
        context: Dict[str, Any] | None = None,
    ) -> ResponseFormat:
        """Return the pre-configured ResponseFormat regardless of inputs."""
        return self.response_to_return

# --- Pre-configured Mock Agents for Different Scenarios ---

def get_completion_agent() -> MockAgent:
    """Returns an agent that simulates successful task completion."""
    return MockAgent({
        "action": "answer",
        "status": "completed",
        "message": "Task completed successfully!"
    })

def get_input_required_agent() -> MockAgent:
    """Returns an agent that simulates needing more user input."""
    return MockAgent({
        "action": "answer",
        "status": "input_required",
        "message": "Please provide more information."
    })

# TODO: working state agent is not a state of response format
def get_working_state_agent() -> MockAgent:
    """Returns an agent that simulates an intermediate 'working' state."""
    return MockAgent({
        "action": "answer",
        "status": "completed",  # Note: there's no "working" status in new protocol
        "message": "Still processing, please wait..."
    })

def get_delegation_agent() -> MockAgent:
    """Returns an agent that simulates delegating to another agent."""
    return MockAgent({
        "action": "call_next_agent",
        "status": "input_required",
        "message": "Delegating task to specialist-agent.",
        "agent_name": "specialist-agent",
        "next_agent_instruction": "Please handle this specialized request"
    })

def get_failed_agent() -> MockAgent:
    """Returns an agent that simulates a failed task."""
    return MockAgent({
        "action": "answer",
        "status": "failed",
        "message": "Task failed due to an error."
    })

def get_error_agent() -> MockAgent:
    """Returns a mock agent that raises an exception during invoke."""
    class ErrorAgent(MockAgent):
        async def invoke(
            self,
            query: str,
            context_id: str,
            task_id: str | None = None,
            context: Dict[str, Any] | None = None,
        ) -> ResponseFormat:
            raise ValueError("Simulated agent error")
    
    # The response data here is irrelevant since invoke will raise an error
    return ErrorAgent({"action": "answer", "status": "failed", "message": "This will not be returned"}) 
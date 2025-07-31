import asyncio

from unit_tests.test_execute_starlette_compliance.unit_test_starlette import (
    test_a2a_executor_scenarios,
)


# NOTE: Checks BaseAgentExecutor logical behaviour
def test_executor_compliance_scenarios():
    """Runs the executor scenario suite that uses mock agents only (offline)."""
    all_passed = asyncio.run(test_a2a_executor_scenarios())
    assert all_passed, "Executor publishes states appropriately (state transition definitions in /unit_tests/test_execute_starlette_compliance/StateTransition_logic.png)" 


"""
Builds four mock agents (get_completion_agent, get_input_required_agent, get_delegation_agent, get_failed_agent) plus an extra "throws-exception" agent.
For each mock agent it calls simulate_starlette_request() which:
creates a fake Starlette-style request context,
instantiates the real BaseAgentExecutor,
feeds the mock agent's ResponseFormat back through the executor,
captures the A2A event stream that the executor would send over SSE.
"""
# Starlette integration test for BaseAgentExecutor
def test_response_format_compliance():
    """Validate that a simple ExampleCompliantAgent returns a ResponseFormat that passes the A2A compliance checks without hitting any external API."""
    from unit_tests.test_invoke_protocol_compliance.test_invoke_return_type.test_agent_a2a_compliance import (
        A2AComplianceTester, ExampleCompliantAgent,
    )

    # Instantiate the example agent that has a hard-coded compliant response
    agent = ExampleCompliantAgent()

    # Run the async compliance check synchronously
    compliance_results = asyncio.run(A2AComplianceTester.test_agent_invoke_compliance(agent))

    # The test should fail with a clear message if the compliance check fails
    assert compliance_results["status"] == "PASSED", compliance_results.get("error", "Unknown error")
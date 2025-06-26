import asyncio

from unit_tests.test_execute_starlette_compliance.unit_test_starlette import (
    test_a2a_executor_scenarios,
)


# NOTE: We avoid relying on pytest-asyncio by keeping the test synchronous
def test_executor_compliance_scenarios():
    """Runs the executor scenario suite that uses mock agents only (offline)."""
    all_passed = asyncio.run(test_a2a_executor_scenarios())
    assert all_passed, "Executor publishes states appropriately (state transition definitions in /unit_tests/test_execute_starlette_compliance/StateTransition_logic.png)" 
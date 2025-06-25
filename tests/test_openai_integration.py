import os
import pytest
import asyncio

# Import helpers from original manual test script
from unit_tests.test_invoke_protocol_compliance.sample_test import (
    create_test_agent,
)

from unit_tests.test_invoke_protocol_compliance.test_invoke_return_type.test_agent_a2a_compliance import (
    A2AComplianceTester,
)
from unit_tests.test_invoke_protocol_compliance.test_llm_invoke_behaviour.test_llm_behavior import (
    LLMBehaviorTester,
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_openai_agent_compliance_and_behavior():
    """Runs compliance + behavior checks on the real OpenAI-backed agent.

    The environment variable OPENAI_API_KEY **must** be set.  If it is not
    present this test will fail immediately, signalling a CI mis-configuration.
    """
    assert os.getenv("OPENAI_API_KEY"), (
        "OPENAI_API_KEY environment variable not set. "
        "This test requires a valid OpenAI key. "
        "Set it locally or configure it as a repository secret in CI."
    )

    agent = create_test_agent()

    compliance_results = await A2AComplianceTester.test_agent_invoke_compliance(agent)
    assert compliance_results["status"] == "PASSED", compliance_results.get("error", "Unknown error")

    behavior_results = await LLMBehaviorTester.test_llm_behavior(agent)
    assert behavior_results["status"] == "PASSED", behavior_results.get("failed_tests") 
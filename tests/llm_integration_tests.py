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


@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_openai_agent_compliance_and_behavior():
    """Runs compliance + behavior checks on the real API-backed agent.

    The environment variable OPENAI_API_KEY, NOVA_API_KEY, other API keys **must** be set.  If it is not
    present this test will fail immediately, signalling a CI mis-configuration.
    The tests if the LLM can respond in a predictable ResponseFormat, if this is failing, the problem is likely in the agent code
    The tests if the LLM can respond in a predictable ResponseFormat, if this is failing, the problem is likely in the prompt
    """
    assert os.getenv("OPENAI_API_KEY"), (
        "OPENAI_API_KEY environment variable not set. "
        "This test requires a valid OpenAI key. "
        "Set it locally or configure it as a repository secret in CI."
    )

    standard_agent = create_test_agent()

    behavior_results = await LLMBehaviorTester.test_llm_behavior(standard_agent)
    assert behavior_results["status"] == "PASSED", behavior_results.get("failed_tests") 
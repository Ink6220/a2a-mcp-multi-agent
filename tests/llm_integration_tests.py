import os
import pytest
import asyncio
import warnings

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

# Filter Pydantic serialization warnings
warnings.filterwarnings(
    "ignore",
    message=".*Expected 9 fields but got.*",
    category=UserWarning
)


@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_openai_agent_compliance_and_behavior():
    """Test OpenAI agent compliance and behavior."""
    assert os.getenv("OPENAI_API_KEY"), (
        "OPENAI_API_KEY environment variable not set. "
        "This test requires a valid OpenAI key. "
        "Set it locally or configure it as a repository secret in CI."
    )

    openai_agent = create_test_agent(prefer_provider="openai")
    behavior_results = await LLMBehaviorTester.test_llm_behavior(openai_agent)
    assert behavior_results["status"] == "PASSED", f"OpenAI agent failed: {behavior_results.get('failed_tests')}"


@pytest.mark.requires_api_key
@pytest.mark.asyncio
async def test_aws_nova_agent_compliance_and_behavior():
    """Test AWS Nova agent compliance and behavior."""
    # Check for AWS/Nova credentials
    assert all([
        os.getenv("AWS_ACCESS_KEY_ID"),
        os.getenv("AWS_SECRET_ACCESS_KEY"),
        os.getenv("AWS_REGION_NAME")
    ]), (
        "AWS credentials not set. "
        "This test requires AWS credentials for Nova: "
        "AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME. "
        "Set them locally or configure as repository secrets in CI."
    )

    aws_agent = create_test_agent(prefer_provider="aws")
    behavior_results = await LLMBehaviorTester.test_llm_behavior(aws_agent)
    assert behavior_results["status"] == "PASSED", f"AWS Nova agent failed: {behavior_results.get('failed_tests')}"


# same as indiv tests above
# @pytest.mark.requires_api_key
# @pytest.mark.asyncio
# async def test_both_agents_integration():
#     """Integration test that runs both OpenAI and AWS Nova agents if available."""
#     has_openai = bool(os.getenv("OPENAI_API_KEY"))
#     has_aws_nova = all([
#         os.getenv("AWS_ACCESS_KEY_ID"),
#         os.getenv("AWS_SECRET_ACCESS_KEY"),
#         os.getenv("AWS_REGION_NAME")
#     ])

#     # At least one provider must be available
#     assert has_openai or has_aws_nova, (
#         "Neither OpenAI nor AWS/Nova credentials are set. "
#         "This test requires at least one of:\n"
#         "1. OPENAI_API_KEY for OpenAI\n"
#         "2. AWS credentials (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME) for Nova"
#     )

#     results = {}
    
#     # Test OpenAI if available
#     if has_openai:
#         print("Testing OpenAI agent...")
#         openai_agent = create_test_agent(prefer_provider="openai")
#         openai_results = await LLMBehaviorTester.test_llm_behavior(openai_agent)
#         results["OpenAI"] = openai_results
        
#     # Test AWS Nova if available
#     if has_aws_nova:
#         print("Testing AWS Nova agent...")
#         aws_agent = create_test_agent(prefer_provider="aws")
#         aws_results = await LLMBehaviorTester.test_llm_behavior(aws_agent)
#         results["AWS Nova"] = aws_results
    
#     # All tested providers must pass
#     failed_providers = []
#     for provider, result in results.items():
#         if result["status"] != "PASSED":
#             failed_providers.append(f"{provider}: {result.get('failed_tests')}")
    
#     assert not failed_providers, f"Some providers failed: {failed_providers}"
    
#     print(f"✅ Successfully tested {len(results)} provider(s): {', '.join(results.keys())}") 
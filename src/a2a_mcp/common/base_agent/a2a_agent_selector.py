import sys
from a2a_mcp.common.types import CustomAgentCard
from a2a_mcp.common.card_discovery import A2ACardDiscovery
from a2a_mcp.common.base_agent.a2a_openai_agent import A2AOpenaiAgent

class A2AAgentSelector:
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        self.provider = agent_card.provider.organization if agent_card.provider else None
        self.agent_card = agent_card
        self.mcp_server = mcp_server
        self.card_discovery = card_discovery
        self.model_integration = self._get_model_integration()
        self.agent = self._create_unified_agent()

    def _get_model_integration(self):
        """Get the appropriate model integration based on provider."""
        provider = self.provider.lower() if self.provider else None
        
        if provider == "aws":
            from a2a_mcp.common.base_agent.aws_integration import validate_aws_setup
            print("🔄 AWS mode enabled - validating AWS setup...")
            aws_valid, aws_integration = validate_aws_setup()
            if not aws_valid:
                print("❌ AWS setup failed. Please check your AWS credentials in .env file.")
                print("Required variables: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME")
                sys.exit(1)
            if aws_integration:
                aws_integration.print_integration_info(self.agent_card.modelName)
            return aws_integration
            
        elif provider == "openai":
            from a2a_mcp.common.base_agent.openai_integration import validate_openai_setup
            print("🔄 OpenAI mode enabled - validating OpenAI API setup...")
            openai_valid, openai_integration = validate_openai_setup()
            if not openai_valid:
                print("❌ OpenAI setup failed. Please check your OpenAI API key in .env file.")
                print("Required variables: OPENAI_API_KEY")
                sys.exit(1)
            if openai_integration:
                openai_integration.print_integration_info(self.agent_card.modelName)
            return openai_integration
            
        elif provider == "anthropic":
            from a2a_mcp.common.base_agent.anthropic_integration import validate_anthropic_setup
            print("🔄 Anthropic mode enabled - validating Anthropic setup...")
            anthropic_valid, anthropic_integration = validate_anthropic_setup()
            if not anthropic_valid:
                print("❌ Anthropic setup failed. Please check your Anthropic API key in .env file.")
                print("Required variables: ANTHROPIC_API_KEY")
                sys.exit(1)
            if anthropic_integration:
                anthropic_integration.print_integration_info(self.agent_card.modelName)
            return anthropic_integration
            
        elif provider == "google":
            from a2a_mcp.common.base_agent.google_integration import validate_google_setup
            print("🔄 Google mode enabled - validating Google API setup...")
            google_valid, google_integration = validate_google_setup()
            if not google_valid:
                print("❌ Google setup failed. Please check your Google API key in .env file.")
                print("Required variables: GOOGLE_API_KEY")
                sys.exit(1)
            if google_integration:
                google_integration.print_integration_info(self.agent_card.modelName)
            return google_integration
            
        else:
            raise ValueError(f"❌ Unsupported provider: {provider}. Supported providers: aws, openai, anthropic, google")

    def _create_unified_agent(self):
        """Create a unified agent that works with any provider through LiteLLM."""
        # Get the LiteLLM model string from the integration
        if self.model_integration:
            litellm_model = self.model_integration.get_model(self.agent_card.modelName)
        else:
            litellm_model = self.agent_card.modelName
        
        # Create the unified agent with original agent card and separate LiteLLM model
        return A2AOpenaiAgent(
            agent_card=self.agent_card,  # Keep original agent card unchanged
            card_discovery=self.card_discovery, 
            mcp_server=self.mcp_server,
            litellm_model=litellm_model  # Pass LiteLLM model string separately
        )

    def get_agent(self):
        return self.agent

from a2a_mcp.common.base_agent.a2a_nova_agent import A2ANovaAgent
from a2a_mcp.common.base_agent.a2a_openai_agent import A2AOpenaiAgent
from a2a_mcp.common.base_agent.a2a_openai_agent_native import A2AOpenaiAgentNative
from a2a_mcp.common.types import CustomAgentCard
from a2a_mcp.common.card_discovery import A2ACardDiscovery

class A2AAgentSelector:
    def __init__(self, agent_card: CustomAgentCard, card_discovery: A2ACardDiscovery, mcp_server: list=[]):
        self.provider = agent_card.provider.organization
        self.agent_card = agent_card
        self.mcp_server = mcp_server
        self.card_discovery = card_discovery
        self.agent = self._select_agent()

    def _select_agent(self):
        if self.provider == "aws":
            return A2ANovaAgent(agent_card=self.agent_card, card_discovery=self.card_discovery, mcp_server=self.mcp_server)
        elif self.provider == "openai":
            return A2AOpenaiAgent(agent_card=self.agent_card, card_discovery=self.card_discovery, mcp_server=self.mcp_server)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def get_agent(self):
        return self.agent

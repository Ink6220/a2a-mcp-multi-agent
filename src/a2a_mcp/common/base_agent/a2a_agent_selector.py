from a2a_mcp.common.base_agent.a2a_nova_agent import A2ANovaAgent
from a2a_mcp.common.base_agent.a2a_openai_agent import A2AOpenaiAgent
from a2a_mcp.common.base_agent.a2a_openai_agent_native import A2AOpenaiAgentNative
from common.types import AgentCard

class A2AAgentSelector:
    def __init__(self, agent_card: AgentCard, mcp_server: list=[]):
        self.provider = agent_card.provider.organization
        self.agent_card = agent_card
        self.mcp_server = mcp_server
        self.agent = self._select_agent()

    def _select_agent(self):
        if self.provider == "aws":
            return A2ANovaAgent(agent_card=self.agent_card, mcp_server=self.mcp_server)
        elif self.provider == "openai":
            return A2AOpenaiAgent(agent_card=self.agent_card, mcp_server=self.mcp_server)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def get_agent(self):
        return self.agent

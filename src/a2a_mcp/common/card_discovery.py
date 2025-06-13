from a2a_mcp.common.base_mcp.filtered_mcp_server_sse import FilteredMCPServerSse
from a2a_mcp.common.types import CustomAgentCard
import time
from colorama import Fore, Style, init
import json
from typing import Tuple

class A2ACardDiscovery:
    def __init__(self,agent_card: CustomAgentCard):
        """ This class use for discover next linked agent from MCP server with filtering based on nextAgent attribute in agent_card """
        self.agent_card: CustomAgentCard = agent_card

        # The cache is always dirty at startup, so that we discovery at least once
        self._cache_dirty = True
        self.remote_agent_cards: dict[str, CustomAgentCard] = {}
        self.remote_agent_info: str | None = None

    async def discovery_agent_card(self, session: FilteredMCPServerSse) -> Tuple[dict[str, CustomAgentCard], str]:
        """ Do discovery by retrieve resource://agent_cards/list from MCP server """
        start_time = time.time()
        if self.agent_card.nextAgent == []:
            self.remote_agent_info = ""
            print(Fore.BLUE + Style.BRIGHT + "[No-Next-Agent-To-Discovery]" + Style.RESET_ALL)
            return self.remote_agent_info
        
        if self.remote_agent_info != None and not self._cache_dirty:
            print(Fore.BLUE + Style.BRIGHT + "[Discovery-Cache]:" + Style.RESET_ALL, time.time() - start_time)
            return self.remote_agent_info
        
        self._cache_dirty = False
        agent_card_list = await session.find_resource("resource://agent_cards/list")
        agent_card_json = json.loads(agent_card_list.contents[0].text)

        for card_url, card in zip(agent_card_json['agent_card_urls'], agent_card_json['agent_cards']):
            if(card['url'] in self.agent_card.nextAgent):
                self.remote_agent_cards[card['name']] = CustomAgentCard(**card)

        agent_info = []
        for ra in self.list_remote_agents():
            agent_info.append(json.dumps(ra))
        self.remote_agent_info = '\n'.join(agent_info)
        print(Fore.BLUE + Style.BRIGHT + "[Discovery]:" + Style.RESET_ALL, time.time() - start_time)
        return self.remote_agent_cards, self.remote_agent_info
    

    def list_remote_agents(self) -> list[dict]:
        """List the available remote agents you can use to delegate the task."""
        if not self.remote_agent_cards:
            return []

        remote_agent_info = []
        for card in self.remote_agent_cards.values():
            # TODO: Fix unicode escape when receive Thai character
            remote_agent_info.append(
                {"name": card.name, "description": card.description, "skill": [s.model_dump() for s in card.skills]}
            )
        return remote_agent_info
    
    def get_remote_agent_info(self) -> str:
        return self.remote_agent_info
    
    def get_remote_agent_cards(self) -> dict[str, CustomAgentCard]:
        return self.remote_agent_cards
    
    def get_remote_agent_card_by_name(self, name) -> CustomAgentCard:
        return self.remote_agent_cards[name]
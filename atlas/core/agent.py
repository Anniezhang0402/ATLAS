"""
Unified Agent Base Class
=================================================================
All ATLAS agents share this conversational base class.
It manages multi-turn conversation history and communicates with any provider
through the unified call_llm gateway.
"""

from typing import Optional, Dict, List
from .llm import call_llm

class Agent: 
    """
    Unified Agent that maintains conversation history and supports multiple
    parallel conversations identified by conversation_id.
    """

    def __init__(
        self,
        system: str = "",
        model: Optional[str] = None,
        temperature: float = 0.7,
        provider: str = "openrouter",
        api_key: Optional[str] = None,
    ):

        self.system = system 

        self.model = model 

        self.temperature = temperature

        self.provider = provider 

        self.api_key = api_key

        self.chat_histories: Dict[str, List[Dict[str, str]]] = {}

    def __call__(self, message: str, conversation_id: str = "default") -> str:
        """
        Send a message to the LLM and return its response.

        The method automatically creates and maintains conversation history
        for the specified conversation_id.
        """

        if conversation_id not in self.chat_histories:
            self.chat_histories[conversation_id] = []

            if self.system:
                self.chat_histories[conversation_id].append(
                    {"role": "system", "content": self.system}
                )
        
        self.chat_histories[conversation_id].append(
            {"role": "user", "content": message}
        )

        result = call_llm(
            prompt=message,
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            system_prompt=self.system,
            api_key=self.api_key,
            messages=self.chat_histories[conversation_id],
        )

        self.chat_histories[conversation_id].append(
            {"role": "assistant", "content": result}
        )

        return result

    def reset(self, conversation_id: Optional[str] = None) -> None:
        """
        Clear the history for one conversation or for all conversations.

        If conversation_id is None, all stored conversation histories are removed.
        Otherwise, only the specified conversation history is removed.
        """

        if conversation_id is None:
            self.chat_histories.clear()

        else:
            self.chat_histories.pop(conversation_id, None)

"""
ATLAS Base Agent
================
A conversational agent that maintains per-counterpart chat histories.

Why per-counterpart? An Annotator may talk to a user AND to a Validator within the same workflow. Each conversation needs its own history.
"""


from typing import Dict, List, Optional
from atlas.llm_client import call_llm


class Agent:
    """
    Base class for all ATLAS agents.

    Subclasses don't strictly need to inherit from this — the class itself
    is general-purpose. But subclassing makes the code more readable and
    lets us add agent-specific helpers later.
    """

    def __init__(
        self,
        system_prompt: str,
        agent_name: str = "default",
        model: Optional[str] = None,
        temperature: float = 0.0,
    ):
        """
        Args:
            system_prompt: The agent's role/instructions.
            agent_name: Key into llm_client.DEFAULT_MODELS for default model.
            model: Explicit model override (e.g. "anthropic/claude-sonnet-4.5").
            temperature: 0.0 = deterministic; 0.7 = creative.
        """
        self.system_prompt = system_prompt
        self.agent_name = agent_name
        self.model = model
        self.temperature = temperature

        # Per-counterpart chat histories.
        # Key: who we're talking to ("user", "validator", etc.)
        # Value: list of {"role", "content"} dicts
        self.chat_histories: Dict[str, List[Dict[str, str]]] = {}

    def __call__(self, message: str, counterpart_id: str = "user") -> str:
        """
        Send a message and get the agent's reply.

        Args:
            message: What to say to the agent.
            counterpart_id: Identifies which conversation this is. Use the
                            same ID across turns to maintain history.

        Returns:
            The agent's text response.
        """
        # Initialize history for new counterpart
        if counterpart_id not in self.chat_histories:
            history = []
            if self.system_prompt:
                history.append({"role": "system", "content": self.system_prompt})
            self.chat_histories[counterpart_id] = history

        # Append user message
        self.chat_histories[counterpart_id].append(
            {"role": "user", "content": message}
        )

        # Call LLM with full history
        reply = call_llm(
            user_prompt=message,  # ignored when messages= is passed
            messages=self.chat_histories[counterpart_id],
            agent=self.agent_name,
            model=self.model,
            temperature=self.temperature,
        )

        # Defensive: detect empty replies (content filter, max_tokens, etc.)
        if not reply or not reply.strip():
            raise ValueError(
                f"Agent '{self.agent_name}' got empty reply from LLM. "
                f"Likely causes: content filter, hit max_tokens, or upstream error. "
                f"Try a different model or simplify the prompt."
            )

        # Append assistant reply to history
        self.chat_histories[counterpart_id].append(
            {"role": "assistant", "content": reply}
        )

        return reply

    def reset(self, counterpart_id: Optional[str] = None):
        """Wipe history for one counterpart, or all if None."""
        if counterpart_id is None:
            self.chat_histories.clear()
        else:
            self.chat_histories.pop(counterpart_id, None)

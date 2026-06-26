"""
Design goal:
Provide a single interface that abstracts away the differences among
OpenAI, Anthropic, OpenRouter, and custom OpenAI-compatible endpoints.
"""

import os
from typing import Optional, Dict, Any, List

_ENV_KEYS = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}

_DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "anthropic": "claude-sonnet-4-6",
    "openrouter": "anthropic/claude-sonnet-4.6",
}

def _resolve_api_key(provider: str, api_key: Optional[str]) -> str:
    """
    Resolve the API key using the following priority:

        Explicitly provided API key
            >
        Environment variable
    """

    if api_key:
        return api_key

    if provider.startswith("http"):
        key = os.environ.get("CUSTOM_API_KEY")

        if key:
            return key

        raise ValueError(
            "Custom endpoints require CUSTOM_API_KEY"
            "or an explicitly provided api_key."
        )

    env_var = _ENV_KEYS.get(provider)

    key = os.environ.get(env_var) if env_var else None

    if not key:
        raise ValueError(
            f"API key for provider '{provider}' was not found. "
            f"Please set environment variable {env_var} "
            f"or provide api_key explicitly."
        )

    return key

def call_llm(
    prompt: str,
    provider: str = "openrouter",
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    system_prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Call an arbitrary LLM provider and return plain text.

    Args:
        prompt:
            User input used when messages is not provided.

        provider:
            "openai", "anthropic", "openrouter",
            or a custom OpenAI-compatible HTTP endpoint.

        model:
            Model name.
            Uses the provider's default model if None.

        api_key:
            Reads from environment variables if None.

        temperature: 
            Sampling temperature.

        max_tokens:
            Maximum number of generated tokens.

        system_prompt:
            System prompt.

        messages:
            Complete conversation history.
            Takes priority over prompt.

    Returns:
        Generated text from the model.
    """

    provider = provider.lower()

    is_custom = provider.startswith("http")

    if not model and not is_custom:
        model = _DEFAULT_MODELS.get(provider)

    if not model:
        raise ValueError(
            f"A model must be specified for provider={provider}."
        )

    key = _resolve_api_key(provider, api_key)

    if messages is None:
        
        messages = []

        if system_prompt:
            messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )

        messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

    # ==========================================================
    # Anthropic
    # ==========================================================

    if provider == "anthropic":

        import anthropic 

        client = anthropic.Anthropic(api_key=key)

        #与openai不同，sys prompt不在messages中，而是单独作为system传递

        sys = system_prompt or ""

        msgs = [
            m 
            for m in messages 
            if m["role"] != "system"
        ]

        if not sys:
            sys = next(
                (
                    m["content"]
                    for m in messages
                    if m["role"] == "system"
                ),
                "",
            )

        resp = client.messages.create(
            model=model,
            system=sys,
            messages=msgs,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        text = resp.content[0].text if resp.content else ""

        return _guard_empty(text, provider, model)


    # ==========================================================
    # OpenAI / OpenRouter / Custom Endpoint
    # ==========================================================
    import openai
    
    if provider == "openai":
        
        client = openai.OpenAI(
            api_key=key,
        )
    
    elif provider == "openrouter":

        client = openai.OpenAI(
            api_key=key,
            base_url="https://openrouter.ai/api/v1",
        )

    else:

        client = openai.OpenAI(
            api_key=key,
            base_url=provider,
        )

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    text = resp.choices[0].message.content
    
    return _guard_empty(text, provider, model)


def _guard_empty(
    text: Optional[str],
    provider: str,
    model: str,
) -> str:
    """
    Defensive validation against empty model responses.
    """

    if (
        text is None
        or not isinstance(text, str)
        or text.strip() == ""
    ):
        raise ValueError(
            f"LLM returned an empty response "
            f"(provider={provider}, model={model}).\n"
            f"Possible causes:\n"
            f"  - Safety or content filtering\n"
            f"  - Tool/function calling instead of text generation\n"
            f"  - Non-standard provider payload\n"
            f"  - max_tokens reached before any text was generated\n"
            f"Suggested actions: try another model, simplify the input, or retry."
        )

    return text
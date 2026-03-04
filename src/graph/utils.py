import os
from pydantic import SecretStr
from langchain_openai import ChatOpenAI

def get_openrouter_model(
    model_name: str, 
    temperature=None, 
    api_key: SecretStr | str | None = None,
    stream_usage: bool = False
) -> ChatOpenAI:
    """
    Initializes a `ChatOpenAI` object with base url redirected to OpenRouter.
    
    Args:
        model_name: The model identifier (e.g., "openai/gpt-4", "anthropic/claude-sonnet-4")
        temperature: Optional temperature setting
        api_key: Optional user-provided API key. If None, uses OPENROUTER_API_KEY from env
        stream_usage: Whether to stream token usage metadata (for token counting)
    
    Returns:
        ChatOpenAI instance configured for OpenRouter
    """
    # Use provided API key or fall back to environment variable
    if api_key is None:
        api_key = SecretStr(os.getenv("OPENROUTER_API_KEY"))
    elif isinstance(api_key, str):
        api_key = SecretStr(api_key)
    
    model = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        temperature=temperature,
        stream_usage=stream_usage
    )

    return model
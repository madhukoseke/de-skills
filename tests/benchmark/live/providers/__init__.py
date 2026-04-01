"""Provider registry for live benchmark transports."""

from . import anthropic, gemini, openai


REGISTRY = {
    "openai": openai,
    "anthropic": anthropic,
    "gemini": gemini,
}


def get_provider(name: str):
    provider = REGISTRY.get(name)
    if provider is None:
        raise KeyError(name)
    return provider

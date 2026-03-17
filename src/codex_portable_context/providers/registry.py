"""Small provider adapter registry."""

from __future__ import annotations

from codex_portable_context.providers.base import SessionProviderAdapter
from codex_portable_context.providers.codex import CodexSessionAdapter

_ADAPTERS: dict[str, SessionProviderAdapter] = {
    "codex": CodexSessionAdapter(),
}


def get_provider_adapter(provider_id: str) -> SessionProviderAdapter:
    """Return the registered provider adapter or raise a clear error."""

    adapter = _ADAPTERS.get(provider_id)
    if adapter is None:
        supported = ", ".join(sorted(_ADAPTERS))
        raise ValueError(
            f"Unknown provider adapter: {provider_id}. "
            f"Supported providers: {supported}"
        )
    return adapter


def registered_provider_ids() -> list[str]:
    """Return the stable provider ids known to the registry."""

    return sorted(_ADAPTERS)

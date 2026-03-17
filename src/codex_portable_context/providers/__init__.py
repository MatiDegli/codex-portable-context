"""Provider adapters for normalized session portability."""

from .base import (
    ProviderCapabilities,
    ProviderSessionDescriptor,
    ProviderSourceContext,
    SessionProviderAdapter,
)
from .registry import get_provider_adapter, registered_provider_ids

__all__ = [
    "ProviderCapabilities",
    "ProviderSessionDescriptor",
    "ProviderSourceContext",
    "SessionProviderAdapter",
    "get_provider_adapter",
    "registered_provider_ids",
]

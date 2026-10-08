"""Cloud provider registry for ontology adapters."""

from __future__ import annotations

from collections.abc import Callable

from wontology.ontology.provider import OntologyProviderAdapter


_ADAPTERS: dict[str, Callable[[], OntologyProviderAdapter]] = {}


def register_ontology_adapter(
    provider: str, factory: Callable[[], OntologyProviderAdapter]
) -> None:
    _ADAPTERS[provider.lower()] = factory


def get_ontology_adapter(provider: str) -> OntologyProviderAdapter:
    factory = _ADAPTERS.get(provider.lower())
    if factory is None:
        raise ValueError(
            f"No ontology adapter registered for {provider!r}. "
            f"Supported providers: {sorted(_ADAPTERS)}"
        )
    return factory()


def supported_ontology_providers() -> list[str]:
    return sorted(_ADAPTERS)

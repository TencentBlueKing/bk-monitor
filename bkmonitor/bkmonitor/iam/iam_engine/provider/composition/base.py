"""Monitor compatibility contract; shared engine owns decision composition."""

from abc import ABC, abstractmethod

from ...core.exceptions import ProviderNotFound


class CompositionPolicy(ABC):
    def __init__(self, providers):
        if not providers:
            raise ValueError("CompositionPolicy requires at least one provider")
        self.providers = list(providers)

    def get_provider(self, name):
        for provider in self.providers:
            if provider.name == name:
                return provider
        raise ProviderNotFound(f"Provider {name!r} not found")

    @abstractmethod
    def is_allowed(self, request):
        """Return the shared migration decision as a bool."""

    @abstractmethod
    def batch_by_resource(self, request):
        """Adapt a resource batch to the shared engine."""

    @abstractmethod
    def batch_by_action(self, request):
        """Adapt an action batch to the shared engine."""

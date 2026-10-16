"""One mode snapshot and convergence lifecycle for both products."""

from collections.abc import Callable, Mapping
from contextlib import nullcontext

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.error_summary import sanitize_error_summary


class ModelSyncError(RuntimeError):
    """A selected model could not converge; deployment/CLI must fail."""


class ModelSyncService:
    def __init__(self, mode_provider, factories: Mapping[AuthMode, Callable], *, lock_factory=nullcontext):
        self.mode_provider = mode_provider
        self.factories = factories
        self.lock_factory = lock_factory

    def run(self, *, apply=False):
        mode = self.mode_provider.get_mode()
        plans = {}
        with self.lock_factory() if apply else nullcontext():
            for target in DEFAULT_DUAL_STACK.modes_for(mode):
                try:
                    migrator = self.factories[target]()
                    plans[target.value] = migrator.migrate(dry_run=not apply)
                except Exception as error:
                    raise ModelSyncError(
                        f"IAM {target.value} model sync failed: {sanitize_error_summary(error)}"
                    ) from error
        return mode, plans

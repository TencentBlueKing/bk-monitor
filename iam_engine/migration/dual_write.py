from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from iam_engine.core.config import DEFAULT_DUAL_STACK
from iam_engine.error_summary import sanitize_error_summary
from iam_engine.provider.capabilities import AuthorizationWriter

logger = logging.getLogger("iam.dual_write")


class DualWriteGrantOrchestrator:
    """Synchronously grant each selected target once, without background recovery.

    Default best-effort calls report failures and continue the remaining targets.
    Strict calls propagate failures. The legacy return contract is preserved.
    Authorization is not transactional with local resource creation; an IAM grant
    can remain if a later business operation rolls back, as with existing V3.
    """

    def __init__(
        self,
        *,
        writers: Sequence[tuple[str, AuthorizationWriter]],
        tenant_id: str,
        grant_observer: Callable[[str, str, str], None],
    ) -> None:
        self.writers = tuple(writers)
        self.tenant_id = tenant_id
        self.grant_observer = grant_observer

    def grant_creator_action(self, application: Mapping[str, Any], *, raise_exception: bool = False) -> Any:
        grant_result = None
        for target_version, writer in self.writers:
            try:
                result = writer.grant_resource_creator_actions(application)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[IAM DualWrite] sync grant failed target_version=%s tenant_id=%s "
                    "resource_type=%s resource_id=%s error_type=%s error=%s",
                    target_version,
                    self.tenant_id,
                    application["type"],
                    application["id"],
                    type(error).__name__,
                    sanitize_error_summary(error),
                )
                self._observe(target_version, application, "failed")
                if raise_exception:
                    raise
                continue
            if target_version == DEFAULT_DUAL_STACK.legacy.value:
                grant_result = result
            logger.info(
                "[IAM DualWrite] sync grant succeeded target_version=%s tenant_id=%s resource_type=%s resource_id=%s",
                target_version,
                self.tenant_id,
                application["type"],
                application["id"],
            )
            self._observe(target_version, application, "succeeded")
        return grant_result

    def _observe(self, target_version: str, application: Mapping[str, Any], result: str) -> None:
        try:
            self.grant_observer(target_version, str(application["type"]), result)
        except Exception as error:  # pylint: disable=broad-except
            logger.exception(
                "[IAM DualWrite] grant observer failed target_version=%s result=%s error_type=%s error=%s",
                target_version,
                result,
                type(error).__name__,
                error,
            )

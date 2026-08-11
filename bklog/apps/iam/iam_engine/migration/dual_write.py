from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from django.db import transaction

from apps.iam.backends.legacy_v3 import LegacyV3GrantError
from apps.iam.backends.v4.exceptions import (
    V4ClientError,
    V4RateLimitError,
    V4ResponseError,
    V4TimeoutError,
    V4TransportError,
)
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter, PreparedAuthorizationGrant
from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository

logger = logging.getLogger("iam.dual_write")


class DualWriteGrantError(RuntimeError):
    """调用方要求严格失败语义时汇总双写错误。"""


class PersistedGrantStateError(RuntimeError):
    """目标记录当前不可执行，严格模式需要继续暴露其持久化失败状态。"""


class LeaseOwnershipLostError(RuntimeError):
    """远端调用结束前 processing lease 已被恢复或转移。"""


@dataclass(frozen=True, slots=True)
class GrantExecution:
    result: Any = None
    error: Exception | None = None


class DualWriteGrantOrchestrator:
    """先持久化、再逐目标 CAS 执行的 V3/V4 授权编排器。"""

    INTENT_VERSION = 1
    SEMANTIC_ROLE = "resource_creator"

    def __init__(
        self,
        *,
        writers: Sequence[tuple[str, AuthorizationWriter]],
        tenant_id: str,
        operator: str,
        repository: IAMAuthorizationGrantRepository | None = None,
    ) -> None:
        self.writers = tuple(writers)
        self.tenant_id = tenant_id
        self.operator = operator
        self.repository = repository or IAMAuthorizationGrantRepository()

    def grant_creator_action(self, application: Mapping[str, Any], *, raise_exception: bool = False) -> Any:
        logical_key = self.make_logical_key(application)
        records: list[tuple[str, AuthorizationWriter, IAMAuthorizationGrant]] = []

        # prepare 只构造请求，不访问远端；同一事务提交全部目标意图后，才允许任何 Worker 看见并执行。
        prepared_writers: list[tuple[str, AuthorizationWriter, PreparedAuthorizationGrant]] = []
        for target_version, writer in self.writers:
            prepared_writers.append((target_version, writer, writer.prepare_resource_creator_actions(application)))

        with transaction.atomic():
            for target_version, writer, prepared in prepared_writers:
                record = self.repository.ensure(
                    logical_key=logical_key,
                    target_version=target_version,
                    defaults=self._record_defaults(application, prepared),
                )
                records.append((target_version, writer, record))

        executions: dict[str, GrantExecution] = {}
        for target_version, writer, record in records:
            executions[target_version] = self.execute_record(record, writer)

        errors = [execution.error for execution in executions.values() if execution.error is not None]
        if executions and len(errors) == len(executions):
            logger.error(
                "[IAM DualWrite] all targets failed logical_key=%s targets=%s",
                logical_key,
                tuple(executions),
            )
        if errors and raise_exception:
            detail = "; ".join(f"{type(error).__name__}: {error}" for error in errors)
            raise DualWriteGrantError(detail) from errors[0]

        v3_execution = executions.get(IAMAuthorizationGrant.TargetVersion.V3)
        return self._restore_v3_result(v3_execution.result if v3_execution else None)

    def execute_record(self, record: IAMAuthorizationGrant, writer: AuthorizationWriter) -> GrantExecution:
        if record.state == IAMAuthorizationGrant.State.SUCCEEDED:
            return GrantExecution(result=record.result)

        lease_owner = uuid.uuid4().hex
        claimed = self.repository.claim(record.pk, lease_owner=lease_owner)
        if claimed is None:
            return self._execution_from_persisted_state(record.pk)

        prepared = PreparedAuthorizationGrant(
            payload=claimed.payload,
            role_id=claimed.role_id,
            expired_at=claimed.expired_at,
        )
        try:
            result = writer.grant_prepared(prepared)
        except Exception as error:  # pylint: disable=broad-except
            state = self.classify_failure(error)
            error_code = getattr(error, "status_code", None) or ""
            persisted, final_state = self.repository.mark_failed(
                claimed,
                lease_owner=lease_owner,
                state=state,
                error=error,
                error_code=str(error_code),
            )
            if not persisted:
                return self._execution_after_lost_lease(claimed)
            logger.warning(
                "[IAM DualWrite] logical_key=%s target=%s state=%s attempt=%s error_type=%s",
                claimed.logical_key,
                claimed.target_version,
                final_state,
                claimed.attempts,
                type(error).__name__,
            )
            return GrantExecution(error=error)

        persisted_result = self._json_value(result)
        persisted = self.repository.mark_succeeded(claimed, lease_owner=lease_owner, result=persisted_result)
        if not persisted:
            return self._execution_after_lost_lease(claimed)
        logger.info(
            "[IAM DualWrite] logical_key=%s target=%s state=%s attempt=%s",
            claimed.logical_key,
            claimed.target_version,
            IAMAuthorizationGrant.State.SUCCEEDED,
            claimed.attempts,
        )
        return GrantExecution(result=result)

    @staticmethod
    def _execution_from_persisted_state(grant_id: int) -> GrantExecution:
        """Return persisted success, otherwise preserve the current state as an explicit strict-mode error."""

        current = IAMAuthorizationGrant.objects.get(pk=grant_id)
        if current.state == IAMAuthorizationGrant.State.SUCCEEDED:
            return GrantExecution(result=current.result)
        return GrantExecution(
            error=PersistedGrantStateError(
                f"IAM grant target={current.target_version} is state={current.state} "
                f"error_type={current.last_error_type or 'none'}"
            )
        )

    def _execution_after_lost_lease(self, grant: IAMAuthorizationGrant) -> GrantExecution:
        """Re-read state after a zero-row CAS write and never report an unpersisted remote result."""

        current = IAMAuthorizationGrant.objects.get(pk=grant.pk)
        if current.state == IAMAuthorizationGrant.State.SUCCEEDED:
            return GrantExecution(result=current.result)
        error = LeaseOwnershipLostError(
            f"IAM grant target={current.target_version} lost lease ownership; current_state={current.state}"
        )
        logger.warning(
            "[IAM DualWrite] logical_key=%s target=%s state=%s attempt=%s error_type=%s",
            current.logical_key,
            current.target_version,
            current.state,
            current.attempts,
            type(error).__name__,
        )
        return GrantExecution(error=error)

    def make_logical_key(self, application: Mapping[str, Any]) -> str:
        components = (
            self.tenant_id,
            "creator_action",
            "user",
            str(application["creator"]),
            str(application["system"]),
            str(application["type"]),
            str(application["id"]),
            self.SEMANTIC_ROLE,
            str(self.INTENT_VERSION),
        )
        return hashlib.sha256("|".join(components).encode("utf-8")).hexdigest()

    def _record_defaults(
        self,
        application: Mapping[str, Any],
        prepared: PreparedAuthorizationGrant,
    ) -> dict[str, Any]:
        return {
            "grant_type": "creator_action",
            "intent_version": self.INTENT_VERSION,
            "tenant_id": self.tenant_id,
            "subject_type": "user",
            "subject_id": str(application["creator"]),
            "operator": self.operator,
            "resource_system": str(application["system"]),
            "resource_type": str(application["type"]),
            "resource_id": str(application["id"]),
            "semantic_role": self.SEMANTIC_ROLE,
            "role_id": prepared.role_id,
            "payload": self._json_value(prepared.payload),
            "expired_at": prepared.expired_at,
        }

    @staticmethod
    def classify_failure(error: Exception) -> str:
        if isinstance(error, V4TimeoutError | V4TransportError):
            return IAMAuthorizationGrant.State.UNKNOWN
        if isinstance(error, V4RateLimitError | LegacyV3GrantError):
            return IAMAuthorizationGrant.State.RETRY_WAIT
        if isinstance(error, V4ResponseError):
            return IAMAuthorizationGrant.State.FAILED_FINAL
        if isinstance(error, V4ClientError):
            status_code = error.status_code or 0
            if status_code >= 500:
                return IAMAuthorizationGrant.State.RETRY_WAIT
            if 400 <= status_code < 500:
                return IAMAuthorizationGrant.State.FAILED_FINAL
        return IAMAuthorizationGrant.State.RETRY_WAIT

    @staticmethod
    def _json_value(value: Any) -> Any:
        return json.loads(json.dumps(value, default=str))

    @staticmethod
    def _restore_v3_result(result: Any) -> Any:
        if isinstance(result, list):
            return tuple(result)
        return result

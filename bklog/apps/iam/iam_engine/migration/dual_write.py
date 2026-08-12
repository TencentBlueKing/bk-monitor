from __future__ import annotations

import hashlib
import json
import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from django.db import transaction

from apps.iam.iam_engine.provider.capabilities import (
    AuthorizationGrantState,
    AuthorizationGrantTarget,
    AuthorizationWriter,
    PreparedAuthorizationGrant,
)

logger = logging.getLogger("iam.dual_write")


class DualWriteGrantError(RuntimeError):
    """调用方要求严格失败语义时汇总双写错误。"""


class PersistedGrantStateError(RuntimeError):
    """目标记录当前不可执行，严格模式需要继续暴露其持久化失败状态。"""


class LeaseOwnershipLostError(RuntimeError):
    """远端调用结束前处理租约已被恢复或转移。"""


class AuthorizationGrantRecord(Protocol):
    """Engine 执行器所需的最小授权意图快照。"""

    pk: int
    target_version: str
    state: str
    attempts: int
    logical_key: str
    payload: Any
    role_id: str
    expired_at: int | None
    result: Any
    last_error_type: str


class AuthorizationGrantRepository(Protocol):
    """授权意图持久化协议，由业务应用注入具体实现。"""

    def ensure(
        self, *, logical_key: str, target_version: str, defaults: dict[str, Any]
    ) -> AuthorizationGrantRecord: ...

    def get(self, grant_id: int) -> AuthorizationGrantRecord: ...

    def mark_preparation_failed(self, grant: AuthorizationGrantRecord, *, error: Exception) -> bool: ...

    def claim(self, grant_id: int, *, lease_owner: str) -> AuthorizationGrantRecord | None: ...

    def mark_succeeded(
        self,
        grant: AuthorizationGrantRecord,
        *,
        lease_owner: str,
        result: Any,
    ) -> bool: ...

    def mark_failed(
        self,
        grant: AuthorizationGrantRecord,
        *,
        lease_owner: str,
        state: str,
        error: Exception,
        error_code: str = "",
    ) -> tuple[bool, str]: ...


@dataclass(frozen=True, slots=True)
class GrantExecution:
    result: Any = None
    error: Exception | None = None


@dataclass(frozen=True, slots=True)
class _PreparedTarget:
    target_version: str
    writer: AuthorizationWriter
    prepared: PreparedAuthorizationGrant
    preparation_error: Exception | None = None


class AuthorizationGrantExecutor:
    """执行一条已持久化意图，不参与创建和事务提交时机。"""

    def __init__(self, repository: AuthorizationGrantRepository) -> None:
        self.repository = repository

    def execute(self, record: AuthorizationGrantRecord, writer: AuthorizationWriter) -> GrantExecution:
        if record.state == AuthorizationGrantState.SUCCEEDED.value:
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
            state = writer.classify_failure(error).value
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

        persisted_result = _json_value(result)
        persisted = self.repository.mark_succeeded(claimed, lease_owner=lease_owner, result=persisted_result)
        if not persisted:
            return self._execution_after_lost_lease(claimed)
        logger.info(
            "[IAM DualWrite] logical_key=%s target=%s state=%s attempt=%s",
            claimed.logical_key,
            claimed.target_version,
            AuthorizationGrantState.SUCCEEDED.value,
            claimed.attempts,
        )
        return GrantExecution(result=result)

    def _execution_from_persisted_state(self, grant_id: int) -> GrantExecution:
        """返回已持久化的成功结果；否则将当前状态转换为严格模式可识别的错误。"""

        current = self.repository.get(grant_id)
        if current.state == AuthorizationGrantState.SUCCEEDED.value:
            return GrantExecution(result=current.result)
        return GrantExecution(
            error=PersistedGrantStateError(
                f"IAM grant target={current.target_version} is state={current.state} "
                f"error_type={current.last_error_type or 'none'}"
            )
        )

    def _execution_after_lost_lease(self, grant: AuthorizationGrantRecord) -> GrantExecution:
        """CAS 回写命中 0 行后重新读取状态，禁止报告未持久化的远端结果。"""

        current = self.repository.get(grant.pk)
        if current.state == AuthorizationGrantState.SUCCEEDED.value:
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


class DualWriteGrantOrchestrator:
    """持久化 V3/V4 意图，并在最外层事务提交后执行远端授权。"""

    INTENT_VERSION = 1
    SEMANTIC_ROLE = "resource_creator"

    def __init__(
        self,
        *,
        writers: Sequence[tuple[str, AuthorizationWriter]],
        tenant_id: str,
        operator: str,
        repository: AuthorizationGrantRepository,
        executor: AuthorizationGrantExecutor | None = None,
    ) -> None:
        self.writers = tuple(writers)
        self.tenant_id = tenant_id
        self.operator = operator
        self.repository = repository
        self.executor = executor or AuthorizationGrantExecutor(repository)

    def grant_creator_action(self, application: Mapping[str, Any], *, raise_exception: bool = False) -> Any:
        """创建授权意图并安排提交后执行。

        调用方已经位于事务中时，本方法只登记提交回调并返回 ``None``；远端结果和严格模式异常
        会在最外层事务提交后产生。当前生产调用点均忽略返回值且不启用严格模式。
        """

        logical_key = self.make_logical_key(application)
        targets = [self._prepare_target(target_version, writer, application) for target_version, writer in self.writers]
        records: list[tuple[_PreparedTarget, AuthorizationGrantRecord, bool]] = []
        executions: dict[str, GrantExecution] = {}

        with transaction.atomic():
            for target in targets:
                record = self.repository.ensure(
                    logical_key=logical_key,
                    target_version=target.target_version,
                    defaults=self._record_defaults(application, target.prepared),
                )
                preparation_failed = False
                if target.preparation_error is not None:
                    preparation_failed = self.repository.mark_preparation_failed(record, error=target.preparation_error)
                records.append((target, record, preparation_failed))

            # Django 会把回调提升到最外层事务；业务回滚时，意图和远端调用都会一起取消。
            transaction.on_commit(
                lambda: self._execute_after_commit(
                    logical_key,
                    records,
                    executions,
                    raise_exception=raise_exception,
                )
            )

        v3_execution = executions.get(AuthorizationGrantTarget.V3.value)
        return _restore_v3_result(v3_execution.result if v3_execution else None)

    @staticmethod
    def _prepare_target(
        target_version: str,
        writer: AuthorizationWriter,
        application: Mapping[str, Any],
    ) -> _PreparedTarget:
        try:
            prepared = writer.prepare_resource_creator_actions(application)
        except Exception as error:  # pylint: disable=broad-except
            # 本地请求构造失败同样需要留下审计记录，但没有可安全补偿的冻结载荷。
            return _PreparedTarget(target_version, writer, PreparedAuthorizationGrant(payload={}), error)
        return _PreparedTarget(target_version, writer, prepared)

    def _execute_after_commit(
        self,
        logical_key: str,
        records: Sequence[tuple[_PreparedTarget, AuthorizationGrantRecord, bool]],
        executions: dict[str, GrantExecution],
        *,
        raise_exception: bool,
    ) -> None:
        for target, record, preparation_failed in records:
            if preparation_failed:
                executions[target.target_version] = GrantExecution(error=target.preparation_error)
            else:
                executions[target.target_version] = self.executor.execute(record, target.writer)

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
            "payload": _json_value(prepared.payload),
            "expired_at": prepared.expired_at,
        }


def _json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _restore_v3_result(result: Any) -> Any:
    if isinstance(result, list):
        return tuple(result)
    return result

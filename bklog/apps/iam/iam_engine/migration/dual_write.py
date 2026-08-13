from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from django.db import transaction

from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter

logger = logging.getLogger("iam.dual_write")


class DualWriteGrantOrchestrator:
    """V3 创建者授权同步直写，V4 授权在最外层事务提交后交给可重试任务。

    V3 保持同步是为了让用户创建资源后立刻拥有权限；V4 走提交后异步投递，既避免在事务里发
    HTTP，也保证业务回滚时不会给不存在的资源授权。
    """

    def __init__(
        self,
        *,
        writers: Sequence[tuple[str, AuthorizationWriter]],
        tenant_id: str,
        operator: str,
        dispatch_v4_grant: Callable[[dict[str, Any]], None],
    ) -> None:
        self.writers = tuple(writers)
        self.tenant_id = tenant_id
        self.operator = operator
        self.dispatch_v4_grant = dispatch_v4_grant

    def grant_creator_action(self, application: Mapping[str, Any], *, raise_exception: bool = False) -> Any:
        """同步完成 V3 授权并返回其结果，同时安排 V4 授权在事务提交后投递。"""

        grant_result = None
        for target_version, writer in self.writers:
            if target_version == AuthMode.V4.value:
                self._schedule_v4_grant(writer, application, raise_exception=raise_exception)
                continue

            try:
                result = writer.grant_resource_creator_actions(application)
            except Exception as error:  # pylint: disable=broad-except
                logger.exception(
                    "[IAM DualWrite] sync grant failed target_version=%s %s error_type=%s error=%s",
                    target_version,
                    _describe(application, self.tenant_id),
                    type(error).__name__,
                    error,
                )
                if raise_exception:
                    raise
                continue

            if target_version == AuthMode.V3.value:
                grant_result = result
            logger.info(
                "[IAM DualWrite] sync grant succeeded target_version=%s %s result=%s",
                target_version,
                _describe(application, self.tenant_id),
                result,
            )

        return grant_result

    def _schedule_v4_grant(
        self,
        writer: AuthorizationWriter,
        application: Mapping[str, Any],
        *,
        raise_exception: bool,
    ) -> None:
        try:
            prepared = writer.prepare_resource_creator_actions(application)
        except Exception as error:  # pylint: disable=broad-except
            # 请求构造失败没有可安全重放的载荷，重试也不会成功，直接按终态处理。
            logger.exception(
                "[IAM DualWrite] v4 prepare failed %s error_type=%s error=%s",
                _describe(application, self.tenant_id),
                type(error).__name__,
                error,
            )
            if raise_exception:
                raise
            return

        task_kwargs = {
            "tenant_id": self.tenant_id,
            "operator": self.operator,
            # 冻结请求，重试原样重放，尤其不能让 expired_at 随重试时间漂移。
            "payload": _json_value(prepared.payload),
            "role_id": prepared.role_id,
            "expired_at": prepared.expired_at,
            "resource_meta": _resource_meta(application),
        }
        # Django 会把回调提升到最外层事务；业务回滚时任务不投递，不会给不存在的资源授权。
        transaction.on_commit(lambda: self._dispatch_after_commit(task_kwargs))

    def _dispatch_after_commit(self, task_kwargs: dict[str, Any]) -> None:
        try:
            self.dispatch_v4_grant(task_kwargs)
        except Exception as error:  # pylint: disable=broad-except
            # 提交后回调抛错会打断同批次其他回调，投递失败只能靠这条日志发现。
            logger.exception(
                "[IAM DualWrite] v4 dispatch failed tenant_id=%s resource=%s error_type=%s error=%s",
                task_kwargs["tenant_id"],
                task_kwargs["resource_meta"],
                type(error).__name__,
                error,
            )


def _resource_meta(application: Mapping[str, Any]) -> dict[str, str]:
    return {
        "subject_id": str(application["creator"]),
        "resource_system": str(application["system"]),
        "resource_type": str(application["type"]),
        "resource_id": str(application["id"]),
    }


def _describe(application: Mapping[str, Any], tenant_id: str) -> str:
    meta = _resource_meta(application)
    return (
        f"tenant_id={tenant_id} subject_id={meta['subject_id']} resource_system={meta['resource_system']} "
        f"resource_type={meta['resource_type']} resource_id={meta['resource_id']}"
    )


def _json_value(value: Any) -> Any:
    """确保冻结载荷可以被 Celery 序列化后原样重放。"""

    return json.loads(json.dumps(value, default=str))

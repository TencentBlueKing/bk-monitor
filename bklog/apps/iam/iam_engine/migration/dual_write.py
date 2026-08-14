from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from django.db import transaction

from apps.iam.error_summary import sanitize_error_summary
from apps.iam.iam_engine.core.config import AuthMode
from apps.iam.iam_engine.provider.capabilities import AuthorizationWriter

logger = logging.getLogger("iam.dual_write")


class DualWriteGrantOrchestrator:
    """V3 与 V4 创建者授权都在调用线程内同步直写，V4 失败才回落到可重试任务。

    两侧都同步是为了让用户创建资源后立刻拥有权限：V4 或 UNION 模式下新资源的权限来自 V4，
    如果首次授权就走异步，从创建成功到 worker 取到任务之间存在一个访问自己新资源被拒的窗口。

    这里明确接受两项代价，因为调用方（如 ``IndexSetHandler.create``）都带 ``transaction.atomic``：

    - 同步授权在事务内发 HTTP，最长按 ``BK_IAM_V4_TIMEOUT`` 拉长事务与连接的持有时间。
    - 同步成功后业务再回滚，V4 会残留一条指向不存在资源的授权，且当前没有回收路径。这与 V3
      既有行为一致，不是本层新引入的问题，但确实是双写放大后的风险。

    失败回落仍然登记在提交回调上：业务回滚时任务不投递，不会给不存在的资源补授权。

    V4 侧的交付契约是「同步优先 + 尽力重试 + 结构化日志」，不是失败补偿：本模块刻意不落授权意图
    表、不做 outbox、也没有周期扫描重投。剩余的丢失窗口需要同步失败与后续投递或重试也失败同时
    发生，只留下 ``[IAM DualWrite]`` / ``[IAM V4 Grant]`` 日志，发现靠日志告警，恢复靠人工按日志中
    的 tenant_id、resource_meta 与 role_id 重新触发一次创建者授权。

    之所以能接受这个窗口：V4 ``add_authorization`` 重复授予同一主体、角色和资源是安全的，重放代价
    很低；而为自动补偿引入状态表、租约和扫描任务的复杂度，超过了当前创建者授权场景的收益。契约若要
    升级为真正的补偿，需要先补回持久化的冻结请求与失败状态，不能只在这一层加重试。
    """

    def __init__(
        self,
        *,
        writers: Sequence[tuple[str, AuthorizationWriter]],
        tenant_id: str,
        operator: str,
        dispatch_v4_grant: Callable[[dict[str, Any]], None],
        grant_observer: Callable[[str, str, str], None],
    ) -> None:
        """grant_observer 按 (target_version, resource_type, result) 接收每个目标的双写结果。

        观测实现由调用方注入，本层不依赖具体的指标或日志设施。
        """
        self.writers = tuple(writers)
        self.tenant_id = tenant_id
        self.operator = operator
        self.dispatch_v4_grant = dispatch_v4_grant
        self.grant_observer = grant_observer

    def grant_creator_action(self, application: Mapping[str, Any], *, raise_exception: bool = False) -> Any:
        """同步完成 V3 与 V4 授权并返回 V3 结果，V4 同步失败时回落到提交后的重试任务。"""

        grant_result = None
        for target_version, writer in self.writers:
            if target_version == AuthMode.V4.value:
                self._grant_v4_with_fallback(writer, application, raise_exception=raise_exception)
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
                self._observe(target_version, application, "failed")
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
            self._observe(target_version, application, "succeeded")

        return grant_result

    def _grant_v4_with_fallback(
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
            self._observe(AuthMode.V4.value, application, "prepare_failed")
            if raise_exception:
                raise
            return

        task_kwargs = {
            "tenant_id": self.tenant_id,
            "operator": self.operator,
            # 冻结请求，回落重试原样重放，尤其不能让 expired_at 随重试时间漂移。
            "payload": _json_value(prepared.payload),
            "role_id": prepared.role_id,
            "expired_at": prepared.expired_at,
            "resource_meta": _resource_meta(application),
        }

        try:
            writer.grant_prepared(prepared)
        except Exception as error:  # pylint: disable=broad-except
            # 这里不做失败分类，统一交给重试任务判定：分类规则只应有一个出处，代价是终态失败会在
            # worker 里多发一次注定失败的请求。同步失败也不上抛，否则回落重试就失去意义。
            logger.warning(
                "[IAM DualWrite] v4 sync grant failed, falling back to retry task %s error_type=%s error=%s",
                _describe(application, self.tenant_id),
                type(error).__name__,
                sanitize_error_summary(error),
            )
            # Django 会把回调提升到最外层事务；业务回滚时任务不投递，不会给不存在的资源授权。
            transaction.on_commit(lambda: self._dispatch_after_commit(task_kwargs))
            return

        logger.info("[IAM DualWrite] v4 sync grant succeeded %s", _describe(application, self.tenant_id))
        self._observe(AuthMode.V4.value, application, "succeeded")

    def _dispatch_after_commit(self, task_kwargs: dict[str, Any]) -> None:
        resource_type = task_kwargs["resource_meta"]["resource_type"]
        try:
            self.dispatch_v4_grant(task_kwargs)
        except Exception as error:  # pylint: disable=broad-except
            # 提交后回调抛错会打断同批次其他回调，所以这里必须吞掉；按类文档的尽力投递契约，
            # 投递失败只能靠这条日志被发现和人工重放。
            logger.exception(
                "[IAM DualWrite] v4 dispatch failed tenant_id=%s resource=%s error_type=%s error=%s",
                task_kwargs["tenant_id"],
                task_kwargs["resource_meta"],
                type(error).__name__,
                error,
            )
            self.grant_observer(AuthMode.V4.value, resource_type, "dispatch_failed")
            return

        # 同步失败的次数由回落投递结果反推：投递成功计 fallback_dispatched，失败计 dispatch_failed。
        self.grant_observer(AuthMode.V4.value, resource_type, "fallback_dispatched")

    def _observe(self, target_version: str, application: Mapping[str, Any], result: str) -> None:
        self.grant_observer(target_version, _resource_meta(application)["resource_type"], result)


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

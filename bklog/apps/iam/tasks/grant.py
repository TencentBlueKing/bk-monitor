from __future__ import annotations

import logging
from typing import Any

from blueapps.core.celery.celery import app

from apps.iam.backends.v4.writer import V4AuthorizationWriter
from apps.iam.error_summary import sanitize_error_summary
from apps.iam.grant_config import AuthorizationGrantConfig, retry_countdown_seconds
from apps.iam.iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant

logger = logging.getLogger("iam.v4.grant")


def dispatch_v4_creator_grant(task_kwargs: dict[str, Any]) -> None:
    """把冻结的 V4 创建者授权请求投递给重试任务。"""

    grant_v4_creator_action.apply_async(kwargs=task_kwargs)


# max_retries 交给 BK_IAM_GRANT_MAX_ATTEMPTS 控制，这里不能提前被 Celery 的默认上限截断。
@app.task(bind=True, ignore_result=True, max_retries=None)
def grant_v4_creator_action(
    self,
    *,
    tenant_id: str,
    operator: str,
    payload: list[dict[str, Any]],
    role_id: str,
    expired_at: int | None,
    resource_meta: dict[str, str],
) -> None:
    """按冻结请求执行 IAM V4 创建者授权，可重试失败按指数退避重投。

    payload 与 expired_at 由投递方一次算定，重试必须原样重放：add_authorization 没有幂等键，
    重复授予同一主体、角色和资源可以接受，但重算 expired_at 会让有效期随重试时间漂移。

    重试耗尽或终态失败后本任务不再做任何补偿，这是 DualWriteGrantOrchestrator 文档里说明的尽力投递
    契约：没有失败状态表也没有扫描重投，该次 V4 授权就此缺失，只能靠下面的 error 日志发现并人工重放。
    """

    max_attempts = AuthorizationGrantConfig.from_settings().max_attempts
    attempt = self.request.retries + 1
    context = (
        f"tenant_id={tenant_id} subject_id={resource_meta.get('subject_id')} "
        f"resource_system={resource_meta.get('resource_system')} "
        f"resource_type={resource_meta.get('resource_type')} resource_id={resource_meta.get('resource_id')} "
        f"role_id={role_id} attempt={attempt} max_attempts={max_attempts}"
    )

    try:
        writer = V4AuthorizationWriter.from_settings(username=operator, bk_tenant_id=tenant_id)
        writer.grant_prepared(PreparedAuthorizationGrant(payload=payload, role_id=role_id, expired_at=expired_at))
    except Exception as error:  # pylint: disable=broad-except
        failure_kind = V4AuthorizationWriter.classify_failure(error)
        detail = (
            f"{context} failure_kind={failure_kind.value} error_type={type(error).__name__} "
            f"error_code={getattr(error, 'status_code', None) or ''} error={sanitize_error_summary(error)}"
        )
        if failure_kind is GrantFailureKind.FAILED_FINAL or attempt >= max_attempts:
            # 表已经去掉，终态只剩这条日志可供检索和告警，前缀必须稳定。
            logger.error("[IAM V4 Grant] final failure %s", detail)
            return
        logger.warning("[IAM V4 Grant] retryable failure %s", detail)
        raise self.retry(exc=error, countdown=retry_countdown_seconds(self.request.retries))

    logger.info("[IAM V4 Grant] succeeded %s", context)

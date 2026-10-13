"""Shared frozen-grant execution; products only supply their Celery and writer adapters."""

import json

from iam_engine.core.config import AuthMode, DEFAULT_DUAL_STACK
from iam_engine.error_summary import sanitize_error_summary
from iam_engine.exceptions import ProviderError, ProviderUnavailable
from iam_engine.migration.grant_config import AuthorizationGrantConfig, retry_countdown_seconds
from iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant
from iam_engine.v4.exceptions import (
    V4ClientError, V4RateLimitError, V4ResponseError, V4TimeoutError, V4TransportError,
)


def classify_grant_failure(error):
    if isinstance(error, V4TimeoutError | V4TransportError):
        return GrantFailureKind.UNKNOWN
    if isinstance(error, V4RateLimitError):
        return GrantFailureKind.RETRY_WAIT
    if isinstance(error, V4ResponseError | ValueError):
        return GrantFailureKind.FAILED_FINAL
    if isinstance(error, V4ClientError):
        code = error.status_code or 0
        if code >= 500:
            return GrantFailureKind.RETRY_WAIT
        if 400 <= code < 500:
            return GrantFailureKind.FAILED_FINAL
    if isinstance(error, ProviderUnavailable):
        code = getattr(error, "code", 0)
        if code == 429 or isinstance(code, int) and code >= 500:
            return GrantFailureKind.RETRY_WAIT
        if isinstance(code, int) and 400 <= code < 500:
            return GrantFailureKind.FAILED_FINAL
        return GrantFailureKind.UNKNOWN
    if isinstance(error, ProviderError):
        return GrantFailureKind.FAILED_FINAL
    return GrantFailureKind.RETRY_WAIT


def dispatch_v4_grant(task, task_kwargs, *, mode_loader, logger):
    if AuthMode.V4 not in DEFAULT_DUAL_STACK.modes_for(mode_loader()):
        logger.info("[IAM V4 Grant] dispatch suppressed: V4 is disabled")
        return
    task.apply_async(kwargs=task_kwargs)


def execute_frozen_v4_grant(
    task, *, writer_factory, mode_loader, logger, tenant_id, operator,
    payload, role_id, expired_at, resource_meta,
):
    """Replay exactly the frozen payload, subject to the current mode.

    Attempts count only background deliveries, not the initial synchronous
    attempt. Exhaustion is logged, with no persisted compensation/outbox.
    No expiry is recomputed during retry.
    """
    max_attempts = AuthorizationGrantConfig.from_settings().max_attempts
    attempt = task.request.retries + 1
    context = json.dumps(
        {"tenant_id": str(tenant_id)[:80], "resource": resource_meta, "role_id": str(role_id)[:80]},
        ensure_ascii=True, default=str,
    )
    context = f"meta={context} attempt={attempt} max_attempts={max_attempts}"
    try:
        if AuthMode.V4 not in DEFAULT_DUAL_STACK.modes_for(mode_loader()):
            logger.info("[IAM V4 Grant] suppressed: V4 is disabled %s", context)
            return
        writer = writer_factory(tenant_id, operator)
        writer.grant_prepared(PreparedAuthorizationGrant(payload, role_id, expired_at))
    except Exception as error:
        failure = classify_grant_failure(error)
        code = getattr(error, "status_code", None) or getattr(error, "code", None) or ""
        detail = f"{context} failure_kind={failure.value} error_type={type(error).__name__} error_code={code} error={sanitize_error_summary(error)}"
        if failure is GrantFailureKind.FAILED_FINAL or attempt >= max_attempts:
            logger.error("[IAM V4 Grant] final failure %s", detail)
            return
        logger.warning("[IAM V4 Grant] retryable failure %s", detail)
        raise task.retry(exc=error, countdown=retry_countdown_seconds(task.request.retries))
    logger.info("[IAM V4 Grant] succeeded %s", context)

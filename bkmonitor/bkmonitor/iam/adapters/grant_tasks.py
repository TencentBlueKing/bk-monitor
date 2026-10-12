"""Celery delivery adapter for frozen V4 grants; no persisted compensation/outbox."""

import logging
import json

from celery import shared_task

from iam_engine.error_summary import sanitize_error_summary
from iam_engine.migration.grant_config import AuthorizationGrantConfig, retry_countdown_seconds
from iam_engine.provider.capabilities import GrantFailureKind, PreparedAuthorizationGrant

from .authorization import MonitorAuthorizationWriter

logger = logging.getLogger("iam.v4.grant")


def dispatch_v4_creator_grant(task_kwargs):
    grant_v4_creator_action.apply_async(kwargs=task_kwargs)


@shared_task(bind=True, ignore_result=True, max_retries=None)
def grant_v4_creator_action(self, *, tenant_id, operator, payload, role_id, expired_at, resource_meta):
    from ..iam_engine.django.facade import get_framework

    max_attempts = AuthorizationGrantConfig.from_settings().max_attempts
    metadata = json.dumps(
        {"tenant_id": str(tenant_id)[:80], "resource": resource_meta, "role_id": str(role_id)[:80]},
        ensure_ascii=True,
        default=str,
    )
    try:
        provider = get_framework().get_provider("v4")
        writer = MonitorAuthorizationWriter(provider, tenant_id=tenant_id, operator=operator)
        writer.grant_prepared(PreparedAuthorizationGrant(payload, role_id, expired_at))
    except Exception as error:
        failure = MonitorAuthorizationWriter.classify_failure(error)
        logger.warning(
            "[IAM V4 Grant] meta=%s attempt=%s failure_kind=%s error=%s",
            metadata,
            self.request.retries + 1,
            failure.value,
            sanitize_error_summary(error),
        )
        if failure is GrantFailureKind.FAILED_FINAL or self.request.retries + 1 >= max_attempts:
            logger.error(
                "[IAM V4 Grant] final failure meta=%s attempt=%s max_attempts=%s failure_kind=%s",
                metadata,
                self.request.retries + 1,
                max_attempts,
                failure.value,
            )
            return
        raise self.retry(exc=error, countdown=retry_countdown_seconds(self.request.retries))
    logger.info("[IAM V4 Grant] succeeded meta=%s", metadata)

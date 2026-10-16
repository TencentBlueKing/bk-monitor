"""Product Celery binding; execution, mode guards and retry policy are shared."""

import logging
from celery import Task, shared_task
from bkmonitor.iam.backends.v4.writer import V4AuthorizationWriter
from bkmonitor.iam.mode import get_mode_provider
from iam_engine.migration.grant_retry import dispatch_v4_grant, execute_frozen_v4_grant

logger = logging.getLogger("iam.v4.grant")


class QueuedIAMGrantTask(Task):
    """IAM compensation must reach a worker even in an eager API process."""

    def apply_async(self, args=None, kwargs=None, **options):
        if self.app.conf.task_always_eager:
            options.setdefault("queue", self.queue)
            options.setdefault("serializer", self.serializer or self.app.conf.task_serializer)
            options.setdefault("ignore_result", self.ignore_result)
            return self.app.send_task(self.name, args=args, kwargs=kwargs, **options)
        return super().apply_async(args=args, kwargs=kwargs, **options)


def dispatch_v4_creator_grant(task_kwargs):
    return dispatch_v4_grant(
        grant_v4_creator_action, task_kwargs,
        mode_loader=lambda: get_mode_provider().get_mode(), logger=logger,
    )


def _build_writer(tenant_id, operator):
    from bkmonitor.iam.backends.config import build_provider

    return V4AuthorizationWriter(
        build_provider("v4", tenant_id=tenant_id), tenant_id=tenant_id, operator=operator
    )


@shared_task(bind=True, base=QueuedIAMGrantTask, queue="celery_cron", ignore_result=True, max_retries=None)
def grant_v4_creator_action(self, *, tenant_id, operator, payload, role_id, expired_at, resource_meta):
    return execute_frozen_v4_grant(
        self, writer_factory=_build_writer, mode_loader=lambda: get_mode_provider().get_mode(), logger=logger,
        tenant_id=tenant_id, operator=operator, payload=payload,
        role_id=role_id, expired_at=expired_at, resource_meta=resource_meta,
    )

from __future__ import annotations

from blueapps.contrib.celery_tools.periodic import periodic_task
from celery.schedules import crontab

from apps.iam.backends.legacy_v3 import LegacyV3AuthorizationWriter
from apps.iam.backends.v4.writer import V4AuthorizationWriter
from apps.iam.grant_config import AuthorizationGrantConfig
from apps.iam.handlers.permission import Permission
from apps.iam.iam_engine.migration.dual_write import DualWriteGrantOrchestrator
from apps.iam.models import IAMAuthorizationGrant
from apps.iam.repositories import IAMAuthorizationGrantRepository
from apps.utils.log import logger


def build_writer(grant: IAMAuthorizationGrant):
    """仅使用授权意图中冻结的租户与操作人重建目标授权写入器。"""
    if grant.target_version == IAMAuthorizationGrant.TargetVersion.V3:
        return LegacyV3AuthorizationWriter(Permission.get_iam_client(grant.tenant_id))
    if grant.target_version == IAMAuthorizationGrant.TargetVersion.V4:
        return V4AuthorizationWriter.from_settings(username=grant.operator, bk_tenant_id=grant.tenant_id)
    raise ValueError(f"unsupported IAM grant target version: {grant.target_version}")


def retry_authorization_grant(grant_id: int) -> None:
    grant = IAMAuthorizationGrant.objects.get(pk=grant_id)
    orchestrator = DualWriteGrantOrchestrator(
        writers=(),
        tenant_id=grant.tenant_id,
        operator=grant.operator,
    )
    orchestrator.execute_record(grant, build_writer(grant))


@periodic_task(run_every=crontab(minute="*/1"))
def compensate_iam_authorization_grants() -> None:
    repository = IAMAuthorizationGrantRepository()
    grant_config = AuthorizationGrantConfig.from_settings()
    recovered = repository.recover_expired_leases()
    due_ids = repository.due_ids(limit=grant_config.compensation_batch_size)
    logger.info("[IAM Compensation] recovered=%s due=%s", recovered, len(due_ids))
    for grant_id in due_ids:
        try:
            retry_authorization_grant(grant_id)
        except Exception:  # pylint: disable=broad-except
            # 单条异常不能中断本轮其他授权意图，状态机内的远端异常会自行落库。
            logger.exception("[IAM Compensation] unexpected failure grant_id=%s", grant_id)

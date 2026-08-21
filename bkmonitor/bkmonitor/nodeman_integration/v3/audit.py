import logging
from dataclasses import dataclass


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NodeManV3AuditEvent:
    api_version: str
    action: str
    method: str
    monitor_operation_id: str | None
    bk_tenant_id: str
    bk_biz_id: int | None
    outcome: str
    error_code: str | int | None = None
    request_id: str | None = None


def record_outbound_audit(event: NodeManV3AuditEvent) -> None:
    """Record outbound metadata without logging request bodies or credentials."""

    logger.info(
        "NodeMan V3 outbound request",
        extra={
            "api_version": event.api_version,
            "action": event.action,
            "method": event.method,
            "monitor_operation_id": event.monitor_operation_id,
            "bk_tenant_id": event.bk_tenant_id,
            "bk_biz_id": event.bk_biz_id,
            "outcome": event.outcome,
            "error_code": event.error_code,
            "request_id": event.request_id,
        },
    )

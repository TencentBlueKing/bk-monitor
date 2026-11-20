"""3.9.x 单租户原地升级散件；不提供跨场景总流程。见同目录 README。"""

from .builtin import migrate_host_metrics, migrate_system_events, migrate_system_processes
from .common import check_data_link, finalize_transfer
from .containers import migrate_containers
from .events import migrate_custom_events, migrate_event
from .metrics import migrate_builtin_metrics, migrate_custom_formats, migrate_custom_metrics, migrate_metric
from .plugins import migrate_plugins, prepare_plugin
from .prerequisites import (
    check_cluster_registration,
    check_data_sources,
    check_settings,
    register_clusters,
    register_kafka_to_gse,
)
from .routes import refresh_routes
from .uptimecheck import deploy_uptimecheck_tasks, migrate_uptimechecks, switch_uptimecheck_tasks

__all__ = [
    "check_settings",
    "check_cluster_registration",
    "check_data_sources",
    "register_clusters",
    "register_kafka_to_gse",
    "check_data_link",
    "finalize_transfer",
    "refresh_routes",
    "migrate_host_metrics",
    "migrate_system_processes",
    "migrate_system_events",
    "migrate_metric",
    "migrate_custom_metrics",
    "migrate_builtin_metrics",
    "migrate_custom_formats",
    "migrate_event",
    "migrate_custom_events",
    "migrate_plugins",
    "prepare_plugin",
    "migrate_containers",
    "deploy_uptimecheck_tasks",
    "migrate_uptimechecks",
    "switch_uptimecheck_tasks",
]

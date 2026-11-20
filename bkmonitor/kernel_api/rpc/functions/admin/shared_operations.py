"""Admin endpoints backed by existing Kernel RPC implementations.

Bindings are explicit so registering a new CLI operation does not automatically
publish an Admin endpoint. Each endpoint keeps the source handler and its input
contract, including business permissions and mutation confirmation.
"""

from functools import partial

from core.drf_resource.exceptions import CustomException
from kernel_api.rpc.registry import KernelRPCFunction, KernelRPCRegistry

from .common import build_response


# (Admin operation, registered implementation, Admin safety level)
SHARED_OPERATIONS = (
    ("environment.info", "info", "read"),
    ("space.scene_related", "biz_scene_related_info", "read"),
    ("metadata.related", "metadata_related_info", "read"),
    ("datasource.kafka_probe", "metadata_kafka_has_data", "inspect"),
    ("query_route.read_space_router", "bkm_cli.read_space_router", "inspect"),
    ("query_route.inspect_related", "unify_query_redis_route", "inspect"),
    ("query_route.refresh_related", "refresh_unify_query_redis_route", "write"),
    ("es_storage.check", "metadata_es_storage_check", "inspect"),
    ("custom_report.metric_check", "metadata_custom_metric_check", "inspect"),
    ("bcs_cluster.related", "metadata_bcs_cluster_related_info", "read"),
    ("bcs_cluster.inspect_metadata", "bkm_cli.inspect_bcs_metadata", "inspect"),
    ("db.model_list", "bkm_cli.list_db_models", "read"),
    ("db.model_read", "bkm_cli.read_db_model", "inspect"),
    ("alarm_strategy.inspect", "bkm_cli.inspect_strategy_config", "inspect"),
    ("alarm_strategy.manage", "bkm_cli.manage_strategy_config", "write"),
    ("alarm_strategy.double_check_query", "bkm_cli.query_double_check_strategies", "read"),
    ("alarm_strategy.double_check_manage", "bkm_cli.manage_double_check_strategy", "write"),
    ("alarm_redis.cache_key", "bkm_cli.read_cache_key", "inspect"),
    ("alarm_redis.cache_footprint", "bkm_cli.measure_cache_footprint", "inspect"),
    ("alarm_redis.config_snapshot", "bkm_cli.read_config_cache", "inspect"),
    ("alarm_redis.routing_plan", "bkm_cli.list_cache_routing", "inspect"),
    ("alarm_redis.routing_apply", "bkm_cli.manage_cache_routing", "write"),
    ("alarm_redis.strategy_cost_snapshots", "bkm_cli.read_redis_strategy_cost_snapshots", "inspect"),
    ("circuit_breaking.manage", "bkm_cli.manage_circuit_breaking", "write"),
    ("alarm_assignment.action_detail", "bkm_cli.inspect_action_detail", "inspect"),
    ("alarm_assignment.config", "bkm_cli.inspect_assign_config", "read"),
    ("alarm_assignment.notice_target", "bkm_cli.inspect_notice_target", "read"),
    ("alarm_assignment.replay", "bkm_cli.replay_assign_match", "inspect"),
    ("issue.inspect", "bkm_cli.inspect_issue", "inspect"),
    ("api_auth_token.query", "bkm_cli.query_api_tokens", "read"),
    ("api_auth_token.manage", "bkm_cli.manage_api_token", "write"),
    ("cluster_info.es_diagnose", "bkm_cli.es_diagnose", "inspect"),
    ("cluster_info.es_capabilities", "bkm_cli.list_es_capabilities", "read"),
    ("platform.query", "bkm_cli.query_platform_source", "inspect"),
    ("unify_query.catalog", "bkm_cli.query_unify_query", "inspect"),
)


def _call(operation: str, source: KernelRPCFunction, safety: str, params: dict) -> dict:
    data = source.handler(params)
    # The platform and UQ catalogs encode provider failures in their own protocol.
    if operation in {"platform.query", "unify_query.catalog"} and data["status"] == "error":
        raise CustomException(message=data["error"]["message"], data=data)

    # Metadata inspections report the resolved tenant in query. Environment-wide
    # handlers can ignore a request tenant, so do not label their results with it.
    tenant = data.get("bk_tenant_id")
    if isinstance(data.get("query"), dict):
        tenant = data["query"].get("bk_tenant_id", tenant)
    if operation == "bcs_cluster.inspect_metadata":
        tenant = params.get("bk_tenant_id")
    if operation.startswith("api_auth_token.") and data["operation"] != "capabilities":
        from bkmonitor.utils.request import get_request_tenant_id
        from constants.common import DEFAULT_TENANT_ID

        tenant = params.get("bk_tenant_id") or get_request_tenant_id(peaceful=True) or DEFAULT_TENANT_ID
    return build_response(
        operation=operation, func_name=f"admin.{operation}", bk_tenant_id=tenant, safety_level=safety, data=data
    )


def register_shared_operations(functions: dict[str, KernelRPCFunction]) -> None:
    for operation, source_name, safety in SHARED_OPERATIONS:
        source = functions[source_name]
        KernelRPCRegistry.register_function(
            func_name=f"admin.{operation}",
            summary=source.summary,
            description=source.description,
            handler=partial(_call, operation, source, safety),
            params_schema=source.params_schema,
            example_params=source.example_params,
        )

"""Environment and custom-report diagnostics shared with the CLI."""

from functools import partial

from rest_framework.exceptions import PermissionDenied

from bkmonitor.utils.request import get_request
from kernel_api.rpc import KernelRPCRegistry

from .common import build_response


def _run(operation, command, params):
    from kernel_api.rpc.functions.bkm_cli.commands import run_readonly_command

    result = run_readonly_command({"command_id": command, "params": params})
    return build_response(
        operation=operation,
        func_name=f"admin.{operation}",
        bk_tenant_id=result.get("context", {}).get("bk_tenant_id"),
        data=result,
        safety_level="inspect",
    )


for operation, command, summary, schema, example in (
    (
        "environment.effective_setting",
        "get_effective_setting",
        "查询动态配置的生效值及其来源",
        {"name": "必填，已注册的动态配置名"},
        {"name": "COMPATIBLE_ALARM_FORMAT"},
    ),
    (
        "custom_report.metric_sync",
        "diagnose_ts_metric_sync",
        "诊断 DataID 的时序指标同步",
        {
            "data_id": "必填，DataID",
            "metrics": "必填，指标名称列表",
            "window_seconds": "可选，检查窗口",
            "history_seconds": "可选，历史窗口",
            "redis_prefix": "可选，Transfer Redis 前缀",
        },
        {"data_id": 50010, "metrics": ["cpu_usage"]},
    ),
    (
        "custom_report.metric_registration",
        "inspect_ts_metric_metadata",
        "核对指标和维度在各 scope 的登记状态",
        {
            "data_id": "必填，DataID",
            "metrics": "必填，指标名称列表",
            "dimensions": "可选，维度名称列表",
            "field_scope": "可选，精确匹配的 scope",
        },
        {"data_id": 50010, "metrics": ["cpu_usage"], "dimensions": ["host"]},
    ),
):
    KernelRPCRegistry.register_function(
        func_name=f"admin.{operation}",
        summary=summary,
        description=summary,
        params_schema=schema,
        example_params=example,
        handler=partial(_run, operation, command),
    )


@KernelRPCRegistry.register(
    "admin.custom_report.report_token",
    summary="读取当前请求租户的数据源上报凭证",
    description="返回指定 DataID 的 Prometheus 或 JSON 上报 Token。请求租户须拥有所有指定的数据源。",
    params_schema={
        "bk_tenant_id": "可选，默认为认证请求的租户",
        "metric_data_id": "指标 DataID，JSON 格式必填",
        "trace_data_id": "可选，Trace DataID",
        "log_data_id": "可选，日志 DataID",
        "profile_data_id": "可选，v1 Profile DataID",
        "format": "prometheus | json | all，默认 all",
        "token_version": "v0 | v1，默认 v0",
        "bk_biz_id": "可选，业务 ID",
        "app_name": "可选，应用名",
    },
    example_params={"metric_data_id": 50010, "format": "json"},
)
def report_token(params):
    from kernel_api.rpc.functions.bkm_cli.commands import get_report_token

    user = getattr(get_request(peaceful=True), "user", None)
    tenant = getattr(user, "tenant_id", None)
    if not getattr(user, "is_authenticated", False) or not tenant or params.get("bk_tenant_id", tenant) != tenant:
        raise PermissionDenied("仅可读取当前认证租户的上报凭证")
    data = get_report_token(params, bk_tenant_id=tenant)
    response = build_response(
        operation="custom_report.report_token",
        func_name="admin.custom_report.report_token",
        bk_tenant_id=tenant,
        safety_level="inspect",
        data=data,
    )
    response["meta"]["sensitive_read"] = True
    return response

"""蓝鲸监控 V3 API 高级封装。"""

from typing import Any, NotRequired, TypedDict

from .client import (
    change_uptime_check_task_status_client,
    create_uptime_check_node_client,
    create_uptime_check_task_client,
    custom_time_series_detail_client,
    delete_alarm_strategy_client,
    delete_collector_plugin_client,
    delete_uptime_check_node_client,
    delete_uptime_check_task_client,
    deploy_uptime_check_task_client,
    edit_uptime_check_node_client,
    edit_uptime_check_task_client,
    export_uptime_check_task_client,
    get_collector_plugin_detail_client,
    get_collector_plugin_upgrade_info_client,
    get_fields_option_values_client,
    get_trace_view_config_client,
    get_uptime_check_node_list_client,
    get_uptime_check_task_list_client,
    import_uptime_check_node_client,
    import_uptime_check_task_client,
    list_collector_plugins_client,
    save_alarm_strategy_client,
    save_alarm_strategy_v2_client,
    save_notice_group_client,
    search_alarm_strategy_client,
    switch_alarm_strategy_client,
    test_uptime_check_task_client,
    upgrade_collect_plugin_client,
)

__all__ = [
    "BaseApmParams",
    "GetFieldsOptionValuesParams",
    "SupportedOperationsResult",
    "ViewConfigResult",
    "custom_time_series_detail",
    "change_uptime_check_task_status",
    "create_uptime_check_node",
    "create_uptime_check_task",
    "delete_uptime_check_node",
    "delete_uptime_check_task",
    "deploy_uptime_check_task",
    "export_uptime_check_task",
    "delete_alarm_strategy",
    "delete_collector_plugin",
    "edit_uptime_check_node",
    "edit_uptime_check_task",
    "get_collector_plugin_detail",
    "get_collector_plugin_upgrade_info",
    "get_fields_option_values",
    "get_trace_view_config",
    "get_uptime_check_node_list",
    "get_uptime_check_task_list",
    "import_uptime_check_node",
    "import_uptime_check_task",
    "list_collector_plugins",
    "save_alarm_strategy",
    "save_alarm_strategy_v2",
    "save_notice_group",
    "search_alarm_strategy",
    "switch_alarm_strategy",
    "test_uptime_check_task",
    "upgrade_collect_plugin",
]


class BaseApmParams(TypedDict):
    """Apm 基础参数"""

    bk_biz_id: int
    app_name: str


class GetFieldsOptionValuesParams(BaseApmParams):
    """获取 trace 字段可选值参数"""

    start_time: int
    end_time: int
    filters: NotRequired[list[dict[str, Any]]]
    query_string: str
    mode: str
    fields: list[str]
    limit: NotRequired[int]


class SupportedOperationsResult(TypedDict):
    """支持的操作类型返回值"""

    label: str
    operator: str
    placeholder: str
    options: NotRequired[list[dict[str, Any]]]


class ViewConfigResult(TypedDict):
    """trace/span 查询视图配置返回值"""

    name: str
    type: str
    alias: str
    is_searched: bool
    is_dimensions: bool
    can_displayed: bool
    supported_operations: list[SupportedOperationsResult]


def get_trace_view_config(bk_tenant_id: str, params: BaseApmParams) -> dict[str, list[ViewConfigResult]]:
    """
    获取 trace 查询视图配置

    Args:
        bk_tenant_id: 租户ID
        params: Apm 基础参数

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    return get_trace_view_config_client(bk_tenant_id=bk_tenant_id, params=params)


def get_fields_option_values(bk_tenant_id: str, params: GetFieldsOptionValuesParams) -> dict[str, list[str]]:
    """
    获取 trace 字段可选值

    Args:
        bk_tenant_id: 租户ID
        params: 获取 trace 字段可选值参数

    Returns:
        结果

    Raises:
        BkApiError: 接口调用失败
    """
    return get_fields_option_values_client(bk_tenant_id=bk_tenant_id, params=params)


def custom_time_series_detail(
    bk_tenant_id: str,
    bk_biz_id: int,
    time_series_group_id: int,
    model_only: bool = False,
    empty_if_not_found: bool = False,
) -> dict[str, Any]:
    """获取自定义指标上报详情

    Args:
        bk_tenant_id: 租户ID
        bk_biz_id: 修改时序分组参数
        time_series_group_id: 自定义时序ID
        model_only: 修改时序分组参数
        empty_if_not_found: 修改时序分组参数
    """
    return custom_time_series_detail_client(
        bk_tenant_id=bk_tenant_id,
        params={
            "bk_biz_id": bk_biz_id,
            "time_series_group_id": time_series_group_id,
            "model_only": model_only,
            "empty_if_not_found": empty_if_not_found,
        },
    )


def save_alarm_strategy(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """保存告警策略。"""
    return save_alarm_strategy_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def save_alarm_strategy_v2(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """保存告警策略 V2。"""
    return save_alarm_strategy_v2_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def delete_alarm_strategy(
    bk_tenant_id: str,
    bk_biz_id: int,
    ids: list[int],
    bk_username: str,
) -> bool:
    """删除告警策略。"""
    api_result = delete_alarm_strategy_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"bk_biz_id": bk_biz_id, "ids": ids},
    )
    return bool(api_result)


def search_alarm_strategy(
    bk_tenant_id: str,
    bk_biz_id: int,
    bk_username: str,
    **params: Any,
) -> tuple[int, list[dict[str, Any]]]:
    """查询告警策略列表。"""
    data = search_alarm_strategy_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"bk_biz_id": bk_biz_id, **params},
    )
    count = data.get("count", 0)
    strategy_list = data.get("strategy_config_list", [])
    return count, strategy_list


def switch_alarm_strategy(
    bk_tenant_id: str,
    bk_biz_id: int,
    ids: list[int],
    is_enabled: bool,
    bk_username: str,
) -> bool:
    """启停告警策略。"""
    return switch_alarm_strategy_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"bk_biz_id": bk_biz_id, "ids": ids, "is_enabled": is_enabled},
    )


def save_notice_group(
    bk_tenant_id: str,
    bk_biz_id: int,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """保存通知组。"""
    return save_notice_group_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"bk_biz_id": bk_biz_id, **params},
    )


def list_collector_plugins(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """查询采集插件列表。"""
    return list_collector_plugins_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def get_collector_plugin_detail(
    bk_tenant_id: str,
    bk_username: str,
    plugin_id: str,
) -> dict[str, Any]:
    """查询采集插件详情。"""
    return get_collector_plugin_detail_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"plugin_id": plugin_id},
    )


def delete_collector_plugin(
    bk_tenant_id: str,
    bk_username: str,
    plugin_ids: list[str],
) -> dict[str, Any]:
    """删除采集插件。"""
    return delete_collector_plugin_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"plugin_ids": plugin_ids},
    )


def get_collector_plugin_upgrade_info(
    bk_tenant_id: str,
    bk_username: str,
    plugin_id: str,
) -> dict[str, Any]:
    """查询采集插件升级信息。"""
    return get_collector_plugin_upgrade_info_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params={"plugin_id": plugin_id},
    )


def upgrade_collect_plugin(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """升级采集插件。"""
    return upgrade_collect_plugin_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def get_uptime_check_node_list(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any] | list[dict[str, Any]]:
    """查询拨测节点列表。"""
    return get_uptime_check_node_list_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def create_uptime_check_node(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """创建拨测节点。"""
    return create_uptime_check_node_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def edit_uptime_check_node(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """编辑拨测节点。"""
    return edit_uptime_check_node_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def delete_uptime_check_node(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """删除拨测节点。"""
    return delete_uptime_check_node_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def get_uptime_check_task_list(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any] | list[dict[str, Any]]:
    """查询拨测任务列表。"""
    return get_uptime_check_task_list_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def create_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """创建拨测任务。"""
    return create_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def edit_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """编辑拨测任务。"""
    return edit_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def delete_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """删除拨测任务。"""
    return delete_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def deploy_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any] | str:
    """下发拨测任务。"""
    return deploy_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def change_uptime_check_task_status(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """修改拨测任务状态。"""
    return change_uptime_check_task_status_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def test_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any] | str:
    """测试拨测任务。"""
    return test_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def import_uptime_check_node(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """导入拨测节点。"""
    return import_uptime_check_node_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def import_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any]:
    """导入拨测任务。"""
    return import_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )


def export_uptime_check_task(
    bk_tenant_id: str,
    bk_username: str,
    **params: Any,
) -> dict[str, Any] | list[dict[str, Any]]:
    """导出拨测任务。"""
    return export_uptime_check_task_client(
        bk_tenant_id=bk_tenant_id,
        user_params={"bk_username": bk_username},
        params=params,
    )

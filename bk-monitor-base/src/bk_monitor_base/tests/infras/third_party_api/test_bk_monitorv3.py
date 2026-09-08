from bk_monitor_base.infras.third_party_api.bk_monitorv3.api import (
    BaseApmParams,
    GetFieldsOptionValuesParams,
    ViewConfigResult,
    create_uptime_check_node,
    get_fields_option_values,
    get_trace_view_config,
    get_uptime_check_task_list,
    list_collector_plugins,
    save_alarm_strategy,
)
from bk_monitor_base.infras.third_party_api.bk_monitorv3.client import (
    create_uptime_check_node_client,
    get_uptime_check_task_list_client,
    list_collector_plugins_client,
    save_alarm_strategy_client,
)


def test_get_trace_view_config(requests_mock):
    """
    测试获取 trace/span 查询视图配置
    """
    requests_mock.get(
        "http://bkapi.example.com/api/bk-monitor/prod/app/apm/view_config/",
        json={
            "result": True,
            "data": {
                "trace_config": [
                    {
                        "name": "trace_id",
                        "type": "keyword",
                        "alias": "Trace ID",
                        "is_searched": True,
                        "is_dimensions": False,
                        "can_displayed": True,
                        "supported_operations": [
                            {"operator": "equal", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"}
                        ],
                    }
                ],
                "span_config": [
                    {
                        "name": "trace_id",
                        "alias": "Trace ID",
                        "type": "keyword",
                        "is_searched": True,
                        "is_dimensions": False,
                        "can_displayed": True,
                        "supported_operations": [
                            {"operator": "equal", "label": "=", "placeholder": "请选择或直接输入，Enter分隔"}
                        ],
                    }
                ],
            },
        },
    )

    params = BaseApmParams(
        bk_biz_id=2,
        app_name="test_app",
    )

    response: dict[str, list[ViewConfigResult]] = get_trace_view_config(bk_tenant_id="system", params=params)
    assert isinstance(response, dict)
    assert isinstance(response["trace_config"], list)
    assert isinstance(response["span_config"], list)
    assert response["trace_config"][0]["name"] == "trace_id"
    assert response["trace_config"][0]["alias"] == "Trace ID"
    assert response["trace_config"][0]["type"] == "keyword"
    assert isinstance(response["trace_config"][0]["supported_operations"], list)
    assert response["trace_config"][0]["supported_operations"][0]["operator"] == "equal"
    assert response["trace_config"][0]["supported_operations"][0]["label"] == "="
    assert response["trace_config"][0]["supported_operations"][0]["placeholder"] == "请选择或直接输入，Enter分隔"


def test_get_fields_option_values(requests_mock):
    """
    测试获取 trace/span 字段可选值
    """
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/apm/get_fields_option_values/",
        json={
            "result": True,
            "data": {"span_name": ["api1", "api2", "api3", "api4", "api5"]},
        },
    )

    params = GetFieldsOptionValuesParams(
        bk_biz_id=2,
        app_name="test_app",
        start_time=1770014164,
        end_time=1770017764,
        query_string="",
        mode="span",
        fields=["span_name"],
        limit=10,
        filters=[],
    )

    response: dict[str, list[str]] = get_fields_option_values(bk_tenant_id="system", params=params)
    assert isinstance(response, dict)
    assert isinstance(response["span_name"], list)
    assert response["span_name"][0] == "api1"


def test_save_alarm_strategy(requests_mock):
    """测试迁移后的告警策略保存接口仍走统一的 bk_monitorv3 模块配置。"""
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/alarm_strategy/save/",
        json={
            "result": True,
            "data": {
                "id": 123,
                "name": "CPU使用率告警",
            },
        },
    )

    response = save_alarm_strategy(
        bk_tenant_id="system",
        bk_username="admin",
        bk_biz_id=2,
        name="CPU使用率告警",
    )

    assert save_alarm_strategy_client.module_name == "bk_monitorv3"
    assert response["id"] == 123
    assert response["name"] == "CPU使用率告警"


def test_list_collector_plugins(requests_mock):
    """测试迁移后的采集插件列表接口仍可正常返回 data 字段。"""
    requests_mock.get(
        "http://bkapi.example.com/api/bk-monitor/prod/app/plugin/list/",
        json={
            "result": True,
            "data": {
                "list": [{"plugin_id": "plugin_1"}],
                "total": 1,
            },
        },
    )

    response = list_collector_plugins(
        bk_tenant_id="system",
        bk_username="admin",
        bk_biz_id=2,
        page=1,
        page_size=10,
    )

    assert list_collector_plugins_client.module_name == "bk_monitorv3"
    assert response["total"] == 1
    assert response["list"][0]["plugin_id"] == "plugin_1"


def test_create_uptime_check_node_uses_bk_monitor_apigw_path(requests_mock):
    """测试拨测节点创建通过 bk-monitor 网关真实路径发起请求。"""
    requests_mock.post(
        "http://bkapi.example.com/api/bk-monitor/prod/app/uptime_check/node/create/",
        json={"result": True, "data": {"id": 123}},
    )

    response = create_uptime_check_node(
        bk_tenant_id="system",
        bk_username="admin",
        bk_biz_id=2,
        ip="127.0.0.1",
        plat_id=0,
        name="node-1",
    )

    assert create_uptime_check_node_client.module_name == "bk_monitorv3"
    assert response["id"] == 123


def test_get_uptime_check_task_list_uses_bk_monitor_apigw_path(requests_mock):
    """测试拨测任务列表通过 bk-monitor 网关真实路径发起请求。"""
    requests_mock.get(
        "http://bkapi.example.com/api/bk-monitor/prod/app/uptime_check/task/list/",
        json={"result": True, "data": []},
    )

    response = get_uptime_check_task_list(
        bk_tenant_id="system",
        bk_username="admin",
        bk_biz_id=2,
    )

    assert get_uptime_check_task_list_client.module_name == "bk_monitorv3"
    assert response == []

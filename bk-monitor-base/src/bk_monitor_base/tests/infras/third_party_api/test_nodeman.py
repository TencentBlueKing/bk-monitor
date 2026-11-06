import json

from bk_monitor_base.infras.third_party_api.nodeman.api import (
    PluginInfo,
    check_subscription_task_ready,
    get_plugin_info,
)
from bk_monitor_base.infras.third_party_api.nodeman.client import subscription_check_task_ready_client


def _get_check_task_ready_url() -> str:
    """构造检查订阅任务是否就绪接口的 ESB URL。"""
    return "/".join(
        [
            subscription_check_task_ready_client.bk_api_url.rstrip("/"),
            subscription_check_task_ready_client.esb_base_url.strip("/"),
            subscription_check_task_ready_client.esb_path,
        ]
    )


def _get_request_body(requests_mock) -> dict:
    """提取最近一次请求的 JSON 请求体。"""
    return json.loads(requests_mock.request_history[0].text)


def test_get_plugin_info(requests_mock):
    """
    测试获取插件信息
    """
    requests_mock.get(
        "http://bkapi.example.com/api/c/compapi/v2/nodeman/plugin_info/?name=test",
        json={
            "result": True,
            "data": [
                {
                    "id": 1,
                    "name": "test",
                    "version": "1.1",
                    "os": "linux",
                    "cpu_arch": "x86_64",
                    "pkg_name": "test_script-1.1.tgz",
                    "pkg_size": 123456,
                    "pkg_mtime": "2025-08-20 07:14:13.560398+00:00",
                    "md5": "d41d8cd98f00b204e9800998ecf8427e",
                    "creator": "admin",
                    "is_ready": True,
                    "is_release_version": True,
                    "source_app_code": "test",
                }
            ],
        },
    )

    response: list[PluginInfo] = get_plugin_info(bk_tenant_id="system", name="test")
    assert response[0].id == 1
    assert response[0].name == "test"
    assert response[0].version == "1.1"
    assert response[0].os == "linux"
    assert response[0].md5 == "d41d8cd98f00b204e9800998ecf8427e"


def test_check_subscription_task_ready_path(requests_mock):
    """测试检查订阅任务接口命中新 ESB 路径并在任务就绪时返回 True。

    测试目的：验证 ``check_subscription_task_ready`` 调用
    ``backend/api/subscription/check_task_ready/`` 新路径。
    前置条件：模拟 API 返回任务就绪状态 ``data=True``。
    预期结果：函数返回 ``True``，且请求命中新的 ESB URL。

    Args:
        requests_mock: requests_mock 提供的 HTTP 请求桩。
    """
    api_url = _get_check_task_ready_url()

    # Arrange: 模拟 API 返回就绪状态。
    requests_mock.post(api_url, json={"result": True, "data": True})

    # Act: 调用检查函数。
    response = check_subscription_task_ready(
        bk_tenant_id="system",
        subscription_id=1,
        task_id_list=[1001, 1002],
    )

    # Assert: 验证返回值和请求路径都符合预期。
    request_body = _get_request_body(requests_mock)
    assert response is True
    assert requests_mock.request_history[0].url == api_url
    assert request_body == {"subscription_id": 1, "task_id_list": [1001, 1002]}


def test_check_subscription_task_ready_returns_false(requests_mock):
    """测试检查订阅任务接口在后端返回未就绪时返回 False。

    测试目的：验证 ``check_subscription_task_ready`` 在任务未就绪时的返回值，
    且不传 ``task_id_list`` 时只发送必需参数。
    前置条件：模拟 API 返回任务未就绪状态 ``data=False``。
    预期结果：函数返回 ``False``。

    Args:
        requests_mock: requests_mock 提供的 HTTP 请求桩。
    """
    api_url = _get_check_task_ready_url()

    # Arrange: 模拟 API 返回未就绪状态。
    requests_mock.post(api_url, json={"result": True, "data": False})

    # Act: 调用检查函数。
    response = check_subscription_task_ready(
        bk_tenant_id="system",
        subscription_id=1,
    )

    # Assert: 验证返回值为 False。
    request_body = _get_request_body(requests_mock)
    assert response is False
    assert requests_mock.request_history[0].url == api_url
    assert request_body == {"subscription_id": 1}

"""蓝鲸应用集群命名空间接口：调用失败必须抛出，不能与"没有集群资源"的空列表混淆。"""

from typing import Any

import pytest

from bk_monitor_base.infras.third_party_api.bk_paas import api
from bk_monitor_base.infras.third_party_api.errors import BkApiError


def _answer_with(monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    """让底层客户端返回给定结果；结果为异常时抛出。"""

    def fake_client(bk_tenant_id: str, params: dict[str, Any]) -> Any:
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(api, "get_app_cluster_namespace_client", fake_client)


@pytest.mark.parametrize(
    "error",
    [
        BkApiError(module="bk_paas", action="get_app_cluster_namespace", method="GET", url="", message="timeout"),
        ConnectionError("refused"),
    ],
)
def test_call_failure_is_raised(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    """网关错误、超时、鉴权失败、应用不存在等调用失败原样抛出，不返回任何列表。"""
    _answer_with(monkeypatch, error)

    with pytest.raises(type(error)):
        api.get_app_cluster_namespace(bk_tenant_id="tenant-a", app_code="demo-app")


@pytest.mark.parametrize(
    "answer",
    [None, {"data": []}, [{"namespace": "bkapp-demo-app-prod"}], ["bkapp-demo-app-prod"]],
)
def test_unrecognized_response_is_rejected(monkeypatch: pytest.MonkeyPatch, answer: Any) -> None:
    """不是集群命名空间列表的返回不能当作结果使用。"""
    _answer_with(monkeypatch, answer)

    with pytest.raises(ValueError):
        api.get_app_cluster_namespace(bk_tenant_id="tenant-a", app_code="demo-app")


@pytest.mark.parametrize(
    "answer",
    [[], [{"bcs_cluster_id": "BCS-K8S-00001", "namespace": "bkapp-demo-app-prod", "environment": "prod"}]],
)
def test_explicit_answer_is_returned(monkeypatch: pytest.MonkeyPatch, answer: list[dict[str, Any]]) -> None:
    """PaaS 明确返回的列表（包括空列表）原样返回。"""
    _answer_with(monkeypatch, answer)

    assert api.get_app_cluster_namespace(bk_tenant_id="tenant-a", app_code="demo-app") == answer

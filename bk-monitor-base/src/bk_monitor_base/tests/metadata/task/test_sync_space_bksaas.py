"""蓝鲸应用空间资源刷新：PaaS 调用失败的应用保留已有登记，只有明确的空结果才写空。

运行真实的集群命名空间接口函数、bulk_request 与刷新任务，只替换 PaaS 客户端、ORM 管理器和 Redis 推送。
"""

import copy
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock

import pytest

from bk_monitor_base.infras.third_party_api.bk_paas import api as bk_paas_api
from bk_monitor_base.infras.third_party_api.errors import BkApiError
from bk_monitor_base.metadata.task import sync_space

SHARED = "shared"


class FakeSpaceResourceManager:
    """只保存 dimension_values；filter 返回副本，必须经 bulk_update/bulk_create 才会落库。"""

    def __init__(self, stored: dict[str, list[dict[str, Any]]]) -> None:
        self.stored = stored

    def filter(self, space_type_id: str, space_id__in: Any) -> list[SimpleNamespace]:
        space_ids = set(space_id__in)
        return [
            SimpleNamespace(space_type_id=space_type_id, space_id=space_id, dimension_values=copy.deepcopy(values))
            for space_id, values in self.stored.items()
            if space_id in space_ids
        ]

    def bulk_update(self, objs: list[Any], fields: list[str], batch_size: int | None = None) -> None:
        for obj in objs:
            self.stored[obj.space_id] = copy.deepcopy(obj.dimension_values)

    def bulk_create(self, objs: list[Any], batch_size: int | None = None) -> None:
        for obj in objs:
            self.stored[obj.space_id] = copy.deepcopy(obj.dimension_values)


def registration(cluster_id: str, *namespaces: str) -> list[dict[str, Any]]:
    """刷新任务写入的 dimension_values 形状。"""
    return [{"cluster_id": cluster_id, "namespace": list(namespaces), "cluster_type": SHARED}]


def cluster_answer(cluster_id: str, *namespaces: str) -> list[dict[str, Any]]:
    """PaaS 接口返回的集群命名空间列表形状。"""
    return [{"bcs_cluster_id": cluster_id, "namespace": ns, "environment": "prod"} for ns in namespaces]


def gateway_error() -> BkApiError:
    return BkApiError(module="bk_paas", action="get_app_cluster_namespace", method="GET", url="", message="error")


@pytest.fixture
def refresh_env(monkeypatch: pytest.MonkeyPatch) -> Any:
    """按 {app_code: (已有登记或 None, PaaS 返回或异常)} 准备环境，返回执行刷新的函数及观测对象。"""
    stored: dict[str, list[dict[str, Any]]] = {}
    answers: dict[str, Any] = {}
    spaces: list[SimpleNamespace] = []
    authorize = Mock()
    logger = Mock()

    def fake_client(bk_tenant_id: str, params: dict[str, Any]) -> Any:
        answer = answers[params["app_code"]]
        if isinstance(answer, Exception):
            raise answer
        return copy.deepcopy(answer)

    monkeypatch.setattr(bk_paas_api, "get_app_cluster_namespace_client", fake_client)
    monkeypatch.setattr(sync_space.models.Space, "objects", SimpleNamespace(filter=lambda space_type_id: list(spaces)))
    monkeypatch.setattr(sync_space.models.SpaceResource, "objects", FakeSpaceResourceManager(stored))
    monkeypatch.setattr(sync_space, "authorize_paas_space_cluster_data_source", authorize)
    monkeypatch.setattr(sync_space, "SpaceTableIDRedis", Mock())
    monkeypatch.setattr(sync_space, "bulk_handle", Mock())
    monkeypatch.setattr(sync_space, "RedisTools", Mock())
    monkeypatch.setattr(sync_space, "logger", logger)

    def run(apps: dict[str, tuple[list[dict[str, Any]] | None, Any]]) -> None:
        for app_code, (previous, answer) in apps.items():
            spaces.append(SimpleNamespace(space_id=app_code, space_type_id="bksaas", bk_tenant_id="tenant-a"))
            if previous is not None:
                stored[app_code] = previous
            answers[app_code] = answer
        # 跳过分布式锁，直接执行任务本体
        sync_space.refresh_bksaas_space_resouce.__wrapped__()

    return SimpleNamespace(run=run, stored=stored, authorize=authorize, logger=logger)


def _error_log_args(logger: Mock) -> list[tuple[Any, ...]]:
    return [call.args for call in logger.error.call_args_list]


def test_failed_call_keeps_previous_dimension_values(refresh_env: Any) -> None:
    """调用失败的应用保留已有登记且不参与重新授权，同批其他应用照常更新，失败数被记录。"""
    failed_previous = registration("BCS-K8S-00001", "bkapp-failed-app-prod")

    refresh_env.run(
        {
            "failed-app": (failed_previous, gateway_error()),
            "healthy-app": (
                registration("BCS-K8S-00001", "bkapp-healthy-app-stag"),
                cluster_answer("BCS-K8S-00002", "bkapp-healthy-app-prod"),
            ),
        }
    )

    assert refresh_env.stored["failed-app"] == failed_previous
    assert refresh_env.stored["healthy-app"] == registration("BCS-K8S-00002", "bkapp-healthy-app-prod")
    assert refresh_env.authorize.call_args.args[0] == {"healthy-app": {"BCS-K8S-00002"}}
    assert any(1 in args and 2 in args for args in _error_log_args(refresh_env.logger))


def test_explicit_empty_answer_writes_empty(refresh_env: Any) -> None:
    """PaaS 明确返回空列表时写入空登记，不记失败。"""
    refresh_env.run(
        {
            "empty-app": (registration("BCS-K8S-00001", "bkapp-empty-app-prod"), []),
            "healthy-app": (None, cluster_answer("BCS-K8S-00001", "bkapp-healthy-app-prod")),
        }
    )

    assert refresh_env.stored["empty-app"] == []
    assert refresh_env.stored["healthy-app"] == registration("BCS-K8S-00001", "bkapp-healthy-app-prod")
    assert _error_log_args(refresh_env.logger) == []


def test_whole_batch_failure_keeps_every_registration(refresh_env: Any) -> None:
    """整批调用全部失败时任务不中断，所有已有登记保持不变。"""
    previous = {f"app-{index}": registration("BCS-K8S-00001", f"bkapp-app-{index}-prod") for index in range(3)}

    refresh_env.run(
        {app_code: (values, ConnectionError("refused")) for app_code, values in copy.deepcopy(previous).items()}
    )

    assert refresh_env.stored == previous
    assert refresh_env.authorize.call_args.args[0] == {}
    assert any(3 in args for args in _error_log_args(refresh_env.logger))

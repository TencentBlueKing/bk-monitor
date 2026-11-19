from unittest.mock import Mock

import pytest
from kubernetes import client

from bk_monitor_base.metadata.utils.bcs import BcsKubeClient


def test_bcs_request_does_not_retain_sdk_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """通过真实 SDK 反序列化结果，检查每个临时客户端都没有创建常驻线程池。"""
    monkeypatch.setattr(client.ApiClient, "request", Mock(return_value=Mock(data=b'{"items": []}')))
    for _ in range(3):
        kube = BcsKubeClient("test-cluster")
        api_client = kube.core_api.api_client
        try:
            result = kube.client_request(kube.core_api.list_namespaced_secret, namespace="test", async_req=True)
            assert result.items == []
            assert api_client._pool is None
        finally:
            api_client.close()

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, current_thread
from unittest.mock import Mock

import pytest
from kubernetes import client

from bkmonitor.utils.bcs import BcsKubeClient
from bkmonitor.utils.bk_collector_config import BkCollectorClusterConfig


def test_requests_release_sdk_clients(monkeypatch):
    request = Mock(return_value=Mock(data=b'{"items": []}'))
    monkeypatch.setattr(client.ApiClient, "request", request)
    for async_params in ({}, {"async_req": True}, {"async_req": False}):
        kube = BcsKubeClient("test-cluster")
        api_client = kube.core_api.api_client
        try:
            result = kube.client_request(kube.core_api.list_namespaced_secret, namespace="test", **async_params)
            assert result.items == []
            assert api_client._pool is None
        finally:
            api_client.close()


def test_repeated_collector_template_reads_retire_workers(monkeypatch):
    workers = []

    def read_template(self, method, url, **kwargs):
        assert method == "GET"
        assert url.endswith("/namespaces/test/configmaps")
        assert self._pool is None
        workers.append(current_thread())
        return Mock(data=b'{"items":[{"data":{"example.conf":"dmFsdWU="}}]}')

    monkeypatch.setattr(client.ApiClient, "request", read_template)
    for _ in range(8):
        assert BkCollectorClusterConfig.sub_config_tpl("test-cluster", "test", "example.conf") == "value"
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()


@pytest.mark.parametrize("status", [403, 404, 503])
def test_api_error_returns_none(monkeypatch, status):
    kube = BcsKubeClient("test-cluster")
    monkeypatch.setattr(kube.core_api.api_client, "request", Mock(side_effect=client.ApiException(status=status)))
    assert kube.client_request(kube.core_api.list_namespaced_secret, namespace="test") is None


def test_transport_timeout_is_not_a_wait_timeout(monkeypatch):
    kube = BcsKubeClient("test-cluster")
    monkeypatch.setattr(kube.core_api.api_client, "request", Mock(side_effect=TimeoutError("transport timeout")))
    with pytest.raises(TimeoutError, match="transport timeout"):
        kube.client_request(kube.core_api.list_namespaced_secret, namespace="test")


def test_timed_out_requests_release_their_workers_after_transport_finishes(monkeypatch):
    clients = [BcsKubeClient("test-cluster") for _ in range(3)]
    workers = []
    all_started = Barrier(4)
    release = Event()

    def stalled_request(*args, **kwargs):
        assert kwargs["_request_timeout"] == (1, 2)
        workers.append(current_thread())
        all_started.wait(timeout=5)
        assert release.wait(5), "client_request blocked on transport cleanup"
        return Mock(data=b'{"items": []}')

    monkeypatch.setattr(client.ApiClient, "request", stalled_request)
    monkeypatch.setattr(BcsKubeClient, "_REQUEST_TIMEOUT", 0.2)
    with ThreadPoolExecutor(max_workers=3) as callers:
        calls = [
            callers.submit(
                kube.client_request, kube.core_api.list_namespaced_secret, namespace="test", _request_timeout=(1, 2)
            )
            for kube in clients
        ]
        try:
            all_started.wait(timeout=5)
            assert all(call.result(timeout=2) is None for call in calls)
        finally:
            release.set()
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()

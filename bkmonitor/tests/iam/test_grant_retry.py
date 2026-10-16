"""Offline task routing, in-memory messaging and frozen authorization retries."""

from contextlib import nullcontext
from unittest.mock import Mock, patch

import pytest
from celery.exceptions import Retry
from celery import Celery, current_app
from django.conf import settings
from django.test import override_settings

from bkmonitor.iam.tasks.grant import _backend_grant_app, grant_v4_creator_action
from config.celery.backend import get_backend_celery_broker_config
from iam_engine.exceptions import ProviderError, ProviderUnavailable


@pytest.fixture
def grant(monkeypatch):
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v4")
    client = Mock()
    provider = Mock()
    provider._get_client.return_value = client
    monkeypatch.setattr("bkmonitor.iam.backends.config.build_provider", lambda name, tenant_id: provider)
    data = {
        "tenant_id": "tenant-a",
        "operator": "alice",
        "role_id": "space_operator",
        "expired_at": 1893456000,
        "resource_meta": {"type": "space", "id": "2\nforged-line"},
        "payload": [
            {
                "subject": {"type": "user", "id": "alice"},
                "expired_at": 1893456000,
                "role_id": "space_operator",
                "related_resource_type_id": "space",
                "resources": [{"type": "space", "id": "2"}],
            }
        ],
    }
    return provider, client, data


def run_task(data, retries=0):
    grant_v4_creator_action.push_request(retries=retries)
    try:
        return grant_v4_creator_action.run(**data)
    finally:
        grant_v4_creator_action.pop_request()


def test_retry_replays_exact_payload_expiry_and_tenant(grant):
    provider, client, data = grant
    run_task(data, retries=4)
    provider._get_client.assert_called_once_with("tenant-a")
    client.add_authorization.assert_called_once_with(items=data["payload"], operator="alice")
    assert data["payload"][0]["expired_at"] == 1893456000


def test_historical_v4_task_is_suppressed_after_switch_to_v3(grant, monkeypatch):
    provider, client, data = grant
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
    with patch.object(grant_v4_creator_action, "retry") as retry:
        run_task(data, retries=4)
    provider._get_client.assert_not_called()
    client.add_authorization.assert_not_called()
    retry.assert_not_called()


def test_union_retry_keeps_frozen_request(grant, monkeypatch):
    _, client, data = grant
    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "union")
    run_task(data)
    client.add_authorization.assert_called_once_with(items=data["payload"], operator="alice")


def test_commit_callback_does_not_dispatch_after_switch_to_v3(grant, monkeypatch):
    from bkmonitor.iam.tasks.grant import dispatch_v4_creator_grant

    monkeypatch.setenv("BKAPP_IAM_PERMISSION_MODE", "v3")
    with patch.object(grant_v4_creator_action, "apply_async") as dispatch:
        dispatch_v4_creator_grant(grant[2])
    dispatch.assert_not_called()


def test_web_grant_stays_on_saas_default_queue(grant):
    from bkmonitor.iam.tasks.grant import dispatch_v4_creator_grant

    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = False
    try:
        with (
            patch.object(app, "send_task") as send,
            patch.object(grant_v4_creator_action, "run") as run,
            patch("bkmonitor.iam.tasks.grant._backend_grant_app") as backend,
        ):
            dispatch_v4_creator_grant(grant[2])
        send.assert_called_once()
        assert send.call_args.args[0] == grant_v4_creator_action.name
        assert send.call_args.args[2] == grant[2]
        assert not send.call_args.kwargs.get("queue")
        backend.assert_not_called()
        run.assert_not_called()
        assert app.conf.task_always_eager is False
    finally:
        app.conf.task_always_eager = previous


def test_eager_api_retry_preserves_delay_and_frozen_payload(grant):
    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = True
    try:
        with _backend_grant_app() as backend:
            with (
                patch("bkmonitor.iam.tasks.grant._backend_grant_app", return_value=nullcontext(backend)),
                patch.object(backend, "send_task") as send,
                patch.object(app, "send_task") as saas_send,
                patch.object(grant_v4_creator_action, "run") as run,
            ):
                grant_v4_creator_action.apply_async(kwargs=grant[2], countdown=60)
            saas_send.assert_not_called()
            run.assert_not_called()
        assert send.call_args.kwargs["countdown"] == 60
        assert send.call_args.kwargs["kwargs"] is grant[2]
        assert send.call_args.kwargs["queue"] == "celery_cron"
    finally:
        app.conf.task_always_eager = previous


@pytest.mark.parametrize("queue", ["celery", "celery_cron"])
def test_worker_real_retry_requeues_on_original_delivery_route(grant, queue):
    _, client, data = grant
    client.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    app = grant_v4_creator_action.app
    previous = app.conf.task_always_eager
    app.conf.task_always_eager = False
    grant_v4_creator_action.push_request(
        id="offline-grant",
        retries=1,
        called_directly=False,
        is_eager=False,
        args=(),
        kwargs=data,
        delivery_info={"exchange": "", "routing_key": queue},
    )
    try:
        with patch.object(app, "send_task") as send:
            with pytest.raises(Retry):
                grant_v4_creator_action.run(**data)
        assert send.call_args.args[2] == data
        assert send.call_args.kwargs["countdown"] == 60
        assert send.call_args.kwargs["retries"] == 2
        assert send.call_args.kwargs["queue"] == queue
        assert client.add_authorization.call_count == 1
    finally:
        grant_v4_creator_action.pop_request()
        app.conf.task_always_eager = previous


@pytest.mark.parametrize("cluster_name", [None, "cluster-a"])
@override_settings(
    RABBITMQ_HOST="backend.example.test",
    RABBITMQ_PORT=5673,
    RABBITMQ_VHOST="backend-vhost",
    RABBITMQ_USER="backend-user",
    RABBITMQ_PASS="password@with:reserved",
)
def test_api_producer_uses_worker_broker_configuration(monkeypatch, cluster_name):
    cluster = Mock(name=cluster_name)
    cluster.name = cluster_name
    cluster.is_default.return_value = cluster_name is None
    monkeypatch.setattr("config.celery.backend.get_cluster", lambda: cluster)
    current = current_app._get_current_object()
    with _backend_grant_app() as backend:
        expected = get_backend_celery_broker_config()
        assert backend.conf.broker_url == expected["broker_url"]
        assert backend.conf.broker_transport_options == expected["broker_transport_options"]
        with backend.connection_for_write() as connection:
            assert connection.hostname == "backend.example.test"
            assert connection.port == 5673
            assert connection.virtual_host == "backend-vhost"
            assert connection.userid == "backend-user"
            assert connection.password == "password@with:reserved"
        route = backend.amqp.router.route({"queue": "celery_cron"}, grant_v4_creator_action.name)
        assert route["queue"].name == "celery_cron"
        assert route["queue"].exchange.name == "celery_cron"
        if cluster_name:
            assert expected["broker_transport_options"] == {"queue_name_prefix": "cluster-a-"}
        else:
            assert expected["broker_transport_options"] == {}
    assert current_app._get_current_object() is current


@pytest.mark.parametrize("eager", [False, True])
def test_real_celery_publication_can_be_consumed_from_selected_queue(grant, monkeypatch, eager):
    """Real Celery/Kombu message roundtrip; memory transport, not a live worker."""
    from bkmonitor.iam.tasks import grant as module

    with Celery("offline-saas", broker="memory://", set_as_current=False) as saas, _backend_grant_app() as backend:
        backend.conf.broker_url = "memory://"
        saas.conf.update(task_always_eager=eager, task_serializer="pickle", accept_content=["pickle"])
        monkeypatch.setattr(module, "_backend_grant_app", lambda: nullcontext(backend))
        task = saas.tasks[grant_v4_creator_action.name]
        target_app = backend if eager else saas
        queue_name = "celery_cron" if eager else saas.conf.task_default_queue
        queue = target_app.amqp.queues[queue_name]
        with target_app.connection_for_write() as connection:
            bound = queue(connection)
            bound.declare()
            bound.purge()
            task.apply_async(kwargs=grant[2])
            message = bound.get(accept=["pickle"])
            assert message is not None
            assert message.headers["task"] == task.name
            _, kwargs, _ = message.payload
            assert kwargs == grant[2]
            assert kwargs["expired_at"] == 1893456000
            message.ack()
            # The receiving app has the task registered, not just a matching queue.
            received_task = target_app.tasks[message.headers["task"]]
            received_task.push_request(
                id=message.headers["id"],
                retries=1,
                called_directly=False,
                is_eager=False,
                args=(),
                kwargs=kwargs,
                delivery_info=message.delivery_info,
            )
            try:
                grant[1].add_authorization.side_effect = ProviderUnavailable("offline timeout")
                with pytest.raises(Retry):
                    received_task.run(**kwargs)
            finally:
                received_task.pop_request()
            retry_message = bound.get(accept=["pickle"])
            assert retry_message is not None
            assert retry_message.headers["retries"] == 2
            assert retry_message.headers["eta"] is not None
            assert retry_message.delivery_info["routing_key"] == message.delivery_info["routing_key"]
            assert retry_message.payload[1] == kwargs
            retry_message.ack()
        grant[1].add_authorization.assert_called_once_with(items=grant[2]["payload"], operator="alice")


@pytest.mark.skipif(settings.ROLE != "worker", reason="requires isolated Worker settings/bootstrap")
def test_real_backend_worker_and_api_producer_share_delivery_config():
    previous = current_app._get_current_object()
    try:
        from alarm_backends.service.scheduler.app import app as worker

        with _backend_grant_app() as producer:
            assert producer.conf.broker_url == worker.conf.broker_url
            assert producer.conf.broker_transport_options == worker.conf.broker_transport_options
            assert producer.amqp.queues["celery_cron"].as_dict() == worker.amqp.queues["celery_cron"].as_dict()
            task = worker.tasks[grant_v4_creator_action.name]
            assert task.app is worker
            assert not task.app.conf.task_always_eager
    finally:
        previous.set_current()


def test_transient_failure_retries_with_backoff(grant):
    _, client, data = grant
    client.add_authorization.side_effect = ProviderUnavailable("offline timeout")
    with patch.object(grant_v4_creator_action, "retry", side_effect=Retry()) as retry:
        with pytest.raises(Retry):
            run_task(data, retries=1)
    assert retry.call_args.kwargs["countdown"] == 60


@pytest.mark.parametrize("error,retries", [(ProviderError("invalid request"), 0), (ProviderUnavailable("offline"), 2)])
@override_settings(BK_IAM_GRANT_MAX_ATTEMPTS=3)
def test_final_and_exhausted_failure_stop_and_log_without_newline(grant, error, retries, caplog):
    _, client, data = grant
    client.add_authorization.side_effect = error
    with patch.object(grant_v4_creator_action, "retry") as retry:
        run_task(data, retries)
    retry.assert_not_called()
    assert any("final failure" in record.getMessage() for record in caplog.records)
    assert all("\n" not in record.getMessage() for record in caplog.records)

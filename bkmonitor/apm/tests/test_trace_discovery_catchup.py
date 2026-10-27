import datetime
import logging
from datetime import datetime as real_datetime
from types import SimpleNamespace

import fakeredis
import pytest

from apm.core.discover.base import TopoHandler
from apm.constants import ApmCacheType
from apm.core.handlers.apm_cache_handler import ApmCacheHandler
from apm.task import tasks


@pytest.fixture
def discovery(mocker):
    handler = object.__new__(TopoHandler)
    handler.bk_biz_id, handler.app_name, handler.task_id = 2, "catchup", "task-1"
    clock = mocker.patch("apm.core.discover.base.datetime.datetime")
    clock.now.return_value = real_datetime.fromtimestamp(10000)
    client = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=client)
    mocker.patch.object(handler, "_get_trace_task_splits", return_value=(10000, 1, "index"))
    mocker.patch.object(handler, "list_trace_ids", return_value=[])
    mocker.patch("apm.core.discover.base.DiscoverContainer.list_discovers", return_value=[])
    mocker.patch.object(TopoHandler, "_trace_target", new_callable=mocker.PropertyMock, return_value=SimpleNamespace())
    query_class = mocker.patch("apm.core.discover.base.SpanQuery")
    query_class.QUERY_MAX_LIMIT = 10000
    query = query_class.return_value.query_group_list
    query.return_value = []
    heartbeat = mocker.patch("apm.core.discover.base.TopoNode.touch_heartbeat", return_value=True)
    mocker.patch("apm.core.discover.base.ThreadPool").return_value.map_ignore_exception.side_effect = lambda fn, args: [
        fn(*item) for item in args
    ]
    return SimpleNamespace(
        handler=handler,
        client=client,
        query=query,
        heartbeat=heartbeat,
        clock=clock,
        key=ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 2, "catchup", data_type="TRACE"),
    )


@pytest.mark.parametrize("last_check, expected_start", [(None, 6400), (7000, 7000), (1000, 6400), (11000, 6400)])
def test_fallback_window_and_success_checkpoint(discovery, last_check, expected_start):
    if last_check is not None:
        discovery.client.set(discovery.key, last_check)
    assert discovery.handler.discover() is True
    assert discovery.query.call_args.args == (expected_start, 10000)
    assert discovery.client.get(discovery.key) == "10000"
    assert 0 < discovery.client.ttl(discovery.key) <= 3600


def test_delayed_round_continues_from_previous_query_end(discovery):
    assert discovery.handler.discover() is True
    discovery.clock.now.return_value = real_datetime.fromtimestamp(11800)
    assert discovery.handler.discover() is True
    assert discovery.query.call_args.args == (10000, 11800)
    assert discovery.client.get(discovery.key) == "11800"


def test_checkpoint_isolated_by_application_source_and_environment(settings):
    settings.PLATFORM, settings.ENVIRONMENT = "test", "test"
    key = ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 2, "app", data_type="TRACE")
    assert key.endswith("2_app_TRACE")
    assert (
        ApmCacheHandler.get_cache_key(ApmCacheType.TOPO_INSTANCE, 2, "app")
        == "BKMONITOR_test_test_APM_TOPO_INSTANCE_HEARTBEAT_2_app"
    )
    assert (
        len(
            {
                key,
                ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 3, "app", data_type="TRACE"),
                ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 2, "other", data_type="TRACE"),
                ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 2, "app", data_type="METRIC"),
            }
        )
        == 4
    )
    settings.ENVIRONMENT = "another"
    assert key != ApmCacheHandler.get_cache_key(ApmCacheType.DISCOVERY_CHECK, 2, "app", data_type="TRACE")


@pytest.mark.parametrize("failure", ["query", "discoverer", "heartbeat", "heartbeat_lock"])
def test_failed_or_incomplete_fallback_keeps_checkpoint(discovery, mocker, failure):
    discovery.client.set(discovery.key, 7000)
    if failure == "query":
        discovery.query.side_effect = RuntimeError("query unavailable")
    elif failure == "discoverer":
        mocker.patch.object(discovery.handler, "_discover_spans", return_value=False)
    elif failure == "heartbeat":
        discovery.heartbeat.side_effect = RuntimeError("write unavailable")
    elif failure == "heartbeat_lock":
        discovery.heartbeat.return_value = False
    if failure in ("query", "heartbeat"):
        with pytest.raises(RuntimeError):
            discovery.handler.discover()
    else:
        assert discovery.handler.discover() is False
    assert discovery.client.get(discovery.key) == "7000"


def make_span(name, kind, end):
    return {"resource": {"service.name": name}, "kind": kind, "end_time": end * 1000000}


def test_single_collapse_uses_kind_priority_and_selected_span_heartbeat(discovery, mocker):
    selected = [make_span("mixed", 3, 8000), make_span("internal-only", 1, 9800), make_span("server", 2, 9700)]
    discovery.query.return_value = selected
    discover = mocker.patch.object(discovery.handler, "_discover_spans", return_value=True)
    assert discovery.handler.discover() is True
    discovery.query.assert_called_once()
    call = discovery.query.call_args
    assert call.args == (6400, 10000)
    assert call.kwargs["limit"] == 10000
    assert call.kwargs["sort"] == ["kind desc", "end_time desc"]
    assert discover.call_args.args[0] == selected
    assert discovery.heartbeat.call_args.args[3] == {"mixed": 8000, "internal-only": 9800, "server": 9700}


def test_discoverer_failure_is_not_logged_as_success(discovery, mocker, caplog):
    class FailingDiscoverer:
        def __init__(self, *args):
            pass

        def discover(self, *args):
            raise RuntimeError("write failed")

    with caplog.at_level(logging.INFO, logger="apm"):
        assert discovery.handler._discover_handle(FailingDiscoverer, [], "topo", {}) is False
    assert "event=discoverer_failed" in caplog.text
    assert "task_id=task-1" in caplog.text
    assert "event=discoverer_finished" not in caplog.text


def test_cron_filters_before_lock_and_preserves_quick_interval(mocker, settings, caplog):
    now = datetime.datetime(2026, 10, 26, 17, 0, tzinfo=datetime.UTC)
    settings.APM_APPLICATION_QUICK_REFRESH_INTERVAL = 2
    settings.APM_APPLICATION_QUICK_REFRESH_DELTA = 30
    mocker.patch.object(tasks.timezone, "now", return_value=now)
    mocker.patch.object(tasks.time, "time", return_value=now.timestamp() + 5)
    mocker.patch.object(tasks.EbpfApplicationConfig.objects, "all").return_value.values.return_value = []
    mocker.patch.object(tasks.ApmApplication.objects, "filter").return_value.values_list.return_value = [
        (2, "old-due", 10, now - datetime.timedelta(hours=1)),
        (2, "old-skip", 12, now - datetime.timedelta(hours=1)),
        (2, "new-due", 22, now),
        (2, "new-skip", 23, now),
    ]
    lock = mocker.patch.object(tasks.ApmCacheHandler, "distributed_lock")
    dispatch = mocker.patch.object(tasks.handler, "apply_async")
    with caplog.at_level(logging.INFO, logger="apm"):
        tasks.topo_discover_cron()
    assert lock.call_args_list == [mocker.call("topo_discover", app_id=10), mocker.call("topo_discover", app_id=22)]
    assert [call.kwargs["args"] for call in dispatch.call_args_list] == [(2, "old-due"), (2, "new-due")]
    assert all("discovery_enqueued_at" in call.kwargs["headers"] for call in dispatch.call_args_list)
    assert caplog.text.count("dispatch_delay_s=5.000") == 2


@pytest.mark.parametrize("result, status", [(True, "success"), (False, "partial"), (None, "partial")])
def test_task_lifecycle_logs_result_and_queue_time(mocker, caplog, result, status):
    topo = mocker.patch.object(tasks, "TopoHandler").return_value
    topo.discover.return_value = result
    mocker.patch.object(tasks.time, "time", return_value=105.0)
    with caplog.at_level(logging.INFO, logger="apm"):
        tasks.handler.push_request(id="task-1", headers={"discovery_enqueued_at": 100.0})
        try:
            tasks.handler.run(2, "app")
        finally:
            tasks.handler.pop_request()
    assert "event=started" in caplog.text
    assert "queue_delay_s=5.0" in caplog.text
    assert f"status={status}" in caplog.text
    assert "event=finished" in caplog.text
    assert "task_id=task-1" in caplog.text


def test_legacy_task_without_headers_and_failure_logs(mocker, caplog):
    topo = mocker.patch.object(tasks, "TopoHandler").return_value
    topo.discover.side_effect = RuntimeError("failed")
    with caplog.at_level(logging.INFO, logger="apm"), pytest.raises(RuntimeError):
        tasks.handler(2, "app")
    assert "queue_delay_s=None" in caplog.text
    assert "event=failed" in caplog.text
    assert "event=finished" in caplog.text
    assert "status=failed" in caplog.text


def test_collapse_keeps_kind_then_time_order_and_application_guard(mocker):
    from apm.core.handlers.query.span_query import SpanQuery
    from bkmonitor.data_source.utils.apm import TraceDatasourceTarget

    target = TraceDatasourceTarget.build(2, "app", "apm_global.shared_trace")
    query = SpanQuery([target])
    request = mocker.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", return_value=[])
    query.query_group_list(
        100,
        200,
        "resource.service.name",
        sort=["kind desc", "end_time desc"],
    )
    body = request.call_args.kwargs["query_body"]
    assert body["order_by"] == ["-kind", "-end_time"]
    config = body["query_configs"][0]
    assert config["distinct"] == "resource.service.name"
    assert config["select"] == []
    assert "kind" not in str(config["filter_dict"])
    assert "app_name" in str(config["filter_dict"])
    assert "bk_biz_id" in str(config["filter_dict"])
    assert body["start_time"] == 100000
    assert body["end_time"] == 200000


def test_checkpoint_uses_query_boundary_instead_of_finish_time(discovery):
    discovery.clock.now.side_effect = [real_datetime.fromtimestamp(10000), real_datetime.fromtimestamp(10500)]
    assert discovery.handler.discover() is True
    assert discovery.client.get(discovery.key) == "10000"
    assert discovery.heartbeat.call_args.args[-1] == 10500


def test_invalid_datasource_logs_skipped_without_discovering(mocker, caplog):
    topo = mocker.patch.object(tasks, "TopoHandler").return_value
    topo.is_valid.return_value = False
    with caplog.at_level(logging.INFO, logger="apm"):
        tasks.handler(2, "app")
    topo.discover.assert_not_called()
    assert "status=skipped" in caplog.text


def test_dispatch_failure_releases_real_lock_and_identifies_application(mocker, settings, caplog):
    now = real_datetime(2026, 10, 26, 17, 0, tzinfo=datetime.UTC)
    settings.APM_APPLICATION_QUICK_REFRESH_INTERVAL = 2
    settings.APM_APPLICATION_QUICK_REFRESH_DELTA = 30
    mocker.patch.object(tasks.timezone, "now", return_value=now)
    mocker.patch.object(tasks.EbpfApplicationConfig.objects, "all").return_value.values.return_value = []
    mocker.patch.object(tasks.ApmApplication.objects, "filter").return_value.values_list.return_value = [
        (2, "app", 10, now - datetime.timedelta(hours=1))
    ]
    client = fakeredis.FakeRedis(decode_responses=True)
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=client)

    def fail(**kwargs):
        assert client.get("apm.tasks.topo.discover.10") is not None
        raise RuntimeError("broker unavailable")

    mocker.patch.object(tasks.handler, "apply_async", side_effect=fail)
    with caplog.at_level(logging.INFO, logger="apm"), pytest.raises(RuntimeError):
        tasks.topo_discover_cron()
    assert client.get("apm.tasks.topo.discover.10") is None
    assert "event=dispatch_failed bk_biz_id=2 app_name=app" in caplog.text
    assert "event=dispatched" not in caplog.text

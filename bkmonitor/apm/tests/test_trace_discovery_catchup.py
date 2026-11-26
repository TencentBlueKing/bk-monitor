import datetime
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime as real_datetime
from threading import Event
from types import SimpleNamespace

import fakeredis
import pytest
from celery.exceptions import Retry
from celery.signals import before_task_publish
from django.db import OperationalError
from redis.lock import Lock

from alarm_backends.service.scheduler.tasks import cron
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
        key=ApmCacheHandler.get_cache_key(ApmCacheType.TRACE_DISCOVERY_CHECK, 2, "catchup"),
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


def test_summary_separates_regular_span_fetch_discovery_and_fallback(discovery, mocker, caplog):
    elapsed = 0
    clock = mocker.patch("apm.core.discover.base.time")
    clock.monotonic.side_effect = lambda: elapsed
    discovery.handler.list_trace_ids.return_value = [["first"], ["second"]]

    def fetch(*args):
        nonlocal elapsed
        elapsed += 3
        return []

    def process(*args, is_fallback=False):
        nonlocal elapsed
        elapsed += 7 if is_fallback else 2
        return True

    mocker.patch.object(discovery.handler, "list_span_by_trace_ids", side_effect=fetch)
    mocker.patch.object(discovery.handler, "_discover_spans", side_effect=process)
    with caplog.at_level(logging.INFO, logger="apm"):
        assert discovery.handler.discover() is True
    (summary,) = [r.getMessage() for r in caplog.records if "event=summary" in r.getMessage()]
    assert "fallback_duration_s=7.000" in summary
    assert "span_fetch_duration_s=6.000 regular_discovery_duration_s=4.000" in summary


def test_trace_checkpoint_isolated_by_application_and_environment(settings):
    settings.PLATFORM, settings.ENVIRONMENT = "test", "test"
    key = ApmCacheHandler.get_cache_key(ApmCacheType.TRACE_DISCOVERY_CHECK, 2, "app")
    assert key == "BKMONITOR_test_test_APM_DISCOVERY_CHECK_2_app_TRACE"
    assert (
        ApmCacheHandler.get_cache_key(ApmCacheType.TOPO_INSTANCE, 2, "app")
        == "BKMONITOR_test_test_APM_TOPO_INSTANCE_HEARTBEAT_2_app"
    )
    assert (
        len(
            {
                key,
                ApmCacheHandler.get_cache_key(ApmCacheType.TRACE_DISCOVERY_CHECK, 3, "app"),
                ApmCacheHandler.get_cache_key(ApmCacheType.TRACE_DISCOVERY_CHECK, 2, "other"),
            }
        )
        == 3
    )
    settings.ENVIRONMENT = "another"
    assert key != ApmCacheHandler.get_cache_key(ApmCacheType.TRACE_DISCOVERY_CHECK, 2, "app")


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


@pytest.fixture
def dispatch_round(mocker, settings):
    now = real_datetime(2026, 10, 26, 17, 0, tzinfo=datetime.UTC)
    settings.APM_APPLICATION_QUICK_REFRESH_INTERVAL = 2
    settings.APM_APPLICATION_QUICK_REFRESH_DELTA = 30
    clock = mocker.patch.object(tasks.timezone, "now", return_value=now)
    mocker.patch.object(tasks.EbpfApplicationConfig.objects, "all").return_value.values.return_value = []
    apps = []
    mocker.patch.object(tasks.ApmApplication.objects, "filter").return_value.values_list.return_value = apps
    redis = fakeredis.FakeRedis()
    mocker.patch.object(ApmCacheHandler, "get_redis_client", return_value=redis)

    # fakeredis without its Lua extra lacks the compare-and-delete release script.
    def release(lock, token):
        assert lock.redis.get(lock.name) == token
        lock.redis.delete(lock.name)

    mocker.patch.object(Lock, "do_release", release)
    mocker.patch.object(cron.metrics, "report_all")
    send = mocker.patch.object(tasks.handler, "apply_async", return_value=SimpleNamespace(id="child"))
    return SimpleNamespace(now=now, clock=clock, apps=apps, send=send)


def run_round(scheduled_at):
    cron.apm_task_tasks_topo_discover_cron.apply(
        headers={"discovery_scheduled_at": scheduled_at.timestamp()}, throw=True
    )


def test_only_trace_discovery_parent_gets_schedule_header():
    sender = cron.apm_task_tasks_topo_discover_cron.name
    headers = {}
    started = int(time.time())
    before_task_publish.send(sender=sender, headers=headers)
    assert started <= headers["discovery_scheduled_at"] <= time.time()
    headers["discovery_scheduled_at"] = 123
    before_task_publish.send(sender=sender, headers=headers)
    assert headers["discovery_scheduled_at"] == 123
    child_headers = {}
    before_task_publish.send(sender=tasks.handler.name, headers=child_headers)
    assert "discovery_scheduled_at" not in child_headers


def test_cron_preserves_quick_interval_for_legacy_and_direct_calls(dispatch_round, mocker, caplog):
    now = dispatch_round.now
    dispatch_round.apps.extend(
        [
            (2, "old-due", 10, now - datetime.timedelta(hours=1)),
            (2, "old-skip", 12, now - datetime.timedelta(hours=1)),
            (2, "new-due", 22, now),
            (2, "new-skip", 23, now),
        ]
    )
    mocker.patch.object(tasks.time, "time", return_value=now.timestamp() + 5)
    with caplog.at_level(logging.INFO, logger="apm"):
        cron.apm_task_tasks_topo_discover_cron.apply(throw=True)
        assert dispatch_round.send.call_count == 2
        tasks.topo_discover_cron()
    calls = dispatch_round.send.call_args_list
    assert [call.kwargs["args"] for call in calls] == [(2, "old-due"), (2, "new-due")]
    assert all(call.kwargs["headers"]["discovery_enqueued_at"] == now.timestamp() + 5 for call in calls)
    assert caplog.text.count("dispatch_delay_s=5.000") == 2


def test_skipped_applications_do_not_access_redis(dispatch_round, mocker):
    now = dispatch_round.now
    dispatch_round.apps.extend([(2, "old", 12, now - datetime.timedelta(hours=1)), (2, "new", 23, now)])
    redis = mocker.patch.object(ApmCacheHandler, "get_redis_client")
    run_round(now)
    redis.assert_not_called()
    dispatch_round.send.assert_not_called()


def test_delayed_parent_uses_original_slot_and_application_age(dispatch_round):
    scheduled = dispatch_round.now + datetime.timedelta(minutes=2)
    dispatch_round.clock.return_value = scheduled + datetime.timedelta(minutes=11)
    dispatch_round.apps.extend(
        [
            (2, "old-due", 12, scheduled - datetime.timedelta(hours=1)),
            (2, "quick-at-schedule", 20, scheduled - datetime.timedelta(minutes=29)),
            (2, "created-later", 24, scheduled + datetime.timedelta(minutes=1)),
            (2, "created-within-minute", 26, scheduled + datetime.timedelta(seconds=20)),
            (2, "due-at-worker-start", 13, scheduled - datetime.timedelta(hours=1)),
        ]
    )
    run_round(scheduled)
    run_round(scheduled + datetime.timedelta(seconds=40))
    assert [call.kwargs["args"] for call in dispatch_round.send.call_args_list] == [
        (2, "old-due"),
        (2, "quick-at-schedule"),
    ]


def test_registered_parent_reports_final_failure_after_retry_limit(dispatch_round):
    task = cron.apm_task_tasks_topo_discover_cron
    tasks.ApmApplication.objects.filter.side_effect = OperationalError("application catalog unavailable")
    with pytest.raises(OperationalError, match="application catalog unavailable"):
        task.apply(retries=task.max_retries, throw=True)
    dispatch_round.send.assert_not_called()


def test_application_query_failure_retries_original_minute(dispatch_round):
    scheduled = dispatch_round.now
    created = scheduled - datetime.timedelta(hours=1)
    applications = [(2, "original-slot", 10, created), (2, "retry-slot", 12, created)]
    tasks.ApmApplication.objects.filter.return_value.values_list.side_effect = [
        OperationalError("application catalog unavailable"),
        applications,
    ]
    dispatch_round.clock.return_value = scheduled + datetime.timedelta(minutes=1)
    with pytest.raises(Retry) as retry:
        run_round(scheduled)
    dispatch_round.send.assert_not_called()
    assert retry.value.sig.options["headers"]["discovery_scheduled_at"] == scheduled.timestamp()
    dispatch_round.clock.return_value = scheduled + datetime.timedelta(minutes=2)
    retry.value.sig.apply(throw=True)
    assert [call.kwargs["args"] for call in dispatch_round.send.call_args_list] == [(2, "original-slot")]


@pytest.mark.parametrize("minutes_apart, expected_sends", [(0, 1), (2, 2)])
def test_overlapping_parent_rounds(dispatch_round, minutes_apart, expected_sends):
    scheduled = dispatch_round.now
    dispatch_round.apps.append((2, "quick", 10, scheduled - datetime.timedelta(minutes=1)))
    entered, resume = Event(), Event()

    def send(**kwargs):
        if not entered.is_set():
            entered.set()
            if not resume.wait(timeout=5):
                raise TimeoutError("overlapping parent did not finish")
        return SimpleNamespace(id="child")

    dispatch_round.send.side_effect = send
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(run_round, scheduled)
        try:
            assert entered.wait(timeout=5)
            try:
                run_round(scheduled + datetime.timedelta(minutes=minutes_apart))
            except Retry as retry:
                assert minutes_apart == 0
                replay = retry.sig
            else:
                replay = None
        finally:
            resume.set()
        first.result(timeout=5)
    if replay is not None:
        replay.apply(throw=True)
    assert dispatch_round.send.call_count == expected_sends


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


def test_dispatch_failure_retries_original_minute_and_continues_next_application(dispatch_round, caplog):
    now = dispatch_round.now
    created = now - datetime.timedelta(hours=1)
    dispatch_round.apps.extend([(2, "app", 10, created), (2, "next-app", 20, created)])
    dispatch_round.send.side_effect = [
        RuntimeError("broker unavailable"),
        SimpleNamespace(id="healthy"),
        SimpleNamespace(id="retried"),
    ]
    with caplog.at_level(logging.INFO, logger="apm"), pytest.raises(Retry) as retry:
        # Messages from older beat processes have no timestamp yet.
        cron.apm_task_tasks_topo_discover_cron.apply(throw=True)
    assert [call.kwargs["args"] for call in dispatch_round.send.call_args_list] == [(2, "app"), (2, "next-app")]
    assert "event=dispatch_failed bk_biz_id=2 app_name=app" in caplog.text
    assert "event=dispatched bk_biz_id=2 app_name=next-app task_id=healthy" in caplog.text
    assert retry.value.sig.options["headers"]["discovery_scheduled_at"] == now.timestamp()
    dispatch_round.clock.return_value = now + datetime.timedelta(minutes=1)
    retry.value.sig.apply(throw=True)
    assert [call.kwargs["args"] for call in dispatch_round.send.call_args_list] == [
        (2, "app"),
        (2, "next-app"),
        (2, "app"),
    ]


@pytest.mark.parametrize("fail_scan, fail_flush", [(False, False), (True, False), (False, True), (True, True)])
def test_regular_discovery_reuses_instances_and_flushes_before_fallback(discovery, mocker, fail_scan, fail_flush):
    from apm.core.discover.cached_mixin import CachedDiscoverMixin

    events = []

    class CachedDiscoverer(CachedDiscoverMixin):
        DISCOVERY_ALL_SPANS = True
        DISCOVERY_REQUIRES_TRACE_CONTEXT = False

        def __init__(self, *args):
            self.pages = 0

        @classmethod
        def _get_cache_type(cls):
            return "test"

        @classmethod
        def to_cache_key(cls, instance):
            return "test"

        @classmethod
        def build_instance_data(cls, instance):
            return instance

        def get_remain_data(self):
            events.append(("read", self))
            return {}

        def discover(self, spans, remain):
            self.pages += 1
            events.append(("discover", self))

        def flush_cache_updates(self):
            events.append(("flush", self))
            if fail_flush:
                raise RuntimeError("flush failed")

    class OtherDiscoverer(CachedDiscoverer):
        def flush_cache_updates(self):
            events.append(("other_flush", self))

    def pages(*args):
        yield ["first"]
        yield ["second"]
        if fail_scan:
            raise RuntimeError("scan failed")

    mocker.patch(
        "apm.core.discover.base.DiscoverContainer.list_discovers", return_value=[CachedDiscoverer, OtherDiscoverer]
    )
    mocker.patch.object(discovery.handler, "list_trace_ids", side_effect=pages)
    mocker.patch.object(discovery.handler, "list_span_by_trace_ids", return_value=[make_span("service", 2, 9000)])
    discovery.client.set(discovery.key, 7000)
    if fail_scan:
        with pytest.raises(RuntimeError, match="scan failed"):
            discovery.handler.discover()
    else:
        assert discovery.handler.discover() is (not fail_flush)

    regular = [obj for event, obj in events if event == "flush"]
    assert len(regular) == 1
    assert regular[0].pages == 2
    assert len([event for event, _ in events if event == "other_flush"]) == 1
    if fail_scan:
        assert len([event for event, _ in events if event == "read"]) == 2
    else:
        fallback_reads = [i for i, (event, _) in enumerate(events) if event == "read"][2:]
        assert all(i > next(j for j, (event, _) in enumerate(events) if event == "other_flush") for i in fallback_reads)
    assert discovery.client.get(discovery.key) == ("7000" if fail_scan or fail_flush else "10000")

import json
import threading
import time
from collections import Counter
from collections.abc import Generator, Iterator
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest
from django.test import override_settings
from rest_framework.exceptions import ValidationError

from bkmonitor.data_source.data_source import BkApmTraceDataSource
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.resource import ResourceEnum
from constants.apm import PreCalculateSpecificField
from monitor_web.overview.search import ApmApplicationSearchItem, SearchItem, Searcher, TraceSearchItem
from monitor_web.overview.views import SearchSerializer, SearchViewSet


TRACE_ID = "a" * 32


def _app(application_id: int, bk_biz_id: int = 2) -> SimpleNamespace:
    return SimpleNamespace(
        application_id=application_id,
        bk_biz_id=bk_biz_id,
        app_name=f"app_{application_id}",
        app_alias=f"应用 {application_id}",
        trace_result_table_id=f"{application_id}_bkmonitor_trace",
        service_count=1,
    )


@pytest.fixture(autouse=True)
def application_permission() -> Iterator[mock.MagicMock]:
    def _allow_all(actions: list, resources: list) -> dict[str, dict[str, bool]]:
        return {str(resource[0].id): {action.id: True for action in actions} for resource in resources}

    with (
        mock.patch("bkmonitor.iam.drf.Permission") as permission_class,
        mock.patch("bkmonitor.iam.drf.check_iam_batch_preflight", return_value=None),
    ):
        permission_class.return_value.batch_is_allowed.side_effect = _allow_all
        yield permission_class


class TestTraceSearchItem:
    @pytest.mark.parametrize("path", ["precalc", "raw"])
    def test_business_permission_does_not_expose_denied_application(
        self, path: str, application_permission: mock.MagicMock
    ) -> None:
        app = _app(1)
        queryset = mock.MagicMock()
        queryset.exclude.return_value = queryset
        queryset.order_by.return_value = queryset
        queryset.only.return_value = queryset
        queryset.first.return_value = app
        queryset.__iter__.return_value = iter([app])
        application_permission.return_value.batch_is_allowed.side_effect = None
        application_permission.return_value.batch_is_allowed.return_value = {
            str(app.application_id): {ActionEnum.VIEW_APM_APPLICATION.id: False}
        }

        with (
            mock.patch.object(TraceSearchItem, "_aggregate_user_visits", return_value={}),
            mock.patch.object(TraceSearchItem, "_get_default_biz_id", return_value=None),
            mock.patch.object(TraceSearchItem, "_get_allowed_bk_biz_ids", return_value=[app.bk_biz_id]) as allowed_biz,
            mock.patch("monitor_web.overview.search.Application.objects.filter", return_value=queryset),
            mock.patch.object(TraceSearchItem, "_load_precalc_table_ids", return_value=["precalc_table"]),
            mock.patch.object(
                TraceSearchItem,
                "_query_precalc_apps_by_trace_ids",
                return_value=[{"trace_id": TRACE_ID, "biz_id": app.bk_biz_id, "app_name": app.app_name}],
            ),
            mock.patch.object(TraceSearchItem, "_query_raw_apps_by_trace_ids", return_value=[TRACE_ID]),
            mock.patch.object(
                TraceSearchItem, f"_path_{'raw' if path == 'precalc' else 'precalc'}", return_value=iter([])
            ),
            mock.patch.object(TraceSearchItem, "_get_biz_name") as biz_name,
        ):
            snapshots = list(TraceSearchItem.search("tenant", "user", TRACE_ID, current_bk_biz_id=app.bk_biz_id))

        assert snapshots == []
        biz_name.assert_not_called()
        application_permission.assert_called_once_with(username="user", bk_tenant_id="tenant", request=None)
        actions, resources = application_permission.return_value.batch_is_allowed.call_args.args
        assert actions == [ActionEnum.VIEW_APM_APPLICATION]
        assert resources[0][0].type == ResourceEnum.APM_APPLICATION.id
        assert str(resources[0][0].id) == str(app.application_id)
        assert resources[0][0].attributes["bk_biz_id"] == str(app.bk_biz_id)
        if path == "raw":
            allowed_biz.assert_called_once_with("tenant", "user", ActionEnum.VIEW_BUSINESS)

    def test_denied_hits_do_not_consume_top_k_or_repeat_permission_checks(
        self, application_permission: mock.MagicMock
    ) -> None:
        apps = [_app(application_id) for application_id in range(1, 8)]

        def _allowed(actions: list, resources: list) -> dict[str, dict[str, bool]]:
            return {
                str(resource[0].id): {action.id: int(resource[0].id) > 3 for action in actions}
                for resource in resources
            }

        application_permission.return_value.batch_is_allowed.side_effect = _allowed
        with (
            mock.patch.object(
                TraceSearchItem,
                "_path_precalc",
                return_value=iter((TRACE_ID, app) for app in [*apps[:3], *apps[:3], *apps[3:]]),
            ),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "user", TRACE_ID))

        assert [item["application_id"] for item in snapshots[-1]["items"]] == [4, 5, 6]
        assert application_permission.return_value.batch_is_allowed.call_count == 6

    @pytest.mark.parametrize("allowed_application_count", [0, 1])
    def test_permission_failure_preserves_checked_hits_and_stops_batch(
        self, application_permission: mock.MagicMock, allowed_application_count: int
    ) -> None:
        apps = [_app(index) for index in range(1, 4)]
        application_permission.return_value.batch_is_allowed.side_effect = [
            *[
                {str(app.application_id): {ActionEnum.VIEW_APM_APPLICATION.id: True}}
                for app in apps[:allowed_application_count]
            ],
            RuntimeError("permission query failed"),
        ]
        snapshots: list[dict[str, Any]] = []
        with (
            mock.patch("monitor_web.overview.search.ThreadPool") as pool,
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter((TRACE_ID, app) for app in apps)),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2") as biz_name,
        ):
            pool.return_value.apply_async.side_effect = lambda callback, args: callback(*args)
            with pytest.raises(RuntimeError, match="permission query failed"):
                snapshots.extend(TraceSearchItem.search("tenant", "user", TRACE_ID))

        assert [[item["application_id"] for item in snapshot["items"]] for snapshot in snapshots] == (
            [[apps[0].application_id]] if allowed_application_count else []
        )
        assert application_permission.return_value.batch_is_allowed.call_count == allowed_application_count + 1
        assert biz_name.call_count == allowed_application_count
        pool.return_value.terminate.assert_called_once()

    def test_close_after_permission_failure_snapshot_stops_search(self, application_permission: mock.MagicMock) -> None:
        apps = [_app(index) for index in range(1, 4)]
        application_permission.return_value.batch_is_allowed.side_effect = [
            {str(apps[0].application_id): {ActionEnum.VIEW_APM_APPLICATION.id: True}},
            RuntimeError("permission query failed"),
        ]
        with (
            mock.patch("monitor_web.overview.search.ThreadPool") as pool,
            mock.patch.object(
                TraceSearchItem, "_path_precalc", return_value=iter((TRACE_ID, app) for app in apps)
            ) as precalc,
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            pool.return_value.apply_async.side_effect = lambda callback, args: callback(*args)
            results = TraceSearchItem.search("tenant", "user", TRACE_ID)
            try:
                snapshot = next(results)
                assert [item["application_id"] for item in snapshot["items"]] == [apps[0].application_id]
            finally:
                results.close()

        assert application_permission.return_value.batch_is_allowed.call_count == 2
        assert precalc.call_args.kwargs["trace_stop"].is_set()
        pool.return_value.terminate.assert_called_once()

    def test_collect_candidate_apps_uses_slim_query_and_preserves_priority(self) -> None:
        visited_app = _app(4, bk_biz_id=3)
        current_service_app = _app(3)
        current_no_service_app = _app(2)
        current_no_service_app.service_count = 0
        allowed_service_app = _app(1, bk_biz_id=4)

        application_queryset = mock.MagicMock()
        application_queryset.exclude.return_value = application_queryset
        application_queryset.order_by.return_value = application_queryset
        application_queryset.only.return_value = application_queryset
        application_queryset.__iter__.return_value = iter(
            [allowed_service_app, current_no_service_app, current_service_app, visited_app]
        )

        with (
            mock.patch.object(
                TraceSearchItem,
                "_aggregate_user_visits",
                return_value={(visited_app.bk_biz_id, visited_app.app_name): 1},
            ),
            mock.patch.object(TraceSearchItem, "_get_default_biz_id", return_value=2),
            mock.patch.object(TraceSearchItem, "_get_allowed_bk_biz_ids", return_value=[4]),
            mock.patch(
                "monitor_web.overview.search.Application.objects.filter", return_value=application_queryset
            ) as filter_apps,
        ):
            candidates = TraceSearchItem._collect_candidate_apps("tenant", "admin", bk_biz_id=2)

        assert [app.application_id for app in candidates] == [4, 3, 2, 1]
        assert set(filter_apps.call_args.kwargs["bk_biz_id__in"]) == {2, 3, 4}
        application_queryset.exclude.assert_called_once_with(trace_result_table_id="")
        application_queryset.order_by.assert_called_once_with()
        assert set(application_queryset.only.call_args.args) == {
            "application_id",
            "bk_biz_id",
            "app_name",
            "app_alias",
            "trace_result_table_id",
            "service_count",
        }

    def test_streams_cumulative_unique_snapshots(self) -> None:
        app_a = _app(1)
        app_b = _app(2)
        app_c = _app(3)

        with (
            mock.patch.object(
                TraceSearchItem, "_path_precalc", return_value=iter([(TRACE_ID, app_a), (TRACE_ID, app_b)])
            ),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([(TRACE_ID, app_a), (TRACE_ID, app_c)])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", side_effect=lambda bk_biz_id: f"业务 {bk_biz_id}"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert all(isinstance(snapshot, dict) for snapshot in snapshots)
        assert all(snapshot["type"] == "trace" and snapshot["name"] == "Trace" for snapshot in snapshots)

        previous_application_ids: list[int] = []
        for snapshot in snapshots:
            application_ids = [item["application_id"] for item in snapshot["items"]]
            assert len(application_ids) > len(previous_application_ids)
            assert application_ids[: len(previous_application_ids)] == previous_application_ids
            assert len(application_ids) == len(set(application_ids))
            previous_application_ids = application_ids

        assert set(previous_application_ids) == {1, 2, 3}

    def test_candidate_exhaustion_keeps_partial_snapshots(self) -> None:
        app_a = _app(1)
        app_b = _app(2)

        with (
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter([(TRACE_ID, app_a)])),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([(TRACE_ID, app_b)])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert {item["application_id"] for item in snapshots[-1]["items"]} == {1, 2}

    def test_stops_after_three_unique_applications(self) -> None:
        apps = [_app(application_id) for application_id in range(1, 5)]

        with (
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter((TRACE_ID, app) for app in apps)),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert [item["application_id"] for item in snapshots[-1]["items"]] == [1, 2, 3]

    def test_batch_coalesces_ready_hits_and_keeps_final_snapshot(self, application_permission: mock.MagicMock) -> None:
        trace_ids = [TRACE_ID, "b" * 32]
        apps = [_app(1), _app(2)]
        precalc_hits = [(trace_id, app) for app in apps for trace_id in trace_ids]

        with (
            mock.patch("monitor_web.overview.search.ThreadPool") as pool,
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter(precalc_hits)),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([(TRACE_ID, apps[0])])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            pool.return_value.apply_async.side_effect = lambda callback, args: callback(*args)
            snapshots = list(TraceSearchItem.search("tenant", "admin", ",".join(trace_ids)))

        assert len(snapshots) == 1
        assert snapshots[0]["type"] == "trace"
        assert snapshots[0]["name"] == "Trace"
        assert [(item["trace_id"], item["application_id"]) for item in snapshots[0]["items"]] == [
            (trace_id, app.application_id) for app in apps for trace_id in trace_ids
        ]
        assert application_permission.return_value.batch_is_allowed.call_count == 2

    def test_batch_streams_first_hit_without_waiting_for_next_hit(self) -> None:
        trace_ids = [TRACE_ID, "b" * 32]
        app = _app(1)
        release = threading.Event()
        waiting = threading.Event()
        path_done = threading.Event()

        def _precalc_path() -> Generator[tuple[str, SimpleNamespace], None, None]:
            try:
                yield trace_ids[0], app
                waiting.set()
                release.wait(timeout=1)
                yield trace_ids[1], app
            finally:
                path_done.set()

        with (
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=_precalc_path()),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            results = TraceSearchItem.search("tenant", "admin", ",".join(trace_ids))
            try:
                first = next(results)
                assert [item["trace_id"] for item in first["items"]] == [trace_ids[0]]
                assert waiting.wait(timeout=1)
                assert not path_done.is_set()
                release.set()
                remaining = list(results)
            finally:
                release.set()
                results.close()

        assert path_done.wait(timeout=1)
        assert len(remaining) == 1
        assert [item["trace_id"] for item in remaining[0]["items"]] == trace_ids

    def test_deadline_keeps_partial_results_without_waiting_for_slow_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert TraceSearchItem._TRACE_SEARCH_TIMEOUT == 10

        app = _app(1)
        release = threading.Event()
        precalc_done = threading.Event()
        raw_done = threading.Event()

        def _precalc_path() -> Generator[tuple[str, SimpleNamespace], None, None]:
            try:
                yield TRACE_ID, app
                release.wait(timeout=1)
            finally:
                precalc_done.set()

        def _raw_path() -> Generator[tuple[str, SimpleNamespace], None, None]:
            try:
                release.wait(timeout=1)
            finally:
                raw_done.set()
            yield from ()

        monkeypatch.setattr(TraceSearchItem, "_TRACE_SEARCH_TIMEOUT", 0.05, raising=False)
        started_at = time.monotonic()
        try:
            with (
                mock.patch.object(TraceSearchItem, "_path_precalc", return_value=_precalc_path()),
                mock.patch.object(TraceSearchItem, "_path_raw", return_value=_raw_path()),
                mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
            ):
                snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))
        finally:
            release.set()

        assert time.monotonic() - started_at < 0.5
        assert [len(snapshot["items"]) for snapshot in snapshots] == [1]
        assert precalc_done.wait(timeout=1)
        assert raw_done.wait(timeout=1)

    def test_precalc_probe_failure_does_not_block_other_tables(self) -> None:
        app = _app(1)
        queried_table_ids: list[str] = []

        def _query_precalc(bk_tenant_id: str, trace_ids: list[str], table_id: str) -> list[dict[str, Any]]:
            queried_table_ids.append(table_id)
            if table_id == "broken_table":
                raise RuntimeError("unify query failed")
            return [{"trace_id": trace_ids[0], "biz_id": str(app.bk_biz_id), "app_name": app.app_name}]

        with (
            mock.patch.object(
                TraceSearchItem,
                "_load_precalc_table_ids",
                return_value=["broken_table", "healthy_table"],
            ),
            mock.patch.object(
                TraceSearchItem,
                "_query_precalc_apps_by_trace_ids",
                side_effect=_query_precalc,
            ),
            mock.patch("monitor_web.overview.search.Application.objects.filter") as application_filter,
        ):
            application_filter.return_value.only.return_value = application_filter.return_value
            application_filter.return_value.first.return_value = app
            hits = list(
                TraceSearchItem._path_precalc(
                    "tenant",
                    [TRACE_ID],
                    stop_event=threading.Event(),
                    trace_stop=threading.Event(),
                    deadline=time.monotonic() + 1,
                )
            )

        assert set(queried_table_ids) == {"broken_table", "healthy_table"}
        assert hits == [(TRACE_ID, app)]
        application_filter.return_value.only.assert_called_once_with(
            "application_id",
            "bk_biz_id",
            "app_name",
            "app_alias",
        )

    def test_raw_probe_failure_does_not_block_other_apps(self) -> None:
        broken_app = _app(1)
        healthy_app = _app(2)

        def _query_raw(trace_ids: list[str], app: SimpleNamespace) -> list[str]:
            if app is broken_app:
                raise RuntimeError("unify query failed")
            return trace_ids

        with (
            mock.patch.object(
                TraceSearchItem,
                "_collect_candidate_apps",
                return_value=[broken_app, healthy_app],
            ),
            mock.patch.object(
                TraceSearchItem,
                "_query_raw_apps_by_trace_ids",
                side_effect=_query_raw,
            ),
        ):
            hits = list(
                TraceSearchItem._path_raw(
                    "tenant",
                    "admin",
                    [TRACE_ID],
                    None,
                    stop_event=threading.Event(),
                    trace_stop=threading.Event(),
                    deadline=time.monotonic() + 1,
                )
            )

        assert hits == [(TRACE_ID, healthy_app)]

    def test_probe_window_limits_concurrency_and_stops_refill(self) -> None:
        max_workers = 4
        active = 0
        max_active = 0
        lock = threading.Lock()
        initial_window_started = threading.Event()

        def _probe(candidate: int) -> int:
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
                if active == max_workers:
                    initial_window_started.set()
            try:
                initial_window_started.wait(timeout=1)
                return candidate
            finally:
                with lock:
                    active -= 1

        stop_event = threading.Event()
        trace_stop = threading.Event()
        results = TraceSearchItem._iter_probe_results(
            list(range(20)),
            _probe,
            max_workers=max_workers,
            stop_event=stop_event,
            trace_stop=trace_stop,
            deadline=time.monotonic() + 2,
        )

        first_result = next(results)
        trace_stop.set()
        remaining_results = list(results)

        assert first_result in range(20)
        assert remaining_results == []
        assert initial_window_started.is_set()
        assert max_active == max_workers

    def test_probe_window_continues_after_future_failure(self) -> None:
        def _probe(candidate: int) -> int:
            if candidate == 1:
                raise RuntimeError("probe failed")
            return candidate

        results = list(
            TraceSearchItem._iter_probe_results(
                [1, 2, 3],
                _probe,
                max_workers=2,
                stop_event=threading.Event(),
                trace_stop=threading.Event(),
                deadline=time.monotonic() + 1,
            )
        )

        assert set(results) == {2, 3}

    def test_paths_use_precalc_and_raw_concurrency_limits(self) -> None:
        stop_event = threading.Event()
        trace_stop = threading.Event()
        deadline = time.monotonic() + 1

        with (
            mock.patch.object(TraceSearchItem, "_load_precalc_table_ids", return_value=["precalc_table"]),
            mock.patch.object(TraceSearchItem, "_iter_probe_results", return_value=iter([])) as iter_results,
        ):
            assert (
                list(
                    TraceSearchItem._path_precalc(
                        "tenant",
                        [TRACE_ID],
                        stop_event=stop_event,
                        trace_stop=trace_stop,
                        deadline=deadline,
                    )
                )
                == []
            )
            assert iter_results.call_args.kwargs["max_workers"] == 5

        with (
            mock.patch.object(TraceSearchItem, "_collect_candidate_apps", return_value=[_app(1)]),
            mock.patch.object(TraceSearchItem, "_iter_probe_results", return_value=iter([])) as iter_results,
        ):
            assert (
                list(
                    TraceSearchItem._path_raw(
                        "tenant",
                        "admin",
                        [TRACE_ID],
                        None,
                        stop_event=stop_event,
                        trace_stop=trace_stop,
                        deadline=deadline,
                    )
                )
                == []
            )
            assert iter_results.call_args.kwargs["max_workers"] == 8

    def test_probe_deadline_does_not_wait_for_inflight_query(self) -> None:
        release = threading.Event()
        probe_started = threading.Event()
        probe_done = threading.Event()

        def _probe(candidate: int) -> int:
            probe_started.set()
            try:
                release.wait(timeout=1)
                return candidate
            finally:
                probe_done.set()

        started_at = time.monotonic()
        try:
            results = list(
                TraceSearchItem._iter_probe_results(
                    [1],
                    _probe,
                    max_workers=1,
                    stop_event=threading.Event(),
                    trace_stop=threading.Event(),
                    deadline=time.monotonic() + 0.05,
                )
            )
        finally:
            release.set()

        assert results == []
        assert probe_started.is_set()
        assert time.monotonic() - started_at < 0.5
        assert probe_done.wait(timeout=1)


class _ListSearchItem(SearchItem):
    received_stop_events: list[threading.Event | None] = []

    @classmethod
    def match(cls, query: str) -> bool:
        return True

    @classmethod
    def search(
        cls,
        bk_tenant_id: str,
        username: str,
        query: str,
        limit: int = 5,
        current_bk_biz_id: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> list[dict[str, Any]]:
        cls.received_stop_events.append(stop_event)
        return [{"type": "list", "name": "List", "items": []}]


class _StreamingSearchItem(SearchItem):
    received_stop_events: list[threading.Event | None] = []

    @classmethod
    def match(cls, query: str) -> bool:
        return True

    @classmethod
    def search(
        cls,
        bk_tenant_id: str,
        username: str,
        query: str,
        limit: int = 5,
        current_bk_biz_id: int | None = None,
        stop_event: threading.Event | None = None,
    ) -> Iterator[dict[str, Any]]:
        cls.received_stop_events.append(stop_event)
        yield {"type": "stream-1", "name": "Stream 1", "items": []}
        yield {"type": "stream-2", "name": "Stream 2", "items": []}


class TestSearcher:
    def test_forwards_list_and_streaming_search_items(self) -> None:
        _ListSearchItem.received_stop_events.clear()
        _StreamingSearchItem.received_stop_events.clear()
        searcher = Searcher("tenant", "admin")
        searcher.search_items = [_ListSearchItem, _StreamingSearchItem]

        results = list(searcher.search("query"))

        assert {result["type"] for result in results} == {"list", "stream-1", "stream-2"}
        received_stop_events = _ListSearchItem.received_stop_events + _StreamingSearchItem.received_stop_events
        assert len(received_stop_events) == 2
        assert received_stop_events[0] is received_stop_events[1]
        assert received_stop_events[0] is not None

    def test_close_sets_request_stop(self) -> None:
        received_stop_events: list[threading.Event | None] = []
        worker_done = threading.Event()

        class BlockingSearchItem(SearchItem):
            @classmethod
            def match(cls, query: str) -> bool:
                return True

            @classmethod
            def search(
                cls,
                bk_tenant_id: str,
                username: str,
                query: str,
                limit: int = 5,
                current_bk_biz_id: int | None = None,
                stop_event: threading.Event | None = None,
            ) -> Iterator[dict[str, Any]]:
                received_stop_events.append(stop_event)
                try:
                    yield {"type": "blocking", "name": "Blocking", "items": []}
                    if stop_event is not None:
                        stop_event.wait(timeout=1)
                finally:
                    worker_done.set()

        searcher = Searcher("tenant", "admin")
        searcher.search_items = [BlockingSearchItem]
        results = searcher.search("query")

        assert next(results)["type"] == "blocking"
        results.close()

        assert received_stop_events[0] is not None
        assert received_stop_events[0].is_set()
        assert worker_done.wait(timeout=1)


class _ClosableResult:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.closed = False
        self._items = iter(items or [{"type": "trace", "name": "Trace", "items": []}])

    def __iter__(self) -> "_ClosableResult":
        return self

    def __next__(self) -> dict[str, Any]:
        return next(self._items)

    def close(self) -> None:
        self.closed = True


def test_search_view_closes_search_generator_when_stream_is_closed() -> None:
    result = _ClosableResult()
    request = SimpleNamespace(query_params={"query": TRACE_ID}, user=SimpleNamespace(username="admin"))

    with (
        mock.patch("monitor_web.overview.views.get_request_tenant_id", return_value="tenant"),
        mock.patch("monitor_web.overview.views.Searcher") as searcher_class,
    ):
        searcher_class.return_value.search.return_value = result
        response = SearchViewSet().list(request)
        event_stream = response._iterator

        assert next(event_stream) == "event: start\n\n"
        event_stream.close()

    assert result.closed


def test_search_view_close_propagates_request_stop_to_search_item() -> None:
    received_stop_events: list[threading.Event | None] = []
    worker_done = threading.Event()

    class BlockingSearchItem(SearchItem):
        @classmethod
        def match(cls, query: str) -> bool:
            return True

        @classmethod
        def search(
            cls,
            bk_tenant_id: str,
            username: str,
            query: str,
            limit: int = 5,
            current_bk_biz_id: int | None = None,
            stop_event: threading.Event | None = None,
        ) -> Iterator[dict[str, Any]]:
            received_stop_events.append(stop_event)
            try:
                yield {"type": "blocking", "name": "Blocking", "items": []}
                if stop_event is not None:
                    stop_event.wait(timeout=1)
            finally:
                worker_done.set()

    request = SimpleNamespace(query_params={"query": TRACE_ID}, user=SimpleNamespace(username="admin"))

    with (
        mock.patch.object(Searcher, "search_items", [BlockingSearchItem]),
        mock.patch("monitor_web.overview.views.get_request_tenant_id", return_value="tenant"),
    ):
        response = SearchViewSet().list(request)
        event_stream = response._iterator

        assert next(event_stream) == "event: start\n\n"
        assert json.loads(next(event_stream).removeprefix("data: "))["type"] == "blocking"
        event_stream.close()

    assert received_stop_events[0] is not None
    assert received_stop_events[0].is_set()
    assert worker_done.wait(timeout=1)


def test_search_view_streams_snapshots_and_end_event() -> None:
    snapshots = [
        {"type": "trace", "name": "Trace", "items": [{"application_id": application_id}]}
        for application_id in range(1, 4)
    ]
    result = _ClosableResult(snapshots)
    request = SimpleNamespace(query_params={"query": TRACE_ID}, user=SimpleNamespace(username="admin"))

    with (
        mock.patch("monitor_web.overview.views.get_request_tenant_id", return_value="tenant"),
        mock.patch("monitor_web.overview.views.Searcher") as searcher_class,
    ):
        searcher_class.return_value.search.return_value = result
        response = SearchViewSet().list(request)
        chunks = [chunk.decode() for chunk in response.streaming_content]

    assert chunks[0] == "event: start\n\n"
    assert chunks[-1] == "event: end\n\n"
    streamed_snapshots = [json.loads(chunk.removeprefix("data: ")) for chunk in chunks[1:-1]]
    assert streamed_snapshots == snapshots
    assert result.closed
    assert response["Cache-Control"] == "no-cache"
    assert response["X-Accel-Buffering"] == "no"


@pytest.mark.parametrize("can_view_application", [True, False])
def test_search_view_streaming_trace_query_uses_application_scope(
    can_view_application: bool, application_permission: mock.MagicMock
) -> None:
    app = _app(1, bk_biz_id=42)
    application_permission.return_value.batch_is_allowed.side_effect = None
    application_permission.return_value.batch_is_allowed.return_value = {
        str(app.application_id): {ActionEnum.VIEW_APM_APPLICATION.id: can_view_application}
    }
    request = SimpleNamespace(query_params={"query": TRACE_ID}, user=SimpleNamespace(username="admin"))

    with (
        mock.patch.object(Searcher, "search_items", [TraceSearchItem]),
        mock.patch("monitor_web.overview.views.get_request_tenant_id", return_value="tenant") as get_tenant_id,
        mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter([])),
        mock.patch.object(TraceSearchItem, "_collect_candidate_apps", return_value=[app]),
        mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 42"),
        mock.patch(
            "bkmonitor.data_source.unify_query.builder.QueryHelper.query",
            return_value=[{"trace_id": TRACE_ID}],
        ) as query,
    ):
        response = SearchViewSet().list(request)
        chunks = [chunk.decode() for chunk in response.streaming_content]

    get_tenant_id.assert_called_once_with()
    query.assert_called_once()
    query_body = query.call_args.kwargs["query_body"]
    assert query_body["bk_biz_id"] == app.bk_biz_id
    if can_view_application:
        assert json.loads(chunks[1].removeprefix("data: "))["items"][0]["application_id"] == app.application_id
    else:
        assert chunks == ["event: start\n\n", "event: end\n\n"]


@pytest.mark.parametrize("separator", [",", ", ", ",&nbsp;"])
def test_search_view_rejects_more_than_twenty_unique_trace_ids(separator: str) -> None:
    trace_ids = [f"{index:032x}" for index in range(21)]
    request = SimpleNamespace(
        query_params={"query": f"&nbsp;{separator.join(trace_ids)}&nbsp;"},
        user=SimpleNamespace(username="admin"),
    )

    with (
        mock.patch("monitor_web.overview.views.Searcher") as searcher,
        pytest.raises(ValidationError, match="最多支持 20 个 TraceID"),
    ):
        SearchViewSet().list(request)

    searcher.assert_not_called()


def test_trace_batch_parses_whitespace_and_deduplicates_before_limit() -> None:
    trace_ids = [f"{index:032x}" for index in range(20)]
    query = " , ".join([*trace_ids, trace_ids[0]])
    serializer = SearchSerializer(data={"query": query})

    assert serializer.is_valid(), serializer.errors
    assert TraceSearchItem.parse_trace_ids(serializer.validated_data["query"]) == trace_ids
    assert TraceSearchItem.match(query)
    assert not ApmApplicationSearchItem.match(query)
    assert not TraceSearchItem.match(f"{TRACE_ID},invalid-trace-id")
    assert not TraceSearchItem.match(f"{TRACE_ID},")


def test_search_view_batch_streams_per_trace_top_k_and_checks_shared_app_once(
    application_permission: mock.MagicMock,
) -> None:
    trace_ids = [TRACE_ID, "b" * 32]
    apps = [_app(application_id) for application_id in range(1, 6)]

    def _allowed(actions: list, resources: list) -> dict[str, dict[str, bool]]:
        return {
            str(resource[0].id): {action.id: int(resource[0].id) != 1 for action in actions} for resource in resources
        }

    application_permission.return_value.batch_is_allowed.side_effect = _allowed
    request = SimpleNamespace(
        query_params={"query": ",".join([*trace_ids, trace_ids[0]]), "bk_biz_id": 2},
        user=SimpleNamespace(username="admin"),
    )
    precalc_hits = [(trace_id, app) for app in apps for trace_id in trace_ids]
    raw_hits = [(trace_id, apps[1]) for trace_id in trace_ids]

    with (
        mock.patch("monitor_web.overview.views.get_request_tenant_id", return_value="tenant"),
        mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter(precalc_hits)) as precalc,
        mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter(raw_hits)) as raw,
        mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
    ):
        response = SearchViewSet().list(request)
        chunks = [chunk.decode() for chunk in response.streaming_content]

    assert chunks[0] == "event: start\n\n"
    assert chunks[-1] == "event: end\n\n"
    snapshots = [json.loads(chunk.removeprefix("data: ")) for chunk in chunks[1:-1]]
    pairs = {(item["trace_id"], item["application_id"]) for item in snapshots[-1]["items"]}
    assert pairs == {(trace_id, app.application_id) for trace_id in trace_ids for app in apps[1:4]}
    assert application_permission.return_value.batch_is_allowed.call_count == 4
    assert precalc.call_args.args == ("tenant", trace_ids)
    assert raw.call_args.args == ("tenant", "admin", trace_ids, 2)
    for previous, current in zip(snapshots, snapshots[1:]):
        assert len(current["items"]) > len(previous["items"])
        assert current["items"][: len(previous["items"])] == previous["items"]


@pytest.mark.parametrize("use_unify_query", [True, False])
@pytest.mark.parametrize("trace_count", [1, 20])
def test_precalc_batch_keeps_independent_limits_and_reuses_application_lookup(
    use_unify_query: bool, trace_count: int
) -> None:
    trace_ids = [TRACE_ID, *[f"{index:032x}" for index in range(1, trace_count)]]
    apps = [_app(index) for index in range(1, 9)]
    documents = [{"trace_id": TRACE_ID, "biz_id": "2", "app_name": app.app_name} for app in apps for _ in range(30)] + [
        {"trace_id": trace_id, "biz_id": "2", "app_name": apps[0].app_name} for trace_id in trace_ids[1:]
    ]
    tables = ["precalc_table_a", "precalc_table_b"]
    dimensions = ["biz_id", "app_name", "trace_id"]
    now = 1793779200

    def _aggregate(spec: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
        field, config = next(iter(spec.items()))
        if "value_count" in config:
            return {field: {"value": len(rows)}}
        terms = config["terms"]
        counts = Counter(row[terms["field"]] for row in rows)
        return {
            field: {
                "buckets": [
                    {
                        "key": key,
                        "doc_count": count,
                        **_aggregate(config["aggregations"], [row for row in rows if row[terms["field"]] == key]),
                    }
                    for key, count in counts.most_common(terms["size"])
                ]
            }
        }

    def _query_es(connection: Any, table_id: str, query_body: dict[str, Any]) -> dict[str, Any]:
        assert table_id in tables
        assert query_body["bk_tenant_id"] == "tenant"
        assert query_body["use_full_index_names"] is True
        assert query_body["size"] == 0
        filters = query_body["query"]["bool"]["filter"]["bool"]["must"]
        assert {"terms": {"trace_id": trace_ids}} in filters[0]["bool"]["must"]
        time_field = PreCalculateSpecificField.MIN_START_TIME
        assert {"range": {time_field: {"gte": (now - 7 * 86400) * 1000000}}} in filters
        assert {"range": {time_field: {"lt": now * 1000000}}} in filters
        return {"aggregations": _aggregate(query_body["aggregations"], documents)}

    def _query_uq(**params: Any) -> dict[str, Any]:
        assert params["bk_tenant_id"] == "tenant"
        assert params["start_time"] == str(now - 7 * 86400)
        assert params["end_time"] == str(now)
        assert len(params["query_list"]) == 1
        query = params["query_list"][0]
        assert query["table_id"] in tables
        assert query["time_field"] == PreCalculateSpecificField.MIN_START_TIME
        assert query["dimensions"] == dimensions
        assert query["function"] == [{"method": "count", "dimensions": dimensions}]
        assert query["time_aggregation"] == {}
        assert query["conditions"]["field_list"] == [{"field_name": "trace_id", "op": "eq", "value": trace_ids}]
        assert query["limit"] == max(5, trace_count)
        # 按 UQ ES 分桶规则回放：最后一个维度在最外层，各层分别应用 limit。
        spec = {"count": {"value_count": {"field": "trace_id"}}}
        for dimension in dimensions:
            spec = {dimension: {"terms": {"field": dimension, "size": query["limit"]}, "aggregations": spec}}
        grouped = _aggregate(spec, documents)
        series = []
        for trace_bucket in grouped["trace_id"]["buckets"]:
            for app_bucket in trace_bucket["app_name"]["buckets"]:
                for biz_bucket in app_bucket["biz_id"]["buckets"]:
                    series.append(
                        {
                            "group_keys": dimensions,
                            "group_values": [biz_bucket["key"], app_bucket["key"], trace_bucket["key"]],
                            "columns": ["_value"],
                            "types": ["double"],
                            "values": [[biz_bucket["count"]["value"]]],
                        }
                    )
        return {"series": series}

    with (
        override_settings(APM_UNIFY_QUERY_BLACK_BIZ_LIST=[] if use_unify_query else ["*"]),
        mock.patch("monitor_web.overview.search.time.time", return_value=now),
        mock.patch.object(TraceSearchItem, "_load_precalc_table_ids", return_value=tables),
        mock.patch(
            "bkmonitor.data_source.unify_query.query.api.unify_query.query_reference", side_effect=_query_uq
        ) as uq,
        mock.patch(
            "bkmonitor.data_source.backends.elastic_search.connection.DatabaseConnection.execute",
            autospec=True,
            side_effect=_query_es,
        ) as es,
        mock.patch("monitor_web.overview.search.Application.objects.filter") as application_filter,
    ):
        by_name = {app.app_name: app for app in apps}

        def _lookup(**filters: Any) -> mock.Mock:
            assert filters["bk_tenant_id"] == "tenant"
            assert filters["bk_biz_id"] == 2
            queryset = mock.Mock()
            queryset.only.return_value.first.return_value = by_name[filters["app_name"]]
            return queryset

        application_filter.side_effect = _lookup
        hits = list(
            TraceSearchItem._path_precalc(
                "tenant", trace_ids, threading.Event(), threading.Event(), time.monotonic() + 1
            )
        )

    assert uq.call_count == (2 if use_unify_query else 0)
    assert es.call_count == (0 if use_unify_query else 2)
    assert Counter(trace_id for trace_id, _ in hits) == {
        trace_id: 10 if trace_id == TRACE_ID else 2 for trace_id in trace_ids
    }
    assert {(trace_id, app.application_id) for trace_id, app in hits} == {
        *((TRACE_ID, app.application_id) for app in apps[:5]),
        *((trace_id, apps[0].application_id) for trace_id in trace_ids[1:]),
    }
    assert application_filter.call_count == 5


def test_precalc_batch_queries_all_ids_on_healthy_table_when_another_table_is_slow() -> None:
    trace_ids = [f"{index:032x}" for index in range(6)]
    release = threading.Event()
    healthy_queried = threading.Event()
    app = _app(1)

    def _query(bk_tenant_id: str, trace_ids: list[str], table_id: str) -> list[dict[str, Any]]:
        if table_id == "slow_table":
            release.wait(timeout=1)
            return []
        healthy_queried.set()
        return [{"trace_id": trace_id, "biz_id": "2", "app_name": app.app_name} for trace_id in trace_ids]

    try:
        with (
            mock.patch.object(TraceSearchItem, "_load_precalc_table_ids", return_value=["slow_table", "healthy_table"]),
            mock.patch.object(TraceSearchItem, "_query_precalc_apps_by_trace_ids", side_effect=_query) as query,
            mock.patch("monitor_web.overview.search.Application.objects.filter") as application_filter,
        ):
            application_filter.return_value.only.return_value.first.return_value = app
            hits = list(
                TraceSearchItem._path_precalc(
                    "tenant", trace_ids, threading.Event(), threading.Event(), time.monotonic() + 0.15
                )
            )
    finally:
        release.set()

    assert healthy_queried.is_set()
    assert {trace_id for trace_id, _ in hits} == set(trace_ids)
    assert all(hit_app is app for _, hit_app in hits)
    assert query.call_count == 2


def test_raw_batch_collapses_spans_and_preserves_shared_application_scope() -> None:
    trace_ids = [TRACE_ID, "b" * 32]
    app = _app(1)
    app.trace_result_table_id = "apm_global.shared_trace"
    spans = [{"trace_id": TRACE_ID}] * 30 + [{"trace_id": trace_ids[1]}]

    def _query(table_id: str, query_body: dict[str, Any]) -> list[dict[str, Any]]:
        assert query_body["bk_biz_id"] == app.bk_biz_id
        assert query_body["limit"] == len(trace_ids)
        config = query_body["query_configs"][0]
        assert config["filter_dict"] == {
            "bk_biz_id__eq": app.bk_biz_id,
            "app_name__eq": app.app_name,
            "trace_id__eq": trace_ids,
        }
        datasource = BkApmTraceDataSource(bk_biz_id=app.bk_biz_id, bk_tenant_id="tenant", **config)
        storage_query = datasource.to_unify_query_config()[0]
        assert storage_query["collapse"] == {"field": "trace_id"}
        assert storage_query["keep_columns"] == ["trace_id"]
        # 使用真实序列化的折叠字段和查询上限回放存储响应。
        collapsed = {}
        for span in spans:
            collapsed.setdefault(span[storage_query["collapse"]["field"]], span)
        return list(collapsed.values())[: query_body["limit"]]

    with (
        mock.patch.object(TraceSearchItem, "_collect_candidate_apps", return_value=[app]) as candidates,
        mock.patch("bkmonitor.data_source.unify_query.builder.QueryHelper.query", side_effect=_query) as query,
    ):
        hits = list(
            TraceSearchItem._path_raw(
                "tenant", "admin", trace_ids, 2, threading.Event(), threading.Event(), time.monotonic() + 1
            )
        )

    assert hits == [(trace_id, app) for trace_id in trace_ids]
    candidates.assert_called_once_with("tenant", "admin", 2)
    query.assert_called_once()


def test_closing_batch_search_stops_both_paths() -> None:
    stop_events: list[threading.Event] = []
    paths_done: list[threading.Event] = []
    both_started = threading.Barrier(2)
    app = _app(1)

    def _path(
        *args: Any, stop_event: threading.Event, trace_stop: threading.Event, deadline: float
    ) -> Generator[tuple[str, SimpleNamespace], None, None]:
        path_done = threading.Event()
        paths_done.append(path_done)
        stop_events.append(trace_stop)
        try:
            both_started.wait(timeout=1)
            yield TRACE_ID, app
            trace_stop.wait(timeout=1)
        finally:
            path_done.set()

    with (
        mock.patch.object(TraceSearchItem, "_path_precalc", side_effect=_path),
        mock.patch.object(TraceSearchItem, "_path_raw", side_effect=_path),
        mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
    ):
        results = TraceSearchItem.search("tenant", "admin", f"{TRACE_ID},{'b' * 32}")
        assert next(results)["items"][0]["trace_id"] == TRACE_ID
        results.close()

    assert all(path_done.wait(timeout=1) for path_done in paths_done)
    assert len(stop_events) == 2
    assert all(stop_event.is_set() for stop_event in stop_events)

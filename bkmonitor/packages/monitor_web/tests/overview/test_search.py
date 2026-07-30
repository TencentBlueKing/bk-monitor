import json
import threading
import time
from collections.abc import Generator, Iterator
from types import SimpleNamespace
from typing import Any
from unittest import mock

import pytest

from monitor_web.overview.search import SearchItem, Searcher, TraceSearchItem
from monitor_web.overview.views import SearchViewSet


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


class TestTraceSearchItem:
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
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter([app_a, app_b])),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([app_a, app_c])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", side_effect=lambda bk_biz_id: f"业务 {bk_biz_id}"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert [len(snapshot["items"]) for snapshot in snapshots] == [1, 2, 3]
        assert all(isinstance(snapshot, dict) for snapshot in snapshots)
        assert all(snapshot["type"] == "trace" and snapshot["name"] == "Trace" for snapshot in snapshots)

        previous_application_ids: list[int] = []
        for snapshot in snapshots:
            application_ids = [item["application_id"] for item in snapshot["items"]]
            assert application_ids[:-1] == previous_application_ids
            assert len(application_ids) == len(set(application_ids))
            previous_application_ids = application_ids

        assert set(previous_application_ids) == {1, 2, 3}

    def test_candidate_exhaustion_keeps_partial_snapshots(self) -> None:
        app_a = _app(1)
        app_b = _app(2)

        with (
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter([app_a])),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([app_b])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert [len(snapshot["items"]) for snapshot in snapshots] == [1, 2]
        assert {item["application_id"] for item in snapshots[-1]["items"]} == {1, 2}

    def test_stops_after_three_unique_applications(self) -> None:
        apps = [_app(application_id) for application_id in range(1, 5)]

        with (
            mock.patch.object(TraceSearchItem, "_path_precalc", return_value=iter(apps)),
            mock.patch.object(TraceSearchItem, "_path_raw", return_value=iter([])),
            mock.patch.object(TraceSearchItem, "_get_biz_name", return_value="业务 2"),
        ):
            snapshots = list(TraceSearchItem.search("tenant", "admin", TRACE_ID))

        assert [len(snapshot["items"]) for snapshot in snapshots] == [1, 2, 3]
        assert [item["application_id"] for item in snapshots[-1]["items"]] == [1, 2, 3]

    def test_deadline_keeps_partial_results_without_waiting_for_slow_paths(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        assert TraceSearchItem._TRACE_SEARCH_TIMEOUT == 10

        app = _app(1)
        release = threading.Event()
        precalc_done = threading.Event()
        raw_done = threading.Event()

        def _precalc_path() -> Generator[SimpleNamespace, None, None]:
            try:
                yield app
                release.wait(timeout=1)
            finally:
                precalc_done.set()

        def _raw_path() -> Generator[SimpleNamespace, None, None]:
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

        def _query_precalc(trace_id: str, table_id: str, limit: int = 5) -> list[dict[str, Any]]:
            queried_table_ids.append(table_id)
            if table_id == "broken_table":
                raise RuntimeError("unify query failed")
            return [{"bk_biz_id": str(app.bk_biz_id), "app_name": app.app_name}]

        with (
            mock.patch.object(
                TraceSearchItem,
                "_load_precalc_table_ids",
                return_value=["broken_table", "healthy_table"],
            ),
            mock.patch.object(
                TraceSearchItem,
                "_query_precalc_apps_by_trace_id",
                side_effect=_query_precalc,
            ),
            mock.patch("monitor_web.overview.search.Application.objects.filter") as application_filter,
        ):
            application_filter.return_value.only.return_value = application_filter.return_value
            application_filter.return_value.first.return_value = app
            hits = list(
                TraceSearchItem._path_precalc(
                    "tenant",
                    TRACE_ID,
                    stop_event=threading.Event(),
                    trace_stop=threading.Event(),
                    deadline=time.monotonic() + 1,
                )
            )

        assert set(queried_table_ids) == {"broken_table", "healthy_table"}
        assert hits == [app]
        application_filter.return_value.only.assert_called_once_with(
            "application_id",
            "bk_biz_id",
            "app_name",
            "app_alias",
        )

    def test_raw_probe_failure_does_not_block_other_apps(self) -> None:
        broken_app = _app(1)
        healthy_app = _app(2)

        def _query_raw(trace_id: str, app: SimpleNamespace) -> bool:
            if app is broken_app:
                raise RuntimeError("unify query failed")
            return True

        with (
            mock.patch.object(
                TraceSearchItem,
                "_collect_candidate_apps",
                return_value=[broken_app, healthy_app],
            ),
            mock.patch.object(
                TraceSearchItem,
                "_query_raw_apps_by_trace_id",
                side_effect=_query_raw,
            ),
        ):
            hits = list(
                TraceSearchItem._path_raw(
                    "tenant",
                    "admin",
                    TRACE_ID,
                    None,
                    stop_event=threading.Event(),
                    trace_stop=threading.Event(),
                    deadline=time.monotonic() + 1,
                )
            )

        assert hits == [healthy_app]

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
                        TRACE_ID,
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
                        TRACE_ID,
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

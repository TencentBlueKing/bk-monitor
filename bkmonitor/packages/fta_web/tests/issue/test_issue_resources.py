"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

Issue 合并/拆分功能单测：覆盖 Resolver fast-path noop + 异常类 + content JSON 格式。
"""

import pytest

from bkmonitor.issue_merge import (
    IssueMergeResolver,
    MergeResolverContext,
)


class TestIssueLogContentResource:
    @staticmethod
    def _issue_ids(count: int) -> list[str]:
        return [f"1700000000{i:02d}" for i in range(count)]

    @staticmethod
    def _prepare_resource(monkeypatch, issue_ids: list[str], *, with_alert: bool = False):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from constants.data_source import DataSourceLabel, DataTypeLabel
        from fta_web.issue import resources

        issue_hits = []
        for issue_id in issue_ids:
            hit = MagicMock()
            hit.meta.id = issue_id
            hit.strategy_id = 1001
            hit.first_alert_time = int(issue_id[:10]) - 60
            issue_hits.append(hit)

        issue_search = MagicMock()
        issue_search.filter.return_value = issue_search
        issue_search.source.return_value = issue_search
        issue_search.params.return_value = issue_search
        issue_search.execute.return_value = SimpleNamespace(hits=issue_hits)
        monkeypatch.setattr(resources.IssueDocument, "search", lambda **kwargs: issue_search)

        query_configs = MagicMock()
        query_configs.values.return_value = [
            {
                "strategy_id": 1001,
                "data_source_label": DataSourceLabel.BK_LOG_SEARCH,
                "data_type_label": DataTypeLabel.LOG,
            }
        ]
        query_config_model = MagicMock()
        query_config_model.objects.filter.return_value = query_configs
        monkeypatch.setattr(resources, "QueryConfigModel", query_config_model)

        buckets = []
        if with_alert:
            for index, issue_id in enumerate(issue_ids):
                bucket = MagicMock()
                bucket.key = issue_id
                alert_hit = MagicMock()
                alert_hit.to_dict.return_value = {"_source": {"id": f"1700000000{index:03d}"}}
                bucket.latest_alert.hits.hits = [alert_hit]
                buckets.append(bucket)

        alert_result = MagicMock()
        alert_result.aggs.issues.buckets = buckets
        alert_search = MagicMock()
        alert_search.filter.return_value = alert_search
        alert_search.aggs.bucket.return_value = MagicMock()
        alert_search.__getitem__.return_value.execute.return_value = alert_result
        return resources, alert_search

    def test_serializer_rejects_more_than_ten_issues(self):
        from fta_web.issue.resources import IssueLogContentResource

        serializer = IssueLogContentResource.RequestSerializer(
            data={"bk_biz_ids": [2], "issue_ids": self._issue_ids(11)}
        )

        assert not serializer.is_valid()
        assert "issue_ids" in serializer.errors

    def test_alert_search_uses_issue_time_range(self, monkeypatch):
        issue_ids = ["170000000000", "170000010000"]
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids)
        captured = {}

        def _search(**kwargs):
            captured.update(kwargs)
            return alert_search

        monkeypatch.setattr(resources.AlertDocument, "search", _search)
        monkeypatch.setattr(resources.time, "time", lambda: 1_700_001_000)

        resources.IssueLogContentResource().perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})

        assert captured == {"start_time": 1_699_999_940, "end_time": 1_700_001_000}

    def test_alert_search_falls_back_to_issue_id_time(self, monkeypatch):
        issue_ids = ["170000000000"]
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids)
        captured = {}

        resources.IssueDocument.search().execute().hits[0].first_alert_time = 0

        def _search(**kwargs):
            captured.update(kwargs)
            return alert_search

        monkeypatch.setattr(resources.AlertDocument, "search", _search)
        monkeypatch.setattr(resources.time, "time", lambda: 1_700_001_000)

        resources.IssueLogContentResource().perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})

        assert captured == {"start_time": 1_700_000_000, "end_time": 1_700_001_000}

    def test_batch_timeout_does_not_wait_for_slow_log_query(self, monkeypatch):
        import threading
        import time

        issue_ids = self._issue_ids(1)
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids, with_alert=True)
        monkeypatch.setattr(resources.AlertDocument, "search", lambda **kwargs: alert_search)
        monkeypatch.setattr(resources.IssueLogContentResource, "BATCH_TIMEOUT", 0.01, raising=False)

        release = threading.Event()

        def _slow_query(*args, **kwargs):
            release.wait(timeout=1)
            return "late log"

        monkeypatch.setattr(resources, "get_alert_relation_info", _slow_query)
        original_submit = resources.IssueLogContentResource.EXECUTOR.submit
        submitted_futures = []

        def _capture_submit(*args, **kwargs):
            future = original_submit(*args, **kwargs)
            submitted_futures.append(future)
            return future

        monkeypatch.setattr(resources.IssueLogContentResource.EXECUTOR, "submit", _capture_submit)

        try:
            started_at = time.monotonic()
            result = resources.IssueLogContentResource().perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})

            assert time.monotonic() - started_at < 0.1
            assert result == {issue_ids[0]: {"log_content": ""}}
        finally:
            release.set()
            for future in submitted_futures:
                future.result(timeout=1)

    def test_log_query_inherits_request_local_tenant(self, monkeypatch):
        from bkmonitor.utils.local import local
        from bkmonitor.utils.tenant import get_local_tenant_id

        issue_ids = self._issue_ids(1)
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids, with_alert=True)
        monkeypatch.setattr(resources.AlertDocument, "search", lambda **kwargs: alert_search)
        monkeypatch.setattr(local, "bk_tenant_id", "tenant-a", raising=False)

        observed_tenant_ids = []

        def _query(*args, **kwargs):
            observed_tenant_ids.append(get_local_tenant_id())
            return "log content"

        monkeypatch.setattr(resources, "get_alert_relation_info", _query)

        result = resources.IssueLogContentResource().perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})

        assert observed_tenant_ids == ["tenant-a"]
        assert result == {issue_ids[0]: {"log_content": "log content"}}

    def test_bk_data_time_series_query_config_is_delegated_to_relation_info(self, monkeypatch):
        from unittest.mock import MagicMock

        from constants.data_source import DataSourceLabel, DataTypeLabel

        issue_ids = self._issue_ids(1)
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids, with_alert=True)
        resources.QueryConfigModel.objects.filter.return_value.values.return_value = [
            {
                "strategy_id": 1001,
                "data_source_label": DataSourceLabel.BK_DATA,
                "data_type_label": DataTypeLabel.TIME_SERIES,
            }
        ]
        monkeypatch.setattr(resources.AlertDocument, "search", lambda **kwargs: alert_search)
        relation_info = MagicMock(return_value='{"log": "clustered log"}')
        monkeypatch.setattr(resources, "get_alert_relation_info", relation_info)

        result = resources.IssueLogContentResource().perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})

        assert result == {issue_ids[0]: {"log_content": "clustered log"}}
        relation_info.assert_called_once()
        assert relation_info.call_args.kwargs == {
            "length_limit": False,
            "query_config": {
                "data_source_label": DataSourceLabel.BK_DATA,
                "data_type_label": DataTypeLabel.TIME_SERIES,
            },
        }

    def test_repeated_timeouts_share_global_concurrency_limit(self, monkeypatch):
        import threading

        issue_ids = self._issue_ids(10)
        resources, alert_search = self._prepare_resource(monkeypatch, issue_ids, with_alert=True)
        monkeypatch.setattr(resources.AlertDocument, "search", lambda **kwargs: alert_search)
        monkeypatch.setattr(resources.IssueLogContentResource, "BATCH_TIMEOUT", 0.05, raising=False)

        release = threading.Event()
        lock = threading.Lock()
        active = 0
        max_active = 0

        def _slow_query(*args, **kwargs):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            try:
                release.wait(timeout=1)
                return "late log"
            finally:
                with lock:
                    active -= 1

        monkeypatch.setattr(resources, "get_alert_relation_info", _slow_query)
        original_submit = resources.IssueLogContentResource.EXECUTOR.submit
        submitted_futures = []
        max_outstanding = 0

        def _counting_submit(*args, **kwargs):
            nonlocal max_outstanding
            future = original_submit(*args, **kwargs)
            submitted_futures.append(future)
            max_outstanding = max(max_outstanding, sum(not item.done() for item in submitted_futures))
            return future

        monkeypatch.setattr(resources.IssueLogContentResource.EXECUTOR, "submit", _counting_submit)

        try:
            resource = resources.IssueLogContentResource()
            resource.perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})
            resource.perform_request({"bk_biz_ids": [2], "issue_ids": issue_ids})
            assert max_active <= 10
            assert max_outstanding <= 10
        finally:
            release.set()
            for future in submitted_futures:
                future.result(timeout=1)


class TestListMergeSourcesAnomalyMessage:
    """``_fetch_member_anomaly_messages`` 行为：

    1) 正常路径：terms agg + top_hits 返回 description → 命中的 member 进入结果字典
    2) 部分 member 无 alert → 不在结果字典（caller 兜底 ``"--"``）
    3) AlertDocument.search 抛异常 → 返回空 dict (fail-open)
    4) first_alert_time 全空 → 走 ``now - 30d`` 兜底窗口（不应抛异常）
    """

    @staticmethod
    def _build_search_stub(buckets: list, on_search=None):
        """构造一条链式可调用的 ES search stub，``buckets`` 即 ``result.aggs.issues.buckets``。"""
        from unittest.mock import MagicMock

        result = MagicMock()
        result.aggs.issues.buckets = buckets

        search_obj = MagicMock()
        search_obj.filter.return_value = search_obj
        search_obj.__getitem__.return_value.execute.return_value = result

        def _search(**kwargs):
            if on_search is not None:
                on_search(kwargs)
            return search_obj

        return _search, search_obj

    @staticmethod
    def _make_bucket(member_id: str, description: str | None):
        """模拟单个 issue_id terms 桶。``description=None`` 表示 top_hits 命中但 description 为空。"""
        from unittest.mock import MagicMock

        bucket = MagicMock()
        bucket.key = member_id
        if description is None:
            bucket.latest_alert.hits.hits = []
        else:
            hit = MagicMock()
            hit.to_dict.return_value = {"_source": {"event": {"description": description}}}
            bucket.latest_alert.hits.hits = [hit]
        return bucket

    def test_normal_path_returns_description_map(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        buckets = [
            self._make_bucket("b1", "AVG(CPU) >= 10%, 当前值 10.19%"),
            self._make_bucket("b2", "Disk IO 异常"),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2"], {"b1": 1_700_000_000, "b2": 1_700_000_500})
        assert result == {
            "b1": "AVG(CPU) >= 10%, 当前值 10.19%",
            "b2": "Disk IO 异常",
        }

    def test_partial_miss_omits_member(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # b1 命中、b2 top_hits 为空、b3 description 为空字符串：均不进入结果
        buckets = [
            self._make_bucket("b1", "CPU 异常"),
            self._make_bucket("b2", None),
            self._make_bucket("b3", ""),
        ]
        search_fn, _ = self._build_search_stub(buckets)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1", "b2", "b3"], {"b1": 1_700_000_000, "b2": 0, "b3": 0})
        assert result == {"b1": "CPU 异常"}

    def test_empty_member_ids_returns_empty(self):
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        # 空入参不应触发 ES 查询，直接返回空 dict
        assert _fetch_member_anomaly_messages([], {}) == {}

    def test_search_exception_fail_open(self, monkeypatch):
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _fetch_member_anomaly_messages

        def _explode(**kwargs):
            raise RuntimeError("ES cluster unreachable")

        monkeypatch.setattr(alert_mod.AlertDocument, "search", _explode)

        # fail-open：返回空 dict，由 caller 在 list_merge_sources 中兜底为 "--"
        assert _fetch_member_anomaly_messages(["b1"], {"b1": 1_700_000_000}) == {}

    def test_all_first_alert_time_empty_uses_fallback_window(self, monkeypatch):
        """所有 member 的 first_alert_time 为空（如旧数据）→ 走 now-30d 兜底窗口，不抛异常。"""
        from bkmonitor.documents import alert as alert_mod
        from fta_web.issue.resources import _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER, _fetch_member_anomaly_messages

        captured: dict = {}

        def _capture(kwargs):
            captured.update(kwargs)

        search_fn, _ = self._build_search_stub([self._make_bucket("b1", "fallback window hit")], on_search=_capture)
        monkeypatch.setattr(alert_mod.AlertDocument, "search", search_fn)

        result = _fetch_member_anomaly_messages(["b1"], {"b1": 0})
        assert result == {"b1": "fallback window hit"}
        # 兜底窗口 ≈ now - 30d；允许少量调用时延误差
        assert captured["end_time"] - captured["start_time"] == _MERGE_SOURCES_ANOMALY_FALLBACK_BUFFER


class TestSearchInjectsSplitInfo:
    """``IssueQueryHandler.search()`` 列表契约：被拆出的独立 Issue 注入 split_info。

    独立守护"search 流程真的会塞 split_info"——避免后续重构 search 时 resolver 单测仍过、
    但列表契约悄悄断裂。patch 掉 ES / 翻译 / 趋势等重链路，只验证注入这一刀。
    """

    @pytest.mark.skip(
        reason="跨层耦合：fta_web.issue.handlers 在 import 链上会 transitively 引入 "
        "alarm_backends.service.scheduler（模块级读取 worker-only 配置 DEFAULT_CRONTAB / "
        "ACTION_TASK_CRONTAB 等），纯 web 角色无法完成 import。待 feature owner 将该 import "
        "改为惰性或提供 web+worker 全栈测试配置后移除 skip。"
    )
    def test_split_member_injected_normal_untouched(self, monkeypatch):
        from unittest.mock import MagicMock

        from fta_web.alert.handlers import translator as translator_mod
        from fta_web.issue.handlers.issue import IssueQueryHandler

        # __new__ 跳过 BaseBizQueryHandler.__init__（避免触发 IAM 权限装配）
        handler = IssueQueryHandler.__new__(IssueQueryHandler)
        handler.bk_biz_ids = [2]

        issues = [{"id": "split-1", "bk_biz_id": 2}, {"id": "normal-1", "bk_biz_id": 2}]

        fake_result = MagicMock()
        fake_result.hits.total.value = len(issues)

        # patch 重链路：ES 查询 / 清洗 / 翻译 / 合并 ctx 加载 / 告警趋势
        monkeypatch.setattr(handler, "search_raw", lambda **kw: (fake_result, None))
        monkeypatch.setattr(handler, "handle_hit_list", lambda sr: issues)
        monkeypatch.setattr(handler, "add_alert_trend", lambda items: None)
        monkeypatch.setattr(translator_mod.StrategyTranslator, "translate_from_dict", lambda self, *a, **k: None)
        monkeypatch.setattr(translator_mod.BizTranslator, "translate_from_dict", lambda self, *a, **k: None)
        monkeypatch.setattr(MergeResolverContext, "load", lambda self: None)
        monkeypatch.setattr(
            IssueMergeResolver,
            "get_split_info_map",
            classmethod(
                lambda cls, ids: {
                    "split-1": {
                        "split_from_main_issue_id": "A",
                        "split_from_main_issue_name": None,
                        "split_reasons": ["误合并，根因不同"],
                        "split_kind": "manual",
                        "split_time": 1716580800,
                        "split_operator": "willgchen",
                    }
                }
            ),
        )

        result = handler.search()
        by_id = {i["id"]: i for i in result["issues"]}
        # 被拆出的独立 Issue 注入 split_info
        assert "split_info" in by_id["split-1"]
        assert by_id["split-1"]["split_info"]["split_reasons"] == ["误合并，根因不同"]
        # 普通 Issue 不注入
        assert "split_info" not in by_id["normal-1"]


class TestRunBatchFreezePropagation:
    """_run_batch：状态机冻结经 web→api 中转后以 BKAPIError 回来。

    custom_exception_handler 把 Error.extra **平铺到响应顶层**（result.update(exc.extra)），
    故 BKAPIError.data 顶层即带 business_code / conflicting_main_issue_id。web 侧须从顶层识别
    并回填 detail，供前端构造"跳主 Issue"引导。这里用真实平铺 payload 形状防回归。
    """

    def test_bkapi_error_flattened_payload_recognized(self):
        from core.errors.api import BKAPIError
        from fta_web.issue.resources import _run_batch

        # 模拟 api role custom_exception_handler 渲染：extra 平铺在 result_json 顶层
        result_json = {
            "result": False,
            "code": 3337109,
            "message": "Issue b1 已被合并到 #a1，请前往主 Issue 操作或先拆分",
            "data": None,
            "business_code": "MERGE_FREEZE_VIOLATION",
            "conflicting_main_issue_id": "a1",
            "issue_id": "b1",
        }

        def _action(bk_biz_id, issue_id):
            raise BKAPIError(system_name="bkmonitor.issue", url="resolve", result=result_json)

        out = _run_batch([{"bk_biz_id": 2, "issue_id": "b1"}], _action)
        assert out["succeeded"] == []
        assert len(out["failed"]) == 1
        failed = out["failed"][0]
        assert failed["issue_id"] == "b1"
        assert failed["code"] == "MERGE_FREEZE_VIOLATION"
        assert failed["detail"]["conflicting_main_issue_id"] == "a1"

    def test_bkapi_error_non_freeze_only_message(self):
        from core.errors.api import BKAPIError
        from fta_web.issue.resources import _run_batch

        result_json = {"result": False, "code": 3337104, "message": "其他业务错误"}

        def _action(bk_biz_id, issue_id):
            raise BKAPIError(system_name="bkmonitor.issue", url="resolve", result=result_json)

        out = _run_batch([{"bk_biz_id": 2, "issue_id": "x1"}], _action)
        failed = out["failed"][0]
        # 非冻结错误：只保留 message，不带 code/detail
        assert "code" not in failed
        assert "detail" not in failed
        assert failed["message"] == "其他业务错误"


class TestSplitReasonsOptional:
    """拆分依据 reasons 改为非必填：缺省 / 空列表均通过校验，validated_data 兜底为 []。

    下游 bulk_reset_for_split（reasons or []）、模型 split_reasons（null=True）、读侧
    split_info（split_reasons or []）本就容忍空，故只需放开两处 serializer。
    """

    # 合法 Issue ID：前 10 位为时间戳（IssueIDField → IssueDocument.parse_timestamp_by_id）
    VALID_ID = "1716000000abcdef01"

    def test_web_split_serializer_reasons_optional(self):
        from fta_web.issue.resources import SplitIssueResource

        s = SplitIssueResource.RequestSerializer(data={"bk_biz_id": 2, "member_issue_id": self.VALID_ID})
        assert s.is_valid(), s.errors
        assert s.validated_data["reasons"] == []

"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

MetricTranslator 指标翻译的取数改造回归。

背景：日志平台类指标（bk_log_search.index_set.{id}）解析后只有 related_id，普通时序类指标带
result_table_id + metric_field。两者拼进同一个 OR 时，MySQL 无法做 index merge，退化成单索引
全扫，生产实测单条 SQL 12.96s。

本文件锁定三件事：
1. 查询按「条件列集合」分组，不会出现跨列 OR；
2. 组内按 MetricTranslator.QUERY_BATCH_SIZE 分批；
3. 输出与原实现等价，且单批失败只丢该批（异常影响面不大于改造前）。
"""

from types import SimpleNamespace
from unittest import mock

from django.db.models import Q
from django.test import override_settings

from fta_web.alert.handlers import translator as translator_module
from fta_web.alert.handlers.translator import MetricTranslator

TENANT_ID = "system"

LOG_ID = "bk_log_search.index_set.123"
LOG_ID_ANOTHER = "bk_log_search.index_set.456"
TS_ID = "bk_monitor.system.cpu_summary.usage"
FTA_ID = "bk_fta.alert.CPU使用率过高"

FIELDS_LOG = frozenset({"data_source_label", "data_type_label", "related_id"})
FIELDS_TS = frozenset({"data_source_label", "data_type_label", "metric_field", "result_table_id"})
FIELDS_FTA = frozenset({"data_source_label", "data_type_label", "metric_field"})


def _branch_field_sets(query: Q) -> list[frozenset]:
    """拆出 Q 里每个 OR 分支的条件列集合；只有一个分支时就是它自身"""
    branches = [child for child in query.children if isinstance(child, Q)]
    if not branches:
        branches = [query]
    return [frozenset(key for key, _ in branch.children) for branch in branches]


def _log_row(index_set_id: str = "123", name: str = "日志索引集") -> SimpleNamespace:
    return SimpleNamespace(
        data_source_label="bk_log_search",
        data_type_label="log",
        result_table_id="rt",
        metric_field="_index",
        metric_field_name=name,
        related_id=index_set_id,
        extend_fields={},
        data_label="",
    )


def _ts_row(name: str = "CPU使用率") -> SimpleNamespace:
    return SimpleNamespace(
        data_source_label="bk_monitor",
        data_type_label="time_series",
        result_table_id="system.cpu_summary",
        metric_field="usage",
        metric_field_name=name,
        related_id="",
        extend_fields={},
        data_label="",
    )


class _RecordingQuerySet:
    """记录 ORM 调用，不真正查库"""

    def __init__(self, record: list):
        self._record = record

    def filter(self, *args, **kwargs):
        if args:
            self._record.append(("q", args[0]))
        else:
            self._record.append(("kwargs", kwargs))
        return self

    def only(self, *fields):
        self._record.append(("only", fields))
        return []


class _RecordingManager:
    def __init__(self):
        self.record = []

    def filter(self, *args, **kwargs):
        return _RecordingQuerySet(self.record).filter(*args, **kwargs)


def _patched_tenant():
    return mock.patch.object(translator_module, "get_request_tenant_id", return_value=TENANT_ID)


class TestBuildQueryGroups:
    """按条件列集合分组：不同列集合绝不落进同一组"""

    def test_grouped_by_field_set(self):
        groups = MetricTranslator._build_query_groups([LOG_ID, LOG_ID_ANOTHER, TS_ID, FTA_ID])

        assert set(groups) == {FIELDS_LOG, FIELDS_TS, FIELDS_FTA}
        assert {key: len(value) for key, value in groups.items()} == {
            FIELDS_LOG: 2,
            FIELDS_TS: 1,
            FIELDS_FTA: 1,
        }

    def test_every_q_matches_its_group_fields(self):
        groups = MetricTranslator._build_query_groups([LOG_ID, TS_ID, FTA_ID])

        for field_set, queries in groups.items():
            for query in queries:
                assert frozenset(key for key, _ in query.children) == field_set

    def test_index_set_id_renamed_to_related_id(self):
        groups = MetricTranslator._build_query_groups([LOG_ID])

        (query,) = groups[FIELDS_LOG]
        keys = {key for key, _ in query.children}
        assert "related_id" in keys
        assert "index_set_id" not in keys

    def test_unparsable_or_unknown_source_skipped(self):
        # "bk_monitor" 单段 → 解析 IndexError；prometheus 无字段映射 → 返回空 dict
        groups = MetricTranslator._build_query_groups(["bk_monitor", "prometheus.sum(rate(x))", ""])

        assert groups == {}


class TestTranslateQueryShape:
    """实际拼出的 SQL：一条 SQL 内只有一个列集合，且分批受控"""

    @override_settings(ROLE="web")
    def test_each_query_contains_single_field_set(self):
        manager = _RecordingManager()
        with mock.patch.object(translator_module.MetricListCache, "objects", manager), _patched_tenant():
            MetricTranslator().translate([LOG_ID, LOG_ID_ANOTHER, TS_ID, FTA_ID])

        q_calls = [payload for kind, payload in manager.record if kind == "q"]
        # 三种列集合 → 三条 SQL
        assert len(q_calls) == 3
        for query in q_calls:
            # 同一条 SQL 内条件列必须一致，否则会重新引入跨列 OR
            assert len(set(_branch_field_sets(query))) == 1

        all_field_sets = {field_set for query in q_calls for field_set in _branch_field_sets(query)}
        assert all_field_sets == {FIELDS_LOG, FIELDS_TS, FIELDS_FTA}

        # 同组的两条日志指标合并进同一条 SQL
        log_queries = [query for query in q_calls if _branch_field_sets(query)[0] == FIELDS_LOG]
        assert len(_branch_field_sets(log_queries[0])) == 2

    @override_settings(ROLE="web")
    def test_tenant_and_only_fields_applied(self):
        manager = _RecordingManager()
        with mock.patch.object(translator_module.MetricListCache, "objects", manager), _patched_tenant():
            MetricTranslator().translate([TS_ID])

        kwargs_calls = [payload for kind, payload in manager.record if kind == "kwargs"]
        assert kwargs_calls[0] == {"bk_tenant_id": TENANT_ID}

        only_calls = [fields for kind, fields in manager.record if kind == "only"]
        assert set(only_calls[0]) == set(MetricTranslator.TRANSLATE_FIELDS)

    @override_settings(ROLE="web")
    def test_biz_filter_only_for_biz_zero(self):
        # 业务 0 的指标才需要 bk_biz_id 过滤，其余业务不加条件（与改造前一致）
        for bk_biz_ids, expect_filter in (([0], True), ([2], False), ([0, 2], True)):
            manager = _RecordingManager()
            with mock.patch.object(translator_module.MetricListCache, "objects", manager), _patched_tenant():
                MetricTranslator(bk_biz_ids=bk_biz_ids).translate([TS_ID])

            biz_calls = [payload for kind, payload in manager.record if kind == "kwargs" and "bk_biz_id__in" in payload]
            assert bool(biz_calls) is expect_filter, bk_biz_ids

    @override_settings(ROLE="web")
    def test_large_group_split_into_batches(self):
        metric_ids = [f"bk_monitor.rt.{index}" for index in range(MetricTranslator.QUERY_BATCH_SIZE * 2 + 20)]
        batches = []

        def fake_query(self, queries, tenant_id):
            batches.append(len(queries))
            return []

        with mock.patch.object(MetricTranslator, "_query_metrics", fake_query), _patched_tenant():
            MetricTranslator().translate(metric_ids)

        batch_size = MetricTranslator.QUERY_BATCH_SIZE
        assert batches == [batch_size, batch_size, 20]


class TestTranslateResult:
    """翻译结果与原实现等价，且异常影响面不大于改造前"""

    @override_settings(ROLE="web")
    def test_translated_name_and_fallback(self):
        def fake_query(self, queries, tenant_id):
            if _branch_field_sets(queries[0])[0] == FIELDS_LOG:
                return [_log_row()]
            return []

        with mock.patch.object(MetricTranslator, "_query_metrics", fake_query), _patched_tenant():
            result = MetricTranslator().translate([LOG_ID, TS_ID])

        assert result[LOG_ID] == "日志索引集"
        # 未命中仍回退为 metric_id 原文
        assert result[TS_ID] == TS_ID

    @override_settings(ROLE="web")
    def test_single_batch_failure_only_loses_that_batch(self):
        def fake_query(self, queries, tenant_id):
            if _branch_field_sets(queries[0])[0] == FIELDS_LOG:
                return [_log_row()]
            raise RuntimeError("模拟某一批失败")

        with mock.patch.object(MetricTranslator, "_query_metrics", fake_query), _patched_tenant():
            result = MetricTranslator().translate([LOG_ID, TS_ID])

        assert result[LOG_ID] == "日志索引集"
        assert result[TS_ID] == TS_ID

    @override_settings(ROLE="web")
    def test_all_batches_failed_returns_original_ids(self):
        def fake_query(self, queries, tenant_id):
            raise RuntimeError("查询失败")

        with mock.patch.object(MetricTranslator, "_query_metrics", fake_query), _patched_tenant():
            result = MetricTranslator().translate([LOG_ID, TS_ID])

        assert result == {LOG_ID: LOG_ID, TS_ID: TS_ID}

    @override_settings(ROLE="api")
    def test_api_role_skips_translation(self):
        with mock.patch.object(MetricTranslator, "_query_metrics") as query_metrics:
            assert MetricTranslator().translate([LOG_ID, TS_ID]) == {}
        query_metrics.assert_not_called()

    @override_settings(ROLE="web")
    def test_empty_values(self):
        with mock.patch.object(MetricTranslator, "_query_metrics") as query_metrics:
            assert MetricTranslator().translate([]) == {}
        query_metrics.assert_not_called()

    @override_settings(ROLE="web")
    def test_no_parsable_metric_skips_query(self):
        with mock.patch.object(MetricTranslator, "_query_metrics") as query_metrics:
            assert MetricTranslator().translate(["bk_monitor", "prometheus.xxx"]) == {}
        query_metrics.assert_not_called()

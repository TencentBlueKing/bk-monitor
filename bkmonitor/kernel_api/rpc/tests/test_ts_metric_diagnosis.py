"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.

纯单元测试：直接测 _diagnose_metric 核心判断逻辑，无需数据库。
"""

from bkmonitor.utils.ts_metric_diagnosis import _diagnose_metric


def _call(
    source_backend="redis",
    redis_metric_score=None,
    redis_dimension_raw=None,
    redis_recent_detail=None,
    redis_history_detail=None,
    ts_metric=None,
    rt_field=None,
    direct_metric_caches=None,
    web_metric_cache_candidates=None,
    ts_group=None,
):
    """调用 _diagnose_metric 的简化包装，未指定参数取安全默认值。"""

    class _FakeGroup:
        bk_data_id = 1573662
        table_id = "7_bkmonitor_time_series_1573662.__default__"
        bk_biz_id = 7

    return _diagnose_metric(
        ts_group=ts_group or _FakeGroup(),
        source_backend=source_backend,
        redis_metric_score=redis_metric_score,
        redis_dimension_raw=redis_dimension_raw,
        redis_recent_detail=redis_recent_detail,
        redis_history_detail=redis_history_detail,
        ts_metric=ts_metric,
        rt_field=rt_field,
        direct_metric_caches=direct_metric_caches or [],
        web_metric_cache_candidates=web_metric_cache_candidates or [],
    )


class TestWebCachePriority:
    """web_metric_cache_candidates 命中时应优先返回 ok，不受 source/metadata 状态影响。"""

    def test_web_cache_beats_bkdata_source_missing(self):
        """复现场景：bkdata source 找不到指标，但策略侧缓存已命中 → 应判定 ok 而非 source。

        Bug: transfer_pipeline_frontend_handled_total 在 BCS-K8S-90001 上，
        BKData 查不到（近期/历史均 None），MetricListCache 以 BK_MONITOR_COLLECTOR 存在，
        原来错误地返回 judge=source。
        """
        candidate = {"data_source_label": "bk_monitor", "result_table_label": "kubernetes"}
        stage, message, _ = _call(
            source_backend="bkdata",
            redis_recent_detail=None,
            redis_history_detail=None,
            web_metric_cache_candidates=[candidate],
        )
        assert stage == "ok"
        assert "策略侧缓存中命中" in message

    def test_web_cache_beats_redis_source_missing(self):
        """redis source 也找不到指标，但策略侧缓存命中 → 应判定 ok。"""
        candidate = {"data_source_label": "bk_monitor", "result_table_label": "kubernetes"}
        stage, message, _ = _call(
            source_backend="redis",
            redis_metric_score=None,
            redis_dimension_raw=None,
            web_metric_cache_candidates=[candidate],
        )
        assert stage == "ok"
        assert "策略侧缓存中命中" in message

    def test_web_cache_beats_metadata_missing(self):
        """source 有数据但 metadata 缺失，策略侧缓存命中 → 应判定 ok 而非 metadata。"""
        score = 1775808502
        candidate = {"data_source_label": "bk_monitor", "result_table_label": "kubernetes"}
        stage, _, _ = _call(
            source_backend="redis",
            redis_metric_score=score,
            redis_dimension_raw=b"{}",
            redis_recent_detail={"field_name": "m", "last_modify_time": score},
            redis_history_detail={"field_name": "m", "last_modify_time": score},
            ts_metric=None,
            rt_field=None,
            web_metric_cache_candidates=[candidate],
        )
        assert stage == "ok"


class TestSourceStage:
    """无 web cache 时，source 层缺失应正确判定 source。"""

    def test_bkdata_source_missing_no_cache(self):
        stage, _, _ = _call(source_backend="bkdata", redis_recent_detail=None, redis_history_detail=None)
        assert stage == "source"

    def test_redis_source_missing_no_cache(self):
        stage, _, _ = _call(source_backend="redis", redis_metric_score=None, redis_dimension_raw=None)
        assert stage == "source"


class TestMetadataStage:
    """source 有数据、无 web cache 时，metadata 缺失应判定 metadata。"""

    def test_ts_metric_missing(self):
        score = 1775808502
        stage, _, _ = _call(
            source_backend="redis",
            redis_metric_score=score,
            redis_dimension_raw=b"{}",
            redis_recent_detail={"field_name": "m", "last_modify_time": score},
            redis_history_detail={"field_name": "m", "last_modify_time": score},
            ts_metric=None,
        )
        assert stage == "metadata"

    def test_rt_field_missing(self):
        score = 1775808502

        class _FakeMetric:
            pass

        stage, _, _ = _call(
            source_backend="redis",
            redis_metric_score=score,
            redis_dimension_raw=b"{}",
            redis_recent_detail={"field_name": "m", "last_modify_time": score},
            redis_history_detail={"field_name": "m", "last_modify_time": score},
            ts_metric=_FakeMetric(),
            rt_field=None,
        )
        assert stage == "metadata"


class TestOkStage:
    """三层全部命中（direct cache）时应判定 ok。"""

    def test_all_layers_ok(self):
        score = 1775808502

        class _FakeMetric:
            pass

        class _FakeField:
            pass

        stage, _, _ = _call(
            source_backend="redis",
            redis_metric_score=score,
            redis_dimension_raw=b"{}",
            redis_recent_detail={"field_name": "m", "last_modify_time": score},
            redis_history_detail={"field_name": "m", "last_modify_time": score},
            ts_metric=_FakeMetric(),
            rt_field=_FakeField(),
            direct_metric_caches=[{"result_table_id": "t", "metric_field": "m"}],
        )
        assert stage == "ok"


class TestWebCacheStage:
    """source+metadata 全命中但 direct cache 缺失 → web_cache。"""

    def test_web_cache_missing(self):
        score = 1775808502

        class _FakeMetric:
            pass

        class _FakeField:
            pass

        stage, _, _ = _call(
            source_backend="redis",
            redis_metric_score=score,
            redis_dimension_raw=b"{}",
            redis_recent_detail={"field_name": "m", "last_modify_time": score},
            redis_history_detail={"field_name": "m", "last_modify_time": score},
            ts_metric=_FakeMetric(),
            rt_field=_FakeField(),
            direct_metric_caches=[],
        )
        assert stage == "web_cache"

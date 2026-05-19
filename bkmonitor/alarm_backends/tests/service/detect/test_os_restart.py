"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from collections import namedtuple

from unittest import mock
import pytest

from alarm_backends.service.detect.strategy.os_restart import OsRestart
from core.errors.alarm_backends.detect import InvalidDataPoint

DataPoint = namedtuple("DataPoint", ["value", "timestamp", "unit", "item", "dimensions"])

datapoint200 = DataPoint(200, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint99 = DataPoint(99, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint30 = DataPoint(30, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint800 = DataPoint(800, 100000000, "%", "item", {"ip": "127.0.0.1"})
datapoint700 = DataPoint(700, 100000000, "%", "item", {"ip": "127.0.0.1"})


class TestOsRestart:
    def test_os_restart_1(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint700, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_os_restart_2(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_os_restart_3(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint800, datapoint99, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint700)) == 0

    def test_os_restart_4(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint99, datapoint30, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 0

    def test_os_restart_5(self):
        # bugfix: 解决云机器买入后，10分钟内部署完agent，开始上报数据，引起的误告。
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, None, None],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 0

    def test_os_restart_6(self):
        # bugfix: 解决云机器买入后，10分钟内部署完agent，开始上报数据，引起的误告。
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, None, datapoint200, datapoint99],
        ):
            detect_engine = OsRestart(config={})
            assert len(detect_engine.detect(datapoint200)) == 3

    def test_anomaly_message(self):
        with mock.patch(
            "alarm_backends.service.detect.strategy.os_restart.OsRestart.history_point_fetcher",
            return_value=[datapoint200, datapoint800, datapoint30, datapoint700],
        ):
            from .mocked_data import datapoint99

            detect_engine = OsRestart(config={})
            anomaly_result = detect_engine.detect_records(datapoint99, 1)
            assert len(anomaly_result) == 1
            assert anomaly_result[0].anomaly_message == "当前服务器在99秒前发生系统重启事件"

    def test_detect_with_invalid_datapoint(self):
        with pytest.raises(InvalidDataPoint):
            detect_engine = OsRestart(config={})
            detect_engine.detect((99, 100000000))


class TestOsRestartQueryHistoryPoints:
    """覆盖 OsRestart.query_history_points 自治预取路径。

    核心修复：long-running 机器 (uptime > 3600) 重启进入 ≤ 3600 时，必须能拿到该机器
    自己的真实历史 entry。修复点：
    - 一次性 unify-query 拉 [min_ts - 25min, max_ts + 1m] 完整窗口
    - 预占位窗口内所有 history_timestamp，阻断 fetch_history_point 回退到 Redis hgetall
    - try/finally 还原 item.query.expression，避免对共享 query 实例的污染
    """

    @staticmethod
    def _make_item(records=None, is_partial=False, original_expression="a <= 3600", n_data_sources=1):
        item = mock.Mock()
        item.id = 67493
        item.strategy = mock.Mock()
        item.strategy.id = 67515
        item.query_configs = [{"agg_interval": 60}]
        item.query = mock.Mock()
        item.query.expression = original_expression
        item.query.is_partial = is_partial
        item.query_record = mock.Mock(return_value=records or [])
        # 模拟 data_sources：每个含独立的 filter_dict，用真实 dict 而非 Mock，便于断言其 in-place 修改
        item.data_sources = []
        for _ in range(n_data_sources):
            ds = mock.Mock()
            ds.filter_dict = {}
            item.data_sources.append(ds)
        return item

    @staticmethod
    def _make_dp(ts, value, item, ip=None):
        dp = mock.Mock()
        dp.timestamp = ts
        dp.value = value
        dp.item = item
        dp.dimensions = {"bk_target_ip": ip} if ip else {}
        return dp

    def test_empty_data_points_is_noop(self):
        detector = OsRestart(config={})
        detector.query_history_points([])
        # 不抛异常即可；不强制约束 _local_history_storage 是否被初始化

    def test_expression_restored_after_normal_path(self):
        item = self._make_item(records=[])
        dp = self._make_dp(1700000000, 23, item)
        detector = OsRestart(config={})
        detector.query_history_points([dp])
        # try/finally 必须还原 expression，避免污染 access/detect 共享的 item.query
        assert item.query.expression == "a <= 3600"
        # query_record 调用时 expression 必然为 "a"（拿到真实 uptime）；结束后已还原
        item.query_record.assert_called_once_with(1700000000 - 1500, 1700000000 + 60)

    def test_partial_keeps_placeholders_empty_and_restores_expression(self):
        item = self._make_item(records=[], is_partial=True)
        dp = self._make_dp(1700000000, 23, item)
        detector = OsRestart(config={})
        detector.query_history_points([dp])
        # expression 在 partial 路径也必须还原
        assert item.query.expression == "a <= 3600"
        # partial 时占位字典必须保留为空 dict，避免基类 fetch_history_point fallback 到 hgetall
        assert detector._local_history_storage, "partial 路径丢失占位 key，会让 fetch 回退到旧 Redis cache"
        assert all(v == {} for v in detector._local_history_storage.values()), (
            "partial 路径不应填充任何 dimensions_md5 entry"
        )

    @mock.patch("alarm_backends.service.detect.strategy.os_restart.adapter_data_access_2_detect")
    @mock.patch("alarm_backends.service.detect.strategy.os_restart.DataRecord")
    def test_prefetch_fills_long_running_host_restart_history(self, mock_data_record, mock_adapter):
        """模拟 long-running 机器在重启周期被 access 推到 detect，
        断言 query_history_points 把该机器在 25min / 10min / 1min 前的真实 uptime 填到 _local_history_storage。
        """
        from alarm_backends.core.cache import key as cache_key

        ts = 1700000000
        records = [
            {"_time_": ts - 1500, "_result_": 5_000_000},  # 25min 前 (long-running)
            {"_time_": ts - 600, "_result_": 5_000_600},  # 10min 前 (long-running)
            {"_time_": ts - 60, "_result_": 5_001_140},  # 上一周期
            {"_time_": ts, "_result_": 23},  # 当前 (重启后)
        ]
        item = self._make_item(records=records)
        dp = self._make_dp(ts, 23, item)

        # mock DataRecord：返回 truthy value 让循环不跳过
        mock_data_record.side_effect = [mock.Mock(value=r["_result_"]) for r in records]

        # mock adapter_data_access_2_detect：返回带 timestamp/record_id/as_dict 的 fake detect_point
        index = {"i": 0}

        def _adapter_side_effect(_record, _item):
            r = records[index["i"]]
            index["i"] += 1
            fp = mock.Mock()
            fp.timestamp = r["_time_"]
            # 用不含点的 fake md5：生产代码以 record_id.split(".")[0] 取桶 key
            fp.record_id = f"md5host1.{r['_time_']}"
            fp.as_dict = mock.Mock(return_value={"value": r["_result_"], "time": r["_time_"]})
            return fp

        mock_adapter.side_effect = _adapter_side_effect

        detector = OsRestart(config={})
        detector.query_history_points([dp])

        # 1) 应当只发 1 次 query_record，O(1) RPC
        item.query_record.assert_called_once_with(ts - 1500, ts + 60)

        # 2) 所有 records 对应的 timestamp 都应有目标机器的 dimensions_md5 entry
        for r in records:
            hkey = cache_key.HISTORY_DATA_KEY.get_key(strategy_id=67515, item_id=67493, timestamp=r["_time_"])
            assert hkey in detector._local_history_storage, f"timestamp={r['_time_']} 未被占位"
            assert "md5host1" in detector._local_history_storage[hkey], (
                f"timestamp={r['_time_']} 缺少目标机器的 dimensions_md5 entry，"
                f"会让 fetch_history_point 返回 None 导致漏报"
            )

        # 3) expression 已还原
        assert item.query.expression == "a <= 3600"


class TestOsRestartIPFilterOptimization:
    """覆盖 OsRestart.query_history_points 按 IP 维度收敛 unify-query 的优化路径。

    优化点：在调用 unify-query 前，把本批次 data_points 的 bk_target_ip 收集成 list，
    临时塞进 data_source.filter_dict["bk_target_ip__eq"]，让 vmselect 端只扫描这 K 台机器，
    typical 业务下降 1-2 个数量级。K > MAX_PREFETCH_IP_FILTER（默认 100）时回退到不加 filter 的全量查询。
    """

    _make_item = staticmethod(TestOsRestartQueryHistoryPoints._make_item)
    _make_dp = staticmethod(TestOsRestartQueryHistoryPoints._make_dp)

    def test_small_batch_applies_ip_filter(self):
        """K=2 的小批次应当在 data_source.filter_dict 中加入 bk_target_ip__eq。"""
        item = self._make_item(records=[])
        dp1 = self._make_dp(1700000000, 23, item, ip="fakehostA")
        dp2 = self._make_dp(1700000000, 31, item, ip="fakehostB")
        detector = OsRestart(config={})
        # capture：在 query_record 被调用的瞬间记录 filter_dict 状态
        observed_filter: dict = {}

        def _capture(start, end):
            observed_filter.update(item.data_sources[0].filter_dict)
            return []

        item.query_record.side_effect = _capture
        detector.query_history_points([dp1, dp2])
        # 调用 query_record 时 filter_dict 应当含 IP 列表（已排序）
        assert "bk_target_ip__eq" in observed_filter
        assert observed_filter["bk_target_ip__eq"] == ["fakehostA", "fakehostB"]

    def test_large_batch_falls_back_to_target_scope(self):
        """K = MAX_PREFETCH_IP_FILTER + 1（默认 101）超出上限应当不加 IP filter，回退到全量查询。"""
        from alarm_backends.service.detect.strategy.os_restart import MAX_PREFETCH_IP_FILTER

        item = self._make_item(records=[])
        ts = 1700000000
        # 构造 K = MAX_PREFETCH_IP_FILTER + 1 个 data_point
        dps = [self._make_dp(ts, 100, item, ip=f"fakehost{i:04d}") for i in range(MAX_PREFETCH_IP_FILTER + 1)]
        detector = OsRestart(config={})
        observed_filter: dict = {}

        def _capture(start, end):
            observed_filter.update(item.data_sources[0].filter_dict)
            return []

        item.query_record.side_effect = _capture
        detector.query_history_points(dps)
        # K 过大，不应加 IP filter
        assert "bk_target_ip__eq" not in observed_filter

    def test_filter_dict_restored_after_normal_path(self):
        """正常路径下 filter_dict 必须 try/finally 还原（避免污染共享 data_source 实例）。"""
        item = self._make_item(records=[])
        # 预置一条 data_source 已有的 filter（模拟 access 阶段或别处加的）
        item.data_sources[0].filter_dict["existing_field__eq"] = "preserved_value"
        original_snapshot = dict(item.data_sources[0].filter_dict)

        dp = self._make_dp(1700000000, 23, item, ip="fakehostA")
        detector = OsRestart(config={})
        detector.query_history_points([dp])

        # 还原后 filter_dict 应当与原始快照一致，不含 IP filter 残留
        assert item.data_sources[0].filter_dict == original_snapshot
        assert "bk_target_ip__eq" not in item.data_sources[0].filter_dict

    def test_filter_dict_restored_after_partial_path(self):
        """partial 路径下 filter_dict 同样必须还原。"""
        item = self._make_item(records=[], is_partial=True)
        item.data_sources[0].filter_dict["existing_field__eq"] = "preserved_value"
        original_snapshot = dict(item.data_sources[0].filter_dict)

        dp = self._make_dp(1700000000, 23, item, ip="fakehostA")
        detector = OsRestart(config={})
        detector.query_history_points([dp])

        assert item.data_sources[0].filter_dict == original_snapshot
        assert "bk_target_ip__eq" not in item.data_sources[0].filter_dict

    def test_no_filter_when_data_points_have_no_ip(self):
        """data_points 全无 bk_target_ip 时，不加 IP filter 且 filter_dict 不变。"""
        item = self._make_item(records=[])
        original_snapshot = dict(item.data_sources[0].filter_dict)

        dp = self._make_dp(1700000000, 23, item)  # 无 ip
        detector = OsRestart(config={})
        observed_filter: dict = {}

        def _capture(start, end):
            observed_filter.update(item.data_sources[0].filter_dict)
            return []

        item.query_record.side_effect = _capture
        detector.query_history_points([dp])

        assert "bk_target_ip__eq" not in observed_filter
        assert item.data_sources[0].filter_dict == original_snapshot

    def test_multi_data_sources_all_get_filter(self):
        """item 含多个 data_sources 时，每个都应当加 IP filter 并独立还原。"""
        item = self._make_item(records=[], n_data_sources=2)
        item.data_sources[0].filter_dict["ds0_existing__eq"] = "ds0"
        item.data_sources[1].filter_dict["ds1_existing__eq"] = "ds1"
        snap0 = dict(item.data_sources[0].filter_dict)
        snap1 = dict(item.data_sources[1].filter_dict)

        dp = self._make_dp(1700000000, 23, item, ip="fakehostA")
        detector = OsRestart(config={})
        captured: list = []

        def _capture(start, end):
            captured.append(dict(item.data_sources[0].filter_dict))
            captured.append(dict(item.data_sources[1].filter_dict))
            return []

        item.query_record.side_effect = _capture
        detector.query_history_points([dp])

        # 调用瞬间两个 data_sources 都被注入了 IP filter
        assert captured[0].get("bk_target_ip__eq") == ["fakehostA"]
        assert captured[1].get("bk_target_ip__eq") == ["fakehostA"]
        # 还原后均回到原始 filter
        assert item.data_sources[0].filter_dict == snap0
        assert item.data_sources[1].filter_dict == snap1

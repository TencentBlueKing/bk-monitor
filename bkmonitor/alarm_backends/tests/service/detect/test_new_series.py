"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import time

from unittest import mock
import pytest

from alarm_backends.core.cache import key
from alarm_backends.service.detect import DataPoint
from alarm_backends.service.detect.strategy.new_series import NewSeries
from bkmonitor.utils.common_utils import count_md5

ITEM_ID = 1
AGG_DIMENSION = ["bk_target_ip", "bk_target_cloud_id"]

# 每个测试用唯一 strategy_id 隔离 Redis key（fakeredis 全会话共享单实例，状态跨测试持久）
_UID = [8000]


@pytest.fixture(autouse=True)
def _isolate_keys():
    _UID[0] += 1
    yield


def make_item(strategy_id=None, item_id=ITEM_ID, agg_dimension=None, agg_interval=60, ns_configs=None):
    item = mock.MagicMock()
    item.strategy.id = _UID[0] if strategy_id is None else strategy_id
    item.id = item_id
    item.query_configs = [
        {"agg_dimension": AGG_DIMENSION if agg_dimension is None else agg_dimension, "agg_interval": agg_interval}
    ]
    # item.algorithms 必须是真实 list(检测器写侧据此取 max(detect_range)/max(max_series))
    item.algorithms = [{"type": "NewSeries", "config": c} for c in (ns_configs or [default_config()])]
    # 让 _new_series_cache 这类动态属性走真实 dict，而非 MagicMock 自动属性
    item._new_series_cache = None
    item.name = "new-series-item"
    return item


def make_dp(fingerprint, timestamp, item):
    dp = DataPoint(
        accessed_data={"value": 1, "time": timestamp, "record_id": f"{fingerprint}.{timestamp}"},
        item=item,
    )
    return dp


def default_config(detect_range=86400, effective_delay=86400, max_series=100000):
    return {"detect_range": detect_range, "effective_delay": effective_delay, "max_series": max_series}


def signature(item):
    return count_md5(sorted(item.query_configs[0]["agg_dimension"]))


def seed_learned(item, ago=10):
    """把 learn_start 预置为很久以前，模拟宽限期已过(非冷启动)。"""
    sig = signature(item)
    learn_key = key.NEW_SERIES_LEARN_START_KEY.get_key(
        strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig
    )
    key.NEW_SERIES_LEARN_START_KEY.client.set(learn_key, int(time.time()) - 86400 - ago)


def seen_score(item, fingerprint):
    sig = signature(item)
    seen_key = key.NEW_SERIES_SEEN_KEY.get_key(strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig)
    return key.NEW_SERIES_SEEN_KEY.client.zscore(seen_key, fingerprint)


@pytest.mark.django_db
class TestNewSeries:
    def test_config_validate(self):
        # detect_range 必填，缺失则抛 InvalidAlgorithmsConfig
        from core.errors.alarm_backends.detect import InvalidAlgorithmsConfig

        with pytest.raises(InvalidAlgorithmsConfig):
            NewSeries(config={})

    def test_a1_first_dimension_alerts_after_warmup(self):
        item = make_item()
        seed_learned(item)  # 非冷启动
        detector = NewSeries(config=default_config())
        dp = make_dp("dimA", 100000000, item)
        detector.pre_detect([dp])
        # 库空 + 非宽限 + 首现 -> 告警
        assert len(detector.detect(dp)) == 1
        # 写入后 score = 数据时间戳
        assert int(seen_score(item, "dimA")) == 100000000

    def test_a2_seen_within_window_no_alert(self):
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config(detect_range=86400))
        dp1 = make_dp("dimB", 100000000, item)
        detector.pre_detect([dp1])
        assert len(detector.detect(dp1)) == 1  # 首现告警，并写入
        # 第二批：同维度，窗内再现 -> 不告警
        item._new_series_cache = None
        detector2 = NewSeries(config=default_config(detect_range=86400))
        dp2 = make_dp("dimB", 100000000 + 60, item)
        detector2.pre_detect([dp2])
        assert len(detector2.detect(dp2)) == 0

    def test_a3_reappear_after_detect_range_alerts(self):
        item = make_item()
        seed_learned(item)
        sig = signature(item)
        seen_key = key.NEW_SERIES_SEEN_KEY.get_key(
            strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig
        )
        # 预置 dimC last_seen 在 detect_range 之外
        key.NEW_SERIES_SEEN_KEY.client.zadd(seen_key, {"dimC": 100000000 - 86400 - 100})
        detector = NewSeries(config=default_config(detect_range=86400))
        dp = make_dp("dimC", 100000000, item)
        detector.pre_detect([dp])
        assert len(detector.detect(dp)) == 1

    def test_b1_cold_start_warmup_no_alert_but_learns(self):
        item = make_item()
        # 不预置 learn_start -> 首跑进入宽限期
        detector = NewSeries(config=default_config(effective_delay=86400))
        dp1 = make_dp("dimD", 100000000, item)
        dp2 = make_dp("dimE", 100000000, item)
        detector.pre_detect([dp1, dp2])
        # 宽限期内：不告警
        assert len(detector.detect(dp1)) == 0
        assert len(detector.detect(dp2)) == 0
        # 但已灌库
        assert int(seen_score(item, "dimD")) == 100000000
        assert int(seen_score(item, "dimE")) == 100000000

    def test_fp4_in_memory_max_ts(self):
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config())
        # 同一维度，批内多个时间戳 -> 应记录最大 ts(不被更旧的覆盖)
        dp_old = make_dp("dimF", 100000000, item)
        dp_new = make_dp("dimF", 100000000 + 300, item)
        detector.pre_detect([dp_new, dp_old])  # 顺序故意先新后旧
        assert int(seen_score(item, "dimF")) == 100000000 + 300

    def test_batch_internal_same_fingerprint_reports_once(self):
        # 积压/补数：同一指纹在一批出现多个时间戳，_seen_before 是批前快照会让其全部命中 is_new，
        # 应批内去重只报一次；不同指纹各自照报。
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config())
        same = [make_dp("dimN", 100000000 + i * 60, item) for i in range(3)]
        other = make_dp("dimO", 100000000, item)
        detector.pre_detect(same + [other])
        fired_same = sum(1 for dp in same if len(detector.detect(dp)) == 1)
        assert fired_same == 1  # 同指纹 3 个时间点只报 1 次
        assert len(detector.detect(other)) == 1  # 不同指纹照报
        # 两个指纹都已灌库(去重不影响写入)
        assert int(seen_score(item, "dimN")) == 100000000 + 120
        assert int(seen_score(item, "dimO")) == 100000000

    def test_batch_exact_duplicate_record_id_reports_once(self):
        # 同维度+同时间戳的重复点(record_id 相同,access 批内去重看不见)是两个独立 DataPoint 对象。
        # fire map 按 id(dp) 建键 -> 各占一格、首个照报(1 次)；若按 record_id 建键会互相覆盖成 0 次。
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config())
        dup1 = make_dp("dimX", 100000000, item)
        dup2 = make_dp("dimX", 100000000, item)
        assert dup1.record_id == dup2.record_id  # 同 record_id
        assert id(dup1) != id(dup2)  # 但是不同对象
        detector.pre_detect([dup1, dup2])
        fired = sum(1 for dp in (dup1, dup2) if len(detector.detect(dp)) == 1)
        assert fired == 1

    def test_extra_context_is_pure_and_idempotent(self):
        # extra_context 必须纯读无副作用：框架命中后会再次调用它渲染消息，
        # 同一数据点连调两次结果必须一致(否则第二次会把 is_new_series 翻成 False)。
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config())
        dp = make_dp("dimP", 100000000, item)
        detector.pre_detect([dp])
        ctx = {"data_point": dp}
        first = detector.extra_context(ctx)["is_new_series"]
        second = detector.extra_context(ctx)["is_new_series"]
        assert first is True
        assert second is True  # 幂等：第二次(消息渲染)不被首次副作用打穿

    def test_c2_late_data_no_backward_overwrite(self):
        # 跨批：先写当前 ts=1000000，再来一批迟到/补数 ts=900000(更旧) -> last_seen 不回退(取 max)
        item = make_item()
        seed_learned(item)
        d1 = NewSeries(config=default_config())
        dp_cur = make_dp("dimL", 1000000, item)
        d1.pre_detect([dp_cur])
        assert int(seen_score(item, "dimL")) == 1000000
        # 第二批迟到数据(更旧 ts)
        item._new_series_cache = None
        d2 = NewSeries(config=default_config())
        dp_late = make_dp("dimL", 900000, item)
        d2.pre_detect([dp_late])
        # last_seen 必须仍是 1000000(不被 900000 倒退覆盖)，否则后续会误判新
        assert int(seen_score(item, "dimL")) == 1000000

    def test_c1_multi_level_diff_config_uses_max(self):
        # 两个 NewSeries 不同 max_series/detect_range 共享同一 seen-zset -> 写侧取 max(最宽松)
        small = default_config(detect_range=3600, max_series=2)
        large = default_config(detect_range=30 * 86400, max_series=100000)
        item = make_item(ns_configs=[small, large])
        seed_learned(item)
        # level 1(小配置)先跑
        d_small = NewSeries(config=small)
        d_large = NewSeries(config=large)
        # 喂 3 个维度：若用 small.max_series=2 判 over-limit 会 safe-fail；用 max=10w 则正常
        dps = [make_dp(f"dimM{i}", 1000000, item) for i in range(3)]
        d_small.pre_detect(dps)
        d_large.pre_detect(dps)
        # 写侧用 max(max_series)=10w -> 不 over-limit，正常写入(seen_before 非 None)
        assert d_small._seen_before is not None
        assert int(seen_score(item, "dimM0")) == 1000000
        # TTL 用 max(detect_range)*2=60 天 -> 远大于 small 的 3600
        sig = signature(item)
        seen_key = key.NEW_SERIES_SEEN_KEY.get_key(
            strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig
        )
        assert key.NEW_SERIES_SEEN_KEY.client.ttl(seen_key) > 86400

    def test_q2_multi_level_share_clean_snapshot(self):
        item = make_item()
        seed_learned(item)
        # level=1 与 level=2 两个 NewSeries 共享同一 item/签名
        d1 = NewSeries(config=default_config())
        d2 = NewSeries(config=default_config())
        dp = make_dp("dimG", 100000000, item)
        d1.pre_detect([dp])  # 读干净态(空) + 写
        d2.pre_detect([dp])  # 复用 d1 的快照(干净态)，不被 d1 的写污染
        # 两个 level 都应判 dimG 为新
        assert len(d1.detect(dp)) == 1
        assert len(d2.detect(dp)) == 1
        # 且只写一次(score 正确)
        assert int(seen_score(item, "dimG")) == 100000000

    def test_over_limit_safe_fail(self):
        # item.algorithms 与 detector 配置一致(max_series=2)，写侧 eff_max_series=2
        item = make_item(ns_configs=[default_config(max_series=2)])
        seed_learned(item)
        detector = NewSeries(config=default_config(max_series=2))
        dps = [make_dp(f"dim{i}", 100000000, item) for i in range(5)]
        detector.pre_detect(dps)
        # 批内去重维度数(5) > max_series(2) -> 安全失败：不写 seen、不告警
        assert detector._seen_before is None
        for dp in dps:
            assert len(detector.detect(dp)) == 0
        assert seen_score(item, "dim0") is None

    def test_fingerprint_is_record_id_prefix(self):
        item = make_item()
        # record_id = "{dimensions_md5}.{ts}"，指纹取前段，与 access 全链路口径一致
        dp = make_dp("abc123md5", 100000000, item)
        assert NewSeries._fingerprint(dp) == "abc123md5"

    def test_failure_safe_branch_no_alert(self):
        item = make_item()
        seed_learned(item)
        detector = NewSeries(config=default_config())
        dp = make_dp("dimH", 100000000, item)
        # 模拟 pre_detect 内部 Redis 失败 -> 安全分支，不报
        with mock.patch.object(NewSeries, "_read_and_write", return_value=None):
            detector.pre_detect([dp])
        assert detector._seen_before is None
        assert len(detector.detect(dp)) == 0

    def test_periodic_clean_trims_to_max_series_and_signature_matches(self):
        from alarm_backends.core.detect_result.clean import CleanResult

        sid = _UID[0]
        iid = 7
        agg_dimension = ["bk_target_ip"]
        max_series = 3
        sig = count_md5(sorted(agg_dimension))
        seen_key = key.NEW_SERIES_SEEN_KEY.get_key(strategy_id=sid, item_id=iid, dimension_signature=sig)
        # 预置 5 个成员(> max_series=3)
        key.NEW_SERIES_SEEN_KEY.client.zadd(seen_key, {f"m{i}": 1000 + i for i in range(5)})

        strategy = {
            "id": sid,
            "items": [
                {
                    "id": iid,
                    "algorithms": [{"type": "NewSeries", "config": {"max_series": max_series, "detect_range": 86400}}],
                    "query_configs": [{"agg_dimension": agg_dimension, "agg_interval": 60}],
                }
            ],
        }
        with (
            mock.patch(
                "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_ids", return_value=[sid]
            ),
            mock.patch(
                "alarm_backends.core.detect_result.clean.StrategyCacheManager.get_strategy_by_ids",
                return_value=[strategy],
            ),
        ):
            CleanResult.clean_new_series_seen_cache()
        # 清理走的 key 与 detector 同签名口径 -> 真实 zset 被收口到 max_series
        assert key.NEW_SERIES_SEEN_KEY.client.zcard(seen_key) == max_series
        # 收口删最旧(score 最小)，保留最新的 m2/m3/m4
        assert key.NEW_SERIES_SEEN_KEY.client.zscore(seen_key, "m0") is None
        assert key.NEW_SERIES_SEEN_KEY.client.zscore(seen_key, "m4") is not None

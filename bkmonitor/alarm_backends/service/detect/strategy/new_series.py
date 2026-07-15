"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from rest_framework import serializers

from bk_monitor_base.strategy import NewSeriesSerializer as BaseNewSeriesSerializer

from alarm_backends.core.cache import key
from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)
from bkmonitor.utils.common_utils import count_md5
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.prometheus import metrics

logger = logging.getLogger("detect")

# 单条 Redis 命令/流水线的成员上限，避免一条命令承载海量成员阻塞节点(沿用 clean.py 先例)。
CHUNK_SIZE = 5000
# 软 TTL 下界，保证 TTL 始终 >= detect_range(承重不等式)。
_MIN_SOFT_TTL = 86400
# NewSeries 算法类型标识(= AlgorithmModel.AlgorithmChoices.NewSeries)
NEW_SERIES_TYPE = "NewSeries"
# 新状态至少积累 5 个非空、非 partial 的有效检测周期，第 6 个有效周期开始告警。
BASELINE_CYCLES = 5


class NewSeriesSerializer(BaseNewSeriesSerializer):
    """检测进程配置校验；保存层 serializer 位于 bkmonitor.strategy。"""

    threshold = serializers.IntegerField(label="告警阈值", required=False, default=0)


class NewSeries(BasicAlgorithmsCollection):
    """
    新维度值检测算法。

    语义：每次检测任务出现新的维度组合(time series)时，倒推 detect_range 时间窗内是否出现过相同维度组合，
    未出现过则告警，出现过则不告警。

    实现：每 (strategy_id, item_id, dimension_signature, threshold) 维护一条 Redis SortedSet
    (member=维度指纹=record_id 前段, score=该维度最近一次出现的数据时间戳)。
    pre_detect 在批检测前一次性读旧态、写新态(item 内相同 threshold 的多 level 只读写一次)；
    extra_context 逐点注入 is_new_series 布尔，复用基类表达式机制产出异常点。

    基线：新状态前 5 个非空、非 partial 批次只灌库不告警，第 6 个有效批次开始检测。
    threshold=0 复用历史 seen/完成态，非零 threshold 使用隔离状态；各 threshold 独立累计进度。
    """

    config_serializer = NewSeriesSerializer
    expr_op = "and"
    desc_tpl = _lazy("出现新的维度值（近 {{ detect_range_display }} 内未出现过）")

    def __init__(self, config, unit="", extra_config=None):
        # 安全分支默认值(若 pre_detect 未跑或失败，extra_context 不报而非崩)
        self._seen_before = None
        self._baseline_batch = False
        # pre_detect 预计算的"每个数据点是否告警" map(键=id(data_point))，让 extra_context 纯读无副作用。
        self._fire_by_dp = {}
        super().__init__(config, unit, extra_config)
        self.detect_range = int(self.validated_config["detect_range"])
        # 兼容存档 effective_delay 字段，但运行时不再按时间宽限；首次拉取是否已完成基线由 baseline_done key 控制。
        self.effective_delay = self.detect_range
        self.max_series = int(self.validated_config.get("max_series", 100000))
        self.threshold = int(self.validated_config.get("threshold", 0))

    def gen_expr(self):
        yield ExprDetectAlgorithms("is_new_series", self.desc_tpl)

    # ------------------------------------------------------------------ #
    # 指纹 / 维度签名 / 批次令牌
    # ------------------------------------------------------------------ #
    @staticmethod
    def _fingerprint(data_point):
        # 维度指纹用 record_id 前段(= access 计算的 dimensions_md5)，是全链路唯一性口径。
        # 进程端口等指标 access 已剥离 listen 等动态维度，故不可用 count_md5(data_point.dimensions) 自算(会每周期判新)。
        return str(data_point.record_id).rsplit(".", 1)[0]

    @staticmethod
    def signature_from_agg_dimension(agg_dimension):
        # 维度集合签名的唯一口径(detector 与周期清理 clean.py 共用，避免双写漂移)。
        return count_md5(sorted(agg_dimension or []))

    @classmethod
    def _dimension_signature(cls, item):
        # 维度集合签名取配置层 agg_dimension(canonical)，不取运行期 item.query.dimensions(无 group_by 时为 None 会崩)。
        # 保存层已保证 NewSeries 策略为单 query_config。
        agg_dimension = None
        if item.query_configs:
            agg_dimension = item.query_configs[0].get("agg_dimension")
        return cls.signature_from_agg_dimension(agg_dimension)

    @staticmethod
    def _item_new_series_configs(item):
        # 同一 item 下所有 NewSeries 算法的配置；相同 threshold 的多 level 共享同一 seen-zset。
        algorithms = getattr(item, "algorithms", None)
        if not isinstance(algorithms, list):
            return []
        return [a.get("config") or {} for a in algorithms if a.get("type") == NEW_SERIES_TYPE]

    @classmethod
    def has_new_series(cls, item):
        return bool(cls._item_new_series_configs(item))

    @classmethod
    def _threshold_configs(cls, item, threshold):
        return [config for config in cls._item_new_series_configs(item) if int(config.get("threshold", 0)) == threshold]

    @classmethod
    def _soft_ttl(cls, item, threshold, default_detect_range=0):
        ns_configs = cls._threshold_configs(item, threshold)
        detect_ranges = [int(c.get("detect_range", 0) or 0) for c in ns_configs]
        detect_ranges.append(int(default_detect_range or 0))
        return max(max(detect_ranges) * 2, _MIN_SOFT_TTL)

    @staticmethod
    def threshold_token(threshold):
        threshold = int(threshold)
        return f"n{abs(threshold)}" if threshold < 0 else f"p{threshold}"

    @classmethod
    def _seen_state(cls, item, sig, threshold):
        params = {
            "strategy_id": item.strategy.id,
            "item_id": item.id,
            "dimension_signature": sig,
        }
        if threshold == 0:
            cache_key = key.NEW_SERIES_SEEN_KEY
        else:
            cache_key = key.NEW_SERIES_THRESHOLD_SEEN_KEY
            params["threshold"] = cls.threshold_token(threshold)
        return cache_key, cache_key.get_key(**params)

    @classmethod
    def _mark_baseline_done(cls, item, sig, threshold, soft_ttl):
        params = {
            "strategy_id": item.strategy.id,
            "item_id": item.id,
            "dimension_signature": sig,
        }
        if threshold == 0:
            cache_key = key.NEW_SERIES_BASELINE_DONE_KEY
        else:
            cache_key = key.NEW_SERIES_THRESHOLD_BASELINE_DONE_KEY
            params["threshold"] = cls.threshold_token(threshold)
        cache_key.client.set(cache_key.get_key(**params), 1, ex=soft_ttl)

    @classmethod
    def _is_baseline_done(cls, item, sig, threshold):
        if threshold != 0:
            done_key = key.NEW_SERIES_THRESHOLD_BASELINE_DONE_KEY.get_key(
                strategy_id=item.strategy.id,
                item_id=item.id,
                dimension_signature=sig,
                threshold=cls.threshold_token(threshold),
            )
            return bool(key.NEW_SERIES_THRESHOLD_BASELINE_DONE_KEY.client.exists(done_key))

        done_key = key.NEW_SERIES_BASELINE_DONE_KEY.get_key(
            strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig
        )
        learn_key = key.NEW_SERIES_LEARN_START_KEY.get_key(
            strategy_id=item.strategy.id, item_id=item.id, dimension_signature=sig
        )
        client = key.NEW_SERIES_BASELINE_DONE_KEY.client
        return bool(client.exists(done_key) or client.exists(learn_key))

    @classmethod
    def _advance_baseline(cls, item, sig, threshold, soft_ttl):
        progress_key = key.NEW_SERIES_BASELINE_PROGRESS_KEY.get_key(
            strategy_id=item.strategy.id,
            item_id=item.id,
            dimension_signature=sig,
            threshold=cls.threshold_token(threshold),
        )
        client = key.NEW_SERIES_BASELINE_PROGRESS_KEY.client
        pipe = client.pipeline(transaction=True)
        pipe.incr(progress_key)
        pipe.expire(progress_key, soft_ttl)
        progress = int(pipe.execute()[0])
        if progress >= BASELINE_CYCLES:
            # 完成态写失败时把进度稳定在门槛，后续有效批次继续重试且仍不告警。
            client.set(progress_key, BASELINE_CYCLES, ex=soft_ttl)
            cls._mark_baseline_done(item, sig, threshold, soft_ttl)
        return progress

    @classmethod
    def bootstrap_empty_batch(cls, item):
        # 保留调度层调用接口；空批次不是有效学习周期，不创建或推进任何状态。
        return cls.has_new_series(item)

    def _range_display(self):
        if self.detect_range % 86400 == 0:
            return _("%(n)s 天") % {"n": self.detect_range // 86400}
        if self.detect_range % 3600 == 0:
            return _("%(n)s 小时") % {"n": self.detect_range // 3600}
        return _("%(n)s 秒") % {"n": self.detect_range}

    @classmethod
    def _is_log_count_item(cls, item):
        if not item.query_configs:
            return False
        query_config = item.query_configs[0]
        return (
            query_config.get("data_source_label") == DataSourceLabel.BK_LOG_SEARCH
            and query_config.get("data_type_label") == DataTypeLabel.LOG
        )

    @staticmethod
    def _numeric_value(data_point):
        try:
            return float(data_point.value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_eligible(cls, data_point, is_log_count, threshold):
        # 日志关键字(COUNT)场景下，唯一可靠的"该分钟有真实文档"信号是 _result_>=1；
        # unify-query 对 date_histogram 设 MinDocCount(0)+ExtendedBounds，无文档的分钟会补出 value=0 的合成桶，
        # 因此先排除日志的非正数桶，再应用用户阈值；负阈值也不能让合成 0 桶进入状态。
        value = cls._numeric_value(data_point)
        if value is None:
            return False
        if is_log_count and value <= 0:
            return False
        return value > threshold

    # ------------------------------------------------------------------ #
    # 逐点检测：读 pre_detect 缓存的旧态，注入布尔
    # ------------------------------------------------------------------ #
    def extra_context(self, context):
        # 纯读 pre_detect 预计算的 fire map，无副作用：框架命中后会再次调用本方法渲染消息(detect->_format_message)，
        # 纯读保证两次调用结果一致、也不被未来"消息模板引用 is_new_series"之类改动悄悄打穿。
        # 默认 False 覆盖 pre_detect 失败/未跑(map 为空)的安全分支(漏报优于误报风暴)。
        return {
            "is_new_series": self._fire_by_dp.get(id(context["data_point"]), False),
            "detect_range_display": self._range_display(),
        }

    # ------------------------------------------------------------------ #
    # 批前预处理：读旧态 + 写新态(item 级共享，多 level 只做一次)
    # ------------------------------------------------------------------ #
    def pre_detect(self, data_points):
        # 防御性重置：保证每次 pre_detect 从干净 map 起步(当前框架每批新建实例，此处为冗余防御)。
        self._fire_by_dp = {}
        item = data_points[0].item
        # access 仅在 partial 查询时按需透传 is_partial=True；跨进程后不能依赖 item.query 运行态。
        if getattr(data_points[0], "is_partial", False):
            self._fire_by_dp = {id(data_point): False for data_point in data_points}
            return

        is_log_count = self._is_log_count_item(item)
        invalid_count = sum(1 for dp in data_points if self._numeric_value(dp) is None)
        if invalid_count:
            metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="invalid_value").inc(
                invalid_count
            )
            logger.warning(
                "[detect][new_series] strategy(%s) item(%s) ignored %s non-numeric values",
                item.strategy.id,
                item.id,
                invalid_count,
            )
        eligible_data_points = [
            dp for dp in data_points if self._is_eligible(dp, is_log_count=is_log_count, threshold=self.threshold)
        ]
        sig = self._dimension_signature(item)
        cache = getattr(item, "_new_series_cache", None)
        # 保留原始列表对象本身，既按真实批次身份复用，又防止对象回收后 id 被下一批复用。
        if not (isinstance(cache, dict) and cache.get("batch") is data_points):
            cache = {"batch": data_points, "entries": {}}
            item._new_series_cache = cache

        cache_key = (sig, self.threshold)
        entries = cache["entries"]
        if cache_key not in entries:
            # 相同阈值的多 level 复用快照和进度，不同阈值各自读写隔离状态。
            entries[cache_key] = self._read_and_write(eligible_data_points, item, sig)

        entry = entries[cache_key]
        if entry is None:
            self._seen_before = None
            self._baseline_batch = False
            return

        self._seen_before = entry["seen_before"]
        self._baseline_batch = entry["baseline_batch"]
        self._compute_fire_map(data_points, {id(dp) for dp in eligible_data_points})

    def _compute_fire_map(self, data_points, eligible_data_point_ids):
        # 预计算每个数据点是否告警，供 extra_context 纯读。判定口径与 detect_records 遍历同序：
        # is_new = 库无该指纹 或 距上次出现已超 detect_range；基线批次一律不报。
        # 批内去重：同一指纹仅放行首个符合点。按 id(data_point) 建键(而非 record_id)——
        # 同维度同时间戳的重复点 record_id 相同，按 record_id 建键会互相覆盖致 0 次告警。
        # 不变量：access 每条记录建独立 DataPoint，批内对象互不相同(id 唯一)；去重靠 flagged 按指纹判。
        flagged = set()
        fire_by_dp = {}
        for data_point in data_points:
            if id(data_point) not in eligible_data_point_ids:
                fire_by_dp[id(data_point)] = False
                continue

            fingerprint = self._fingerprint(data_point)
            last_seen = self._seen_before.get(fingerprint)
            is_new = (last_seen is None) or (int(data_point.timestamp) - last_seen > self.detect_range)
            fire = (not self._baseline_batch) and is_new and (fingerprint not in flagged)
            if fire:
                flagged.add(fingerprint)
            fire_by_dp[id(data_point)] = fire
        self._fire_by_dp = fire_by_dp

    def _read_and_write(self, data_points, item, sig):
        strategy_id = item.strategy.id
        item_id = item.id
        seen_cache_key, seen_key = self._seen_state(item, sig, self.threshold)
        client = seen_cache_key.client
        start = time.time()
        # 仅相同阈值的多 level 共享 seen-zset，写侧取该阈值组最宽松配置。
        ns_configs = self._threshold_configs(item, self.threshold)
        eff_detect_range = max([self.detect_range] + [int(c.get("detect_range", 0) or 0) for c in ns_configs])
        eff_max_series = max([self.max_series] + [int(c.get("max_series", 0) or 0) for c in ns_configs])
        try:
            baseline_done = self._is_baseline_done(item, sig, self.threshold)
            # 1) 内存按指纹聚合本批最大时间戳(Redis<6.2 无 ZADD GT，不能靠 Redis 取 max)。
            latest = {}
            for data_point in data_points:
                fp = self._fingerprint(data_point)
                ts = int(data_point.timestamp)
                if fp not in latest or ts > latest[fp]:
                    latest[fp] = ts

            # over-limit 安全失败：本批去重维度数超过追踪上限 → 不写 seen、不报、上报指标，让用户调大 max_series/降基数。
            if len(latest) > eff_max_series:
                metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="over_limit").inc()
                logger.warning(
                    "[detect][new_series] strategy(%s) item(%s) batch series(%s) exceed max_series(%s), safe-fail",
                    strategy_id,
                    item_id,
                    len(latest),
                    eff_max_series,
                )
                return None

            fps = list(latest.keys())

            # 2) 读旧态(本批之前)：分块流水线 zscore(Redis<6.2 无 ZMSCORE)。
            seen_before = {}
            for i in range(0, len(fps), CHUNK_SIZE):
                chunk = fps[i : i + CHUNK_SIZE]
                # RedisProxy 会复用首次创建的 PipelineProxy，首次即启用事务，确保后续首块 ZADD+EXPIRE
                # 不会因复用此前的非事务读 pipeline 而失去原子性。
                pipe = client.pipeline(transaction=True)
                for fp in chunk:
                    pipe.zscore(seen_key, fp)
                for fp, score in zip(chunk, pipe.execute()):
                    if score is not None:
                        seen_before[fp] = int(float(score))

            soft_ttl = max(eff_detect_range * 2, _MIN_SOFT_TTL)

            # 3) 写新态：仅满足阈值的数据点进入 seen；没有满足阈值的数据点时仍可推进有效周期。
            if fps:
                first_chunk = fps[:CHUNK_SIZE]
                first_mapping = {fp: max(latest[fp], seen_before.get(fp, 0)) for fp in first_chunk}
                # 首次创建和常规续期统一使用事务流水线，使第一批 ZADD 与 EXPIRE 原子提交，不产生无 TTL 新键。
                pipe = client.pipeline(transaction=True)
                pipe.zadd(seen_key, first_mapping)
                pipe.expire(seen_key, soft_ttl)
                pipe.execute()
                for i in range(CHUNK_SIZE, len(fps), CHUNK_SIZE):
                    chunk = fps[i : i + CHUNK_SIZE]
                    client.zadd(seen_key, {fp: max(latest[fp], seen_before.get(fp, 0)) for fp in chunk})
                metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="seen_write").inc(len(fps))

                # 4) 热路径内存安全阀：缓存超 2*max_series 时分批 trim。
                self._safety_trim(client, seen_key, strategy_id, eff_max_series)

            # 5) seen 写成功后推进学习。存量完成态不创建进度，但继续续期，避免活跃策略意外重新学习。
            if baseline_done:
                self._mark_baseline_done(item, sig, self.threshold, soft_ttl)
            else:
                self._advance_baseline(item, sig, self.threshold, soft_ttl)

            return {"seen_before": seen_before, "baseline_batch": not baseline_done}
        except Exception as e:  # noqa  失败安全分支：不冒泡到 detect 主流程，不误报，由 metric 暴露。
            metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="failure").inc()
            logger.exception(
                "[detect][new_series] strategy(%s) item(%s) pre_detect failed, safe-fail this batch: %s",
                strategy_id,
                item_id,
                e,
            )
            return None
        finally:
            metrics.NEW_SERIES_PROCESS_TIME.labels(strategy_id=metrics.TOTAL_TAG).observe(time.time() - start)

    def _safety_trim(self, client, seen_key, strategy_id, max_series):
        try:
            card = client.zcard(seen_key)
            if card <= max_series * 2:
                return
            excess = card - max_series
            removed = 0
            while removed < excess:
                step = min(CHUNK_SIZE, excess - removed)
                client.zremrangebyrank(seen_key, 0, step - 1)
                removed += step
            metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="trim").inc(removed)
        except Exception as e:  # noqa  安全阀失败不影响检测正确性(判定靠时间戳，不靠淘汰)。
            logger.warning("[detect][new_series] strategy(%s) safety trim failed: %s", strategy_id, e)

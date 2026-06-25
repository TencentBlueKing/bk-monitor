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

from bk_monitor_base.strategy import NewSeriesSerializer

from alarm_backends.core.cache import key
from alarm_backends.service.detect.strategy import (
    BasicAlgorithmsCollection,
    ExprDetectAlgorithms,
)
from bkmonitor.utils.common_utils import count_md5
from core.prometheus import metrics

logger = logging.getLogger("detect")

# 单条 Redis 命令/流水线的成员上限，避免一条命令承载海量成员阻塞节点(沿用 clean.py 先例)。
CHUNK_SIZE = 5000
# 软 TTL 下界，保证 TTL 始终 >= detect_range(承重不等式)。
_MIN_SOFT_TTL = 86400
# NewSeries 算法类型标识(= AlgorithmModel.AlgorithmChoices.NewSeries)
NEW_SERIES_TYPE = "NewSeries"


class NewSeries(BasicAlgorithmsCollection):
    """
    新维度值检测算法。

    语义：每次检测任务出现新的维度组合(time series)时，倒推 detect_range 时间窗内是否出现过相同维度组合，
    未出现过则告警，出现过则不告警。

    实现：每 (strategy_id, item_id, dimension_signature) 维护一条 Redis SortedSet
    (member=维度指纹=record_id 前段, score=该维度最近一次出现的数据时间戳)。
    pre_detect 在批检测前一次性读旧态、写新态(item 级共享，多 level 只读写一次)；
    extra_context 逐点注入 is_new_series 布尔，复用基类表达式机制产出异常点。

    冷启动：effective_delay 宽限期内(策略首次生效后)只灌库不告警，避免存量序列首轮全判新。
    """

    config_serializer = NewSeriesSerializer
    expr_op = "and"
    desc_tpl = _lazy("出现新的维度值（近 {{ detect_range_display }} 内未出现过）")

    def __init__(self, config, unit="", extra_config=None):
        # 安全分支默认值(若 pre_detect 未跑或失败，extra_context 不报而非崩)
        self._seen_before = None
        self._warmup = False
        # pre_detect 预计算的"每个数据点是否告警" map(键=id(data_point))，让 extra_context 纯读无副作用。
        self._fire_by_dp = {}
        super().__init__(config, unit, extra_config)
        self.detect_range = int(self.validated_config["detect_range"])
        # 宽限期恒等于检测窗口(detect_range)：NewSeries 不设独立宽限期,忽略存档 effective_delay,使新老策略
        # 运行口径一致。seen-set 留存全部(无按时间淘汰),历史深度 = now-learn_start,故宽限达 detect_range
        # 即"已学满一个检测窗口";调大 detect_range 会让 warmup 自动重新进入(补差额),无需改 learn_start。
        self.effective_delay = self.detect_range
        self.max_series = int(self.validated_config.get("max_series", 100000))

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
        # 同一 item 下所有 NewSeries 算法的配置(可能多 level 分属不同 detect_range/max_series，共享同一 seen-zset)。
        algorithms = getattr(item, "algorithms", None)
        if not isinstance(algorithms, list):
            return []
        return [a.get("config") or {} for a in algorithms if a.get("type") == NEW_SERIES_TYPE]

    @staticmethod
    def _batch_token(data_points):
        # 用内容令牌标识"本批"，供 item 级快照在同一次 detect() 内多 level 复用，跨批自然失效。
        return (
            len(data_points),
            str(data_points[0].record_id),
            str(data_points[-1].record_id),
        )

    def _range_display(self):
        if self.detect_range % 86400 == 0:
            return _("%(n)s 天") % {"n": self.detect_range // 86400}
        if self.detect_range % 3600 == 0:
            return _("%(n)s 小时") % {"n": self.detect_range // 3600}
        return _("%(n)s 秒") % {"n": self.detect_range}

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
        sig = self._dimension_signature(item)
        token = self._batch_token(data_points)

        cache = getattr(item, "_new_series_cache", None)
        if not (isinstance(cache, dict) and cache.get("token") == token):
            cache = {"token": token, "by_sig": {}}
            item._new_series_cache = cache

        by_sig = cache["by_sig"]
        if sig not in by_sig:
            # 同一 (item, 维度签名, 批次) 下，仅首个 detector 读旧态+写新态；其余 level 复用快照、不重复读写。
            by_sig[sig] = self._read_and_write(data_points, item, sig)

        entry = by_sig[sig]
        if entry is None:
            self._seen_before = None
            self._warmup = False
            return

        self._seen_before = entry["seen_before"]
        self._warmup = (int(time.time()) - entry["learn_start"]) < self.effective_delay
        self._compute_fire_map(data_points)

    def _compute_fire_map(self, data_points):
        # 预计算每个数据点是否告警，供 extra_context 纯读。判定口径与 detect_records 遍历同序：
        # is_new = 库无该指纹 或 距上次出现已超 detect_range；宽限期内一律不报。
        # 批内去重：同一指纹仅放行首个符合点。按 id(data_point) 建键(而非 record_id)——
        # 同维度同时间戳的重复点 record_id 相同，按 record_id 建键会互相覆盖致 0 次告警。
        # 不变量：access 每条记录建独立 DataPoint，批内对象互不相同(id 唯一)；去重靠 flagged 按指纹判。
        flagged = set()
        fire_by_dp = {}
        for data_point in data_points:
            fingerprint = self._fingerprint(data_point)
            last_seen = self._seen_before.get(fingerprint)
            is_new = (last_seen is None) or (int(data_point.timestamp) - last_seen > self.detect_range)
            fire = (not self._warmup) and is_new and (fingerprint not in flagged)
            if fire:
                flagged.add(fingerprint)
            fire_by_dp[id(data_point)] = fire
        self._fire_by_dp = fire_by_dp

    def _read_and_write(self, data_points, item, sig):
        strategy_id = item.strategy.id
        item_id = item.id
        seen_key = key.NEW_SERIES_SEEN_KEY.get_key(strategy_id=strategy_id, item_id=item_id, dimension_signature=sig)
        learn_key = key.NEW_SERIES_LEARN_START_KEY.get_key(
            strategy_id=strategy_id, item_id=item_id, dimension_signature=sig
        )
        client = key.NEW_SERIES_SEEN_KEY.client
        start = time.time()
        # 多 level 共享同一 seen-zset：写侧(TTL/over-limit/trim)取 item 内所有 NewSeries 算法的最宽松配置，
        # 避免"先跑的小窗口/小上限 level"破坏另一 level 的承重不等式(与 clean.py 的 max() 口径对齐)。
        ns_configs = self._item_new_series_configs(item)
        eff_detect_range = max([self.detect_range] + [int(c.get("detect_range", 0) or 0) for c in ns_configs])
        eff_max_series = max([self.max_series] + [int(c.get("max_series", 0) or 0) for c in ns_configs])
        try:
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
                pipe = client.pipeline(transaction=False)
                for fp in chunk:
                    pipe.zscore(seen_key, fp)
                for fp, score in zip(chunk, pipe.execute()):
                    if score is not None:
                        seen_before[fp] = int(float(score))

            soft_ttl = max(eff_detect_range * 2, _MIN_SOFT_TTL)

            # 3) 写新态：分块 zadd，score=max(本批最大ts, 旧态)。跨批取 max(等价 ZADD GT)，
            #    防止迟到/补数的更旧时间戳把 last_seen 倒退(Redis<6.2 无 ZADD GT，故内存取 max)。
            for i in range(0, len(fps), CHUNK_SIZE):
                chunk = fps[i : i + CHUNK_SIZE]
                client.zadd(seen_key, {fp: max(latest[fp], seen_before.get(fp, 0)) for fp in chunk})
            # 紧跟 zadd 立即续期，最小化"已写 seen 但无 TTL"的窗口(M5)。
            client.expire(seen_key, soft_ttl)
            metrics.NEW_SERIES_PROCESS_COUNT.labels(strategy_id=metrics.TOTAL_TAG, type="seen_write").inc(len(fps))

            # 4) learn_start：仅在 seen 首写成功之后 setnx，避免"learn_start 写成功而 seen 为空"的半成品态。
            learn_start = client.get(learn_key)
            now = int(time.time())
            if learn_start is None:
                client.set(learn_key, now, nx=True, ex=soft_ttl)  # set 带 ex 原子 TTL
                learn_start = client.get(learn_key)
            else:
                client.expire(learn_key, soft_ttl)  # 已存在则续期，与 seen 同 ttl 一起过期
            learn_start = int(float(learn_start)) if learn_start is not None else now

            # 5) 热路径内存安全阀：缓存超 2*max_series 时分批 trim(主清理交周期任务，这里仅防两次清理间爆量)。
            self._safety_trim(client, seen_key, strategy_id, eff_max_series)

            return {"seen_before": seen_before, "learn_start": learn_start}
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

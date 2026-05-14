"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""
系统重启算法：基于时序数据 system.env.uptime 进行判断。
uptime表示主机运行时长。
该检测算法依赖bkmonitorbeat采集器被gse agent托管(机器重启后bkmonitorbeat自动拉起)否则无数据上报会导致该检测算法失效。
"""

import functools
import json
import logging

from django.utils.translation import gettext_lazy as _

from alarm_backends.core.cache import key
from alarm_backends.service.access.data.records import DataRecord
from alarm_backends.service.detect.strategy import (
    ExprDetectAlgorithms,
    adapter_data_access_2_detect,
)
from alarm_backends.service.detect.strategy.simple_ring_ratio import SimpleRingRatio
from alarm_backends.service.detect.strategy.threshold import Threshold

logger = logging.getLogger("detect")


class OsRestart(SimpleRingRatio):
    expr_op = "and"
    desc_tpl = _("当前服务器在{{data_point.value}}秒前发生系统重启事件")
    config_serializer = None

    def gen_expr(self):
        # 主机运行时长在0到600秒之间
        yield Threshold(config=[[{"threshold": 0, "method": "gt"}, {"threshold": 600, "method": "lte"}]])
        # 主机当前运行时长比前一个周期值小，或者前一个周期值为空
        yield ExprDetectAlgorithms(
            "(previous is None or (value < previous)) and (is_ok_10minute_ago or is_ok_25minute_ago)",
            "{value} < {previous}",
        )
        # 系统重启的检测原理：
        #
        # 检查采集器上报的机器运行时长数据：
        #
        # 1. 主机运行时长在0到600秒之间（10分钟内有开机行为）
        # 2. 主机当前运行时长比前一个周期值小，或者前一个周期值为空（上一分钟未上报数据，或者上一分钟运行时长大于当前时刻）
        # 3. 判断主机10分钟前及25分钟前是否有时长数据上报。
        # 4. 如果有，则表明是重启，如果没有上报说明有4种情况： 1. 机器一直未开机。 2. 机器开机，但是数据未上报。3. 机器重启耗时超过至少25分钟。
        # 这种情况通过ping不可达和agent失联进行补充。 4. 机器一直未开机，开机后在10-25分钟内发生了重新启动事件也能检测出重启。
        # 5. ！！！机器一直未开机，开机后10分钟内发生重启事件，此极端情况无法告警！！！

    def extra_context(self, context):
        env = dict(previous=None, ip="")
        history_data_points = self.history_point_fetcher(context.data_point, greed=True)
        if history_data_points[1]:
            env["previous"] = history_data_points[1].value

        env["is_ok_10minute_ago"] = history_data_points[2] is not None
        env["is_ok_25minute_ago"] = history_data_points[3] is not None
        env["ip"] = context.data_point.dimensions.get("ip", "")

        return env

    def get_history_offsets(self, item):
        agg_interval = item.query_configs[0]["agg_interval"]
        # 保留 offset=0 占位以维持 history_point_fetcher(greed=True) 返回列表的索引语义
        # ([1]=previous, [2]=is_ok_10min, [3]=is_ok_25min)。
        # offset=0 在新的 query_history_points 中不再用于 publish 通用缓存。
        return [0, agg_interval, 60 * 10, 60 * 25]

    def query_history_points(self, data_points):
        """
        OsRestart 自治的历史数据预取，覆写 HistoryPointFetcher.query_history_points 的通用 cache 路径。

        背景：access 侧对 OsRestart 策略改写 expression="a <= 3600"（core/cache/strategy.py），
        long-running 机器（uptime > 3600）的数据点从未进入 detect、也从未被 publish 到
        HISTORY_DATA_KEY 的 hash 内。当这类机器重启进入 uptime ≤ 3600 时，通用 cache 路径会
        因同 timestamp 已被其他"持续 ≤ 3600 的机器"写入而走入 cache hit + entry miss 路径，
        is_ok_10minute_ago / is_ok_25minute_ago 静默 False，最终导致漏报。

        本方法一次性发起单次 unify-query，覆盖 [min_ts - 25min, max_ts + 1m] 的完整窗口，
        并把 expression 改写为 "a"（去掉 a <= 3600 过滤），把真实历史填充到本地
        _local_history_storage。多机器并发场景天然合并为一次 promql 多 series，RPC 数 O(1)。

        关键不变量：窗口内每个 history_timestamp 必须在 _local_history_storage 中存在对应的
        entry（即使是空 dict）。否则基类 fetch_history_point 会因 `history_key not in
        _local_history_storage` 而 fallback 到 client.hgetall(history_key)，再次取到被"持续
        ≤ 3600 的机器"刷新进 Redis 的旧 hash，原 bug 会复现。
        """
        if not data_points:
            return
        item = data_points[0].item
        original_expression = item.query.expression
        # 改写 expression 拿真实 uptime（access 侧 a <= 3600 过滤的逆操作）；try/finally 保证还原，
        # 避免改动 access 与 detect 共享的 item.query 实例后泄漏到后续调用。
        item.query.expression = "a"
        try:
            sorted_data_points = sorted(data_points, key=lambda x: x.timestamp)
            agg_interval = item.query_configs[0]["agg_interval"]
            offsets = self.get_history_offsets(item)
            max_offset = max((o[1] if isinstance(o, tuple) else o) for o in offsets)
            from_timestamp = sorted_data_points[0].timestamp - max_offset
            until_timestamp = sorted_data_points[-1].timestamp + agg_interval

            history_key_maker = functools.partial(
                key.HISTORY_DATA_KEY.get_key,
                strategy_id=item.strategy.id,
                item_id=item.id,
            )

            # 预占位：保证窗口内每个 history_timestamp 都在 _local_history_storage 中存在 entry，
            # 阻断基类 fetch_history_point 回退到 Redis hgetall 的路径。
            self._local_history_storage = {
                history_key_maker(timestamp=ts): {} for ts in range(from_timestamp, until_timestamp, agg_interval)
            }

            item_records = item.query_record(from_timestamp, until_timestamp)
            if item.query.is_partial:
                # VM vmstorage 节点临时不可用。保持已占位的空 entry，让本周期 is_ok_*_ago=False，
                # 漏报 1 个周期但避免误用旧 cache 数据；下个周期 unify-query 恢复后自动回正。
                logger.warning(
                    "strategy(%s) item(%s) os_restart history query is partial, "
                    "fallback to no-history mode, time_range(%s, %s)",
                    item.strategy.id,
                    item.id,
                    from_timestamp,
                    until_timestamp,
                )
                return

            # 直接按 (history_key, dimensions_md5) 结构填本地索引，bypass 通用 Redis cache 短路逻辑。
            for record in item_records:
                point = DataRecord(item, record)
                if not point.value:
                    continue
                detect_point = adapter_data_access_2_detect(point, item)
                history_key = history_key_maker(timestamp=detect_point.timestamp)
                # 已被预占位的 key 直接取到 dict；超出预占位范围的（理论上不会发生，防御性处理）则补建。
                bucket = self._local_history_storage.setdefault(history_key, {})
                bucket[detect_point.record_id.split(".")[0]] = json.dumps(detect_point.as_dict())
        finally:
            item.query.expression = original_expression

    def gen_anomaly_point(self, data_point, detect_result, level, auto_format=True):
        ap = super().gen_anomaly_point(data_point, detect_result, level)
        ap.anomaly_message = self._format_message(data_point)
        return ap

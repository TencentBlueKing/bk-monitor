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

from django.utils.functional import cached_property
from django.utils.translation import gettext as _
from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import InnerDoc, Search, field

from bkmonitor.documents import EventDocument
from bkmonitor.documents.base import BaseDocument, Date
from bkmonitor.documents.constants import ES_INDEX_SETTINGS
from bkmonitor.models import NO_DATA_TAG_DIMENSION
from constants.alert import (
    EVENT_SEVERITY,
    HANDLE_STAGE_DICT,
    CMDB_TARGET_DIMENSIONS,
    EventStatus,
)
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.errors.alert import AlertNotFoundError


@registry.register_document
class AlertDocument(BaseDocument):
    REINDEX_ENABLED = True
    REINDEX_QUERY = Search().filter("term", status=EventStatus.ABNORMAL).to_dict()

    # mget 单批 id 上限：超过则分批普通 search（替代 scroll），避免单次 size 过大
    MGET_BATCH_SIZE = 5000

    bk_tenant_id = field.Keyword()
    id = field.Keyword(required=True)
    seq_id = field.Long()

    alert_name = field.Text(fields={"raw": field.Keyword()})
    strategy_id = field.Keyword()

    # 告警创建时间(服务器时间)
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)

    # 告警开始时间
    begin_time = Date(format=BaseDocument.DATE_FORMAT)
    # 告警结束时间
    end_time = Date(format=BaseDocument.DATE_FORMAT)
    # 告警持续的最新时间
    latest_time = Date(format=BaseDocument.DATE_FORMAT)
    # 首次异常时间
    first_anomaly_time = Date(format=BaseDocument.DATE_FORMAT)

    # 告警负责人，对应页面上的通知人
    assignee = field.Keyword(multi=True)

    # 指派负责人
    appointee = field.Keyword(multi=True)

    # 升级关注人
    supervisor = field.Keyword(multi=True)

    # 关注人, 只可以查看，不可以操作
    follower = field.Keyword(multi=True)

    # 持续时间
    duration = field.Long()
    # 确认时长
    ack_duration = field.Long()

    # 最新一次 Event
    event = field.Object(doc_class=type("EventInnerDoc", (EventDocument, InnerDoc), {}))
    severity = field.Integer()
    status = field.Keyword()

    is_blocked = field.Boolean()

    is_handled = field.Boolean()
    is_ack = field.Boolean()
    is_ack_noticed = field.Boolean()
    ack_operator = field.Keyword()
    is_shielded = field.Boolean()
    shield_left_time = field.Integer()
    shield_id = field.Keyword(multi=True)
    handle_stage = field.Keyword(multi=True)
    labels = field.Keyword(multi=True)
    assign_tags = field.Nested(
        properties={
            "key": field.Keyword(),
            "value": field.Text(required=True, fields={"raw": field.Keyword(ignore_above=256)}),
        }
    )

    # 下一个状态设置的时间，用于状态流转
    next_status = field.Keyword()
    next_status_time = Date(format=BaseDocument.DATE_FORMAT)

    # 某个告警只会属于某一个故障，不可能同属于多个故障（否则这多个故障也应该属于一个故障）
    incident_id = field.Keyword()

    # 所属 Issue 的 ES _id（null 表示未关联）
    issue_id = field.Keyword()

    dedupe_md5 = field.Keyword()

    class Dimension(InnerDoc):
        key = field.Keyword()
        value = field.Keyword()
        display_key = field.Keyword()
        display_value = field.Keyword()

        def to_dict(self) -> dict:
            return super().to_dict(skip_empty=False)

    dimensions = field.Object(enabled=False, multi=True, doc_class=Dimension)

    # 告警的更多信息，例如：当时的策略快照
    extra_info = field.Object(enabled=False)

    class Index:
        name = "bkfta_alert"
        settings = ES_INDEX_SETTINGS.copy()

    def get_index_time(self):
        return self.parse_timestamp_by_id(self.id)

    @classmethod
    def parse_timestamp_by_id(cls, uuid: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return int(str(uuid)[:10])

    @classmethod
    def parse_sequence_by_id(cls, uuid: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return int(str(uuid)[10:])

    @classmethod
    def get(cls, id) -> "AlertDocument":
        """
        获取单条告警
        """
        try:
            ts = cls.parse_timestamp_by_id(id)
        except Exception:
            raise ValueError(f"invalid alert_id: {id}")
        # ts 反解自 alert_id 前 10 位 = begin_time。但 doc 实际索引日期由状态决定：
        # ABNORMAL 告警每天被 reindex 搬运到当天索引（旧索引中被 delete_by_query 删除）；
        # RESOLVED 告警永久停在状态切换那天的索引。因此查询窗口必须延伸到 now，
        # 否则只搜 begin_time 当天会漏掉所有跨期 doc。build_index_name_by_time
        # 已有"跨度 > 15 天退化月通配"规则保证 ES 负载可控。
        hits = cls.search(start_time=ts, end_time=int(time.time())).filter("term", id=id).execute().hits
        if not hits:
            raise AlertNotFoundError({"alert_id": id})
        return cls(**hits[0].to_dict())

    @classmethod
    def mget(cls, ids, fields: list = None) -> list["AlertDocument"]:
        """
        获取多条告警
        """
        if not ids:
            return []
        # 反解每个 id 的 begin_time（前 10 位）作为索引下界依据；无法反解的记 None，
        # 稍后并入最老批次按全局下界兜底（与原实现对无法反解 id 的处理一致）。
        parsed = []
        for id in ids:
            try:
                parsed.append((cls.parse_timestamp_by_id(id), id))
            except Exception:  # NOCC:broad-except(设计如此:)
                parsed.append((None, id))
        ts_values = [ts for ts, _ in parsed if ts is not None]
        global_min = min(ts_values) if ts_values else None
        # 上界固定 now：ABNORMAL 每天 reindex 到今日、RESOLVED 停在结束那天，doc 必落在
        # [begin_time, now]，故上界不可收窄（同 get()）。
        end_time = int(time.time())

        # 先按 begin_time 升序再分批：把时间相近的 id 聚到同一批，使每批可用"本批最小 begin_time"
        # 作为索引下界。否则当输入 id 在原始顺序里被打散时，每个分批都可能混进很老的 id，被迫对
        # 每一批都展开"全量最老 begin_time 到 now"的宽索引范围（分批数 × 宽范围）；排序后只有真正
        # 含老 id 的那一批才展开宽范围，其余批各查自己的窄范围。下界取本批最小即足以覆盖本批全部
        # doc（每个 doc 落在 [本批某 id 的 begin_time, now] ⊆ [本批最小 begin_time, now]）。
        # 无法反解的 id 记全局下界、随之排到最老批次，用最宽窗口兜底。
        parsed.sort(key=lambda p: p[0] if p[0] is not None else (global_min if global_min is not None else 0))

        # 分批普通 search 替代 scan()（scroll API），避免高并发批量 mget 在 ES 积压 scroll
        # context（曾突破 max_open_scroll_context=500 致 alert.manager 成功率告警）。mget 是按 id
        # 的有界查询，单批 terms 命中 ≤ 本批 id 数，一次 execute 即取完，无需 scroll 深翻页。
        # size 取本批 id 数 2 倍：reindex 期间同一 alert 可能在新旧索引各存一份，2 倍确保两份都
        # 取回再去重，不会因截断而漏掉较新副本。绝大多数调用单批不满，size 远小于上限、不在每个
        # 分片多占结果堆；满批时 size = 2 × MGET_BATCH_SIZE = 10000，恰等于 ES 默认
        # max_result_window（from=0，不越界）。
        # 同 id 去重保最新：按 -update_time 排序，首次出现（当前写索引中的最新副本）保留，旧副本
        # （reindex 后待 delete_by_query 清理、update_time 不大于新副本）丢弃。用 ES 排序而非比较
        # source，故 fields 过滤掉 update_time 时仍能正确判别。_id 即 alert id（save 时写入），恒存在。
        docs = {}
        for i in range(0, len(parsed), cls.MGET_BATCH_SIZE):
            batch = parsed[i : i + cls.MGET_BATCH_SIZE]
            batch_ts = [ts for ts, _ in batch if ts is not None]
            start_time = min(batch_ts) if batch_ts else global_min
            chunk = [id for _, id in batch]
            search = cls.search(start_time=start_time, end_time=end_time).filter("terms", id=chunk)
            if fields:
                search = search.source(fields=fields)
            search = search.sort("-update_time")
            for hit in search.params(size=len(chunk) * 2).execute():
                if hit.meta.id not in docs:
                    docs[hit.meta.id] = cls(**hit.to_dict())
        return list(docs.values())

    @classmethod
    def get_by_dedupe_md5(cls, dedupe_md5, start_time=None) -> "AlertDocument":
        search_object = cls.search(all_indices=True)
        if start_time:
            search_object = search_object.filter("range", latest_time={"gte": start_time})
        hits = search_object.filter("term", dedupe_md5=dedupe_md5).sort(*["-create_time"]).execute().hits
        if not hits:
            raise AlertNotFoundError({"alert_id": dedupe_md5})
        return cls(**hits[0].to_dict())

    # @property
    # def duration(self) -> int:
    #     """
    #     持续时间
    #     """
    #     # 加上60秒的冗余，避免显示为0
    #     return self.latest_time - self.begin_time + 60

    @cached_property
    def severity_display(self):
        """
        级别名称
        :rtype: str
        """
        for severity, display in EVENT_SEVERITY:
            if severity == self.severity:
                return str(display)
        return ""

    @property
    def strategy(self):
        if not self.extra_info or getattr(self.extra_info, "strategy", None) is None:
            return None
        return self.extra_info["strategy"].to_dict()

    @property
    def assign_group(self):
        if not self.extra_info or not getattr(self.extra_info, "matched_rule_info", None):
            return {}
        matched_rule_info = self.extra_info["matched_rule_info"].to_dict()
        return matched_rule_info.get("group_info") or {}

    @property
    def agg_dimensions(self):
        if not self.extra_info or "agg_dimensions" not in self.extra_info:
            return []
        return self.extra_info["agg_dimensions"]

    @property
    def origin_alarm(self):
        if not self.extra_info or "origin_alarm" not in self.extra_info:
            return None
        return self.extra_info["origin_alarm"].to_dict()

    @property
    def stage_display(self):
        """
        处理阶段
        """
        if self.is_shielded:
            return _("已屏蔽")
        if self.is_ack:
            return _("已确认")
        if self.handle_stage:
            return HANDLE_STAGE_DICT.get(self.handle_stage[0])
        if self.is_handled:
            return _("已通知")
        if self.is_blocked:
            return _("已流控")
        return ""

    @property
    def event_document(self):
        return EventDocument(**self.event.to_dict())

    @property
    def target_dimensions(self):
        # 目标维度
        return [d.to_dict() for d in self.dimensions if d.key in CMDB_TARGET_DIMENSIONS]

    @property
    def common_dimensions(self):
        # 非目标维度
        return [d.to_dict() for d in self.dimensions if d.key not in CMDB_TARGET_DIMENSIONS]

    @property
    def common_dimension_tuple(self) -> tuple:
        return tuple(sorted([(d["key"], d["value"]) for d in self.common_dimensions], key=lambda x: x[0]))

    @property
    def is_composite_strategy(self):
        """
        检查是否为关联告警策略
        """
        strategy = self.strategy
        if not strategy:
            return False
        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                if query_config["data_type_label"] == DataTypeLabel.ALERT:
                    return True
        return False

    @property
    def is_fta_event_strategy(self):
        """
        检查是否为自愈事件策略
        """
        strategy = self.strategy
        if not strategy:
            return False
        for item in strategy["items"]:
            for query_config in item["query_configs"]:
                if (
                    query_config["data_type_label"] == DataTypeLabel.EVENT
                    and query_config["data_source_label"] == DataSourceLabel.BK_FTA
                ):
                    return True
        return False

    @property
    def status_detail(self):
        if self.status == EventStatus.ABNORMAL and getattr(self.extra_info, "is_recovering", False):
            return EventStatus.RECOVERING
        return self.status

    @property
    def cycle_handle_record(self):
        if not self.extra_info or getattr(self.extra_info, "cycle_handle_record", None) is None:
            return {}
        return self.extra_info["cycle_handle_record"].to_dict()

    def is_no_data(self):
        """
        是否为无数据告警
        """
        event = self.event.to_dict()
        for dimension in event.get("tags", []):
            if NO_DATA_TAG_DIMENSION == dimension["key"]:
                return True
        return False

    def refresh_duration(self):
        """
        刷新告警持续时间
        """
        if self.is_composite_strategy:
            # 如果是关联告警，则按当前时间计算告警持续时间
            duration = int(time.time()) - self.first_anomaly_time
        else:
            # 其他情况，按照最新事件时间计算持续时间
            duration = self.latest_time - self.first_anomaly_time
            # 设置60s的冗余时间，避免显示为0
        duration = max(duration, 60)
        self.duration = duration

# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import operator
import time
from collections import defaultdict
from functools import reduce
from typing import Dict, List

from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy as _lazy
from elasticsearch_dsl import Q

from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionPlugin, ConvergeRelation
from bkmonitor.utils.time_tools import hms_string
from constants.action import (
    ACTION_DISPLAY_STATUS_CHOICES,
    ACTION_DISPLAY_STATUS_DICT,
    ActionDisplayStatus,
    ActionSignal,
    ConvergeStatus,
)
from constants.alert import EVENT_SEVERITY
from fta_web.alert.handlers.base import (
    AlertDimensionFormatter,
    BaseBizQueryHandler,
    BaseQueryTransformer,
    QueryField,
)
from fta_web.alert.handlers.translator import (
    AbstractTranslator,
    ActionPluginTypeTranslator,
    ActionSignalTranslator,
    BizTranslator,
)


class ActionQueryTransformer(BaseQueryTransformer):
    VALUE_TRANSLATE_FIELDS = {
        "alert_level": EVENT_SEVERITY,
        "status": ACTION_DISPLAY_STATUS_CHOICES,
    }

    query_fields = [
        QueryField("id", _lazy("处理记录ID"), is_char=True),
        QueryField("converge_id", _lazy("收敛记录ID")),
        QueryField("is_converge_primary", _lazy("是否为收敛关键记录")),
        QueryField("status", _lazy("状态")),
        QueryField("failure_type", _lazy("失败类型")),
        QueryField("ex_data", _lazy("异常信息"), searchable=False),
        QueryField("strategy_id", _lazy("策略ID")),
        QueryField("strategy_name", _lazy("策略名称"), agg_field="strategy_name.raw", is_char=True),
        QueryField("signal", _lazy("触发信号")),
        QueryField("alert_id", _lazy("告警ID")),
        QueryField("alert_level", _lazy("告警级别")),
        QueryField("operator", _lazy("负责人")),
        QueryField("inputs", _lazy("动作输入"), searchable=False),
        QueryField("outputs", _lazy("动作输出"), searchable=False),
        QueryField("failure_type", _lazy("动作输入")),
        QueryField("execute_times", _lazy("执行次数")),
        QueryField("action_plugin_type", _lazy("套餐类型")),
        QueryField("action_plugin", _lazy("套餐插件快照"), searchable=False),
        QueryField("action_name", _lazy("套餐名称"), agg_field="action_name.raw", is_char=True),
        QueryField("action_config", _lazy("套餐配置"), searchable=False),
        QueryField("action_config_id", _lazy("套餐ID")),
        QueryField("is_parent_action", _lazy("是否为子任务")),
        QueryField("related_action_ids", _lazy("关联的任务ID")),
        QueryField("parent_action_id", _lazy("父记录ID")),
        QueryField("create_time", _lazy("创建时间")),
        QueryField("update_time", _lazy("更新时间")),
        QueryField("end_time", _lazy("结束时间")),
        QueryField("bk_target_display", _lazy("目标")),
        QueryField("bk_biz_id", _lazy("业务ID")),
        QueryField("bk_biz_name", _lazy("业务名称"), is_char=True),
        QueryField("bk_set_ids", _lazy("集群ID")),
        QueryField("bk_set_names", _lazy("集群名称")),
        QueryField("bk_module_ids", _lazy("模块ID")),
        QueryField("bk_module_names", _lazy("模块名称")),
        QueryField("raw_id", _lazy("原始ID")),
        QueryField("duration", _lazy("处理时长")),
        QueryField("operate_target_string", _lazy("执行对象")),
        QueryField("content", _lazy("处理内容"), searchable=False),
        QueryField("dimensions", _lazy("维度信息"), searchable=False),
    ]


class ActionQueryHandler(BaseBizQueryHandler):
    """
    动作查询
    """

    query_transformer = ActionQueryTransformer
    CONST_MINUTES = 60

    def __init__(
        self,
        bk_biz_ids: List[int] = None,
        alert_ids: List[str] = None,
        status: List[str] = None,
        parent_action_id=None,
        username: str = "",
        **kwargs,
    ):
        super(ActionQueryHandler, self).__init__(bk_biz_ids, username, **kwargs)
        self.alert_ids = alert_ids
        self.status = [status] if isinstance(status, str) else status
        self.search_parent_action_id = None
        self.raw_id = None
        self.search_collect_action = False
        self.start_time = self.start_time or 0
        self.end_time = self.end_time or 0

        if not self.ordering:
            # 默认排序
            self.ordering = ["-create_time"]

        if parent_action_id:
            parent_action = ActionInstanceDocument.get(id=parent_action_id)
            if not parent_action:
                return

            # 搜索范围内在当前任务创建的前后一分钟，保证所有的汇总任务能搜索到
            self.start_time = parent_action.create_time - self.CONST_MINUTES
            self.end_time = parent_action.end_time + self.CONST_MINUTES if parent_action.end_time else int(time.time())

            if parent_action.is_parent_action:
                if self.alert_ids:
                    self.alert_ids.extend(parent_action.alert_id)
                else:
                    self.alert_ids = parent_action.alert_id
                self.search_parent_action_id = parent_action.raw_id
                self.search_collect_action = True
            else:
                self.raw_id = parent_action.raw_id

        if self.alert_ids:
            # 如果给了 告警ID，则时间范围按 告警起止时间进行查询
            alerts = AlertDocument.mget(self.alert_ids, fields=["create_time", "update_time"])
            now_ts = int(time.time())
            start_time = 0
            end_time = now_ts
            for alert in alerts:
                start_time = max(start_time, alert.create_time)
                if alert.end_time:
                    end_time = min(end_time, alert.update_time)
            self.start_time = max(self.start_time, start_time)
            self.end_time = max(self.end_time, end_time)

    def get_exclude_parent_search_object(self, search_object):
        """
        根据条件判断是否需要排除
        :param search_object:
        :return:
        """
        for condition in self.conditions:
            if condition["key"] == "parent_action_id":
                values = [int(v) for v in condition["value"]]
                if 0 in values:
                    return search_object.exclude("term", signal="collect")
        return search_object.exclude("term", is_parent_action=True)

    def get_search_object(self, start_time: int = None, end_time: int = None):
        start_time = start_time or self.start_time
        end_time = end_time or self.end_time

        search_object = ActionInstanceDocument.search(start_time=self.start_time, end_time=self.end_time)
        search_object = self.get_exclude_parent_search_object(search_object)

        if self.search_parent_action_id and self.search_collect_action:
            search_object = search_object.filter(
                Q("term", parent_action_id=self.search_parent_action_id) | Q("term", signal=ActionSignal.COLLECT)
            )

        if self.raw_id:
            search_object = search_object.filter("term", raw_id=self.raw_id)

        search_object = self.add_biz_condition(search_object)

        if self.username:
            search_object = search_object.filter("term", operator=self.username)

        if start_time and end_time and not self.alert_ids:
            # 没有传告警ID才需要限定时间范围，否则会导致返回的处理记录不完整（有的记录是在告警结束后生成的）
            search_object = search_object.filter(
                (Q("range", end_time={"gte": start_time}) | ~Q("exists", field="end_time"))
                & Q("range", create_time={"lte": end_time})
            )

        if self.status:
            search_object = search_object.filter("terms", status=self.status)
        elif not self.alert_ids and not self.search_parent_action_id:
            # 是否显示“已收敛”，“已屏蔽”等未实际执行动作的记录
            search_object = search_object.filter(
                "terms", status=[ActionDisplayStatus.SUCCESS, ActionDisplayStatus.FAILURE, ActionDisplayStatus.RUNNING]
            )

        if self.alert_ids:
            search_object = search_object.filter("terms", alert_id=self.alert_ids)

        return search_object

    def search(self, show_overview=False, show_aggs=False, show_dsl=False):
        exc = None
        search_object = None
        try:
            search_object = self.get_search_object()
            search_object = self.add_conditions(search_object, self.conditions)
            search_object = self.add_query_string(search_object, self.query_string)
            search_object = self.add_ordering(search_object, self.ordering)
            search_object = self.add_pagination(search_object, self.page, self.page_size)

            if show_overview:
                search_object = self.add_overview(search_object)

            if show_aggs:
                search_object = self.add_aggs(search_object)

            search_result = search_object.params(track_total_hits=True).execute()
        except Exception as e:
            search_result = self.make_empty_response()
            exc = e

        actions = self.handle_hit_list(search_result)

        result = {
            "actions": actions,
            "total": min(search_result.hits.total.value, 10000),
        }

        if show_overview:
            result["overview"] = self.handle_overview(search_result)

        if show_aggs:
            result["aggs"] = self.handle_aggs(search_result)

        if show_dsl and search_object:
            result["dsl"] = search_object.to_dict()

        if exc:
            exc.data = result
            raise exc

        return result

    def add_biz_condition(self, search_object):
        queries = []
        if self.authorized_bizs is not None and self.bk_biz_ids:
            # 进行我有权限的告警过滤
            queries.append(Q("terms", **{"bk_biz_id": self.authorized_bizs}))

        if self.bk_biz_ids == []:
            # 如果不带任何业务信息，表示获取跟自己相关的告警
            queries.append(Q("term", operator=self.request_username))

        if self.unauthorized_bizs and self.request_username:
            queries.append(
                Q(Q("terms", **{"bk_biz_id": self.unauthorized_bizs}) & Q("term", operator=self.request_username))
            )
        if queries:
            return search_object.filter(reduce(operator.or_, queries))
        return search_object

    @classmethod
    def handle_hit_list(cls, hits=None):
        hits = hits or []
        hits = [cls.handle_hit(hit) for hit in hits]
        hits = cls.add_converge_count(hits)
        hits = cls.add_plugin_type_display(hits)
        ActionSignalTranslator().translate_from_dict(hits, "signal", "signal_display")
        return hits

    @classmethod
    def add_plugin_type_display(cls, hits):
        for hit in hits:
            hit["action_plugin_type_display"] = hit.get("action_plugin").get("name", hit["action_plugin_type"])
        return hits

    @classmethod
    def add_converge_count(cls, hits):
        """
        追加处理记录的收敛告警数量
        """
        converge_ids = set()
        for hit in hits:
            if hit.get("is_converge_primary") and hit.get("converge_id"):
                converge_ids.add(hit["converge_id"])

        queryset = ConvergeRelation.objects.filter(
            converge_id__in=list(converge_ids), converge_status=ConvergeStatus.SKIPPED
        )

        converge_alerts = defaultdict(set)
        for converge in queryset:
            converge_alerts[converge.converge_id].update(converge.alerts)

        for hit in hits:
            if hit.get("is_converge_primary") and hit.get("converge_id"):
                hit["converge_count"] = len(converge_alerts.get(hit["converge_id"], []))
            else:
                hit["converge_count"] = 0
        return hits

    @classmethod
    def handle_hit(cls, hit):
        cleaned_data = super().handle_hit(hit)

        if "duration" in cleaned_data:
            # 转换为人类可读形式
            cleaned_data["duration"] = hms_string(cleaned_data["duration"])

        cleaned_data["dimension_string"] = AlertDimensionFormatter.get_dimensions_str(
            cleaned_data.get("dimensions", [])
        )
        cleaned_data["ex_data"] = cleaned_data["ex_data"] or {}
        cleaned_data["status_tips"] = cleaned_data["ex_data"].get("message") or ""

        return cleaned_data

    def parse_condition_item(self, condition: dict) -> Q:
        if condition["key"] == "duration":
            # 对 key 为 stage 进行特殊处理
            return reduce(
                operator.or_,
                [
                    Q("range", duration=self.DurationOption.FILTER[value])
                    for value in condition["value"]
                    if value in self.DurationOption.FILTER
                ],
            )
        return super(ActionQueryHandler, self).parse_condition_item(condition)

    def add_overview(self, search_object):
        # 总览聚合
        search_object.aggs.bucket("status", "terms", field="status")
        return search_object

    def add_aggs(self, search_object):
        # 高级筛选聚合
        search_object.aggs.bucket("action_plugin_type", "terms", field="action_plugin_type", size=10000)
        search_object.aggs.bucket("signal", "terms", field="signal")
        search_object.aggs.bucket("duration", "range", field="duration", ranges=list(self.DurationOption.AGG.values()))
        return search_object

    def handle_overview(self, search_result):
        result = {
            "id": "action",
            "name": _("处理记录"),
            "count": search_result.hits.total.value,
            "children": [],
        }

        if search_result.aggs:
            bucket_dict = {bucket.key: bucket.doc_count for bucket in search_result.aggs.status.buckets}
        else:
            bucket_dict = {}

        overview_status = self.status or [ActionDisplayStatus.SUCCESS, ActionDisplayStatus.FAILURE]

        for status in overview_status:
            result["children"].append(
                {
                    "id": status,
                    "name": ACTION_DISPLAY_STATUS_DICT[status],
                    "count": bucket_dict.get(status, 0),
                }
            )

        return result

    @classmethod
    def handle_aggs(cls, search_result):
        fields = [
            (
                "action_plugin_type",
                _("套餐类型"),
                [(plugin.plugin_key, plugin.name) for plugin in ActionPlugin.objects.all()],
            ),
            (
                "signal",
                _("触发信号"),
                [
                    item
                    for item in list(ActionSignal.ACTION_SIGNAL_DICT.items())
                    if item[0] not in [ActionSignal.EXECUTE]
                ],
            ),
            ("duration", _("处理时长"), list(cls.DurationOption.DISPLAY.items())),
        ]

        results = []

        for field_name, display_name, choices in fields:
            if search_result.aggs:
                bucket_dict = {bucket.key: bucket.doc_count for bucket in search_result.aggs[field_name].buckets}
            else:
                bucket_dict = {}

            result = {
                "id": field_name,
                "name": display_name,
                "count": sum(bucket_dict.values()),
                "children": [
                    {"id": key, "name": display, "count": bucket_dict.get(key, 0)} for key, display in choices
                ],
            }
            results.append(result)
        return results

    def date_histogram(self, interval: str = "auto"):
        status_choices = {
            ActionDisplayStatus.SUCCESS: _lazy("成功"),  # 处理成功
            ActionDisplayStatus.FAILURE: _lazy("失败"),  # 处理失败
        }

        interval = self.calculate_agg_interval(self.start_time, self.end_time, interval)

        # 查询时间对齐
        start_time = self.start_time // interval * interval
        end_time = self.end_time // interval * interval + interval

        search_object = self.get_search_object(start_time=start_time, end_time=end_time)
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object.aggs.bucket(
            "display_status", "filter", {"terms": {"status": list(status_choices.keys())}}
        ).bucket("status", "terms", field="status").bucket(
            "time", "date_histogram", field="end_time", fixed_interval=f"{interval}s"
        )
        search_result = search_object[:0].execute()

        all_series = defaultdict(dict)
        for ts in range(start_time, end_time, interval):
            for status in status_choices:
                all_series[status][ts * 1000] = 0

        if search_result.aggs:
            for status_bucket in search_result.aggs.display_status.status.buckets:
                for time_bucket in status_bucket.time.buckets:
                    all_series[status_bucket.key][int(time_bucket.key_as_string) * 1000] = time_bucket.doc_count

        result_data = {
            "series": [
                {"data": list(series.items()), "name": status, "display_name": status_choices[status]}
                for status, series in all_series.items()
            ],
            "unit": "",
        }

        return result_data

    def top_n(self, fields: List, size=10, translators: Dict[str, AbstractTranslator] = None, char_add_quotes=True):
        translators = {
            "signal": ActionSignalTranslator(),
            "action_plugin_type": ActionPluginTypeTranslator(),
            "bk_biz_id": BizTranslator(),
        }
        return super(ActionQueryHandler, self).top_n(fields, size, translators, char_add_quotes)

"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django_elasticsearch_dsl.search import Search
from elasticsearch_dsl import Q
from elasticsearch_dsl.response import Response
from elasticsearch_dsl.response.aggs import BucketData
from elasticsearch_dsl.utils import AttrList

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.incident import IncidentDocument
from bkmonitor.utils.time_tools import hms_string
from constants.incident import IncidentLevel, IncidentStatus,INCIDENT_STATUS_DICT
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.base import (
    BaseBizQueryHandler,
    BaseQueryTransformer,
    QueryField,
)
from fta_web.alert.handlers.translator import BizTranslator


class IncidentQueryTransformer(BaseQueryTransformer):
    NESTED_KV_FIELDS = {"tags": "tags"}
    VALUE_TRANSLATE_FIELDS = {
        "level": IncidentLevel.get_enum_translate_list(),
        "status": IncidentStatus.get_enum_translate_list(),
    }
    """
    incident_id = field.Keyword(required=True)
    incident_name = field.Text()  # 故障名称
    incident_reason = field.Text()  # 故障原因
    status = field.Keyword()  # 故障状态
    level = field.Keyword()  # 故障级别
    assignees = field.Keyword(multi=True)  # 故障负责人
    handlers = field.Keyword(multi=True)  # 故障处理人
    labels = field.Keyword(multi=True)  # 标签

    # 故障创建时间(服务器时间)
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)

    # 故障开始时间
    begin_time = Date(format=BaseDocument.DATE_FORMAT)
    # 故障结束时间
    end_time = Date(format=BaseDocument.DATE_FORMAT)
    # 故障持续的最新时间
    latest_time = Date(format=BaseDocument.DATE_FORMAT)

    # 故障维度信息
    dimensions = field.Object(enabled=False)
    # 故障额外信息，用于存放其他内容
    extra_info = field.Object(enabled=False)
    """
    query_fields = [
        QueryField("id", _lazy("故障ID")),
        QueryField("incident_id", _lazy("故障主键")),
        QueryField("incident_name", _lazy("故障名称")),
        QueryField("incident_reason", _lazy("故障原因")),
        QueryField("bk_biz_id", _lazy("业务ID")),
        QueryField("status", _lazy("故障状态")),
        QueryField("status_order", _lazy("故障状态排序字段")),
        QueryField("level", _lazy("故障级别")),
        QueryField("assignees", _lazy("负责人")),
        QueryField("handlers", _lazy("处理人")),
        QueryField("labels", _lazy("标签")),
        QueryField("create_time", _lazy("故障检出时间")),
        QueryField("update_time", _lazy("故障更新时间")),
        QueryField("begin_time", _lazy("故障开始时间")),
        QueryField("end_time", _lazy("故障结束时间")),
        QueryField("snapshot", _lazy("故障图谱快照")),
        QueryField("alert_count", _lazy("故障告警数")),
    ]
    doc_cls = IncidentDocument


class IncidentQueryHandler(BaseBizQueryHandler):
    """
    故障查询
    """

    query_transformer = IncidentQueryTransformer

    # “我的故障” 状态名称
    MINE_STATUS_NAME = "MY_INCIDENT"
    MY_ASSIGNEE_STATUS_NAME = "MY_ASSIGNEE_INCIDENT"
    MY_HANDLER_STATUS_NAME = "MY_HANDLER_INCIDENT"

    def __init__(self, bk_biz_ids: list[int] = None, username: str = "", status: list[str] = None, **kwargs):
        super().__init__(bk_biz_ids, username, **kwargs)
        self.status = [status] if isinstance(status, str) else status
        if not self.ordering:
            # 默认排序
            self.ordering = ["status_order", "-create_time"]

    def get_search_object(self, start_time: int = None, end_time: int = None):
        """
        获取查询对象
        """
        start_time = start_time or self.start_time
        end_time = end_time or self.end_time

        search_object = IncidentDocument.search(start_time=self.start_time, end_time=self.end_time)

        if start_time and end_time:
            search_object = search_object.filter(
                (Q("range", end_time={"gte": start_time}) | ~Q("exists", field="end_time"))
                & (Q("range", begin_time={"lte": end_time}) | Q("range", create_time={"lte": end_time}))
                & (Q("range", begin_time={"gte": start_time}) | Q("range", create_time={"gte": start_time}))
            )

        search_object = self.add_biz_condition(search_object)

        if self.status:
            queries = []
            for status in self.status:
                if status == self.MINE_STATUS_NAME:
                    queries.append(
                        Q("term", assignees=self.request_username) | Q("term", appointee=self.request_username)
                    )
                if status == self.MY_ASSIGNEE_STATUS_NAME:
                    queries.append(Q("term", assignees=self.request_username))
                if status == self.MY_HANDLER_STATUS_NAME:
                    queries.append(Q("term", handlers=self.request_username))
                else:
                    queries.append(Q("term", status=status))

            if queries:
                search_object = search_object.filter(reduce(operator.or_, queries))

        return search_object

    def search(self, show_overview: bool = False, show_aggs: bool = False) -> dict:
        search_object = self.get_search_object()
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)
        search_object = self.add_ordering(search_object)
        search_object = self.add_pagination(search_object)

        if show_overview:
            search_object = self.add_overview(search_object)

        if show_aggs:
            search_object = self.add_aggs(search_object)

        search_result = search_object.execute()
        incidents = self.handle_hit_list(search_result.hits)
        for incident in incidents:
            incident["bk_biz_id"] = int(incident["bk_biz_id"])
        BizTranslator().translate_from_dict(incidents, "bk_biz_id", "bk_biz_name")

        result = {
            "total": min(search_result.hits.total.value, 10000),
            "incidents": incidents,
        }

        if show_overview:
            result["overview"] = self.handle_overview(search_result)

        if show_aggs:
            result["aggs"] = self.handle_aggs(search_result)

        return result

    def add_biz_condition(self, search_object: Search) -> Search:
        queries = []
        if self.authorized_bizs is not None and self.bk_biz_ids:
            # 进行我有权限的告警过滤
            queries.append(Q("terms", **{"bk_biz_id": self.authorized_bizs}))

        user_condition = Q(
            Q("term", assignee=self.request_username)
            | Q("term", appointee=self.request_username)
            | Q("term", supervisor=self.request_username)
        )
        if self.bk_biz_ids == []:
            # 如果不带任何业务信息，表示获取跟自己相关的告警
            queries.append(user_condition)

        if self.unauthorized_bizs and self.request_username:
            queries.append(Q(Q("terms", **{"bk_biz_id": self.unauthorized_bizs}) & user_condition))

        if queries:
            return search_object.filter(reduce(operator.or_, queries))
        return search_object

    @classmethod
    def handle_hit_list(cls, hits: AttrList = None) -> list[dict]:
        hits = hits or []
        incidents = [cls.handle_hit(hit) for hit in hits]
        return incidents

    @classmethod
    def handle_hit(cls, hit) -> dict:
        incident = super().handle_hit(hit)
        incident["status_alias"] = IncidentStatus(incident["status"].lower()).alias
        incident["level_alias"] = IncidentLevel(incident["level"]).alias
        if incident["end_time"]:
            incident["duration"] = hms_string(incident["end_time"] - incident["begin_time"])
        else:
            incident["duration"] = hms_string(int(time.time()) - incident["begin_time"])
        return incident

    def _get_buckets(
            self,
            result: dict[tuple[tuple[str, any]], any],
            dimensions: dict[str, any],
            aggregation: BucketData,
            agg_fields: list[str],
    ):
        """
        获取聚合结果
        """
        if agg_fields:
            field = agg_fields[0]
            if field.startswith("tags."):
                buckets = aggregation[field].key.value.buckets
            else:
                buckets = aggregation[field].buckets
            for bucket in buckets:
                dimensions[field] = bucket.key
                self._get_buckets(result, dimensions, bucket, agg_fields[1:])
        else:
            dimension_tuple: tuple = tuple(dimensions.items())
            result[dimension_tuple] = aggregation

    def date_histogram(self, interval: str = "auto", group_by: list[str] | None = None, bucket_size: int = 100) -> dict:
        new_interval: int = self.calculate_agg_interval(self.start_time, self.end_time, interval)
        # 默认按status聚合
        if group_by is None:
            group_by = ["status"]

        # status 会被单独处理
        status_group = False
        if "status" in group_by:
            status_group = True
            group_by = [field for field in group_by if field != "status"]

        # TODO: tags开头的字段是否能够进行嵌套聚合？

        tags_field_count = 0
        for field in group_by:
            if field.startswith("tags."):
                tags_field_count += 1
        if tags_field_count > 1:
            raise ValueError("can not group by more than one tags field")

        # 将tags开头的字段放在后面
        group_by = sorted(group_by, key=lambda x: x.startswith("tags."))

        # 查询时间对齐
        start_time = self.start_time // new_interval * new_interval
        end_time = self.end_time // new_interval * new_interval + new_interval
        now_time = int(time.time()) // new_interval * new_interval + new_interval
        search_object = self.get_search_object(start_time=start_time, end_time=end_time)
        search_object = self.add_conditions(search_object)
        search_object = self.add_query_string(search_object)

        # 已经恢复或关闭的故障，按end_time聚合
        ended_object = search_object.aggs.bucket(
            "end_time", "filter", {"range": {"end_time": {"lte": end_time}}}
        ).bucket("end_incident", "filter", {"terms": {"status": [
            IncidentStatus.RECOVERING.value, IncidentStatus.RECOVERED.value, IncidentStatus.CLOSED.value,
            IncidentStatus.MERGED.value]}})
        # 查询时间范围内产生的故障，按begin_time聚合
        new_anomaly_object = search_object.aggs.bucket(
            "begin_time", "filter", {"range": {"begin_time": {"gte": start_time, "lte": end_time}}}
        )
        # 开始时间在查询时间范围之前的故障总数
        old_anomaly_object = search_object.aggs.bucket(
            "init_incident", "filter", {"range": {"begin_time": {"lt": start_time}}}
        )
        # 时间聚合
        ended_object = ended_object.bucket(
            "time", "date_histogram", field="end_time", fixed_interval=f"{new_interval}s"
        ).bucket("status", "terms", field="status")
        new_anomaly_object = new_anomaly_object.bucket(
            "time", "date_histogram", field="begin_time", fixed_interval=f"{new_interval}s"
        )

        # 维度聚合
        for field in group_by:
            ended_object = self.add_agg_bucket(ended_object, field, size=bucket_size)
            new_anomaly_object = self.add_agg_bucket(new_anomaly_object, field, size=bucket_size)
            old_anomaly_object = self.add_agg_bucket(old_anomaly_object, field, size=bucket_size)

        # 查询
        search_result = search_object[:0].execute()
        result = defaultdict(
            lambda: {
                status: {ts * 1000: 0 for ts in range(start_time, min(now_time, end_time), new_interval)}
                for status in INCIDENT_STATUS_DICT
            }
        )

        if hasattr(search_result.aggs, "begin_time"):
            for time_bucket in search_result.aggs.begin_time.time.buckets:
                begin_time_result = {}
                self._get_buckets(begin_time_result, {}, time_bucket, group_by)

                key = int(time_bucket.key_as_string) * 1000
                for dimension_tuple, bucket in begin_time_result.items():
                    if key in result[dimension_tuple][IncidentStatus.ABNORMAL.value]:
                        result[dimension_tuple][IncidentStatus.ABNORMAL.value][key] = bucket.doc_count

        if hasattr(search_result.aggs, "end_time") and hasattr(search_result.aggs.end_time, "end_incident"):
            for time_bucket in search_result.aggs.end_time.end_incident.time.buckets:
                for status_bucket in time_bucket.status.buckets:
                    end_time_result = {}
                    self._get_buckets(end_time_result, {}, status_bucket, group_by)

                    key = int(time_bucket.key_as_string) * 1000
                    for dimension_tuple, bucket in end_time_result.items():
                        if key in result[dimension_tuple][status_bucket.key]:
                            result[dimension_tuple][status_bucket.key][key] = bucket.doc_count

        init_incident_result = {}
        if hasattr(search_result.aggs, "init_incident"):
            self._get_buckets(init_incident_result, {}, search_result.aggs.init_incident, group_by)
        # 获取全部维度
        all_dimensions = set(result.keys()) | set(init_incident_result.keys())
        # 按维度分别统计事件数量
        for dimension_tuple in all_dimensions:
            all_series = result[dimension_tuple]

            if dimension_tuple in init_incident_result:
                current_abnormal_count = init_incident_result[dimension_tuple].doc_count
            else:
                current_abnormal_count = 0

            for ts in all_series[IncidentStatus.ABNORMAL.value]:
                # 异常是一个持续的状态，会随着时间的推移不断叠加
                # 一旦有恢复或关闭\已解决\已合并的告警，异常告警将会相应减少
                all_series[IncidentStatus.ABNORMAL.value][ts] = (
                        current_abnormal_count
                        + all_series[IncidentStatus.ABNORMAL.value][ts]
                        - all_series[IncidentStatus.CLOSED.value][ts]
                        - all_series[IncidentStatus.RECOVERED.value][ts]
                        - all_series[IncidentStatus.RECOVERING.value][ts]
                        - all_series[IncidentStatus.MERGED.value][ts]
                )
                current_abnormal_count = all_series[IncidentStatus.ABNORMAL.value][ts]

            # 如果不按status聚合，需要将status聚合的结果合并到一起
            if not status_group:
                for ts in all_series[IncidentStatus.ABNORMAL.value]:
                    all_series[IncidentStatus.ABNORMAL.value][ts] += (
                            all_series[IncidentStatus.CLOSED.value][ts] + all_series[IncidentStatus.RECOVERED.value][ts]
                    )
                all_series.pop(IncidentStatus.CLOSED.value, None)
                all_series.pop(IncidentStatus.RECOVERED.value, None)
                all_series.pop(IncidentStatus.RECOVERING.value, None)
                all_series.pop(IncidentStatus.MERGED.value, None)
        return result

    def add_overview(self, search_object: Search) -> Search:
        """补充检索全览的检索结构.

        :param search_object: 检索结构
        :return: 包含全览的检索结构
        """
        search_object.aggs.bucket("status", "terms", field="status")
        search_object.aggs.bucket("assignees", "filter", {"term": {"assignees": self.request_username}})
        search_object.aggs.bucket("handlers", "filter", {"term": {"handlers": self.request_username}})
        return search_object

    def handle_overview(self, search_result: Response) -> dict:
        """处理返回内容中的检索全览部分.

        :param search_result: 检索结果
        :return: 故障全览内容
        """
        if search_result.aggs:
            status_dict = {bucket.key: bucket.doc_count for bucket in search_result.aggs.status.buckets}
        else:
            status_dict = {}
        return {
            "id": "incident",
            "name": _("故障"),
            "count": search_result.hits.total.value,
            "children": [
                {
                    "id": self.MY_ASSIGNEE_STATUS_NAME,
                    "name": _("我负责的"),
                    "count": search_result.aggs.assignees.doc_count if search_result.aggs else 0,
                },
                {
                    "id": self.MY_HANDLER_STATUS_NAME,
                    "name": _("我处理的"),
                    "count": search_result.aggs.handlers.doc_count if search_result.aggs else 0,
                },
                *[
                    {
                        "id": status,
                        "name": alias,
                        "count": status_dict.get(status, 0),
                    }
                    for status, alias in IncidentStatus.get_enum_translate_list()
                ],
            ],
        }

    def add_aggs(self, search_object: Search) -> Search:
        """补充检索聚合统计的检索结构.

        :param search_object: 检索结构
        :return: 包含聚合统计的检索结构
        """
        search_object.aggs.bucket("level", "terms", field="level")
        return search_object

    def handle_aggs(self, search_result: Response) -> list[dict]:
        """处理返回内容中的检索聚合统计部分.

        :param search_result: 检索结果
        :return: 故障聚合统计内容
        """
        agg_result = [
            self.handle_aggs_level(search_result),
        ]

        return agg_result

    def handle_aggs_level(self, search_result: Response) -> dict:
        if search_result.aggs:
            level_dict = {bucket.key: bucket.doc_count for bucket in search_result.aggs.level.buckets}
        else:
            level_dict = {}

        result = {
            "id": "level",
            "name": _("级别"),
            "count": sum(level_dict.values()),
            "children": [
                {"id": level, "name": str(alias), "count": level_dict.get(level, 0)}
                for level, alias in IncidentLevel.get_enum_translate_list()
            ],
        }
        return result

    def top_n(self, fields: list, size=10, translators: dict = None) -> dict:
        return super().top_n(fields, size, translators)


class IncidentAlertQueryHandler(AlertQueryHandler):
    @classmethod
    def handle_hit(cls, hit):
        return cls.clean_document(AlertDocument(**hit.to_dict()))

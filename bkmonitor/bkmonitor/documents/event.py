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

from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import field

from bkmonitor.documents.base import BaseDocument, Date
from core.errors.alert import EventNotFoundError


@registry.register_document
class EventDocument(BaseDocument):

    # time 字段在时间偏移量范围内，使用 time 字段作为索引时间
    INDEX_TIME_OFFSET = 24 * 60 * 60

    # 事件标识
    id = field.Keyword(required=True)
    event_id = field.Keyword(required=True)
    plugin_id = field.Keyword(required=True)
    strategy_id = field.Keyword()

    # 事件内容
    alert_name = field.Text(required=True, fields={"raw": field.Keyword()})
    description = field.Text()
    severity = field.Integer()
    tags = field.Nested(
        properties={
            "key": field.Keyword(),
            "value": field.Text(required=True, fields={"raw": field.Keyword(ignore_above=256)}),
        }
    )
    target_type = field.Keyword()
    target = field.Keyword()
    assignee = field.Keyword()
    status = field.Keyword()

    # 事件分类
    metric = field.Keyword(multi=True)
    category = field.Keyword()
    data_type = field.Keyword()

    # 控制字段
    dedupe_keys = field.Keyword(multi=True)
    dedupe_md5 = field.Keyword()

    # 时间信息
    # 事件产生时间
    time = Date(required=True, format=BaseDocument.DATE_FORMAT)
    # 异常时间
    anomaly_time = Date(required=False, format=BaseDocument.DATE_FORMAT)
    # 数据接入时间
    bk_ingest_time = Date(format=BaseDocument.DATE_FORMAT)
    # 清洗时间
    bk_clean_time = Date(format=BaseDocument.DATE_FORMAT)
    # 事件创建时间(服务器时间)
    create_time = Date(format=BaseDocument.DATE_FORMAT)

    # 目标信息
    bk_biz_id = field.Keyword()
    ip = field.Keyword()
    ipv6 = field.Keyword()
    bk_cloud_id = field.Keyword()
    bk_service_instance_id = field.Keyword()
    bk_host_id = field.Keyword()
    bk_topo_node = field.Keyword(multi=True)

    # 事件的更多信息
    extra_info = field.Object(enabled=False)

    def get_index_time(self):
        if self.create_time and self.time and abs(self.create_time - self.time) > self.INDEX_TIME_OFFSET:
            # time 字段在时间偏移量范围内，使用 time 字段作为索引时间，否则使用 create_time
            return self.create_time
        return self.time

    @classmethod
    def get_by_event_id(cls, event_id) -> "EventDocument":
        hits = cls.search(all_indices=True).filter("term", event_id=event_id).sort(*["-create_time"]).execute().hits
        if not hits:
            raise EventNotFoundError({"event_id": event_id})
        return cls(**hits[0].to_dict())

    @classmethod
    def get_by_metric_id_and_target(cls, metric_id, target, start_time=None):

        search_object = cls.search(all_indices=True)
        if start_time:
            search_object = search_object.filter("range", create_time={"gte": start_time})

        hits = (
            search_object.filter("term", target=target)
            .filter("terms", metric=metric_id)
            .sort(*["-create_time"])
            .execute()
            .hits
        )
        if not hits:
            raise EventNotFoundError({"event_id": "{}_{}".format(metric_id, target)})
        return cls(**hits[0].to_dict())

    class Index:
        name = "bkfta_event"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

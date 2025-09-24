# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
import uuid
from typing import List

from django_elasticsearch_dsl.registries import registry
from elasticsearch_dsl import InnerDoc, Search, field

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BaseDocument, Date
from constants.incident import IncidentStatus
from core.drf_resource import api
from core.errors.incident import IncidentNotFoundError

logger = logging.getLogger("action")
MAX_INCIDENT_CONTENTS_SIZE = 10000
MAX_INCIDENT_ALERT_SIZE = 10000


class IncidentBaseDocument(BaseDocument):
    def get_index_time(self):
        return self.parse_timestamp_by_id(self.id)

    @classmethod
    def parse_timestamp_by_id(cls, id: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return int(str(id)[:10])

    @classmethod
    def parse_incident_id_by_id(cls, id: str) -> int:
        """
        从 UUID 反解时间戳
        """
        return int(str(id)[10:])

    def to_dict(self, include_meta: bool = False, skip_empty: bool = True):
        """
        补充值没有值的字段
        """
        result = super().to_dict(include_meta=include_meta, skip_empty=skip_empty)
        for name, field_type in self._fields.items():
            if name not in result:
                if isinstance(field_type, field.Keyword) and field_type._multi:
                    result[name] = []
                elif isinstance(field_type, field.Object):
                    result[name] = {}
                else:
                    result[name] = None
        return result


class IncidentItemsMixin:
    @classmethod
    def list_by_incident_id(
        cls,
        incident_id: int,
        start_time: int = None,
        end_time: int = None,
        limit: int = MAX_INCIDENT_CONTENTS_SIZE,
        order_by: str = "create_time",
    ) -> List:
        """根据故障ID获取故障关联的内容(故障根因结果快照、故障操作记录、故障通知记录)

        :param incident_id: 故障ID
        :return: 故障关联的内容
        """
        if start_time or end_time:
            search = cls.search(start_time=start_time, end_time=end_time)
        else:
            search = cls.search(all_indices=True)
        search = search.filter("term", incident_id=incident_id)
        search = search.sort(order_by).params(size=limit or MAX_INCIDENT_CONTENTS_SIZE)
        hits = search.execute().hits
        return [cls(**hit.to_dict()) for hit in hits]


@registry.register_document
class IncidentSnapshotDocument(IncidentItemsMixin, IncidentBaseDocument):
    id = field.Keyword(required=True)
    incident_id = field.Keyword()  # 故障ID
    bk_biz_ids = field.Keyword(multi=True)  # 故障影响的业务列表
    status = field.Keyword()  # 故障当前快照状态
    alerts = field.Keyword(multi=True)  # 故障关联的告警
    events = field.Keyword(multi=True)  # 故障关联的事件

    # 故障快照创建时间(服务器时间)
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)

    content = field.Object()  # 故障内容
    fpp_snapshot_id = field.Keyword()  # 故障当前快照的图谱快照ID

    # 故障额外信息，用于存放其他内容
    extra_info = field.Object(enabled=False)

    class Index:
        name = "bkmonitor_aiops_incident_snapshot"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    def __init__(self, *args, **kwargs):
        super(IncidentSnapshotDocument, self).__init__(*args, **kwargs)
        if self.id is None:
            self.id = f"{self.create_time}{uuid.uuid4().hex[:8]}"


@registry.register_document
class IncidentDocument(IncidentBaseDocument):
    REINDEX_ENABLED = True
    REINDEX_QUERY = Search().filter("term", status=IncidentStatus.ABNORMAL.value).to_dict()

    id = field.Keyword(required=True)
    incident_id = field.Keyword(required=True)
    incident_name = field.Text()  # 故障名称
    incident_reason = field.Text()  # 故障原因
    status = field.Keyword()  # 故障状态
    status_order = field.Keyword()  # 故障状态排序字段
    level = field.Keyword()  # 故障级别
    bk_biz_id = field.Keyword()  # 故障业务ID
    assignees = field.Keyword(multi=True)  # 故障负责人
    handlers = field.Keyword(multi=True)  # 故障处理人
    labels = field.Keyword(multi=True)  # 标签

    # 最新故障根因定位结果
    snapshot = field.Object(doc_class=type("IncidentSnapshotInnerDoc", (IncidentSnapshotDocument, InnerDoc), {}))

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
    dimensions = field.Object(enabled=False, multi=True)
    # 故障额外信息，用于存放其他内容
    extra_info = field.Object(enabled=False)
    # 反馈根因的信息
    feedback = field.Object(enabled=False)

    # 检索或者排序需要的字段
    alert_count = field.Long()

    class Index:
        name = "bkmonitor_aiops_incident_info"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    def __init__(self, *args, **kwargs):
        super(IncidentDocument, self).__init__(*args, **kwargs)
        if self.id is None:
            self.id = f"{self.create_time}{self.incident_id}"

    def generate_assignees(self, snapshot) -> None:
        """生成故障负责人

        :param snapshot: 故障分析结果图谱快照信息
        """
        assignees = set()
        for incident_alert in snapshot.alert_entity_mapping.values():
            if incident_alert.entity.is_root:
                alert_doc = AlertDocument.get(incident_alert.id)
                assignees = assignees | set(alert_doc.assignee)

        self.assignees = list(assignees)

    def generate_handlers(self, snapshot) -> None:
        """生成故障处理人

        :param snapshot: 故障分析结果图谱快照信息
        """
        handlers = set()
        for incident_alert in snapshot.alert_entity_mapping.values():
            alert_doc = AlertDocument.get(incident_alert.id)
            handlers = handlers | set(alert_doc.assignee)

        self.handlers = list(handlers)

    @classmethod
    def get(cls, id: str, fetch_remote: bool = True) -> "IncidentDocument":
        """
        获取单条故障
        """
        try:
            ts = cls.parse_timestamp_by_id(id)
        except Exception:
            raise ValueError("invalid uuid: {}".format(id))
        hits = cls.search(start_time=ts, end_time=ts).filter("term", id=id).execute().hits
        if not hits:
            raise IncidentNotFoundError({"id": id})

        incident_document_info = hits[0].to_dict()
        if fetch_remote:
            try:
                incident_id = cls.parse_incident_id_by_id(id)
                incident_info = api.bkdata.get_incident_detail(incident_id=incident_id)
                if isinstance(incident_info["dimensions"], str):
                    incident_info["dimensions"] = json.loads(incident_info["dimensions"])
                if isinstance(incident_info["feedback"], str):
                    incident_info["feedback"] = json.loads(incident_info["feedback"])
                incident_document_info.update(incident_info)
            except Exception as e:
                logger.error(f"Can not get incident info from bkbase api: {str(e)}")

        return cls(**incident_document_info)

    @classmethod
    def mget(cls, ids: List[int], fields: List = None) -> List["IncidentDocument"]:
        """
        获取多条故障
        """
        if not ids:
            return []
        # 根据ID的时间区间确定需要查询的索引范围
        start_time = None
        end_time = None
        for id in ids:
            try:
                ts = cls.parse_timestamp_by_id(id)
            except Exception:  # NOCC:broad-except(设计如此:)
                continue
            if not start_time:
                start_time = ts
            else:
                start_time = min(start_time, ts)
            if not end_time:
                end_time = ts
            else:
                end_time = max(end_time, ts)

        search = cls.search(start_time=start_time, end_time=end_time).filter("terms", id=ids)

        if fields:
            search = search.source(fields=fields)

        return [cls(**hit.to_dict()) for hit in search.params(size=5000).scan()]


@registry.register_document
class IncidentOperationDocument(IncidentItemsMixin, IncidentBaseDocument):
    id = field.Keyword(required=True)
    incident_id = field.Keyword()  # 故障ID
    operator = field.Keyword()  # 故障操作人
    operation_type = field.Keyword()  # 故障操作类型

    # 故障流水创建时间和更新时间
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)

    # 故障操作额外信息，用于存放其他内容，每种操作类型内容不一样
    extra_info = field.Object(enabled=False)

    class Index:
        name = "bkmonitor_aiops_incident_operation"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    def __init__(self, *args, **kwargs):
        super(IncidentOperationDocument, self).__init__(*args, **kwargs)
        if self.id is None:
            self.id = f"{self.create_time}{uuid.uuid4().hex[:8]}"


@registry.register_document
class IncidentNoticeDocument(IncidentItemsMixin, IncidentBaseDocument):
    id = field.Keyword(required=True)
    incident_id = field.Keyword()  # 故障ID
    notice_id = field.Keyword()  # 通知ID，一个故障的一次通知的统一ID，包含要通知的所有人及多种通知方式

    notify_way = field.Keyword()  # 通知方式
    receiver = field.Keyword()  # 接收人

    # 故障通知流水创建时间和更新时间
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    update_time = Date(format=BaseDocument.DATE_FORMAT)

    # 故障通知流水额外信息，用于存放失败时的异常信息
    extra_info = field.Object(enabled=False)

    class Index:
        name = "bkmonitor_aiops_incident_notice"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    def __init__(self, *args, **kwargs):
        super(IncidentNoticeDocument, self).__init__(*args, **kwargs)
        if self.id is None:
            self.id = f"{self.create_time}{uuid.uuid4().hex[:8]}"

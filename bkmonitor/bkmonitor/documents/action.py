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
import logging
import time
from typing import List

from django_elasticsearch_dsl.registries import registry
from elasticsearch.helpers import BulkIndexError
from elasticsearch_dsl import Search, field

from bkmonitor.documents.base import BaseDocument, Date
from constants.action import ActionDisplayStatus, ActionPluginType

logger = logging.getLogger("action")


@registry.register_document
class ActionInstanceDocument(BaseDocument):
    REINDEX_ENABLED = True
    REINDEX_QUERY = Search().filter("term", status=ActionDisplayStatus.RUNNING).to_dict()

    class OpType:
        # 执行动作
        ACTION = "ACTION"

    alert_id = field.Keyword(multi=True)
    # 任务创建时间(服务器时间)
    create_time = Date(format=BaseDocument.DATE_FORMAT)
    op_type = field.Keyword()

    id = field.Keyword(required=True)
    raw_id = field.Long()
    status = field.Keyword()
    failure_type = field.Keyword()
    ex_data = field.Object(enabled=False)

    # 策略内容
    strategy_id = field.Keyword()
    strategy_name = field.Text(fields={"raw": field.Keyword()})

    # 关联告警信息
    signal = field.Keyword()
    alert_level = field.Keyword()
    operator = field.Keyword(multi=True)
    inputs = field.Object(enabled=False)
    outputs = field.Object(enabled=False)
    execute_times = field.Long()
    content = field.Object(enabled=False)

    # 告警关联内容
    action_plugin_type = field.Keyword()
    action_plugin = field.Object(enabled=False)
    action_name = field.Text(fields={"raw": field.Keyword()})
    action_config_id = field.Keyword()
    action_config = field.Object(enabled=False)

    # 任务需要拆分的，需要将子任务添加到DB中，当存在子任务的时候，父任务不做任务处理，子任务都完成的时候，父任务也完成
    is_parent_action = field.Boolean()  # 存在子任务
    parent_action_id = field.Keyword()  # 存在父任务
    related_action_ids = field.Keyword(multi=True)

    update_time = Date(format=BaseDocument.DATE_FORMAT)

    # 处理结束时间
    end_time = Date(format=BaseDocument.DATE_FORMAT)
    duration = field.Long()

    # 收敛参数
    converge_id = field.Keyword()
    is_converge_primary = field.Boolean()

    # target相关内容
    operate_target_string = field.Keyword()
    dimensions = field.Object(enabled=False, multi=True)
    bk_target_display = field.Keyword()
    bk_biz_id = field.Keyword()
    bk_biz_name = field.Keyword()
    bk_set_ids = field.Keyword(multi=True)
    bk_set_names = field.Keyword()
    bk_module_ids = field.Keyword(multi=True)
    bk_module_names = field.Keyword()

    class Index:
        name = "bkfta_action"
        settings = {"number_of_shards": 3, "number_of_replicas": 1, "refresh_interval": "1s"}

    def get_index_time(self):
        return self.create_time

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
    def get(cls, id) -> "ActionInstanceDocument":
        """
        获取单条处理记录
        """
        try:
            ts = cls.parse_timestamp_by_id(id)
        except Exception:
            raise ValueError("invalid action_id: {}".format(id))

        hits = cls.search(start_time=ts, end_time=ts).filter("term", id=id).execute().hits
        if not hits:
            return None
        return cls(**hits[0].to_dict())

    @classmethod
    def mget(cls, ids, fields=None) -> List["ActionInstanceDocument"]:
        """
        获取多条处理记录
        """
        # 根据ID的时间区间确定需要查询的索引范围

        # 根据ID的时间区间确定需要查询的索引范围
        search = cls.compile_search(ids).filter("terms", id=ids)
        if fields:
            search = search.source(fields=fields)
        hits = search.execute().hits

        return [cls(**hit.to_dict()) for hit in hits]

    @classmethod
    def compile_search(cls, ids, start_time=None, end_time=None):
        for search_id in ids:
            try:
                # 一样的规则，所以复用id的解析
                ts = ActionInstanceDocument.parse_timestamp_by_id(search_id)
            except Exception:
                continue
            start_time = min(start_time, ts) if start_time else ts
            end_time = max(end_time, ts) if end_time else ts
        return cls.search(start_time=start_time, end_time=end_time)

    @classmethod
    def mget_by_alert(
        cls, alert_ids, fields=None, exclude=None, include=None, ordering=None
    ) -> List["ActionInstanceDocument"]:
        search = cls.compile_search(alert_ids, end_time=int(time.time())).filter("terms", alert_id=alert_ids)
        if exclude:
            for key, value in exclude.items():
                search = search.exclude("term", **{key: value})
        if include:
            for key, value in include.items():
                search = search.filter("term", **{key: value})
        if fields:
            search = search.source(fields)
        ordering = ordering or ["-create_time"]
        search = search.sort(*ordering)
        hits = search.execute().hits
        return [cls(**hit.to_dict()) for hit in hits]

    @classmethod
    def bulk_create_or_update(cls, documents):
        all_ids = [doc.id for doc in documents]
        existed_ids = [hit["id"] for hit in cls.mget(ids=all_ids)]
        actions = []

        for doc in documents:
            actions.append(doc.prepare_action("index"))
        try:
            cls().parallel_bulk(actions=actions)
            logger.info(
                "update action document,total: (%s), updated: (%s), created (%s)",
                len(all_ids),
                len(existed_ids),
                len(all_ids) - len(existed_ids),
            )
        except BulkIndexError as e:

            error_uuids = []
            for err in e.errors:
                # 记录保存失败的事件ID
                error_uuids.add(str(err["index"]["_id"]))
            logger.error("update action document error: %s, error_uuids:", e.errors, ",".join(error_uuids))

    @property
    def plugin_name(self):
        """插件名称"""
        return self.action_plugin["name"]

    @property
    def plugin_type_name(self):
        """插件类型名称"""
        return ActionPluginType.PLUGIN_TYPE_DICT.get(self.action_plugin["plugin_type"], "")

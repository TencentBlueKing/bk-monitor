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
from typing import Optional

from django.conf import settings
from django.db import models
from django.db.transaction import atomic
from django.utils.translation import ugettext as _
from elasticsearch import Elasticsearch

from bkmonitor.utils.db.fields import JsonField
from metadata import config
from metadata.models.result_table import ResultTableField, ResultTableOption
from metadata.models.storage import ClusterInfo, ESStorage

from .base import CustomGroupBase

logger = logging.getLogger("metadata")


class EventGroup(CustomGroupBase):

    """事件分组记录"""

    event_group_id = models.AutoField(verbose_name="分组ID", primary_key=True)
    event_group_name = models.CharField(verbose_name="事件分组名", max_length=255)

    GROUP_ID_FIELD = "event_group_id"
    GROUP_NAME_FIELD = "event_group_name"

    # 时间字段的配置
    STORAGE_TIME_OPTION = {"es_type": "date_nanos", "es_format": "epoch_millis"}

    # Event字段配置
    STORAGE_EVENT_OPTION = {
        "es_type": "object",
        "es_properties": {"content": {"type": "text"}, "count": {"type": "integer"}},
    }

    # target字段配置
    STORAGE_TARGET_OPTION = {"es_type": "keyword"}

    # dimension字段配置
    STORAGE_DIMENSION_OPTION = {"es_type": "object", "es_dynamic": True}

    # dimension字段配置
    STORAGE_EVENT_NAME_OPTION = {"es_type": "keyword"}

    # 默认的动态维度发现配置
    STORAGE_ES_DYNAMIC_CONFIG = {
        "dynamic_templates": [{"discover_dimension": {"path_match": "dimensions.*", "mapping": {"type": "keyword"}}}]
    }

    # 默认ES配置信息
    STORAGE_ES_CONFIG = {
        "retention": settings.TS_DATA_SAVED_DAYS,
        # 默认1天区分一个index
        "slice_gap": 60 * 24,
        "date_format": "%Y%m%d",
        "mapping_settings": STORAGE_ES_DYNAMIC_CONFIG,
        "index_settings": {
            "number_of_shards": config.ES_SHARDS_CONFIG,
            "number_of_replicas": config.ES_REPLICAS_CONFIG,
        },
    }

    # 存储字段信息
    STORAGE_FIELD_LIST = [
        {
            "field_name": "event",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": STORAGE_EVENT_OPTION,
            "is_config_by_user": True,
        },
        {
            "field_name": "target",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": STORAGE_TARGET_OPTION,
            "is_config_by_user": True,
        },
        {
            "field_name": "dimensions",
            "field_type": ResultTableField.FIELD_TYPE_OBJECT,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": STORAGE_DIMENSION_OPTION,
            "is_config_by_user": True,
        },
        {
            "field_name": "event_name",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": STORAGE_EVENT_NAME_OPTION,
            "is_config_by_user": True,
        },
    ]

    DEFAULT_STORAGE = ClusterInfo.TYPE_ES
    DEFAULT_STORAGE_CONFIG = STORAGE_ES_CONFIG

    @staticmethod
    def make_table_id(bk_biz_id, bk_data_id, table_name=None):
        bk_biz_id_str = str(bk_biz_id)
        if bk_biz_id_str > "0":
            return "{}_bkmonitor_event_{}".format(bk_biz_id, bk_data_id)
        elif bk_biz_id_str < "0":
            return f"bkmonitor_{bk_biz_id_str.split('-')[-1]}_bkmonitor_event_{bk_data_id}"

        return "bkmonitor_event_{}".format(bk_data_id)

    def update_metrics(self, metric_info):
        return Event.modify_event_list(self.event_group_id, metric_info)

    @property
    def result_table_option(self):
        """
        返回结果表event_list的option内容
        :return:
        """

        # 更新result_table的option
        event_list = Event.objects.filter(event_group_id=self.event_group_id).values("event_name", "dimension_list")
        return {event["event_name"]: event["dimension_list"] for event in event_list}

    @property
    def consul_path(self):
        """返回consul路径配置"""

        return "{}/data_id/{}/event".format(config.CONSUL_PATH, self.bk_data_id)

    def update_event_dimensions_from_es(self, client: Optional[Elasticsearch] = None):
        """
        从ES更新事件及维度信息等内容
        对于一个过久未有上报的事件，那么其将会一直被保留在元数据当中
        对于仍然可以查询到的事件，那么现有的维度将会和已有的维度进行聚合，产生新的维度
        :return: True or raise Exception
        """
        if not client:
            # 获取ES客户端
            client = ESStorage.objects.get(table_id=self.table_id).get_client()

        # 获取当前index下，所有的event_name集合
        # result格式为：
        # [
        #     {
        #       "key" : "login",
        #       "doc_count" : 2
        #     },
        #     {
        #       "key" : "corefile",
        #       "doc_count" : 1
        #     },
        #     {
        #       "key" : "diskfull",
        #       "doc_count" : 1
        #     }
        # ]
        result = client.search(
            index="{}*".format(self.table_id),
            body={
                "aggs": {"find_event_name": {"terms": {"field": "event_name", "size": 10000}}},
                # 降低返回的内容条数，我们只关注聚合后的内容
                "size": 0,
            },
        )["aggregations"]["find_event_name"]["buckets"]
        logger.info("event->[{}] found total event->[{}]".format(self.event_group_id, len(result)))

        # 逐个获取信息
        event_dimension_list = []
        for event_info in result:
            try:
                result = client.search(
                    index="{}*".format(self.table_id),
                    body={
                        "query": {"bool": {"must": {"term": {"event_name": event_info["key"]}}}},
                        "size": 1,
                        "sort": {"time": "desc"},
                    },
                )["hits"]["hits"][
                    0
                ]  # 只需要其中一个命中的结果即可

            except IndexError:
                continue

            event_dimension_list.append(
                {"event_name": event_info["key"], "dimension_list": list(result["_source"]["dimensions"].keys())}
            )
            logger.info(
                "event->[{}] added new event_dimension->[{}]".format(self.event_group_id, event_dimension_list[0])
            )

        # 更新所有的相关事件
        Event.modify_event_list(self.event_group_id, event_dimension_list)
        logger.info("event->[{}] update all dimension success.".format(self.event_group_id))

        return True

    def remove_metrics(self):
        # 删除所有的事件以及事件维度
        custom_events = Event.objects.filter(event_group_id=self.event_group_id)
        logger.debug(
            "going to delete all dimension and custom_event->[{}] for EventGroup->[{}] deletion.".format(
                custom_events.count(), self.event_group_id
            )
        )
        custom_events.delete()
        logger.info("all metrics about EventGroup->[{}] is deleted.".format(self.event_group_id))

    def to_json(self):
        return {
            "event_group_id": self.event_group_id,
            "bk_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "table_id": self.table_id,
            "event_group_name": self.event_group_name,
            "label": self.label,
            "is_enable": self.is_enable,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
            "event_info_list": [
                event_info.to_json()
                for event_info in Event.objects.filter(event_group_id=self.event_group_id).only(
                    "event_id", "event_name", "dimension_list"
                )
            ],
            "data_label": self.data_label,
        }

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_event_group(
        cls,
        bk_data_id,
        bk_biz_id,
        event_group_name,
        label,
        operator,
        event_info_list=None,
        table_id=None,
        data_label: Optional[str] = None,
    ):
        """
        创建一个新的自定义分组记录
        :param bk_data_id: 数据源ID
        :param bk_biz_id: 业务ID
        :param event_group_name: 事件组名称
        :param label: 标签，描述事件监控对象
        :param operator: 操作者
        :param event_info_list: metric列表
        :param table_id: 需要制定的table_id，否则通过默认规则创建得到
        :param data_label: 数据标签
        :return: group object
        """
        group = super().create_custom_group(
            bk_data_id=bk_data_id,
            bk_biz_id=bk_biz_id,
            custom_group_name=event_group_name,
            label=label,
            operator=operator,
            metric_info_list=event_info_list,
            table_id=table_id,
            data_label=data_label,
        )

        fields = cls.STORAGE_FIELD_LIST
        option_value = [field["field_name"] for field in fields]
        option_value.append("time")

        ResultTableOption.create_option(
            table_id=group.table_id, name=ResultTableOption.OPTION_ES_DOCUMENT_ID, value=option_value, creator="system"
        )

        # 需要刷新一次外部依赖的consul，触发transfer更新
        from metadata.models import DataSource

        DataSource.objects.get(bk_data_id=bk_data_id).refresh_consul_config()

        return group

    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_event_group(
        self,
        operator,
        event_group_name=None,
        label=None,
        is_enable=None,
        event_info_list=None,
        data_label: Optional[str] = None,
    ):
        """
        修改一个事件组
        :param operator: 操作者
        :param event_group_name: 事件组名
        :param label: 事件组标签
        :param is_enable: 是否启用事件组
        :param event_info_list: metric信息,
        :param data_label: 数据标签
        :return: True or raise
        """
        return self.modify_custom_group(
            operator=operator,
            custom_group_name=event_group_name,
            label=label,
            is_enable=is_enable,
            metric_info_list=event_info_list,
            data_label=data_label,
        )

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_event_group(self, operator):
        """
        删除一个指定的事件组
        :param operator: 操作者
        :return: True or raise
        """
        return self.delete_custom_group(operator=operator)


class Event(models.Model):
    """事件描述"""

    TARGET_DIMENSION_NAME = "target"

    event_id = models.AutoField(verbose_name="事件ID", primary_key=True)
    event_group_id = models.IntegerField(verbose_name="事件所属分组ID")
    event_name = models.CharField(verbose_name="事件名称", max_length=255)
    dimension_list = JsonField(verbose_name="维度列表", default=[])
    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)

    class Meta:
        # 同一个事件分组下，不可以存在同样的事件名称
        unique_together = ("event_group_id", "event_name")
        verbose_name = "事件描述记录"
        verbose_name_plural = "事件描述记录表"

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_event_list(cls, event_group_id, event_info_list):
        """
        批量的修改/创建某个事件分组下的事件
        :param event_group_id: 事件分组ID
        :param event_info_list: 具体事件内容信息，[{
            "event_name": "core_file",
            "dimension_list": ["module", "set", "path"]
        }, {
            "event_name": "disk_full",
            "dimension_list": ["module", "set", "partition"]
        }]
        :return: True or raise
        """
        # 0. 判断是否真的存在某个group_id
        if not EventGroup.objects.filter(event_group_id=event_group_id).exists():
            logger.info("event_group_id->[{}] not exists, nothing will do.".format(event_group_id))
            raise ValueError(_("事件组ID[{}]不存在，请确认后重试").format(event_group_id))

        # 1. 遍历所有的事件进行处理，判断是否存在custom_event_id
        for event_info in event_info_list:
            # 如果存在这个custom_event_id，那么需要进行修改
            try:
                event_name = event_info["event_name"]
                dimension_list = event_info["dimension_list"]
            except KeyError as key:
                logger.error("event_info_list got bad event_info->[{}] which has no key->[{}]".format(event_info, key))
                raise ValueError(_("事件列表配置有误，请确认后重试"))

            # NOTE: 维度 [target] 必须存在; 如果不存在时，则需要添加 [target] 维度
            if cls.TARGET_DIMENSION_NAME not in dimension_list:
                dimension_list.append(cls.TARGET_DIMENSION_NAME)

            try:
                # 判断是否已经存在这个事件
                custom_event = cls.objects.get(event_name=event_name, event_group_id=event_group_id)
            except cls.DoesNotExist:
                # 如果不存在事件，创建一个新的时间
                custom_event = cls.objects.create(event_name=event_name, event_group_id=event_group_id)
                logger.info("new custom_event->[{}] is create for group_id->[{}].".format(custom_event, event_group_id))

            # 修改已有的事件配置, 但是考虑需要保持已有的维度，需要将新旧两个维度merge
            old_dimension_set = set(custom_event.dimension_list)
            new_dimension_set = set(dimension_list)
            # 大小写不敏感，因此需要覆盖
            custom_event.event_name = event_name
            custom_event.dimension_list = list(old_dimension_set.union(new_dimension_set))
            custom_event.save()

            # 后续可以在此处追加其他修改内容
            logger.info(
                "event_group_id->[{}] has update event_id->[{}] all dimension->[{}]".format(
                    event_group_id, custom_event.event_name, len(dimension_list)
                )
            )

        return True

    @property
    def event_group(self):
        """
        对象获得event_group的缓存
        :return:
        """
        if getattr(self, "_event_group", None) is None:
            self._event_group = EventGroup.objects.get(event_group_id=self.event_group_id)

        return self._event_group

    def to_json(self):
        return {"event_id": self.event_id, "event_name": self.event_name, "dimension_list": self.dimension_list}

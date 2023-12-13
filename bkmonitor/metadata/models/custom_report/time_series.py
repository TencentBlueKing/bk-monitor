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
import datetime
import json
import logging
import math
import time
from typing import Dict, List, Optional, Set, Tuple, Union

from django.conf import settings
from django.db import models
from django.db import utils as django_db_utils
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.timezone import make_aware
from django.utils.timezone import now as tz_now
from django.utils.translation import ugettext as _

from bkmonitor.utils.db.fields import JsonField
from metadata import config
from metadata.models.constants import (
    BULK_CREATE_BATCH_SIZE,
    BULK_UPDATE_BATCH_SIZE,
    DB_DUPLICATE_ID,
)
from metadata.models.result_table import (
    ResultTable,
    ResultTableField,
    ResultTableOption,
)
from metadata.models.storage import ClusterInfo
from metadata.utils.db import filter_model_by_in_page
from packages.utils.redis_client import RedisClient

from .base import CustomGroupBase

logger = logging.getLogger("metadata")


class TimeSeriesGroup(CustomGroupBase):
    time_series_group_id = models.AutoField(verbose_name="分组ID", primary_key=True)
    time_series_group_name = models.CharField(verbose_name="自定义时序分组名", max_length=255)

    # 默认表名
    DEFAULT_MEASUREMENT = "__default__"

    GROUP_ID_FIELD = "time_series_group_id"
    GROUP_NAME_FIELD = "time_series_group_name"

    # 默认存储INFLUXDB
    DEFAULT_STORAGE = ClusterInfo.TYPE_INFLUXDB

    # 默认INFLUXDB存储配置
    DEFAULT_STORAGE_CONFIG = {"use_default_rp": True}

    # Event字段配置
    STORAGE_EVENT_OPTION = {}

    # target字段配置
    STORAGE_TARGET_OPTION = {}

    # dimension字段配置
    STORAGE_DIMENSION_OPTION = {}

    # dimension字段配置
    STORAGE_EVENT_NAME_OPTION = {}

    STORAGE_FIELD_LIST = [
        {
            "field_name": "target",
            "field_type": ResultTableField.FIELD_TYPE_STRING,
            "tag": ResultTableField.FIELD_TAG_DIMENSION,
            "option": STORAGE_TARGET_OPTION,
            "is_config_by_user": True,
        }
    ]

    # 组合一个默认的tableid
    @staticmethod
    def make_table_id(bk_biz_id, bk_data_id, table_name=None):
        if str(bk_biz_id) != "0":
            return "{}_bkmonitor_time_series_{}.{}".format(bk_biz_id, bk_data_id, TimeSeriesGroup.DEFAULT_MEASUREMENT)

        return "bkmonitor_time_series_{}.{}".format(bk_data_id, TimeSeriesGroup.DEFAULT_MEASUREMENT)

    def make_metric_table_id(self, field_name):
        # 结果表是bk_k8s开头，保证这些的结果表和用户的结果表是区别开的
        return f"bk_k8s_{self.time_series_group_name}_{field_name}"

    @atomic(config.DATABASE_CONNECTION_NAME)
    def update_tag_fields(
        self, table_id: str, tag_list: List[Tuple[str, str]], update_description: bool = False
    ) -> bool:
        """
        更新维度信息
        @param tag_list: 维度列表
        @param table_id: 结果表ID
        @param update_description: 是否需要更新描述
        :return: True | False
        """

        for tag in tag_list:
            field_name, description = tag
            try:
                rt_field = ResultTableField.objects.get(
                    table_id=table_id,
                    field_name=field_name,
                    tag__in=[
                        ResultTableField.FIELD_TAG_DIMENSION,
                        ResultTableField.FIELD_TAG_TIMESTAMP,
                        ResultTableField.FIELD_TAG_GROUP,
                    ],
                )
                if rt_field.description != description and update_description:
                    rt_field.description = description
                    rt_field.save()
            except ResultTableField.DoesNotExist:
                ResultTableField.objects.create(
                    table_id=table_id,
                    field_name=field_name,
                    description=description,
                    tag=ResultTableField.FIELD_TAG_DIMENSION,
                    field_type=ResultTableField.FIELD_TYPE_STRING,
                    creator="system",
                    last_modify_user="system",
                    default_value="",
                    is_config_by_user=True,
                    is_disabled=False,
                )
            except django_db_utils.IntegrityError as e:
                if e.args[0] == DB_DUPLICATE_ID:
                    logger.error(
                        "result table field is duplicated, data_id: [%s], table_id: [%s], duplicate field: [%s]",
                        self.bk_data_id,
                        table_id,
                        field_name,
                    )
                raise
            logger.debug(
                "table->[%s] is not split measurement now make sure field->[%s] dimension is exists.",
                table_id,
                field_name,
            )

        logger.info("table->[%s] refresh tag count->[%s] success.", table_id, len(tag_list))
        return True

    def update_metric_field(self, field_name: str, is_disabled: bool) -> bool:
        """
        更新单个指标的信息
        @param field_name:
        @param is_disabled: 指标是否启用
        :return: True | False
        """
        # 判断后续需要使用的结果表
        table_id = self.table_id

        # 更新指标列信息
        # 先进行查询，如果存在，并且有变动才进行更新；如果不存在，则进行创建
        rt_field, is_created = ResultTableField.objects.get_or_create(
            table_id=table_id,
            field_name=field_name,
            tag=ResultTableField.FIELD_TAG_METRIC,
            defaults={
                "field_type": ResultTableField.FIELD_TYPE_FLOAT,
                "creator": "system",
                "last_modify_user": "system",
                "default_value": 0,
                "is_config_by_user": True,
                "is_disabled": is_disabled,
            },
        )
        # 判断是否有字段的更新，如果有变化则进行更新
        is_field_update = False
        # NOTE: is_disabled 字段不可能为空
        if rt_field.is_disabled != is_disabled:
            rt_field.is_disabled = is_disabled
            rt_field.save(update_fields=["is_disabled"])
            is_field_update = True

        # RTField 有新增 或是 is_disabled 有变更，需要刷新 consul
        if is_created or is_field_update:
            self.NEED_REFRESH_CONSUL = True

        logger.info("table->[%s] metric field->[%s] is update.", table_id, field_name)
        return True

    def is_auto_discovery(self) -> bool:
        """
        判断是否是自动发现
        :return: True：是自动发现/False：不是自动发现（插件白名单模式）
        """
        return not ResultTableOption.objects.filter(
            table_id=self.table_id, name='enable_field_black_list', value="false"
        ).exists()

    def _refine_metric_tags(self, metric_info: List) -> Dict:
        """去除重复的维度"""
        metric_dict, tag_dict = {}, {}
        # 标识是否需要更新描述
        is_update_description = True
        for item in metric_info:
            # 格式: {field_name: 是否禁用}
            metric_dict[item["field_name"]] = not item.get("is_active", True)
            # 兼容传入 tag_value_list/tag_list 的情况
            if "tag_value_list" in item:
                is_update_description = False
                for tag in item["tag_value_list"].keys():
                    tag_dict[tag] = ""
            else:
                for tag in item.get("tag_list", []):
                    # 取第一个值，后面重复的直接忽略
                    if tag in tag_dict:
                        continue
                    tag_dict[tag["field_name"]] = tag["description"]

        return {
            "is_update_description": is_update_description,
            "metric_dict": metric_dict,
            "tag_dict": tag_dict,
        }

    def _bulk_create_or_update_metrics(
        self,
        table_id: str,
        metric_dict: Dict,
        need_create_metrics: Set,
        need_update_metrics: Set,
    ):
        """批量创建或更新字段"""
        logger.info("bulk create or update rt metrics")
        create_records = []
        for metric in need_create_metrics:
            create_records.append(
                ResultTableField(
                    table_id=table_id,
                    field_name=metric,
                    tag=ResultTableField.FIELD_TAG_METRIC,
                    field_type=ResultTableField.FIELD_TYPE_FLOAT,
                    creator="system",
                    last_modify_user="system",
                    default_value=0,
                    is_config_by_user=True,
                    is_disabled=metric_dict.get(metric, False),
                )
            )
        # 开始写入数据
        ResultTableField.objects.bulk_create(create_records, batch_size=BULK_CREATE_BATCH_SIZE)
        logger.info("bulk create metric successfully")

        # 开始批量更新
        update_records = []
        qs_objs = filter_model_by_in_page(
            ResultTableField,
            "field_name__in",
            need_update_metrics,
            other_filter={"table_id": table_id, "tag": ResultTableField.FIELD_TAG_METRIC},
        )
        for obj in qs_objs:
            expect_metric_status = metric_dict.get(obj.field_name, False)
            if obj.is_disabled != expect_metric_status:
                obj.is_disabled = expect_metric_status
                update_records.append(obj)
        ResultTableField.objects.bulk_update(update_records, ["is_disabled"], batch_size=BULK_UPDATE_BATCH_SIZE)
        logger.info("batch update metric successfully")

    def _bulk_create_or_update_tags(
        self,
        table_id: str,
        tag_dict: Dict,
        need_create_tags: Set,
        need_update_tags: Set,
        update_description: bool,
    ):
        """批量创建或更新 tag"""
        logger.info("bulk create or update rt tag")
        create_records = []
        for tag in need_create_tags:
            create_records.append(
                ResultTableField(
                    table_id=table_id,
                    field_name=tag,
                    description=tag_dict.get(tag, ""),
                    tag=ResultTableField.FIELD_TAG_DIMENSION,
                    field_type=ResultTableField.FIELD_TYPE_STRING,
                    creator="system",
                    last_modify_user="system",
                    default_value="",
                    is_config_by_user=True,
                    is_disabled=False,
                )
            )
        # 开始写入数据
        ResultTableField.objects.bulk_create(create_records, batch_size=BULK_CREATE_BATCH_SIZE)
        logger.info("bulk create tag successfully")

        # 开始批量更新
        update_records = []
        qs_objs = filter_model_by_in_page(
            ResultTableField,
            "field_name__in",
            need_update_tags,
            other_filter={
                "table_id": table_id,
                "tag__in": [
                    ResultTableField.FIELD_TAG_DIMENSION,
                    ResultTableField.FIELD_TAG_TIMESTAMP,
                    ResultTableField.FIELD_TAG_GROUP,
                ],
            },
        )
        for obj in qs_objs:
            expect_tag_description = tag_dict.get(obj.field_name, "")
            if obj.description != expect_tag_description and update_description:
                obj.description = expect_tag_description
                update_records.append(obj)
        ResultTableField.objects.bulk_update(update_records, ["description"], batch_size=BULK_UPDATE_BATCH_SIZE)
        logger.info("batch update tag successfully")

    def bulk_refresh_rt_fields(self, table_id: str, metric_info: List):
        """批量刷新结果表打平的指标和维度"""
        # 创建或更新
        metric_tag_info = self._refine_metric_tags(metric_info)
        # 通过结果表过滤到到指标和维度
        exist_fields = ResultTableField.objects.filter(
            table_id=table_id,
        ).values("field_name", "tag")
        exist_metrics, exist_tags = set(), set()
        for field in exist_fields:
            field_name = field["field_name"]
            if field["tag"] == ResultTableField.FIELD_TAG_METRIC:
                exist_metrics.add(field_name)
            # NOTE: 这里追加指标类型，是为了访问维度和指标重复
            elif field["tag"] in [
                ResultTableField.FIELD_TAG_DIMENSION,
                ResultTableField.FIELD_TAG_TIMESTAMP,
                ResultTableField.FIELD_TAG_GROUP,
                ResultTableField.FIELD_TAG_METRIC,
            ]:
                exist_tags.add(field_name)

        # 过滤需要创建或更新的指标
        metric_dict = metric_tag_info["metric_dict"]
        metric_set = set(metric_dict.keys())
        need_create_metrics = metric_set - exist_metrics
        # 获取已经存在的指标，然后进行批量更新
        need_update_metrics = metric_set - need_create_metrics
        self._bulk_create_or_update_metrics(table_id, metric_dict, need_create_metrics, need_update_metrics)
        # 过滤需要创建或更新的维度
        tag_dict = metric_tag_info["tag_dict"]
        tag_set = set(tag_dict.keys())
        need_create_tags = tag_set - exist_tags
        need_update_tags = tag_set - need_create_tags
        self._bulk_create_or_update_tags(
            table_id,
            tag_dict,
            need_create_tags,
            need_update_tags,
            metric_tag_info["is_update_description"],
        )
        logger.info("bulk refresh rt fields successfully")

    @atomic(config.DATABASE_CONNECTION_NAME)
    def update_metrics(self, metric_info):
        # 记录是否有指标更新
        # 通过功能开关控制是否使用新的功能，避免未知问题
        if settings.IS_ENABLE_METADATA_FUNCTION_CONTROLLER:
            # 判断是否真的存在某个group_id
            group_id = self.time_series_group_id
            try:
                group = TimeSeriesGroup.objects.get(time_series_group_id=group_id)
            except TimeSeriesGroup.DoesNotExist:
                logger.info("time_series_group_id->[%s] not exists, nothing will do.", group_id)
                raise ValueError(f"ts group id: {group_id} not found")
            # 刷新 ts 中指标和维度
            is_updated = TimeSeriesMetric.bulk_refresh_ts_metrics(
                group_id, group.table_id, metric_info, group.is_auto_discovery
            )
            # 刷新 rt 表中的指标和维度
            self.bulk_refresh_rt_fields(group.table_id, metric_info)
            return is_updated
        else:
            is_updated = TimeSeriesMetric.update_metrics(self.time_series_group_id, metric_info)

        tag_set = set()
        field_list = []
        tag_total_list = []
        update_description = True

        for item in metric_info:
            field_name = item["field_name"]
            field_list.append(field_name)
            # 兼容传入 tag_value_list/tag_list 的情况
            if "tag_value_list" in item:
                update_description = False
                tag_list = [(k, "") for k in item["tag_value_list"].keys()]
            else:
                tag_list = [(tag["field_name"], tag["description"]) for tag in item.get("tag_list", [])]

            # 捕获异常，然后添加额外信息，用于后续告警通知
            # NOTE: 异常时，仅记录
            try:
                self.update_metric_field(field_name=field_name, is_disabled=not item.get("is_active", True))
            except Exception as e:
                logger.error(
                    "update result table field failed, data_id: [%s], table_id: [%s], field: [%s], err: %s",
                    self.bk_data_id,
                    self.table_id,
                    field_name,
                    str(e),
                )
                continue

            logger.info(f"table->[{self.table_id}] now make sure field->[{field_name}] metric is exists.")

            # 否则，需要积累遍历所有的指标维度
            for tag in tag_list:
                name, _ = tag
                if name in tag_set:
                    continue
                tag_set.add(name)
                tag_total_list.append(tag)
            logger.info("group->[%s] is not split add tag->[%s] to set.", self.time_series_group_name, tag_list)

        # 如果是统一结果表，则统一创建维度字段，降低重复的DB请求
        try:
            self.update_tag_fields(self.table_id, tag_total_list, update_description)
        except Exception as e:
            # 记录异常日志
            logger.error(
                "update update_metrics failed, data_id: [%s], table_id: [%s], err: %s",
                self.bk_data_id,
                self.table_id,
                str(e),
            )

        logger.info(f"table->[{self.table_id}] now process metrics done.")
        return is_updated

    @property
    def datasource_options(self):
        return [
            {"name": "metrics_report_path", "value": self.metric_consul_path},
            {"name": "disable_metric_cutter", "value": "true"},
        ]

    @property
    def metric_consul_path(self):
        return "{}/influxdb_metrics/{}/time_series_metric".format(config.CONSUL_PATH, self.bk_data_id)

    def get_metrics_from_redis(self, expired_time: Optional[int] = settings.TIME_SERIES_METRIC_EXPIRED_SECONDS):
        """从 redis 中获取数据

        其中，redis 中数据有 transfer 上报
        """
        client = RedisClient.from_envs(prefix="BK_MONITOR_TRANSFER")
        custom_metrics_key = f"{settings.METRICS_KEY_PREFIX}{self.bk_data_id}"
        metric_dimensions_key = f"{settings.METRIC_DIMENSIONS_KEY_PREFIX}{self.bk_data_id}"

        now_time = tz_now()
        fetch_step = settings.MAX_METRICS_FETCH_STEP
        valid_begin_ts = (now_time - datetime.timedelta(seconds=expired_time)).timestamp()
        metrics_filter_params = {"name": custom_metrics_key, "min": valid_begin_ts, "max": now_time.timestamp()}

        metrics_info = []
        # 分批拉取 redis 数据，防止大批量数据拖垮
        for i in range(math.ceil(client.zcount(**metrics_filter_params) / fetch_step)):
            try:
                # 0. 首先获取有效期内的所有 metrics
                metrics_with_scores: List[Tuple[bytes, float]] = client.zrangebyscore(
                    **metrics_filter_params, start=fetch_step * i, num=fetch_step, withscores=True
                )
            except Exception:
                logger.exception("failed to get metrics from storage, filter params: %s", metrics_filter_params)
                # metrics 可能存在大批量内容，可容忍某一步出错
                continue

            # 1. 获取当前这批 metrics 的 dimensions 信息
            try:
                dimensions_list: List[bytes] = client.hmget(metric_dimensions_key, [x[0] for x in metrics_with_scores])
            except Exception:
                logger.exception("failed to get dimensions from metrics")
                continue

            # 2. 尝试更新 metrics 和对应 dimensions(tags)
            for j, metric_with_score in enumerate(metrics_with_scores):
                # 理论上 metrics 和 dimensions 列表一一对应
                dimensions_info = dimensions_list[j]
                if not dimensions_info:
                    continue

                try:
                    dimensions = json.loads(dimensions_info)["dimensions"]
                except Exception:
                    logger.exception("failed to parse dimension from dimensions info: %s", dimensions_info)
                    continue

                # 因为获取到的为bytes类型，避免后续更新`table id`时，组装格式错误，转换为字符串
                field_name = metric_with_score[0]
                if type(field_name) == bytes:
                    field_name = field_name.decode("utf-8")
                metrics_info.append(
                    {
                        "field_name": field_name,
                        "tag_value_list": dimensions,
                        "last_modify_time": metric_with_score[1],
                    }
                )
        return metrics_info

    def update_time_series_metrics(self) -> bool:
        """从远端存储中同步TS的指标和维度对应关系

        :return: 返回是否有更新指标
        """
        metrics_info = self.get_metrics_from_redis(expired_time=settings.FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS)
        # 如果为空，直接返回
        if not metrics_info:
            return False

        # 记录是否有更新，然后推送redis并发布通知
        is_updated = self.update_metrics(metrics_info)
        logger.debug("TimeSeriesGroup<%s> already updated all metrics", self.pk)

        return is_updated

    def remove_metrics(self):
        # 删除所有的metrics信息
        metrics_queryset = TimeSeriesMetric.objects.filter(group_id=self.time_series_group_id)
        logger.debug(
            "going to delete all metrics->[{}] for {}->[{}] deletion.".format(
                metrics_queryset.count(), self.__class__.__name__, self.time_series_group_id
            )
        )
        metrics_queryset.delete()
        logger.info("all metrics about {}->[{}] is deleted.".format(self.__class__.__name__, self.time_series_group_id))

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_time_series_group(
        cls,
        bk_data_id,
        bk_biz_id,
        time_series_group_name,
        label,
        operator,
        metric_info_list=None,
        table_id=None,
        is_split_measurement=True,
        default_storage_config=None,
        additional_options: Optional[dict] = None,
        data_label: Optional[str] = None,
    ):
        """
        创建一个新的自定义分组记录
        :param bk_data_id: 数据源ID
        :param bk_biz_id: 业务ID
        :param time_series_group_name: 自定义时序组名称
        :param label: 标签，描述事件监控对象
        :param operator: 操作者
        :param metric_info_list: metric列表
        :param table_id: 需要制定的table_id，否则通过默认规则创建得到
        :param is_split_measurement: 是否启动自动分表逻辑
        :param default_storage_config: 默认存储配置
        :param additional_options: 附带创建的 ResultTableOption
        :param data_label: 数据标签
        :return: group object
        """

        custom_group = super().create_custom_group(
            bk_data_id=bk_data_id,
            bk_biz_id=bk_biz_id,
            custom_group_name=time_series_group_name,
            label=label,
            operator=operator,
            metric_info_list=metric_info_list,
            table_id=table_id,
            is_split_measurement=is_split_measurement,
            default_storage_config=default_storage_config,
            additional_options=additional_options,
            data_label=data_label,
        )

        # 需要刷新一次外部依赖的consul，触发transfer更新
        from metadata.models import DataSource

        DataSource.objects.get(bk_data_id=bk_data_id).refresh_consul_config()

        return custom_group

    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_time_series_group(
        self,
        operator,
        time_series_group_name=None,
        label=None,
        is_enable=None,
        field_list=None,
        enable_field_black_list=None,
        metric_info_list=None,
        data_label: Optional[str] = None,
    ):
        """
        修改一个自定义时序组
        :param operator: 操作者
        :param time_series_group_name: 自定义时序组名
        :param label:  自定义时序组标签
        :param is_enable: 是否启用自定义时序组
        :param field_list: metric信息,
        :param enable_field_black_list: 黑名单的启用状态，bool,
        :param metric_info_list: metric信息
        :param data_label: 数据标签
        :return: True or raise
        """
        return self.modify_custom_group(
            operator=operator,
            custom_group_name=time_series_group_name,
            label=label,
            is_enable=is_enable,
            metric_info_list=metric_info_list,
            field_list=field_list,
            enable_field_black_list=enable_field_black_list,
            data_label=data_label,
        )

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_time_series_group(self, operator):
        """
        删除一个指定的自定义时序组
        :param operator: 操作者
        :return: True or raise
        """
        return self.delete_custom_group(operator=operator)

    def to_json(self):
        return {
            "time_series_group_id": self.time_series_group_id,
            "time_series_group_name": self.time_series_group_name,
            "bk_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "table_id": self.table_id,
            "label": self.label,
            "is_enable": self.is_enable,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
            "metric_info_list": self.get_metric_info_list(),
            "data_label": self.data_label,
        }

    def to_json_v2(self):
        """
        v2版本统一返回数组结构，并兼容分表与否两个版本
        """
        if self.is_split_measurement:
            return self.to_split_json()
        else:
            return [self.to_json()]

    def to_split_json(self):
        """
        基于分表规则，将单个group的数据按指标名进行切表，并修改table_id
        """
        metrics = self.get_metric_info_list()
        # 这里需要兼容未上报数据的情况
        if not metrics:
            return [self.to_json()]
        results = []
        is_auto_discovery = self.is_auto_discovery()
        data_label = self.data_label
        for metric in metrics:
            results.append(
                {
                    "time_series_group_id": self.time_series_group_id,
                    "time_series_group_name": self.time_series_group_name,
                    "bk_data_id": self.bk_data_id,
                    "bk_biz_id": self.bk_biz_id,
                    "table_id": metric["table_id"],
                    "label": self.label,
                    "is_enable": self.is_enable,
                    "creator": self.creator,
                    "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "last_modify_user": self.last_modify_user,
                    "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "metric_info_list": [metric],
                    "is_auto_discovery": is_auto_discovery,
                    "data_label": data_label,
                }
            )

        return results

    def to_json_self_only(self):
        return {
            "time_series_group_id": self.time_series_group_id,
            "time_series_group_name": self.time_series_group_name,
            "bk_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "table_id": self.table_id,
            "label": self.label,
            "is_enable": self.is_enable,
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _filter_metric_by_dimension(self, metrics: List, dimension_name: str, dimension_value: str) -> (Set, Set):
        metric_by_dimension_name = set()
        metric_by_dimension_value = set()
        for d in metrics:
            tag_value_list = d.get("tag_value_list", {})
            # 匹配 tag 名称
            if dimension_name and dimension_name in tag_value_list:
                metric_by_dimension_name.add(d.get("field_name"))
            if not dimension_value:
                continue
            # 匹配 tag 值
            for __, val in tag_value_list.items():
                # NOTE: 当 val 为空时，直接跳过
                if not val:
                    continue
                values = val.get("values") or []
                if values and dimension_value in values:
                    metric_by_dimension_value.add(d.get("field_name"))
        return metric_by_dimension_name, metric_by_dimension_value

    def get_ts_metrics_by_dimension(self, dimension_name: str, dimension_value: str) -> List:
        """获取指标名称
        从 redis 中获取数据，然后比对满足条件的记录，获取到指标名称

        [{
            'field_name': 'test',
            'tag_value_list': {
                'bk_biz_id': {'last_update_time': 1662009139, 'values': []},
                'parent_scenario': {'last_update_time': 1662009139, 'values': []},
                'scenario': {'last_update_time': 1662009139, 'values': []},
                'target': {'last_update_time': 1662009139, 'values': []},
                'target_biz_id': {'last_update_time': 1662009139, 'values': []},
                'target_biz_name': {'last_update_time': 1662009139, 'values': []}
            },
            'last_modify_time': 1662009139.0
        }]
        """
        redis_data = self.get_metrics_from_redis()
        # 如果不需要过滤，则直接返回
        if not (dimension_name or dimension_value):
            return []
        # 过滤到满足条件的 metric 信息
        metric_by_dimension_name, metric_by_dimension_value = self._filter_metric_by_dimension(
            redis_data,
            dimension_name,
            dimension_value,
        )

        # 兼容未升级Transfer的查询
        if (
            dimension_name == "bk_monitor_namespace/bk_monitor_name"
            and dimension_value
            and not (metric_by_dimension_name & metric_by_dimension_value)  # 交集为空时尝试用旧的name和value过滤
        ):
            dimension_name = "bk_monitor_name"
            dimension_value = dimension_value.split("/", maxsplit=1)[-1]
            metric_by_dimension_name, metric_by_dimension_value = self._filter_metric_by_dimension(
                redis_data,
                dimension_name,
                dimension_value,
            )
        # 如果都存在，则取交集
        if dimension_name and dimension_value:
            return list(metric_by_dimension_name & metric_by_dimension_value)
        # 否则，返回存在的值
        return list(metric_by_dimension_name or metric_by_dimension_value)

    def get_metric_info_list_with_label(self, dimension_name: str, dimension_value: str):
        metric_info_list = []

        metric_filter_params = {"group_id": self.time_series_group_id}
        orm_field_map = {}

        # 如果是serviceMonitor上报的指标，
        # TimeSeriesMetric的tag值会包含 bk_monitor_name
        # TimeSeriesTag的value值会包含servicemonitor的名称
        if dimension_name:
            metric_filter_params.update({"tag_list__contains": dimension_name})

        # 用于过滤指标记录
        metric_list = self.get_ts_metrics_by_dimension(dimension_name, dimension_value)
        # 如果 redis 数据中有满足的 metric 信息，则添加到过滤条件中
        # 如果有传入 dimension_name 或 dimension_value，但是没有满足的 metric 信息，则直接返回
        if not metric_list and (dimension_name or dimension_value):
            return []

        if metric_list:
            metric_filter_params["field_name__in"] = metric_list

        for orm_field in (
            ResultTableField.objects.filter(table_id=self.table_id).values(*TimeSeriesMetric.ORM_FIELD_NAMES).iterator()
        ):
            orm_field_map[orm_field["field_name"]] = orm_field
        # 获取过期分界线
        last = datetime.datetime.now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        # 查找过期时间以前的数据
        for metric in TimeSeriesMetric.objects.filter(**metric_filter_params, last_modify_time__gt=last).iterator():
            metric_info = metric.to_metric_info_with_label(self, field_map=orm_field_map)
            # 当一个指标可能某些原因被删除时，不必再追加到结果中
            if metric_info is None:
                continue

            metric_info_list.append(metric_info)

        return metric_info_list

    def get_metric_info_list(self):
        metric_info_list = []

        orm_field_map = {}
        for orm_field in (
            ResultTableField.objects.filter(table_id=self.table_id).values(*TimeSeriesMetric.ORM_FIELD_NAMES).iterator()
        ):
            orm_field_map[orm_field["field_name"]] = orm_field
        # 获取过期分界线
        last = datetime.datetime.now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        time_series_metric_query = TimeSeriesMetric.objects.filter(group_id=self.time_series_group_id)
        # 如果是插件白名单模式，不需要判断过期时间
        if self.is_auto_discovery():
            time_series_metric_query = time_series_metric_query.filter(last_modify_time__gt=last)
        # 查找过期时间以前的数据
        for metric in time_series_metric_query.iterator():
            metric_info = metric.to_metric_info(field_map=orm_field_map, group=self)
            # 当一个指标可能某些原因被删除时，不必再追加到结果中
            if metric_info is None:
                continue

            metric_info_list.append(metric_info)

        return metric_info_list

    def set_table_id_disable(self):
        """
        将相关的结果表都设置为已经废弃
        1. 对于公共结果表的，直接设置公共结果表废弃使用
        2. 对于拆分结果表的，需要遍历相关的所有metric，将每个结果表逐一设置为废弃使用
        :return: True | False
        """
        # 1. 判断是否公共结果表
        if not self.is_split_measurement:
            # 公共结果表，直接设置即可
            ResultTable.objects.filter(table_id=self.table_id).update(is_deleted=True, is_enable=False)
            logger.info("ts group->[%s] table_id->[%s] is set to disabled now.", self.custom_group_name, self.table_id)

            return True

        # 2. 拆分结果表的，先遍历所有的metric
        # TODO 这里需要调整,因为实际拆分结果表也不会生成新的tableid了，对应的应该在TimeSeriesMetric上增加状态位
        logger.info("ts group->[%s] is split measurement will disable all tables.", self.custom_group_name)
        for metric_group in TimeSeriesMetric.objects.filter(group_id=self.custom_group_id):
            # 2.1 每个metric拼接出结果表名
            table_id = self.make_metric_table_id(metric_group.field_name)
            # 2.2 设置该结果表启用
            ResultTable.objects.filter(table_id=self.table_id).update(is_deleted=True, is_enable=False)
            logger.info("ts group->[%s] per table_id->[%s] is set to disabled now.", self.custom_group_name, table_id)

        logger.info("ts group->[%s] all table_id is set to disabled now.", self.custom_group_name)
        return True


class TimeSeriesMetric(models.Model):
    """自定义时序schema描述
    field: [tag1, tag2...]
    """

    TARGET_DIMENSION_NAME = "target"

    ORM_FIELD_NAMES = (
        "table_id",
        "field_name",
        "field_type",
        "unit",
        "tag",
        "description",
        "is_disabled",
    )

    group_id = models.IntegerField(verbose_name="自定义时序所属分组ID")
    table_id = models.CharField(verbose_name="table名", default="", max_length=255)

    field_id = models.AutoField(verbose_name="自定义时序字段ID", primary_key=True)
    field_name = models.CharField(verbose_name="自定义时序字段名称", max_length=255)
    tag_list = JsonField(verbose_name="Tag列表", default=[])
    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)
    last_index = models.IntegerField(verbose_name="上次consul的modify_index", default=0)

    label = models.CharField(verbose_name="指标监控对象", default="", max_length=255)

    class Meta:
        # 同一个事件分组下，不可以存在同样的事件名称
        unique_together = ("group_id", "field_name")
        verbose_name = "自定义时序描述记录"
        verbose_name_plural = "自定义时序描述记录表"

    def make_table_id(self, bk_biz_id, bk_data_id, table_name=None):
        if str(bk_biz_id) != "0":
            return "{}_bkmonitor_time_series_{}.{}".format(bk_biz_id, bk_data_id, self.field_name)

        return "bkmonitor_time_series_{}.{}".format(bk_data_id, self.field_name)

    def to_rt_field_json(self):
        """
        仅返回自身相关的信息json格式，其他的内容需要调用方自行追加，目前已知需要用户自定义添加的内容
        1. option, 字段选项内容
        :param is_consul_config:
        :return:
        """

        result = []
        # TODO 模拟rtfield进行的返回，需要补充各字段的数据源
        metric = {
            "field_name": self.field_name,
            "type": ResultTableField.FIELD_TYPE_FLOAT,
            "tag": ResultTableField.FIELD_TAG_METRIC,
            "default_value": 0,
            "is_config_by_user": True,  # 是否已被用户确认添加
            "description": "",
            "unit": "",
            "alias_name": "",
        }
        result.append(metric)
        timestamp = {
            "field_name": "time",
            "type": ResultTableField.FIELD_TYPE_TIMESTAMP,
            "tag": ResultTableField.FIELD_TAG_TIMESTAMP,
            "default_value": 0,
            "is_config_by_user": True,  # 是否已被用户确认添加
            "description": "",
            "unit": "",
            "alias_name": "",
        }
        result.append(timestamp)

        for tag in self.tag_list:
            dimension = {
                "field_name": tag,
                "type": ResultTableField.FIELD_TYPE_STRING,
                "tag": ResultTableField.FIELD_TAG_DIMENSION,
                "default_value": "",
                "is_config_by_user": True,  # 是否已被用户确认添加
                "description": "",
                "unit": "",
                "alias_name": "",
            }
            result.append(dimension)

        return result

    @classmethod
    def get_metric_tag_from_metric_info(cls, metric_info: Dict) -> List:
        # 获取 tag
        if "tag_value_list" in metric_info:
            tags = set(metric_info["tag_value_list"].keys())
        else:
            tags = {tag["field_name"] for tag in metric_info.get("tag_list", [])}

        # 添加特殊字段，兼容先前逻辑
        tags.add("target")
        return list(tags)

    @classmethod
    def _bulk_create_metrics(
        cls,
        metrics_dict: Dict,
        need_create_metrics: Union[List, Set],
        group_id: int,
        table_id: str,
        is_auto_discovery: bool,
    ) -> bool:
        """批量创建指标"""
        records = []
        for metric in need_create_metrics:
            metric_info = metrics_dict.get(metric)
            # 如果获取不到指标数据，则跳过
            if not metric_info:
                continue
            tag_list = cls.get_metric_tag_from_metric_info(metric_info)
            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True) and not is_auto_discovery:
                continue
            # 获取结果表
            params = {
                "field_name": metric,
                "group_id": group_id,
                "table_id": f"{table_id.split('.')[0]}.{metric}",
                "tag_list": tag_list,
            }
            logger.info("create ts metric data: %s", json.dumps(params))
            records.append(cls(**params))
        # 开始批量创建
        cls.objects.bulk_create(records, batch_size=BULK_CREATE_BATCH_SIZE)
        return True

    @classmethod
    def _bulk_update_metrics(
        cls, metrics_dict: Dict, need_update_metrics: Union[List, Set], group_id: int, is_auto_discovery: bool
    ):
        """批量更新指标，针对记录仅更新最后更新时间和 tag 字段"""
        qs_objs = filter_model_by_in_page(
            TimeSeriesMetric, "field_name__in", need_update_metrics, other_filter={"group_id": group_id}
        )
        records, white_list_disabled_metric = [], set()
        # 组装更新的数据
        for obj in qs_objs:
            metric = obj.field_name
            metric_info = metrics_dict.get(metric)
            # 如果找不到指标数据，则忽略
            if not metric_info:
                continue
            last_modify_time = make_aware(
                datetime.datetime.fromtimestamp(metric_info.get("last_modify_time", time.time()))
            )
            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True):
                if is_auto_discovery:
                    last_modify_time = make_aware(datetime.datetime(1970, 1, 1))
                else:
                    white_list_disabled_metric.add(metric)
            # 标识是否需要更新
            is_need_update = False
            # 先设置最后更新时间 1 天更新一次，减少对 db 的操作
            if (last_modify_time - obj.last_modify_time).days >= 1:
                is_need_update = True
                obj.last_modify_time = last_modify_time

            # 如果 tag 不一致，则进行更新
            tag_list = cls.get_metric_tag_from_metric_info(metric_info)
            if set(obj.tag_list or []) != set(tag_list):
                is_need_update = True
                obj.tag_list = tag_list

            if is_need_update:
                records.append(obj)
        # 白名单模式，如果存在需要禁用的指标，则需要删除；应该不会太多，直接删除
        if white_list_disabled_metric:
            cls.objects.filter(group_id=group_id, field_name__in=white_list_disabled_metric).delete()
        logger.info("white list disabled metric: %s, group_id: %s", json.dumps(white_list_disabled_metric), group_id)

        # 批量更新指定的字段
        cls.objects.bulk_update(records, ["last_modify_time", "tag_list"], batch_size=BULK_UPDATE_BATCH_SIZE)

    @classmethod
    def bulk_refresh_ts_metrics(
        cls, group_id: int, table_id: str, metric_info_list: List, is_auto_discovery: bool
    ) -> bool:
        """
            更新或创建时序指标数据

            :param group_id: 自定义分组ID
            :param table_id: 结果表
            :param metric_info_list: 具体自定义时序内容信息，[{
                "field_name": "core_file",
                "tag_value_list": {"endpoint": {'last_update_time': 1701438084,
        'values': None},
                "last_modify_time": 1464567890123,
            }, {
                "field_name": "disk_full",
                "tag_list": {"module": {"values": ["foo",]}, "set": {"values": ["foo",]}, "partition": {}}
                "last_modify_time": 1464567890123,
            }]
            :param is_auto_discovery: 指标是否自动发现
            :return: True or raise
        """
        _metrics_dict = {m["field_name"]: m for m in metric_info_list if m.get("field_name")}
        # 获取不存在的指标，然后批量创建
        metrics_by_group_id = cls.objects.filter(group_id=group_id).values_list("field_name", flat=True)
        # 获取需要批量创建的指标
        _metrics = set(_metrics_dict.keys())
        # NOTE: 这里仅针对创建时，推送路由数据
        is_create = False
        need_create_metrics = _metrics - set(metrics_by_group_id)
        # 获取已经存在的指标，然后进行批量更新
        need_update_metrics = _metrics - need_create_metrics
        # 如果存在，则批量创建
        if need_create_metrics:
            is_create = cls._bulk_create_metrics(
                _metrics_dict, need_create_metrics, group_id, table_id, is_auto_discovery
            )
        # 批量更新
        if need_update_metrics:
            cls._bulk_update_metrics(_metrics_dict, need_update_metrics, group_id, is_auto_discovery)

        return is_create

    @classmethod
    def update_metrics(cls, group_id, metric_info_list):
        """
        批量的修改/创建某个自定义时序分组下的metric信息
        :param group_id: 自定义分组ID
        :param metric_info_list: 具体自定义时序内容信息，[{
            "field_name": "core_file",
            "tag_list": {"module": {"values": ["foo",]}, "set": {"values": ["foo",]}, "partition": {}}
            "last_modify_time": 1464567890123,
        }, {
            "field_name": "disk_full",
            "tag_list": {"module": {"values": ["foo",]}, "set": {"values": ["foo",]}, "partition": {}}
            "last_modify_time": 1464567890123,
        }]
        :return: True or raise
        """
        # 0. 判断是否真的存在某个group_id
        if not TimeSeriesGroup.objects.filter(time_series_group_id=group_id).exists():
            logger.info("time_series_group_id->[{}] not exists, nothing will do.".format(group_id))
            raise ValueError(_("自定义时序组ID[{}]不存在，请确认后重试").format(group_id))
        group = TimeSeriesGroup.objects.get(time_series_group_id=group_id)

        # 标识是否有更新
        is_updated = False
        # 是否是自动发现
        is_auto_discovery = group.is_auto_discovery()
        # 1. 遍历所有的事件进行处理，判断是否存在custom_event_id
        # 现有的字段名列表
        field_name_list = []
        # 需要删除的指标（白名单模式下禁用的指标）
        white_list_disabled_metric = []
        for metric_info in metric_info_list:
            # 判断传入数据是否包含 values (tag_value_list/tag_list)
            if "tag_value_list" in metric_info:
                tag_list = list(metric_info["tag_value_list"].keys())
            else:
                tag_list = [tag["field_name"] for tag in metric_info.get("tag_list", [])]

            # 如果存在这个custom_event_id，那么需要进行修改
            try:
                field_name = metric_info["field_name"]
                field_name_list.append(field_name)
            except KeyError as key:
                logger.error("metric_info got bad metric->[%s] which has no key->[%s]", json.dumps(metric_info), key)
                raise ValueError(_("自定义时序列表配置有误，请确认后重试"))

            last_modify_time = make_aware(
                datetime.datetime.fromtimestamp(metric_info.get("last_modify_time", time.time()))
            )

            # NOTE: 维度 [target] 必须存在; 如果不存在时，则需要添加 [target] 维度
            if cls.TARGET_DIMENSION_NAME not in tag_list:
                tag_list.append(cls.TARGET_DIMENSION_NAME)

            created = False
            try:
                # 判断是否已经存在这个指标
                metric_obj = cls.objects.get(field_name=field_name, group_id=group_id)
            except cls.DoesNotExist:
                # 如果不存在指标，创建一个新的
                metric_obj = cls.objects.create(field_name=field_name, group_id=group_id)
                created = True
                logger.info("new metric_obj->[{}] is create for group_id->[{}].".format(metric_obj, group_id))
                # NOTE: 如果有新增, 则标识要更新，删除时，可以不立即更新
                is_updated = True

            # 生成/更新真实表id
            database_name = group.table_id.split(".")[0]
            metric_obj.table_id = f"{database_name}.{metric_obj.field_name}"

            if created or last_modify_time > metric_obj.last_modify_time:
                logger.info(
                    "time_series_group_id->[{}],field_name->[{}] will change index from->[{}] to [{}]".format(
                        group_id, metric_obj.field_name, metric_obj.last_index, last_modify_time
                    )
                )
                # 如果指标被禁用
                if not metric_info.get("is_active", True):
                    # 黑名单模式下，设置过期时间为 1970
                    if is_auto_discovery:
                        metric_obj.last_modify_time = datetime.datetime(1970, 1, 1)
                    else:
                        white_list_disabled_metric.append(metric_obj.field_id)

                # 有效期内的维度直接覆盖
                # 判断是否需要保存操作
                need_save_op = False
                if set(metric_obj.tag_list or []) != set(tag_list):
                    metric_obj.tag_list = tag_list
                    need_save_op = True
                # TODO: 还需要继续优化，先设置最后更新时间 1 天更新一次，减少对 db 的操作
                if (last_modify_time - metric_obj.last_modify_time).days >= 1:
                    metric_obj.last_modify_time = last_modify_time
                    need_save_op = True
                if need_save_op:
                    metric_obj.save()

                # 后续可以在此处追加其他修改内容
                logger.info(
                    "time_series_group_id->[{}] has update field_name->[{}] all tags->[{}]".format(
                        group_id, metric_obj.field_name, metric_obj.tag_list
                    )
                )

        if white_list_disabled_metric:
            cls.objects.filter(group_id=group_id, field_id__in=white_list_disabled_metric).delete()

        return is_updated

    @cached_property
    def group(self):
        """
        对象获得group的缓存
        :return:
        """
        return TimeSeriesGroup.objects.get(time_series_group_id=self.group_id)

    def to_json(self):
        return {"field_id": self.field_id, "field_name": self.field_name, "tag_list": self.tag_list}

    def to_metric_info_with_label(self, group: TimeSeriesGroup, field_map=None):
        """
         {
            "field_name": "mem_usage",
            "description": "mem_usage_2",
            "unit": "M",
            "type": "double",
            "label": "service-k8s",
            "use_group": "container_performance",
            "tag_list": [
                {
                    "field_name": "test_name",
                    "description": "test_name_2",
                    "unit": "M",
                    "type": "double",
                }
            ]
        }
        """
        orm_field_map = field_map or {}
        if not orm_field_map:
            for orm_field in (
                ResultTableField.objects.filter(table_id=group.table_id).values(*self.ORM_FIELD_NAMES).iterator()
            ):
                orm_field_map[orm_field["field_name"]] = orm_field

        result = {
            "field_name": self.field_name,
            "metric_display_name": "",
            "unit": "",
            "type": "double",
            "label": self.label,
            "tag_list": [],
            "tag_value_list": [],
        }

        # 填充指标信息
        if self.field_name not in orm_field_map:
            logger.warning(
                f"metric->[{self.field_name}] is not exists in table->[{group.table_id}] "
                f"not metrics info will return."
            )
            return None

        orm_field = orm_field_map[self.field_name]
        result["table_id"] = self.table_id
        result["description"] = orm_field["description"]
        result["unit"] = orm_field["unit"]
        result["type"] = orm_field["field_type"]

        # 遍历维度填充维度信息
        for tag in self.tag_list:
            item = {"field_name": tag, "description": ""}
            # 如果维度不存在了，则表示字段可能已经被删除了
            if tag in orm_field_map:
                orm_field = orm_field_map[tag]
                item["description"] = orm_field["description"]
                item["unit"] = orm_field["unit"]
                item["type"] = orm_field["field_type"]

            result["tag_list"].append(item)

        return result

    def to_metric_info(self, field_map=None, group=None):
        """
         {
            "field_name": "mem_usage",
            "description": "mem_usage_2",
            "unit": "M",
            "type": "double",
            "tag_list": [
                {
                    "field_name": "test_name",
                    "description": "test_name_2",
                    "unit": "M",
                    "type": "double",
                }
            ]
        }
        """
        if not group:
            group = self.group
        orm_field_map = field_map or {}
        if not orm_field_map:
            for orm_field in (
                ResultTableField.objects.filter(table_id=group.table_id).values(*self.ORM_FIELD_NAMES).iterator()
            ):
                orm_field_map[orm_field["field_name"]] = orm_field

        result = {
            "field_name": self.field_name,
            "metric_display_name": "",
            "unit": "",
            "type": "double",
            "tag_list": [],
        }

        # 填充指标信息
        if self.field_name not in orm_field_map:
            logger.warning(
                f"metric->[{self.field_name}] is not exists in table->[{group.table_id}] "
                f"not metrics info will return."
            )
            return None

        orm_field = orm_field_map[self.field_name]
        result["table_id"] = self.table_id
        result["description"] = orm_field["description"]
        result["unit"] = orm_field["unit"]
        result["type"] = orm_field["field_type"]
        result["is_disabled"] = orm_field["is_disabled"]

        # 遍历维度填充维度信息
        for tag in self.tag_list:
            item = {"field_name": tag, "description": ""}
            # 如果维度不存在了，则表示字段可能已经被删除了
            if tag in orm_field_map:
                orm_field = orm_field_map[tag]
                item["description"] = orm_field["description"]
                item["unit"] = orm_field["unit"]
                item["type"] = orm_field["field_type"]

            result["tag_list"].append(item)

        return result


class TimeSeriesTagManager(models.Manager):
    """自定义时序标签(维度)管理器"""

    def create_by_infos(self, metric_obj: TimeSeriesMetric, tag_infos: Dict[str, dict]) -> List["TimeSeriesTag"]:
        """通过关键信息批量构建标签实例"""
        _ins = []
        for tag_name, tag_info in tag_infos.items():
            (
                tag,
                created,
            ) = self.update_or_create(
                group_id=metric_obj.group_id,
                metric_id=metric_obj.pk,
                name=tag_name,
                defaults={"values": tag_info.get("values", [])},
            )
            if created:
                logger.debug("tag <%s> has been created", tag_name)

            _ins.append(tag)

        logger.debug("metric <%s> already updated all tags", metric_obj.field_name)
        return _ins


class TimeSeriesTag(models.Model):
    """自定义时序标签(维度)"""

    group_id = models.IntegerField(verbose_name="自定义时序所属分组ID")
    metric_id = models.IntegerField(verbose_name="自定义时序Schema ID")
    name = models.CharField(verbose_name="标签(维度)", max_length=128)
    values = JsonField(verbose_name="维度值列表", default=[])

    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)

    objects = TimeSeriesTagManager()

    class Meta:
        unique_together = ("group_id", "metric_id", "name")

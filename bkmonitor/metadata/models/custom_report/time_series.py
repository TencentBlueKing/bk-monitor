"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
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
import re
import time

from django.conf import settings
from django.db import models
from django.db import utils as django_db_utils
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.timezone import make_aware
from django.utils.timezone import now as tz_now
from django.utils.translation import gettext as _
from django.db.models import Q

from bkmonitor.utils.db.fields import JsonField
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata import config
from metadata.models.constants import (
    BULK_CREATE_BATCH_SIZE,
    BULK_UPDATE_BATCH_SIZE,
    DB_DUPLICATE_ID,
    DataIdCreatedFromSystem,
)
from metadata.models.data_source import DataSource
from metadata.models.result_table import (
    ResultTable,
    ResultTableField,
    ResultTableOption,
)
from metadata.models.storage import ClusterInfo
from metadata.utils.db import filter_model_by_in_page
from metadata.utils.redis_tools import RedisTools
from utils.redis_client import RedisClient

from .base import CustomGroupBase

logger = logging.getLogger("metadata")


class TimeSeriesGroup(CustomGroupBase):
    """
    自定义时序数据源

    tips: 历史已将表取名为 Group 后缀，这里暂时保留不做变更，实际的指标分组是记录在 TimeSeriesScope 表中

    整体的逻辑关系如下：

    TimeSeriesGroup  ->  TimeSeriesScope ->  TimeSeriesMetric
    数据源                指标分组              指标
    """

    time_series_group_id = models.AutoField(verbose_name="分组ID", primary_key=True)
    time_series_group_name = models.CharField(verbose_name="自定义时序分组名", max_length=255)
    # 指标分组的维度key配置，例如 ["service_name", "scope_name"]
    metric_group_dimensions = models.JSONField(verbose_name="指标分组的维度key配置", default=[])

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

    FIELD_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")

    # 组合一个默认的table_id
    @staticmethod
    def make_table_id(bk_biz_id, bk_data_id, table_name=None, bk_tenant_id=DEFAULT_TENANT_ID):
        if settings.ENABLE_MULTI_TENANT_MODE:  # 若启用多租户模式,则在结果表前拼接租户ID
            logger.info("make_table_id: enable multi-tenant mode")
            if str(bk_biz_id) != "0":
                return f"{bk_tenant_id}_{bk_biz_id}_bkmonitor_time_series_{bk_data_id}.{TimeSeriesGroup.DEFAULT_MEASUREMENT}"
            return f"{bk_tenant_id}_bkmonitor_time_series_{bk_data_id}.{TimeSeriesGroup.DEFAULT_MEASUREMENT}"
        else:
            if str(bk_biz_id) != "0":
                return f"{bk_biz_id}_bkmonitor_time_series_{bk_data_id}.{TimeSeriesGroup.DEFAULT_MEASUREMENT}"

            return f"bkmonitor_time_series_{bk_data_id}.{TimeSeriesGroup.DEFAULT_MEASUREMENT}"

    def make_metric_table_id(self, field_name):
        # 结果表是bk_k8s开头，保证这些的结果表和用户的结果表是区别开的
        if settings.ENABLE_MULTI_TENANT_MODE:  # 若启用多租户模式,则在结果表前拼接租户ID
            logger.info("make_metric_table_id: enable multi-tenant mode")
            return f"bk_k8s_{self.bk_tenant_id}_{self.time_series_group_name}_{field_name}"
        return f"bk_k8s_{self.time_series_group_name}_{field_name}"

    @atomic(config.DATABASE_CONNECTION_NAME)
    def update_tag_fields(
        self, table_id: str, tag_list: list[tuple[str, str]], update_description: bool = False
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
                    bk_tenant_id=self.bk_tenant_id,
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
                    bk_tenant_id=self.bk_tenant_id,
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
            bk_tenant_id=self.bk_tenant_id,
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
            table_id=self.table_id, bk_tenant_id=self.bk_tenant_id, name="enable_field_black_list", value="false"
        ).exists()

    def _refine_metric_tags(self, metric_info: list) -> dict:
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
                    if not tag.get("field_name") or tag["field_name"] in tag_dict:
                        continue
                    tag_dict[tag["field_name"]] = tag.get("description", "")

        return {
            "is_update_description": is_update_description,
            "metric_dict": metric_dict,
            "tag_dict": tag_dict,
        }

    def _bulk_create_or_update_metrics(
        self,
        table_id: str,
        metric_dict: dict,
        need_create_metrics: set,
        need_update_metrics: set,
    ):
        """批量创建或更新字段"""
        logger.info("bulk create or update rt metrics")
        create_records = []
        for metric in need_create_metrics:
            create_records.append(
                ResultTableField(
                    table_id=table_id,
                    field_name=metric,
                    bk_tenant_id=self.bk_tenant_id,
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
            other_filter={
                "table_id": table_id,
                "tag": ResultTableField.FIELD_TAG_METRIC,
                "bk_tenant_id": self.bk_tenant_id,
            },
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
        tag_dict: dict,
        need_create_tags: set,
        need_update_tags: set,
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
                    bk_tenant_id=self.bk_tenant_id,
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
                "bk_tenant_id": self.bk_tenant_id,
            },
        )
        for obj in qs_objs:
            expect_tag_description = tag_dict.get(obj.field_name, "")
            if obj.description != expect_tag_description and update_description:
                obj.description = expect_tag_description
                update_records.append(obj)
        ResultTableField.objects.bulk_update(update_records, ["description"], batch_size=BULK_UPDATE_BATCH_SIZE)
        logger.info("batch update tag successfully")

    def bulk_refresh_rt_fields(self, table_id: str, metric_info: list):
        """批量刷新结果表打平的指标和维度"""
        # 创建或更新
        metric_tag_info = self._refine_metric_tags(metric_info)
        # 通过结果表过滤到到指标和维度
        # NOTE: 因为 `ResultTableField` 字段是打平的，因此，需要排除已经存在的，以已经存在的为准
        exist_fields = set(
            ResultTableField.objects.filter(table_id=table_id, bk_tenant_id=self.bk_tenant_id).values_list(
                "field_name", flat=True
            )
        )
        # 过滤需要创建或更新的指标
        metric_dict = metric_tag_info["metric_dict"]
        metric_set = set(metric_dict.keys())
        need_create_metrics = metric_set - exist_fields
        # 获取已经存在的指标，然后进行批量更新
        need_update_metrics = metric_set - need_create_metrics
        self._bulk_create_or_update_metrics(table_id, metric_dict, need_create_metrics, need_update_metrics)
        # 过滤需要创建或更新的维度
        tag_dict = metric_tag_info["tag_dict"]
        tag_set = set(tag_dict.keys())
        # 需要创建的 tag 需要再剔除和指标重复的字段名称
        need_create_tags = tag_set - exist_fields - need_create_metrics
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
        # 判断是否真的存在某个group_id
        group_id = self.time_series_group_id
        try:
            group = TimeSeriesGroup.objects.get(time_series_group_id=group_id)
        except TimeSeriesGroup.DoesNotExist:
            logger.info("time_series_group_id->[%s] not exists, nothing will do.", group_id)
            raise ValueError(f"ts group id: {group_id} not found")
        # 刷新 ts 中指标和维度
        is_updated = TimeSeriesMetric.bulk_refresh_ts_metrics(
            group_id, group.table_id, metric_info, group.is_auto_discovery()
        )
        self.bulk_refresh_rt_fields(group.table_id, metric_info)
        return is_updated

    @property
    def datasource_options(self):
        return [
            {"name": "metrics_report_path", "value": self.metric_consul_path},
            {"name": "disable_metric_cutter", "value": "true"},
        ]

    @property
    def data_source(self):
        """
        返回一个结果表的数据源
        :return: DataSource object
        """
        return DataSource.objects.get(bk_data_id=self.bk_data_id)

    @property
    def metric_consul_path(self):
        return f"{config.CONSUL_PATH}/influxdb_metrics/{self.bk_data_id}/time_series_metric"

    def get_metric_from_bkdata(self) -> list:
        """通过bkdata获取数据信息"""

        # TODO: 多租户 BkBase关联信息
        from metadata.models import AccessVMRecord, BCSClusterInfo

        default_resp = []
        try:
            vm_rt = AccessVMRecord.objects.get(result_table_id=self.table_id).vm_result_table_id
        except AccessVMRecord.DoesNotExist:
            return default_resp
        # 获取指标
        params = {
            "bk_tenant_id": self.bk_tenant_id,
            "storage": config.VM_STORAGE_TYPE,
            "result_table_id": vm_rt,
            "values": BCSClusterInfo.DEFAULT_SERVICE_MONITOR_DIMENSION_TERM,
        }
        # 如果是 APM 场景，使用 v2 版本的 API
        if self.metric_group_dimensions:
            params["version"] = "v2"

        data = api.bkdata.query_metric_and_dimension(**params) or []
        if not data:
            return default_resp
        # 组装数据
        metric_dimension = data["metrics"]
        if not metric_dimension:
            return default_resp
        ret_data = []
        for md in metric_dimension:
            # 过滤非法的指标名
            if not self.FIELD_NAME_REGEX.match(md["name"]):
                logger.warning("invalid metric name: %s", md["name"])
                continue

            # 兼容旧的 dimensions 格式
            if "dimensions" in md:
                tag_value_list = {}
                for d in md["dimensions"]:
                    tag_value_list[d["name"]] = {
                        "last_update_time": d["update_time"],
                        "values": [v["value"] for v in d["values"]],
                    }
                item = {
                    "field_name": md["name"],
                    "last_modify_time": md["update_time"] // 1000,
                    "tag_value_list": tag_value_list,
                }
            # 处理新的 group_dimensions 格式
            elif "group_dimensions" in md:
                # 收集所有维度组合中的维度名称
                all_dimensions = set()
                latest_update_time = 0
                # 保存分组信息
                group_dimensions_info = {}
                # 构造 tag_value_list，用于存储每个维度的更新时间和值列表
                tag_value_list = {}

                for group_key, group_info in md["group_dimensions"].items():
                    dimensions = group_info.get("dimensions", [])
                    all_dimensions.update(dimensions)
                    # 获取最新的更新时间
                    update_time = group_info.get("update_time", 0)
                    if update_time > latest_update_time:
                        latest_update_time = update_time
                    # 保存分组信息
                    group_dimensions_info[group_key] = {
                        "dimensions": dimensions,
                        "update_time": update_time,
                    }

                    for dim_name in dimensions:
                        if dim_name not in tag_value_list:
                            # 使用默认值：空列表表示该维度存在但暂无具体值
                            tag_value_list[dim_name] = {
                                "last_update_time": update_time,
                                "values": [],
                            }
                        else:
                            # 如果维度已存在，更新为最新的时间和值
                            if update_time > tag_value_list[dim_name]["last_update_time"]:
                                tag_value_list[dim_name]["last_update_time"] = update_time

                item = {
                    "field_name": md["name"],
                    "last_modify_time": latest_update_time // 1000,
                    "tag_value_list": tag_value_list,
                    "group_dimensions": group_dimensions_info,  # 添加分组信息
                }
            else:
                logger.warning("metric %s has no dimensions or group_dimensions", md["name"])
                continue

            ret_data.append(item)
        return ret_data

    def get_metrics_from_redis(self, expired_time: int | None = settings.TIME_SERIES_METRIC_EXPIRED_SECONDS):
        """从 redis 中获取数据

        其中，redis 中数据有 transfer 上报
        而从 bkdata 获取指标数据有两个版本，对于 v2 版本，仅有 update_time_series_metrics() 方法对其兼容
        """
        # 从 bkdata 获取指标数据
        data = RedisTools.get_list(config.METADATA_RESULT_TABLE_WHITE_LIST)
        # 默认开启单指标单表后，需要根据数据源的来源决定从哪里获取指标数据（redis/bkdata）
        if self.table_id in data or self.data_source.created_from == DataIdCreatedFromSystem.BKDATA.value:
            return self.get_metric_from_bkdata()

        # 获取redis中数据
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
                metrics_with_scores: list[tuple[bytes, float]] = client.zrangebyscore(
                    **metrics_filter_params, start=fetch_step * i, num=fetch_step, withscores=True
                )
            except Exception:
                logger.exception("failed to get metrics from storage, filter params: %s", metrics_filter_params)
                # metrics 可能存在大批量内容，可容忍某一步出错
                continue

            # 1. 获取当前这批 metrics 的 dimensions 信息
            try:
                dimensions_list: list[bytes] = client.hmget(metric_dimensions_key, [x[0] for x in metrics_with_scores])
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
                if isinstance(field_name, bytes):
                    field_name = field_name.decode("utf-8")

                # 过滤非法的指标名
                if not self.FIELD_NAME_REGEX.match(field_name):
                    logger.warning("invalid metric name: %s", field_name)
                    continue

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
            f"going to delete all metrics->[{metrics_queryset.count()}] for {self.__class__.__name__}->[{self.time_series_group_id}] deletion."
        )
        metrics_queryset.delete()
        logger.info(f"all metrics about {self.__class__.__name__}->[{self.time_series_group_id}] is deleted.")

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_time_series_group(
        cls,
        bk_data_id,
        bk_biz_id,
        time_series_group_name,
        label,
        operator,
        bk_tenant_id: str,
        metric_info_list=None,
        table_id=None,
        is_split_measurement=True,
        is_builtin=False,
        default_storage_config=None,
        additional_options: dict | None = None,
        data_label: str | None = None,
        metric_group_dimensions: list[str] | None = None,
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
        :param is_builtin: 是否内置
        :param default_storage_config: 默认存储配置
        :param additional_options: 附带创建的 ResultTableOption
        :param data_label: 数据标签
        :param bk_tenant_id: 租户ID
        :param metric_group_dimensions: 分组维度信息
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
            is_builtin=is_builtin,
            is_split_measurement=is_split_measurement,
            default_storage_config=default_storage_config,
            additional_options=additional_options,
            data_label=data_label,
            bk_tenant_id=bk_tenant_id,
            metric_group_dimensions=metric_group_dimensions,
        )

        # 需要刷新一次外部依赖的consul，触发transfer更新
        from metadata.models import DataSource

        DataSource.objects.get(bk_data_id=bk_data_id).refresh_consul_config()

        return custom_group

    @classmethod
    def _post_process_create(cls, custom_group, kwargs):
        # None 和 [] 都不保存
        if kwargs.get("metric_group_dimensions"):
            custom_group.metric_group_dimensions = kwargs["metric_group_dimensions"]
            custom_group.save()

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
        data_label: str | None = None,
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
            "bk_tenant_id": self.bk_tenant_id,
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
            "bk_tenant_id": self.bk_tenant_id,
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

    def _filter_metric_by_dimension(self, metrics: list, dimension_name: str, dimension_value: str) -> tuple[set, set]:
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

    def get_ts_metrics_by_dimension(self, dimension_name: str, dimension_value: str) -> list:
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
            ResultTableField.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
            .values(*TimeSeriesMetric.ORM_FIELD_NAMES)
            .iterator()
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
            ResultTableField.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id)
            .values(*TimeSeriesMetric.ORM_FIELD_NAMES)
            .iterator()
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
            ResultTable.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).update(
                is_deleted=True, is_enable=False
            )
            logger.info(
                "ts group->[%s] table_id->[%s] of bk_tenant_id->[%s] is set to disabled now.",
                self.custom_group_name,
                self.table_id,
                self.bk_tenant_id,
            )

            return True

        # 2. 拆分结果表的，先遍历所有的metric
        # TODO 这里需要调整,因为实际拆分结果表也不会生成新的table_id了，对应的应该在TimeSeriesMetric上增加状态位

        logger.info("ts group->[%s] is split measurement will disable all tables.", self.custom_group_name)
        for metric_group in TimeSeriesMetric.objects.filter(group_id=self.custom_group_id):
            # 2.1 每个metric拼接出结果表名
            table_id = self.make_metric_table_id(metric_group.field_name)
            # 2.2 设置该结果表启用
            ResultTable.objects.filter(table_id=self.table_id, bk_tenant_id=self.bk_tenant_id).update(
                is_deleted=True, is_enable=False
            )

            logger.info(
                "ts group->[%s] of bk_tenant_id->[%s]per table_id->[%s] is set to disabled now.",
                self.custom_group_name,
                self.bk_tenant_id,
                table_id,
            )

        logger.info(
            "ts group->[%s] of bk_tenant_id->[%s] all table_id is set to disabled now.",
            self.custom_group_name,
            self.bk_tenant_id,
        )
        return True


class TimeSeriesScope(models.Model):
    """
    自定义时序指标分组
    """

    # todo hhh 补充是否开启自动匹配正则的开关
    DimensionConfigFields = [
        "desc",  # 字段描述
        "common",  # 常用维度
        "hidden",  # 显隐
    ]

    # 创建来源选项
    CREATE_FROM_DATA = "data"  # 数据自动创建
    CREATE_FROM_USER = "user"  # 用户手动创建
    CREATE_FROM_CHOICES = [
        (CREATE_FROM_DATA, "数据自动创建"),
        (CREATE_FROM_USER, "用户手动创建"),
    ]

    # scope_name 字段验证规则：只允许中文、英文、数字、下划线
    SCOPE_NAME_REGEX = re.compile(r"^[\u4e00-\u9fa5a-zA-Z0-9_]+$")

    # group_id 来自于 TimeSeriesGroup.time_series_group_id，关联数据源
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID", db_index=True)

    scope_name = models.CharField(verbose_name="指标分组名", max_length=255, db_collation="utf8_bin")

    # 维度字段配置，可配置的选项，需要在 DimensionConfigFields 中定义
    dimension_config = models.JSONField(verbose_name="分组下的维度配置", default={})

    manual_list = models.JSONField("手动分组的指标列表", default=[])
    auto_rules = models.JSONField("自动分组的匹配规则列表", default=[])

    # 创建来源：data-数据自动创建，user-用户手动创建
    create_from = models.CharField(
        verbose_name="创建来源",
        max_length=10,
        choices=CREATE_FROM_CHOICES,
        default=CREATE_FROM_DATA,
        db_index=True,
    )

    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)

    class Meta:
        unique_together = ("group_id", "scope_name")
        verbose_name = "自定义时序数据分组记录"
        verbose_name_plural = "自定义时序数据分组记录表"

    def is_create_from_data(self):
        """检查是否允许编辑"""
        return self.create_from == TimeSeriesScope.CREATE_FROM_DATA

    @staticmethod
    def _is_default_scope(scope_name: str) -> bool:
        """判断 scope_name 是否为 default 分组
        :return: 如果是 default 分组返回 True，否则返回 False
        """
        return scope_name == TimeSeriesMetric.DEFAULT_SCOPE or scope_name.endswith(
            f"||{TimeSeriesMetric.DEFAULT_SCOPE}"
        )

    @classmethod
    def _validate_scope_name(cls, scope_name: str):
        """验证 scope_name 格式是否合法

        :param scope_name: 指标分组名称
        :raises ValueError: 如果格式不合法
        """
        if not scope_name:
            raise ValueError(_("指标分组名不能为空"))

        if not cls.SCOPE_NAME_REGEX.match(scope_name):
            raise ValueError(_("指标分组名只能包含中文、英文、数字和下划线"))

    @classmethod
    def _get_final_scope_name(cls, scope_data: dict) -> str:
        """获取最终的 scope_name

        对于 APM 场景，scope_name 的格式为 {service_name}||{scope_name}
        如果 scope_data 中有 service_name，则使用 APM 格式
        """
        scope_name = scope_data.get("scope_name")
        service_name = scope_data.get("service_name")

        cls._validate_scope_name(scope_name)
        # APM 场景：如果有 service_name，使用 APM 格式
        if service_name:
            return f"{service_name}||{scope_name}"

        return scope_name

    def update_matched_dimension_config(self, delete_unmatched_dimensions=False):
        """
        更新维度配置

        创建维度配置：
        1. dimension_config 视为 X
        2. manual_list 视为 Y（从 manual_list 中的指标获取维度）
        3. 最终维度集合是 X | Y

        更新维度配置：
        1. 先将旧 dimension_config 用传递进来的 dimension_config 进行覆盖，视为 X
        2. manual_list 视为 Y
        3. 当 delete_unmatched_dimensions 为 true 则最终集合为 (X & Y) | Y，反之 X | Y

        :param delete_unmatched_dimensions: 是否删除不再匹配的维度配置，默认为 False
        """
        # 1. 获取当前分组下已有的维度配置（X）
        current_dimension_config = self.dimension_config or {}

        # 2. 根据 manual_list 获取匹配的指标列表的 tag_list 做并集（Y）
        # 注意：只使用 manual_list，不使用 auto_rules
        matched_metric_dimensions = set()

        if self.manual_list:
            # 查询该分组下可操作的指标
            scope_filter = TimeSeriesMetric.get_default_scope_metric_filter(self.scope_name)
            available_metrics = TimeSeriesMetric.objects.filter(group_id=self.group_id).filter(scope_filter)

            # 遍历所有指标，找出在 manual_list 中的指标的维度
            for metric in available_metrics:
                # 判断指标是否在 manual_list 中
                if metric.field_name in self.manual_list:
                    # 将该指标的所有维度加入到集合中
                    if metric.tag_list:
                        matched_metric_dimensions.update(metric.tag_list)

        # 3. 计算新的维度配置
        if delete_unmatched_dimensions:
            # (X & Y) | Y = Y（只保留 Y 中的维度）
            updated_dimension_config = {
                dimension_name: current_dimension_config.get(dimension_name, {})
                for dimension_name in matched_metric_dimensions
            }
        else:
            # X | Y（保留 X 中的所有配置，并添加 Y 中的新维度）
            updated_dimension_config = current_dimension_config.copy()
            for dimension_name in matched_metric_dimensions:
                updated_dimension_config.setdefault(dimension_name, {})

        # 更新 dimension_config
        self.dimension_config = updated_dimension_config

    def _match_metric(self, field_name: str) -> bool:
        """判断指标名称是否匹配 manual_list 或 auto_rules"""
        import re

        # 手动分组：直接匹配指标名称
        if self.manual_list and field_name in self.manual_list:
            return True

        # 自动分组：使用正则表达式匹配
        if self.auto_rules:
            for rule in self.auto_rules:
                try:
                    if re.match(rule, field_name):
                        return True
                except re.error:
                    logger.warning(
                        "Invalid regex pattern in auto_rules: %s for group_id: %s, scope_name: %s",
                        rule,
                        self.group_id,
                        self.scope_name,
                    )
                    continue
        return False

    @classmethod
    def get_ungrouped_metrics_qs(cls, group_id: int, scope_name: str):
        """获取未分组下的指标

        未分组指标 = 该 group_id default 数据分组的指标 - 该 group_id 下所有 manual_list 的并集

        :param group_id: 自定义时序数据源ID
        :param scope_name: 指标分组名，用于确定 default 数据分组的 scope
        :return: 包含未分组指标的 QuerySet
        """
        # 1. 查询所有 manual_list 的并集
        all_manual_lists = cls.objects.filter(group_id=group_id).values_list("manual_list", flat=True)
        all_manual_metrics = set()
        for manual_list in all_manual_lists:
            if manual_list:
                all_manual_metrics.update(manual_list)

        # 2. 查询 default 数据分组中不在 manual_list 中的指标（一次查询完成）
        scope_filter = TimeSeriesMetric.get_default_scope_metric_filter(scope_name=scope_name)
        queryset = TimeSeriesMetric.objects.filter(group_id=group_id).filter(scope_filter)
        return queryset.exclude(field_name__in=all_manual_metrics)

    @classmethod
    def _validate_manual_list_metrics_in_default_scope(
        cls, group_id: int, manual_list: list | None, old_manual_list: list | None = None, scope_name: str | None = None
    ):
        """校验 manual_list 中的指标是否都在 default 数据分组

        对于新增的指标，需要确保它们在未分组下的指标列表中

        :param group_id: 自定义时序数据源ID
        :param manual_list: 新的 manual_list
        :param old_manual_list: 旧的 manual_list，用于计算新增的指标。如果为 None，则视为创建场景（旧列表为空）
        :param scope_name: 指标分组名，用于确定 default 数据分组的 scope
        """
        if not manual_list:
            return

        # 计算新增的指标
        added_metrics = set(manual_list) - set(old_manual_list or [])
        if not added_metrics:
            return

        # 检查新增的指标是否在未分组列表中
        ungrouped_metric_names = set(
            cls.get_ungrouped_metrics_qs(group_id=group_id, scope_name=scope_name).values_list("field_name", flat=True)
        )
        invalid_added_metrics = added_metrics - ungrouped_metric_names

        if invalid_added_metrics:
            raise ValueError(
                _("新增的指标不在未分组列表中，可能已被其他分组使用: group_id={}, invalid_added_metrics={}").format(
                    group_id, list(invalid_added_metrics)
                )
            )

    @classmethod
    def bulk_ensure_or_merge_scopes(
        cls,
        group_id: int,
        scope_dimensions_map: dict,
    ):
        """批量确保 TimeSeriesScope 记录存在，如果存在则合并维度配置

        此方法用于 metric 批量创建/更新场景，批量确保 scope 存在并合并

        :param group_id: 自定义分组ID
        :param scope_dimensions_map: scope 名称到维度列表的映射字典，格式: {scope_name: [dimension1, dimension2, ...]}
        """
        if not scope_dimensions_map:
            return

        # 过滤掉 default 分组，不允许创建和更新 default 分组（包括 "default" 和以 "||default" 结尾的分组）
        scope_dimensions_map = {
            scope_name: dimensions
            for scope_name, dimensions in scope_dimensions_map.items()
            if not cls._is_default_scope(scope_name)
        }

        if not scope_dimensions_map:
            return

        # 获取所有 scope_name 列表
        scope_names = list(scope_dimensions_map.keys())

        # 一次性查询所有相关的 scope 记录
        existing_scopes = {
            scope.scope_name: scope for scope in cls.objects.filter(group_id=group_id, scope_name__in=scope_names)
        }

        # 准备批量更新和创建的记录
        scopes_to_update = []
        scopes_to_create = []

        for scope_name, dimensions in scope_dimensions_map.items():
            if scope_name in existing_scopes:
                # 记录已存在，合并维度配置（添加新维度，保留已有配置）
                scope = existing_scopes[scope_name]
                existing_config = scope.dimension_config or {}
                for dim in dimensions:
                    existing_config.setdefault(dim, {})
                scope.dimension_config = existing_config
                # 始终使用数据分组
                scope.create_from = cls.CREATE_FROM_DATA
                scopes_to_update.append(scope)
            else:
                # 记录不存在，准备创建新记录
                dimension_config = {dim: {} for dim in dimensions}
                scopes_to_create.append(
                    cls(
                        group_id=group_id,
                        scope_name=scope_name,
                        dimension_config=dimension_config,
                        manual_list=[],
                        auto_rules=[],
                        create_from=cls.CREATE_FROM_DATA,
                    )
                )

        # 批量更新已存在的记录
        if scopes_to_update:
            cls.objects.bulk_update(
                scopes_to_update, ["dimension_config", "create_from"], batch_size=BULK_UPDATE_BATCH_SIZE
            )

        # 批量创建新记录
        if scopes_to_create:
            cls.objects.bulk_create(scopes_to_create, batch_size=BULK_CREATE_BATCH_SIZE)

    @classmethod
    def _common_check_scopes(cls, bk_tenant_id, scopes):
        # 验证所有 group_id 是否存在且属于当前租户
        group_ids = {scope["group_id"] for scope in scopes}
        valid_groups = set(
            TimeSeriesGroup.objects.filter(
                time_series_group_id__in=group_ids, bk_tenant_id=bk_tenant_id, is_delete=False
            ).values_list("time_series_group_id", flat=True)
        )
        invalid_group_ids = group_ids - valid_groups
        if invalid_group_ids:
            raise ValueError(_("自定义时序分组不存在，请确认后重试: group_ids={}").format(invalid_group_ids))

    @classmethod
    def _check_scopes_for_create(cls, bk_tenant_id: str, scopes: list[dict]):
        """检查批量创建的分组数据

        :param bk_tenant_id: 租户ID
        :param scopes: 批量创建的分组列表
        """
        cls._common_check_scopes(bk_tenant_id, scopes)

        # 1.1 检查是否有重复的 scope_name
        final_scope_names = []
        scope_keys = []
        for scope_data in scopes:
            try:
                final_scope_name = cls._get_final_scope_name(scope_data)
            except ValueError as e:
                raise ValueError(_("指标分组名[{}]格式不合法: {}").format(scope_data["scope_name"], str(e)))
            final_scope_names.append(final_scope_name)
            scope_keys.append((scope_data["group_id"], final_scope_name))

        group_ids = {scope["group_id"] for scope in scopes}
        existing_scopes = {
            (s.group_id, s.scope_name): s
            for s in cls.objects.filter(group_id__in=group_ids, scope_name__in=final_scope_names)
        }
        duplicate_scopes = []
        for scope_key in scope_keys:
            if scope_key in existing_scopes:
                duplicate_scopes.append(f"{scope_key[0]}:{scope_key[1]}")
        if duplicate_scopes:
            raise ValueError(_("指标分组名已存在，请确认后重试: {}").format(", ".join(duplicate_scopes)))

        # 1.3 检查批次内部是否有重复的 scope_name（同一 group_id 下）
        # 构建批次内的最终 scope_name 映射：{(group_id, final_scope_name): [index1, index2, ...]}
        batch_scope_names = {}
        for idx, scope_key in enumerate(scope_keys):
            batch_scope_names.setdefault(scope_key, []).append(idx)

        # 检查批次内是否有重复
        for (group_id, scope_name), indices in batch_scope_names.items():
            if len(indices) > 1:
                raise ValueError(
                    _("批次内存在重复的分组名: group_id={}, scope_name={}, 位置索引={}").format(
                        group_id, scope_name, ", ".join(map(str, indices))
                    )
                )

        # 1.4 校验同一批次内的 manual_list 是否有重复
        batch_manual_list_metrics = {}  # {metric_name: [(group_id, scope_name, idx), ...]}
        for idx, scope_data in enumerate(scopes):
            manual_list = scope_data.get("manual_list")
            if manual_list:
                final_scope_name = cls._get_final_scope_name(scope_data)
                group_id = scope_data["group_id"]
                for metric in manual_list:
                    batch_manual_list_metrics.setdefault(metric, []).append((group_id, final_scope_name, idx))

        # 检查批次内是否有重复的指标
        for metric, locations in batch_manual_list_metrics.items():
            if len(locations) > 1:
                location_strs = [f"group_id={loc[0]}, scope_name={loc[1]}, 位置索引={loc[2]}" for loc in locations]
                raise ValueError(
                    _("批次内存在重复的指标: metric={}, 出现位置=[{}]").format(metric, "; ".join(location_strs))
                )

        # 1.5 校验 manual_list 中的指标是否都在 default 数据分组
        for scope_data in scopes:
            manual_list = scope_data.get("manual_list")
            if manual_list is not None:
                # 创建场景，没有旧的 manual_list
                final_scope_name = cls._get_final_scope_name(scope_data)
                cls._validate_manual_list_metrics_in_default_scope(
                    group_id=scope_data["group_id"],
                    manual_list=manual_list,
                    old_manual_list=None,
                    scope_name=final_scope_name,
                )

    @classmethod
    def _create_scope_data(cls, scopes: list[dict]) -> dict:
        """创建分组数据

        :param scopes: 批量创建的分组列表
        :return: 创建的分组字典 {(group_id, scope_name): scope_obj}
        """
        # 2.1 批量创建新记录
        scopes_to_create = []
        final_scope_names = []
        for scope_data in scopes:
            final_scope_name = cls._get_final_scope_name(scope_data)
            final_scope_names.append(final_scope_name)

            scope_obj = cls(
                group_id=scope_data["group_id"],
                scope_name=final_scope_name,
                dimension_config=scope_data.get("dimension_config", {}),
                manual_list=scope_data.get("manual_list", []),
                auto_rules=scope_data.get("auto_rules", []),
                create_from=cls.CREATE_FROM_USER,
            )
            # 创建时：X | Y（dimension_config 视为 X，manual_list 视为 Y）
            # 如果提供了 manual_list，需要计算维度配置
            if scope_obj.manual_list:
                scope_obj.update_matched_dimension_config(delete_unmatched_dimensions=False)

            scopes_to_create.append(scope_obj)

        if scopes_to_create:
            cls.objects.bulk_create(scopes_to_create, batch_size=BULK_CREATE_BATCH_SIZE)

        # 2.2 查询已创建的对象并返回
        group_ids = {scope["group_id"] for scope in scopes}
        created_scopes = {
            (s.group_id, s.scope_name): s
            for s in cls.objects.filter(group_id__in=group_ids, scope_name__in=final_scope_names)
        }

        return created_scopes

    @classmethod
    def _build_scope_results(cls, scopes: list[dict], scope_objects: dict) -> list[dict]:
        """构建分组结果列表

        :param scopes: 原始分组列表
        :param scope_objects: 分组对象字典，可能是 {scope_id: scope_obj} 或 {(group_id, scope_name): scope_obj}
        :return: 结果列表
        """
        results = []
        for scope_data in scopes:
            # 判断 scope_objects 的 key 类型
            # 如果有 scope_id，说明是更新场景，使用 scope_id 查找
            if "scope_id" in scope_data:
                scope_id = scope_data["scope_id"]
                time_series_scope = scope_objects[scope_id]
            else:
                # 否则是创建场景，使用 (group_id, final_scope_name) 查找
                final_scope_name = cls._get_final_scope_name(scope_data)
                group_id = scope_data["group_id"]
                scope_key = (group_id, final_scope_name)
                time_series_scope = scope_objects[scope_key]

            results.append(
                {
                    "scope_id": time_series_scope.id,
                    "group_id": time_series_scope.group_id,
                    "scope_name": time_series_scope.scope_name,
                    "dimension_config": time_series_scope.dimension_config,
                    "manual_list": time_series_scope.manual_list,
                    "auto_rules": time_series_scope.auto_rules,
                    "create_from": time_series_scope.create_from,
                }
            )
        return results

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_create_scopes(
        cls,
        bk_tenant_id: str,
        scopes: list[dict],
    ) -> list[dict]:
        """批量创建自定义时序指标分组

        :param bk_tenant_id: 租户ID
        :param scopes: 批量创建的分组列表，格式:
            [{
                "group_id": 1,
                "scope_name": "test_scope",
                "dimension_config": {},
                "manual_list": [],
                "auto_rules": []
            }]
        :return: 创建结果列表
        """
        # 第一步：检查
        cls._check_scopes_for_create(bk_tenant_id, scopes)

        # 第二步：创建
        created_scopes = cls._create_scope_data(scopes)

        # 第三步：返回
        return cls._build_scope_results(scopes, created_scopes)

    @classmethod
    def _check_scopes_for_modify(cls, bk_tenant_id: str, scopes: list[dict]) -> dict:
        """检查批量修改的分组数据

        :param bk_tenant_id: 租户ID
        :param scopes: 批量修改的分组列表
        :return: existing_scopes 现有分组对象字典 {scope_id: scope_obj}
        """

        cls._common_check_scopes(bk_tenant_id, scopes)

        # 1.1 批量查询要更新的记录（通过 scope_id）
        scope_ids = [scope_data["scope_id"] for scope_data in scopes]
        existing_scopes = {s.id: s for s in cls.objects.filter(id__in=scope_ids)}

        # 1.2 检查是否所有 scope 都存在
        found_scope_ids = set(existing_scopes.keys())
        requested_scope_ids = set(scope_ids)
        missing_scope_ids = requested_scope_ids - found_scope_ids
        if missing_scope_ids:
            raise ValueError(
                _("指标分组不存在，请确认后重试: scope_id={}").format(", ".join(map(str, missing_scope_ids)))
            )

        # 1.3 检查批次内部是否有重复的 scope_name（同一 group_id 下）
        # 构建批次内的最终 scope_name 映射：{(group_id, final_scope_name): [scope_id1, scope_id2, ...]}
        batch_scope_names = {}
        for scope_data in scopes:
            scope_id = scope_data["scope_id"]
            scope_obj = existing_scopes[scope_id]

            # 确定最终的 scope_name（如果提供了新名称则使用新名称，否则使用原名称）
            new_scope_name = scope_data.get("scope_name")
            if new_scope_name is not None:
                final_scope_name = cls._get_final_scope_name(scope_data)
            else:
                final_scope_name = scope_obj.scope_name

            key = (scope_obj.group_id, final_scope_name)
            batch_scope_names.setdefault(key, []).append(scope_id)

        # 检查批次内是否有重复
        for (group_id, scope_name), scope_ids in batch_scope_names.items():
            if len(scope_ids) > 1:
                raise ValueError(
                    _("批次内存在重复的分组名: group_id={}, scope_name={}, scope_ids={}").format(
                        group_id, scope_name, ", ".join(map(str, scope_ids))
                    )
                )

        # 1.4 检查分组名（如果要修改 scope_name）
        for scope_data in scopes:
            scope_id = scope_data["scope_id"]
            new_scope_name = scope_data.get("scope_name")

            # 提前跳过：没有提供新分组名
            if new_scope_name is None:
                continue

            scope_obj = existing_scopes[scope_id]

            # 构建组合后的新 scope_name
            final_new_scope_name = cls._get_final_scope_name(scope_data)

            # 提前跳过：新分组名与当前分组名相同
            if final_new_scope_name == scope_obj.scope_name:
                continue

            # 检查：data 类型的 scope 不允许修改 scope_name
            if scope_obj.is_create_from_data():
                raise ValueError(
                    _("数据自动创建的分组不允许修改分组名: scope_id={}, scope_name={}").format(
                        scope_obj.id, scope_obj.scope_name
                    )
                )

            # 检查新分组名是否已存在于数据库中（同一 group_id 下，排除本批次要更新的记录）
            all_scope_ids_in_batch = [s["scope_id"] for s in scopes]
            if (
                cls.objects.filter(group_id=scope_obj.group_id, scope_name=final_new_scope_name)
                .exclude(id__in=all_scope_ids_in_batch)
                .exists()
            ):
                raise ValueError(
                    _("指标分组名已存在: group_id={}, scope_name={}").format(scope_obj.group_id, final_new_scope_name)
                )

        # 1.5 校验同一批次内的 manual_list 是否有重复
        batch_manual_list_metrics = {}  # {metric_name: [(group_id, scope_name, idx), ...]}
        for idx, scope_data in enumerate(scopes):
            manual_list = scope_data.get("manual_list")
            if manual_list:
                scope_id = scope_data["scope_id"]
                scope_obj = existing_scopes[scope_id]
                for metric in manual_list:
                    batch_manual_list_metrics.setdefault(metric, []).append(
                        (scope_obj.group_id, scope_obj.scope_name, idx)
                    )

        # 检查批次内是否有重复的指标
        for metric, locations in batch_manual_list_metrics.items():
            if len(locations) > 1:
                location_strs = [f"group_id={loc[0]}, scope_name={loc[1]}, 位置索引={loc[2]}" for loc in locations]
                raise ValueError(
                    _("批次内存在重复的指标: metric={}, 出现位置=[{}]").format(metric, "; ".join(location_strs))
                )

        # 1.6 校验 manual_list 中的指标是否都在 default 数据分组
        for scope_data in scopes:
            manual_list = scope_data.get("manual_list")
            if manual_list is not None:
                scope_id = scope_data["scope_id"]
                scope_obj = existing_scopes[scope_id]
                # 更新场景，需要获取旧的 manual_list
                old_manual_list = scope_obj.manual_list or []
                cls._validate_manual_list_metrics_in_default_scope(
                    group_id=scope_obj.group_id,
                    manual_list=manual_list,
                    old_manual_list=old_manual_list,
                    scope_name=scope_obj.scope_name,
                )

        return existing_scopes

    @classmethod
    def _update_scopes_data(cls, scopes: list[dict], existing_scopes: dict) -> dict:
        """更新分组数据

        :param scopes: 批量修改的分组列表
        :param existing_scopes: 现有分组对象字典 {scope_id: scope_obj}
        :return: 更新后的分组字典 {scope_id: scope_obj}
        """
        # 2.1 准备更新数据
        scopes_to_update = []  # 需要批量更新的 scope 对象列表
        update_fields = set()  # 需要更新的字段集合

        for scope_data in scopes:
            scope_id = scope_data["scope_id"]
            scope_obj = existing_scopes[scope_id]

            has_updates = False

            # 更新 scope_name
            new_scope_name = scope_data.get("scope_name")
            if new_scope_name is not None:
                final_new_scope_name = cls._get_final_scope_name(scope_data)
                if final_new_scope_name != scope_obj.scope_name:
                    scope_obj.scope_name = final_new_scope_name
                    update_fields.add("scope_name")
                    has_updates = True

            # 更新 dimension_config（先将旧 dimension_config 用传递进来的 dimension_config 进行覆盖，视为 X）
            dimension_config_updated = False
            if scope_data.get("dimension_config") is not None:
                scope_obj.dimension_config = scope_data["dimension_config"]
                update_fields.add("dimension_config")
                has_updates = True
                dimension_config_updated = True

            # 更新 manual_list
            manual_list = scope_data.get("manual_list")
            manual_list_updated = False
            if manual_list is not None:
                scope_obj.manual_list = manual_list
                update_fields.add("manual_list")
                has_updates = True
                manual_list_updated = True

            # 更新 auto_rules
            auto_rules = scope_data.get("auto_rules")
            if auto_rules is not None:
                scope_obj.auto_rules = auto_rules
                update_fields.add("auto_rules")
                has_updates = True

            # 如果更新了 dimension_config 或 manual_list，且 manual_list 存在，需要重新计算维度配置
            # 更新时：先将旧 dimension_config 用传递进来的 dimension_config 进行覆盖，视为 X
            # manual_list 视为 Y
            # 当 delete_unmatched_dimensions 为 true 则最终集合为 (X & Y) | Y，反之 X | Y
            if (dimension_config_updated or manual_list_updated) and scope_obj.manual_list:
                delete_unmatched_dimensions = scope_data.get("delete_unmatched_dimensions", False)
                # 直接在内存对象上更新维度配置
                scope_obj.update_matched_dimension_config(delete_unmatched_dimensions=delete_unmatched_dimensions)
                update_fields.add("dimension_config")
                has_updates = True

            if has_updates:
                scopes_to_update.append(scope_obj)

        # 2.2 一次性批量更新所有字段
        if scopes_to_update:
            cls.objects.bulk_update(
                scopes_to_update,
                list(update_fields),
                batch_size=BULK_UPDATE_BATCH_SIZE,
            )

        # 2.3 最后统一查询一次以获取所有最新数据（通过 scope_id）
        scope_ids = [scope_data["scope_id"] for scope_data in scopes]
        updated_scopes = {s.id: s for s in cls.objects.filter(id__in=scope_ids)}

        return updated_scopes

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_modify_scopes(
        cls,
        bk_tenant_id: str,
        scopes: list[dict],
    ) -> list[dict]:
        """批量修改自定义时序指标分组

        :param bk_tenant_id: 租户ID
        :param scopes: 批量修改的分组列表，格式:
            [{
                "scope_id": 1,  # 必填，分组ID
                "scope_name": "new_test_scope",  # 可选，用于修改分组名
                "dimension_config": {},  # 可选
                "manual_list": [],  # 可选
                "auto_rules": [],  # 可选
                "delete_unmatched_dimensions": False  # 可选
            }]
        :return: 修改结果列表
        """
        # 第一步：检查
        existing_scopes = cls._check_scopes_for_modify(bk_tenant_id, scopes)

        # 第二步：更新
        updated_scopes = cls._update_scopes_data(scopes, existing_scopes)

        # 第三步：返回
        return cls._build_scope_results(scopes, updated_scopes)

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_delete_scopes(
        cls,
        bk_tenant_id: str,
        scopes: list[dict],
    ):
        """批量删除自定义时序指标分组

        :param bk_tenant_id: 租户ID
        :param scopes: 批量删除的分组列表，格式:
            [{
                "group_id": 1,
                "scope_name": "test_scope"
            }]
        """
        cls._common_check_scopes(bk_tenant_id, scopes)

        # 批量获取要删除的 TimeSeriesScope
        scope_conditions = Q()
        requested_scopes = set()
        for scope_data in scopes:
            final_scope_name = cls._get_final_scope_name(scope_data)
            scope_conditions |= Q(group_id=scope_data["group_id"], scope_name=final_scope_name)
            requested_scopes.add((scope_data["group_id"], final_scope_name))

        time_series_scopes = cls.objects.filter(scope_conditions)

        # 检查是否所有 scope 都存在
        found_scopes = {(s.group_id, s.scope_name) for s in time_series_scopes}
        missing_scopes = requested_scopes - found_scopes

        if missing_scopes:
            missing_names = [f"{gid}:{name}" for gid, name in missing_scopes]
            raise ValueError(_("指标分组不存在，请确认后重试: {}").format(", ".join(missing_names)))

        # 分类处理：区分 data 类型和 user 类型
        data_scopes = []  # 数据自动创建的 scope
        user_scopes = []  # 用户手动创建的 scope

        for time_series_scope in time_series_scopes:
            if time_series_scope.is_create_from_data():
                data_scopes.append(time_series_scope)
            else:
                user_scopes.append(time_series_scope)

        # 对于 data 类型的 scope：清空 manual_list 和 auto_rules，并清理 dimension_config
        if data_scopes:
            for scope in data_scopes:
                # 1. 清空 manual_list 和 auto_rules
                scope.manual_list = []
                scope.auto_rules = []

                # 2. 从 metric 表中获取对应数据分组 scope 的所有 metric 的维度
                # 查询该分组下的所有指标
                metrics = TimeSeriesMetric.objects.filter(group_id=scope.group_id, field_scope=scope.scope_name)

                # 3. 计算所有 metric 的维度并集
                all_metric_dimensions = set()
                for metric in metrics:
                    if metric.tag_list:
                        all_metric_dimensions.update(metric.tag_list)

                # 4. 从 dimension_config 中删除不属于这些维度的配置
                current_dimension_config = scope.dimension_config or {}
                # 只保留属于 metric 维度的配置
                scope.dimension_config = {
                    dim_name: dim_config
                    for dim_name, dim_config in current_dimension_config.items()
                    if dim_name in all_metric_dimensions
                }

            # 批量更新 data 类型的 scope
            cls.objects.bulk_update(
                data_scopes, ["manual_list", "auto_rules", "dimension_config"], batch_size=BULK_UPDATE_BATCH_SIZE
            )

        # 对于 user 类型的 scope：直接删除
        if user_scopes:
            cls.objects.filter(pk__in=[scope.pk for scope in user_scopes]).delete()


class TimeSeriesMetric(models.Model):
    """
    自定义时序指标表
    """

    TARGET_DIMENSION_NAME = "target"

    DEFAULT_SERVICE = "unknown_service"  # 默认服务
    DEFAULT_SCOPE = "default"  # 默认分组

    ORM_FIELD_NAMES = (
        "table_id",
        "field_name",
        "field_type",
        "unit",
        "tag",
        "description",
        "is_disabled",
    )

    MetricConfigFields = [
        "desc",  # 别名
        "unit",  # 单位
        "hidden",  # 显隐
        "aggregate_method",  # 常用聚合方法
        "function",  # 常用聚合函数
        "interval",  # 默认聚合周期
        "disabled",  # 是否禁用
    ]

    field_id = models.AutoField(verbose_name="字段ID", primary_key=True)

    # group_id 来自于 TimeSeriesGroup.time_series_group_id，关联数据源
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID", db_index=True)
    table_id = models.CharField(verbose_name="table名", default="", max_length=255)

    # 对于 APM 的场景来说分组的格式为 {service_name}||{scope_name}，其余场景中都是自动赋值为 default
    field_scope = models.CharField(
        verbose_name="指标字段数据分组名", default=DEFAULT_SCOPE, max_length=255, db_collation="utf8_bin"
    )
    field_name = models.CharField(verbose_name="指标字段名称", max_length=255, db_collation="utf8_bin")
    tag_list = JsonField(verbose_name="Tag列表", default=[])

    # 字段其他配置，可配置的字段 key 需要在 MetricConfigFields 中定义
    field_config = models.JSONField(verbose_name="字段其他配置", default=dict)

    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)

    label = models.CharField(verbose_name="指标监控对象", default="", max_length=255, db_index=True)

    # 已废弃，已转为从 bkbase 获取数据，consul 会逐步下线
    last_index = models.IntegerField(verbose_name="上次consul的modify_index", default=0)

    class Meta:
        # 同一个数据源，同一个分组下，不可以存在同样的指标字段名称
        unique_together = ("group_id", "field_scope", "field_name")
        verbose_name = "自定义时序描述记录"
        verbose_name_plural = "自定义时序描述记录表"

    @staticmethod
    def get_default_scope_metric_filter(scope_name: str):
        # 如果 scope_name 包含 "||"，提取 service_name 部分
        if "||" in scope_name:
            service_name = scope_name.split("||", 1)[0]
            return Q(field_scope=f"{service_name}||{TimeSeriesMetric.DEFAULT_SCOPE}")
        # 如果 scope_name 不包含 "||"，直接使用 DEFAULT_SCOPE
        else:
            return Q(field_scope=TimeSeriesMetric.DEFAULT_SCOPE)

    def make_table_id(self, bk_biz_id, bk_data_id, table_name=None):
        if str(bk_biz_id) != "0":
            return f"{bk_biz_id}_bkmonitor_time_series_{bk_data_id}.{self.field_name}"

        return f"bkmonitor_time_series_{bk_data_id}.{self.field_name}"

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
    def get_metric_tag_from_metric_info(cls, metric_info: dict) -> list:
        # 获取 tag
        if "tag_value_list" in metric_info:
            tags = set(metric_info["tag_value_list"].keys())
        else:
            tags = {tag["field_name"] for tag in metric_info.get("tag_list", [])}

        # 添加特殊字段，兼容先前逻辑
        tags.add("target")
        return list(tags)

    @classmethod
    def _extract_field_scope_from_group_key(cls, group_key: str) -> str:
        """从 group_dimensions 的 key 中提取 field_scope

        例如: "service_name:api-server||scope_name:production" -> "api-server||production"

        特殊处理：
        - 如果 service_name 不存在或值为空，使用 "unknown_service"
        - 如果 scope_name 不存在或值为空，使用 "default"
        """
        parts = group_key.split("||")

        # 解析所有的 key:value 对
        key_value_map = {}
        for part in parts:
            if ":" in part:
                key, value = part.split(":", 1)
                key_value_map[key.strip()] = value.strip() if value.strip() else None

        # 提取 service_name，如果不存在或为空，使用默认值 "unknown_service"
        service_name = key_value_map.get("service_name") or cls.DEFAULT_SERVICE

        # 提取 scope_name，如果不存在或为空，使用默认值 "default"
        scope_name = key_value_map.get("scope_name") or cls.DEFAULT_SCOPE

        # 组合成 field_scope
        return f"{service_name}||{scope_name}"

    @classmethod
    def _bulk_create_metrics(
        cls,
        metrics_dict: dict,
        group_id: int,
        table_id: str,
        is_auto_discovery: bool,
        need_create_metrics: set | None = None,
        need_create_metrics_with_scope: set | None = None,
    ) -> bool:
        """批量创建指标

        :param metrics_dict: 指标信息字典
        :param group_id: 分组ID
        :param table_id: 结果表ID
        :param is_auto_discovery: 是否自动发现
        :param need_create_metrics: 需要创建的字段名集合，格式: set[field_name, ...]
        :param need_create_metrics_with_scope: 需要创建的 (field_name, field_scope) 组合集合，格式: set[(field_name, field_scope), ...]
        """
        # 根据传入的参数选择不同的处理函数
        if need_create_metrics_with_scope:
            records, scope_dimensions_map = cls._create_metrics_with_combinations(
                metrics_dict, need_create_metrics_with_scope, group_id, table_id, is_auto_discovery
            )
        elif need_create_metrics:
            records, scope_dimensions_map = cls._create_metrics_with_field_names(
                metrics_dict, need_create_metrics, group_id, table_id, is_auto_discovery
            )
        else:
            # 如果两个参数都为空，直接返回
            return False

        # 批量创建 TimeSeriesScope 记录，并传入对应的维度列表
        if scope_dimensions_map:
            # 将 set 转换为 list
            scope_dimensions_list_map = {
                scope_name: list(dimensions_set) for scope_name, dimensions_set in scope_dimensions_map.items()
            }
            TimeSeriesScope.bulk_ensure_or_merge_scopes(
                group_id=group_id,
                scope_dimensions_map=scope_dimensions_list_map,
            )

        # 开始批量创建指标
        cls.objects.bulk_create(records, batch_size=BULK_CREATE_BATCH_SIZE)
        return True

    @classmethod
    def _create_metrics_with_combinations(
        cls,
        metrics_dict: dict,
        need_create_metrics: set,
        group_id: int,
        table_id: str,
        is_auto_discovery: bool,
    ) -> tuple[list, dict]:
        """使用组合模式创建指标记录

        :param metrics_dict: 指标信息字典
        :param need_create_metrics: 需要创建的 (field_name, field_scope) 组合集合
        :param group_id: 分组ID
        :param table_id: 结果表ID
        :param is_auto_discovery: 是否自动发现
        :return: (记录列表, scope维度映射字典)
        """
        records = []
        scope_dimensions_map = {}

        for field_name, field_scope in need_create_metrics:
            metric_info = metrics_dict.get(field_name)
            # 如果获取不到指标数据，则跳过
            if not metric_info:
                continue
            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True) and not is_auto_discovery:
                continue

            for group_key, group_info in metric_info["group_dimensions"].items():
                extracted_scope = cls._extract_field_scope_from_group_key(group_key)
                # 只创建匹配的 field_scope
                if extracted_scope != field_scope:
                    continue

                dimensions = group_info.get("dimensions", [])

                # 维度 [target] 必须存在; 如果不存在时，则需要添加 [target] 维度
                if cls.TARGET_DIMENSION_NAME not in dimensions:
                    dimensions.append(cls.TARGET_DIMENSION_NAME)

                params = {
                    "field_name": field_name,
                    "group_id": group_id,
                    "table_id": f"{table_id.split('.')[0]}.{field_name}",
                    "tag_list": dimensions,
                    "field_scope": field_scope,
                }
                logger.info("create ts metric data with group_dimensions: %s", json.dumps(params))
                records.append(cls(**params))

                # 收集该 scope 的所有维度（使用 set 去重）
                scope_dimensions_map.setdefault(field_scope, set()).update(dimensions)

        return records, scope_dimensions_map

    @classmethod
    def _create_metrics_with_field_names(
        cls,
        metrics_dict: dict,
        need_create_metrics: set,
        group_id: int,
        table_id: str,
        is_auto_discovery: bool,
    ) -> tuple[list, dict]:
        """使用字段名模式创建指标记录

        :param metrics_dict: 指标信息字典
        :param need_create_metrics: 需要创建的字段名集合
        :param group_id: 分组ID
        :param table_id: 结果表ID
        :param is_auto_discovery: 是否自动发现
        :return: (记录列表, scope维度映射字典)
        """
        records = []
        scope_dimensions_map = {}

        for metric in need_create_metrics:
            metric_info = metrics_dict.get(metric)
            # 如果获取不到指标数据，则跳过
            if not metric_info:
                continue
            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True) and not is_auto_discovery:
                continue
            tag_list = cls.get_metric_tag_from_metric_info(metric_info)
            params = {
                "field_name": metric,
                "group_id": group_id,
                "table_id": f"{table_id.split('.')[0]}.{metric}",
                "tag_list": tag_list,
            }
            logger.info("create ts metric data: %s", json.dumps(params))
            records.append(cls(**params))

            # 旧格式使用默认的 scope_name，收集维度
            scope_dimensions_map.setdefault("default", set()).update(tag_list)

        return records, scope_dimensions_map

    @classmethod
    def _bulk_update_metrics(
        cls,
        metrics_dict: dict,
        group_id: int,
        is_auto_discovery: bool,
        need_update_metrics: set | None = None,
        need_update_metrics_with_scope: set | None = None,
    ) -> bool:
        """批量更新指标，针对记录仅更新最后更新时间和 tag 字段

        :param metrics_dict: 指标信息字典
        :param group_id: 分组ID
        :param is_auto_discovery: 是否自动发现
        :param need_update_metrics: 需要更新的字段名集合，格式: set[field_name, ...]
        :param need_update_metrics_with_scope: 需要更新的 (field_name, field_scope) 组合集合，格式: set[(field_name, field_scope), ...]
        """
        # 根据传入的参数选择不同的处理函数
        if need_update_metrics_with_scope:
            records, white_list_disabled_metric, scope_dimensions_map, need_push_router = (
                cls._update_metrics_with_combinations(
                    metrics_dict, need_update_metrics_with_scope, group_id, is_auto_discovery
                )
            )
        elif need_update_metrics:
            records, white_list_disabled_metric, scope_dimensions_map, need_push_router = (
                cls._update_metrics_with_field_names(metrics_dict, need_update_metrics, group_id, is_auto_discovery)
            )
        else:
            # 如果两个参数都为空，直接返回
            return False

        # 白名单模式，如果存在需要禁用的指标，则需要删除；应该不会太多，直接删除
        if white_list_disabled_metric:
            cls.objects.filter(group_id=group_id, field_name__in=white_list_disabled_metric).delete()
        logger.info("white list disabled metric: %s, group_id: %s", json.dumps(white_list_disabled_metric), group_id)

        # 批量更新或创建 TimeSeriesScope 记录，并传入对应的维度列表
        if scope_dimensions_map:
            # 将 set 转换为 list
            scope_dimensions_list_map = {
                scope_name: list(dimensions_set) for scope_name, dimensions_set in scope_dimensions_map.items()
            }
            TimeSeriesScope.bulk_ensure_or_merge_scopes(
                group_id=group_id,
                scope_dimensions_map=scope_dimensions_list_map,
            )

        # 批量更新指定的字段
        cls.objects.bulk_update(records, ["last_modify_time", "tag_list"], batch_size=BULK_UPDATE_BATCH_SIZE)
        return need_push_router

    @classmethod
    def _update_metrics_with_combinations(
        cls,
        metrics_dict: dict,
        need_update_metrics: set,
        group_id: int,
        is_auto_discovery: bool,
    ) -> tuple[list, set, dict, bool]:
        """使用组合模式更新指标记录

        :param metrics_dict: 指标信息字典
        :param need_update_metrics: 需要更新的 (field_name, field_scope) 组合集合
        :param group_id: 分组ID
        :param is_auto_discovery: 是否自动发现
        :return: (更新记录列表, 禁用指标集合, scope维度映射字典, 是否需要推送路由)
        """
        records = []
        white_list_disabled_metric = set()
        scope_dimensions_map = {}
        need_push_router = False

        # 构建查询条件：需要同时匹配 field_name 和 field_scope
        field_name_list = [field_name for field_name, _ in need_update_metrics]
        qs_objs = filter_model_by_in_page(
            TimeSeriesMetric, "field_name__in", field_name_list, other_filter={"group_id": group_id}
        )

        # 将组合转换为集合，方便快速查找
        combinations_set = set(need_update_metrics)

        for obj in qs_objs:
            # 只处理匹配的 (field_name, field_scope) 组合
            if (obj.field_name, obj.field_scope) not in combinations_set:
                continue

            metric_info = metrics_dict.get(obj.field_name)
            # 如果找不到指标数据，则忽略
            if not metric_info:
                continue

            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True):
                if is_auto_discovery:
                    last_modify_time = make_aware(datetime.datetime(1970, 1, 1))
                else:
                    white_list_disabled_metric.add(obj.field_name)
                    continue
            else:
                last_modify_time = make_aware(
                    datetime.datetime.fromtimestamp(metric_info.get("last_modify_time", time.time()))
                )

            # 从 group_dimensions 中根据 field_scope 获取维度
            new_dimensions = []
            for group_key, group_info in metric_info.get("group_dimensions", {}).items():
                extracted_scope = cls._extract_field_scope_from_group_key(group_key)
                # 只处理匹配的 field_scope
                if extracted_scope != obj.field_scope:
                    continue
                new_dimensions = group_info.get("dimensions", [])
                break

            # 维度 [target] 必须存在; 如果不存在时，则需要添加 [target] 维度
            if cls.TARGET_DIMENSION_NAME not in new_dimensions:
                new_dimensions.append(cls.TARGET_DIMENSION_NAME)

            need_push_router = cls._collect_update_records(
                last_modify_time, need_push_router, new_dimensions, obj, records
            )

            # 收集该 scope 的所有维度（使用 set 去重）
            scope_dimensions_map.setdefault(obj.field_scope, set()).update(new_dimensions)

        return records, white_list_disabled_metric, scope_dimensions_map, need_push_router

    @classmethod
    def _update_metrics_with_field_names(
        cls,
        metrics_dict: dict,
        need_update_metrics: set,
        group_id: int,
        is_auto_discovery: bool,
    ) -> tuple[list, set, dict, bool]:
        """使用字段名模式更新指标记录

        :param metrics_dict: 指标信息字典
        :param need_update_metrics: 需要更新的字段名集合
        :param group_id: 分组ID
        :param is_auto_discovery: 是否自动发现
        :return: (更新记录列表, 禁用指标集合, scope维度映射字典, 是否需要推送路由)
        """
        records = []
        white_list_disabled_metric = set()
        scope_dimensions_map = {}
        need_push_router = False

        qs_objs = filter_model_by_in_page(
            TimeSeriesMetric, "field_name__in", need_update_metrics, other_filter={"group_id": group_id}
        )

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
                    continue

            # 旧格式：通过方法获取
            new_dimensions = cls.get_metric_tag_from_metric_info(metric_info)

            need_push_router = cls._collect_update_records(
                last_modify_time, need_push_router, new_dimensions, obj, records
            )

            # 收集该 scope 的所有维度（使用 set 去重）
            scope_dimensions_map.setdefault(obj.field_scope, set()).update(new_dimensions)

        return records, white_list_disabled_metric, scope_dimensions_map, need_push_router

    @classmethod
    def _collect_update_records(cls, last_modify_time, need_push_router, new_dimensions, obj, records):
        # 标识是否需要更新
        is_need_update = False
        # 先设置最后更新时间 1 天更新一次，减少对 db 的操作
        if (last_modify_time - obj.last_modify_time).days >= 1:
            is_need_update = True
            obj.last_modify_time = last_modify_time
        # NOTE：当时间变更超过有效期阈值时，更新路由；适用`指标重新启用`场景
        if (last_modify_time - obj.last_modify_time).seconds >= settings.TIME_SERIES_METRIC_EXPIRED_SECONDS:
            need_push_router = True
        # 如果 tag 不一致，则进行更新
        if set(obj.tag_list or []) != set(new_dimensions):
            is_need_update = True
            # 合并维度：保留旧维度，添加新维度
            obj.tag_list = list(set(obj.tag_list or []) | set(new_dimensions))
        if is_need_update:
            logger.info(f"update ts metric {obj.field_name} {obj.field_scope} {obj.tag_list}")
            records.append(obj)
        return need_push_router

    @classmethod
    def bulk_refresh_ts_metrics(
        cls, group_id: int, table_id: str, metric_info_list: list, is_auto_discovery: bool
    ) -> bool:
        """
        更新或创建时序指标数据

        :param group_id: 自定义分组ID
        :param table_id: 结果表
        :param metric_info_list: 具体自定义时序内容信息，支持两种格式：
            格式1 - 带 tag_value_list（旧格式）：
            [{
                "field_name": "core_file",
                "tag_value_list": {
                    "endpoint": {
                        'last_update_time': 1701438084,
                        'values': ["value1", "value2"]
                    }
                },
                "last_modify_time": 1464567890123,
            }]

            格式2 - 带 group_dimensions（新格式）：
            [{
                "field_name": "cpu_usage",
                "tag_value_list": {
                    "endpoint": {
                        'last_update_time': 1701438084,
                        'values': ["value1", "value2"]
                    }
                },
                "group_dimensions": {
                    "service_name:api-server||scope_name:production": {
                        "dimensions": ["service_name", "disk", "pod", "region"],
                        "update_time": 1678901234
                    }
                },
                "last_modify_time": 1678901234,
            }]

            格式3 - 带 tag_list（兼容格式）：
            [{
                "field_name": "disk_full",
                "tag_list": [
                    {"field_name": "module", "description": "模块"},
                    {"field_name": "set", "description": "集群"}
                ],
                "last_modify_time": 1464567890123,
            }]
        :param is_auto_discovery: 指标是否自动发现
        :return: True or raise
        """
        _metrics_dict = {m["field_name"]: m for m in metric_info_list if m.get("field_name")}

        # 检查是否有 group_dimensions 格式的数据
        has_group_dimensions = any("group_dimensions" in m for m in metric_info_list if m.get("field_name"))

        if has_group_dimensions:
            # 新逻辑：基于 (field_name, field_scope) 组合判断
            # 获取现有的 (field_name, field_scope) 组合
            existing_records = cls.objects.filter(group_id=group_id).values_list("field_name", "field_scope")
            existing_combinations = {(field_name, field_scope) for field_name, field_scope in existing_records}

            # 构建期望的 (field_name, field_scope) 组合
            expected_combinations = set()
            for metric_info in metric_info_list:
                field_name = metric_info.get("field_name")
                if not field_name:
                    continue
                if "group_dimensions" in metric_info:
                    for group_key in metric_info["group_dimensions"].keys():
                        field_scope = cls._extract_field_scope_from_group_key(group_key)
                        expected_combinations.add((field_name, field_scope))
                else:
                    # 旧格式，使用默认的 field_scope
                    expected_combinations.add((field_name, "default"))

            # 计算需要创建和更新的记录
            need_create_combinations = expected_combinations - existing_combinations
            need_update_combinations = expected_combinations & existing_combinations
            logger.info(
                f"need_create_combinations: {need_create_combinations}, need_update_combinations: {need_update_combinations}"
            )

            # NOTE: 针对创建或者时间变动时，推送路由数据
            need_push_router = False
            # 如果存在，则批量创建（传递完整的 combinations）
            if need_create_combinations:
                need_push_router = cls._bulk_create_metrics(
                    _metrics_dict,
                    group_id,
                    table_id,
                    is_auto_discovery,
                    need_create_metrics_with_scope=need_create_combinations,
                )
            # 批量更新（传递完整的 combinations）
            if need_update_combinations:
                need_push_router |= cls._bulk_update_metrics(
                    _metrics_dict, group_id, is_auto_discovery, need_update_metrics_with_scope=need_update_combinations
                )
        else:
            # 旧逻辑：仅基于 field_name 判断
            metrics_by_group_id = cls.objects.filter(group_id=group_id).values_list("field_name", flat=True)
            _metrics = set(_metrics_dict.keys())
            need_create_metrics = _metrics - set(metrics_by_group_id)
            need_update_metrics = _metrics - need_create_metrics

            # NOTE: 针对创建或者时间变动时，推送路由数据
            need_push_router = False
            # 如果存在，则批量创建
            if need_create_metrics:
                need_push_router = cls._bulk_create_metrics(
                    _metrics_dict, group_id, table_id, is_auto_discovery, need_create_metrics=need_create_metrics
                )
            # 批量更新
            if need_update_metrics:
                need_push_router |= cls._bulk_update_metrics(
                    _metrics_dict, group_id, is_auto_discovery, need_update_metrics=need_update_metrics
                )

        return need_push_router

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
            logger.info(f"time_series_group_id->[{group_id}] not exists, nothing will do.")
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
                logger.info(f"new metric_obj->[{metric_obj}] is create for group_id->[{group_id}].")
                # NOTE: 如果有新增, 则标识要更新，删除时，可以不立即更新
                is_updated = True

            # 生成/更新真实表id
            database_name = group.table_id.split(".")[0]
            metric_obj.table_id = f"{database_name}.{metric_obj.field_name}"

            if created or last_modify_time > metric_obj.last_modify_time:
                logger.info(
                    f"time_series_group_id->[{group_id}],field_name->[{metric_obj.field_name}] will change index from->[{metric_obj.last_index}] to [{last_modify_time}]"
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
                # NOTE：当时间变更超过有效期阈值时，更新路由；适用`指标重新启用`场景
                if (
                    last_modify_time - metric_obj.last_modify_time
                ).seconds >= settings.TIME_SERIES_METRIC_EXPIRED_SECONDS:
                    is_updated = True
                if need_save_op:
                    metric_obj.save()

                # 后续可以在此处追加其他修改内容
                logger.info(
                    f"time_series_group_id->[{group_id}] has update field_name->[{metric_obj.field_name}] all tags->[{metric_obj.tag_list}]"
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
                ResultTableField.objects.filter(table_id=group.table_id, bk_tenant_id=group.bk_tenant_id)
                .values(*self.ORM_FIELD_NAMES)
                .iterator()
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
                f"metric->[{self.field_name}] is not exists in table->[{group.table_id}] not metrics info will return."
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
                ResultTableField.objects.filter(table_id=group.table_id, bk_tenant_id=group.bk_tenant_id)
                .values(*self.ORM_FIELD_NAMES)
                .iterator()
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
                f"metric->[{self.field_name}] is not exists in table->[{group.table_id}] not metrics info will return."
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

    def create_by_infos(self, metric_obj: TimeSeriesMetric, tag_infos: dict[str, dict]) -> list["TimeSeriesTag"]:
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

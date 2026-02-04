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
from collections import defaultdict

from django.conf import settings
from django.db import models
from django.db import utils as django_db_utils
from django.db.transaction import atomic
from django.utils.functional import cached_property
from django.utils.timezone import make_aware
from django.utils.timezone import now as tz_now
from django.utils.translation import gettext as _

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
    # 指标分组的维度key配置，[{"key": "service_name", "default_value": "unknown_service"}, ...]
    metric_group_dimensions = models.JSONField(verbose_name="指标分组的维度key配置", default=list)

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

    @classmethod
    def get_scope_name_from_group_key(cls, group_key: str, metric_group_dimensions: list | None = None) -> str:
        """
        从 group_key 转换为 field_scope 字符串（仅用于 get_metric_from_bkdata）

        :param group_key: 例如 "service_name:api-server||scope_name:production"
        :param metric_group_dimensions: 分组维度配置，例如 [
            {"key": "service_name", "default_value": "unknown_service"},
            {"key": "scope_name", "default_value": "default"}
        ]
        :return: field_scope 字符串
        """
        if not group_key or not metric_group_dimensions:
            return TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME

        # 解析 group_key 为键值对
        key_value_map = {}
        for part in group_key.split("||"):
            if ":" in part:
                key, value = part.split(":", 1)
                key_value_map[key.strip()] = value.strip()

        # 按列表顺序，提取值并拼接
        levels = []
        for dim_config in metric_group_dimensions:
            dim_name = dim_config.get("key", "")
            value = key_value_map.get(dim_name) or dim_config.get("default_value", "")
            levels.append(value)

        # 如果 levels 里面全为空，直接返回默认值
        if all(not level for level in levels):
            return TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME

        # 拼接并返回
        result = "||".join(levels)
        return result if result else TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME

    @classmethod
    def get_default_scope_info(cls, scope_name: str, metric_group_dimensions: list | None = None) -> tuple[bool, str]:
        default_name = TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME

        # 快速判断：scope_name 就是 "default"
        if scope_name == default_name:
            return True, default_name

        # 基于维度配置计算
        if metric_group_dimensions:
            # 获取最后一级的默认值
            last_default_value = metric_group_dimensions[-1].get("default_value", default_name)

            # 判断是否为默认分组：检查最后一级是否为默认值
            scope_levels = scope_name.split("||")
            is_default = scope_levels[-1] == last_default_value

            # 生成默认分组名称：前面的层级使用 scope_name 的实际值，最后一级使用默认值
            if len(scope_levels) > 1:
                default_scope_name = "||".join(scope_levels[:-1] + [last_default_value])
            else:
                default_scope_name = last_default_value

            return is_default, default_scope_name

        # 如果没有维度配置，返回默认值
        return False, default_name

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

        logger.info("table->[%s] metric field->[%s] is update(%s).", table_id, field_name, is_field_update)
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
        # 根据field_name聚合metric_info，合并tag_value_list
        aggregated_metrics = defaultdict(lambda: {"tag_value_list": {}, "tag_list": []})

        for item in metric_info:
            field_name = item.get("field_name")
            if not field_name:
                continue

            # 初始化聚合数据
            aggregated_metrics[field_name].setdefault("field_name", field_name)

            # 合并 tag_value_list
            tag_value_list = item.get("tag_value_list", {})
            for tag_name, tag_info in tag_value_list.items():
                existing_tag = aggregated_metrics[field_name]["tag_value_list"].get(tag_name)
                new_values = set(tag_info.get("values", []))
                new_update_time = tag_info.get("last_update_time", 0)

                if existing_tag:
                    # 合并 values（去重）并取最新的 last_update_time
                    existing_tag["values"] = list(set(existing_tag["values"]) | new_values)
                    existing_tag["last_update_time"] = max(existing_tag["last_update_time"], new_update_time)
                else:
                    # 新建 tag 信息
                    aggregated_metrics[field_name]["tag_value_list"][tag_name] = {
                        "last_update_time": new_update_time,
                        "values": list(new_values),
                    }

        # 将聚合后的数据转换为列表
        metric_info = list(aggregated_metrics.values())

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
        # 刷新 tsScope
        new_metric_info_list = TimeSeriesScope.bulk_refresh_ts_scopes(group, metric_info)
        # 刷新 ts 中指标和维度
        is_updated = TimeSeriesMetric.bulk_refresh_ts_metrics(
            group_id, group.table_id, new_metric_info_list, group.is_auto_discovery()
        )
        # 刷新 rt 表中的指标和维度
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

            if self.metric_group_dimensions:
                latest_update_time = 0
                for group_key, group_info in md["group_dimensions"].items():
                    # 获取最新的更新时间
                    update_time = group_info.get("update_time", 0)
                    if update_time > latest_update_time:
                        latest_update_time = update_time

                    tag_value_list = {}
                    for dim_name in group_info.get("dimensions", []):
                        tag_value_list[dim_name] = {
                            "last_update_time": update_time,
                            "values": [],
                        }

                    item = {
                        "field_name": md["name"],
                        "field_scope": TimeSeriesGroup.get_scope_name_from_group_key(
                            group_key, self.metric_group_dimensions
                        ),
                        "last_modify_time": latest_update_time // 1000,
                        "tag_value_list": tag_value_list,
                    }
                    ret_data.append(item)
            else:
                tag_value_list = {}
                for d in md["dimensions"]:
                    tag_value_list[d["name"]] = {
                        "last_update_time": d["update_time"],
                        "values": [v["value"] for v in d["values"]],
                    }
                item = {
                    "field_name": md["name"],
                    "field_scope": TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME,
                    "last_modify_time": md["update_time"] // 1000,
                    "tag_value_list": tag_value_list,
                }
                ret_data.append(item)
        return ret_data

    def get_metrics_from_redis(self, expired_time: int | None = settings.TIME_SERIES_METRIC_EXPIRED_SECONDS):
        """从 redis 中获取数据

        其中，redis 中数据有 transfer 上报
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
                        "field_scope": TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME,
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
        metric_group_dimensions: list | None = None,
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
        """后处理创建"""
        metric_group_dimensions = kwargs.get("metric_group_dimensions")
        if metric_group_dimensions:
            custom_group.metric_group_dimensions = metric_group_dimensions
            custom_group.save()
        else:
            # 如果不存在 metric_group_dimensions，则创建默认的 scope 记录
            TimeSeriesScope.objects.create(
                group_id=custom_group.time_series_group_id,
                scope_name=TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME,
                dimension_config={},
                auto_rules=[],
                create_from=TimeSeriesScope.CREATE_FROM_DEFAULT,
            )

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

        # 获取对应的 scope 列表
        scope_map = {}
        for scope in TimeSeriesScope.objects.filter(group_id=self.time_series_group_id):
            scope_map[scope.id] = scope

        # 获取过期分界线
        last = datetime.datetime.now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        # 查找过期时间以前的数据
        for metric in TimeSeriesMetric.objects.filter(**metric_filter_params, last_modify_time__gt=last).iterator():
            metric_info = metric.to_metric_info_with_label(self, field_map=orm_field_map, scope_map=scope_map)
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

        # 获取对应的 scope 列表
        scope_map = {}
        for scope in TimeSeriesScope.objects.filter(group_id=self.time_series_group_id):
            scope_map[scope.id] = scope

        # 获取过期分界线
        last = datetime.datetime.now() - datetime.timedelta(seconds=settings.TIME_SERIES_METRIC_EXPIRED_SECONDS)
        time_series_metric_query = TimeSeriesMetric.objects.filter(group_id=self.time_series_group_id)

        # 如果是插件白名单模式，不需要判断过期时间
        if self.is_auto_discovery():
            time_series_metric_query = time_series_metric_query.filter(last_modify_time__gt=last)
        # 查找过期时间以前的数据
        for metric in time_series_metric_query.iterator():
            metric_info = metric.to_metric_info(field_map=orm_field_map, group=self, scope_map=scope_map)
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

    DimensionConfigFields = [
        "alias",  # 字段别名
        "common",  # 常用维度
        "hidden",  # 显隐
    ]

    # 创建来源选项
    CREATE_FROM_DATA = "data"  # 数据自动创建
    CREATE_FROM_USER = "user"  # 用户手动创建
    CREATE_FROM_DEFAULT = "default"  # 默认分组
    CREATE_FROM_CHOICES = [
        (CREATE_FROM_DATA, "数据自动创建"),
        (CREATE_FROM_USER, "用户手动创建"),
        (CREATE_FROM_DEFAULT, "默认分组"),
    ]

    # group_id 来自于 TimeSeriesGroup.time_series_group_id，关联数据源
    group_id = models.IntegerField(verbose_name="自定义时序数据源ID", db_index=True)

    scope_name = models.CharField(verbose_name="指标分组名", max_length=255, db_collation="utf8_bin")

    # 维度字段配置，可配置的选项，需要在 DimensionConfigFields 中定义
    dimension_config = models.JSONField(verbose_name="分组下的维度配置", default={})

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

    def is_create_from_data_or_default(self):
        return (
            self.create_from == TimeSeriesScope.CREATE_FROM_DATA
            or self.create_from == TimeSeriesScope.CREATE_FROM_DEFAULT
        )

    @classmethod
    def get_scope_name_prefix(cls, scope_name: str) -> str:
        if not scope_name:
            return ""

        # 如果以分隔符结尾（未分组），先去掉末尾的分隔符
        if scope_name.endswith("||"):
            scope_name = scope_name[: -len("||")]

        # 如果没有分隔符，说明是一级分组，前缀为空
        if "||" not in scope_name:
            return ""

        # 返回除了最后一级之外的部分
        return scope_name.rsplit("||", 1)[0]

    @classmethod
    def update_dimension_config_and_metrics_scope_id(cls, scope_moves: dict, need_update_metrics: bool = True):
        """批量更新指标分组和维度配置

        :param scope_moves: {(source_scope, sink_scope): [moved_metrics]}
        :param need_update_metrics: 是否需要更新指标的 scope_id
        """
        if not scope_moves:
            return

        all_metrics_to_update = []
        scopes_to_update = []

        for (source_scope, sink_scope), moved_metrics in scope_moves.items():
            if not moved_metrics:
                continue

            # 1. 收集被移动指标的所有维度
            moved_dimensions = {dim for metric in moved_metrics if metric.tag_list for dim in metric.tag_list}

            # 2. 构建维度配置：从源分组提取或创建空配置
            source_config = source_scope.dimension_config if source_scope else {}
            moved_config = {dim: source_config.get(dim, {}) for dim in moved_dimensions}

            # 3. 更新指标的 scope_id
            for metric in moved_metrics:
                metric.scope_id = sink_scope.id
            all_metrics_to_update.extend(moved_metrics)

            # 4. 合并维度配置到目标分组（增量保存）
            sink_scope.dimension_config = {**(sink_scope.dimension_config or {}), **moved_config}
            scopes_to_update.append(sink_scope)

        # 5. 批量更新数据库
        if all_metrics_to_update and need_update_metrics:
            TimeSeriesMetric.objects.bulk_update(all_metrics_to_update, ["scope_id"], batch_size=BULK_UPDATE_BATCH_SIZE)
        if scopes_to_update:
            TimeSeriesScope.objects.bulk_update(
                scopes_to_update, ["dimension_config"], batch_size=BULK_UPDATE_BATCH_SIZE
            )

    @classmethod
    def _match_scope_by_auto_rules(cls, scope, field_name: str) -> bool:
        if not scope.auto_rules:
            return False

        for rule in scope.auto_rules:
            try:
                if re.match(rule, field_name):
                    return True
            except re.error:
                logger.warning(
                    f"Invalid regex pattern in auto_rules: {rule} for group_id: {scope.group_id}, "
                    f"scope_name: {scope.scope_name}"
                )
        return False

    @classmethod
    def _determine_scope_name_for_new_metric(
        cls,
        field_name: str,
        field_scope: str,
        prefix_to_obj: dict,
        metric_group_dimensions: list | None = None,
    ) -> tuple[str, bool]:
        # 新建场景
        is_default, default_name = TimeSeriesGroup.get_default_scope_info(field_scope, metric_group_dimensions)
        if is_default:
            # 默认分组：尝试匹配 auto_rules
            prefix = cls.get_scope_name_prefix(field_scope)
            for scope in prefix_to_obj.get(prefix, []):
                if cls._match_scope_by_auto_rules(scope, field_name):
                    return scope.scope_name, False
            # 未匹配则使用默认分组 scope
            return default_name, True
        else:
            # 非默认分组：直接使用对应 scope
            return field_scope, False

    @classmethod
    def _collect_metrics_and_dimensions(
        cls,
        group_id: int,
        metric_info_list: list,
        metric_group_dimensions: list | None = None,
    ) -> tuple:
        # 获取所有 scope 记录并构建索引
        all_scopes = list(cls.objects.filter(group_id=group_id))

        # 按前缀分组并排序（用于 auto_rules 匹配）
        prefix_to_obj = defaultdict(list)
        for scope in all_scopes:
            prefix = cls.get_scope_name_prefix(scope.scope_name)
            prefix_to_obj[prefix].append(scope)
        for scopes in prefix_to_obj.values():
            scopes.sort(key=lambda x: x.last_modify_time, reverse=True)

        # 查询已有指标的 scope_id（用于更新场景）
        field_keys = [
            (metric_info.get("field_name"), metric_info.get("field_scope", TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME))
            for metric_info in metric_info_list
            if metric_info.get("field_name")
        ]
        if not field_keys:
            return {}, {}

        existing_metrics = TimeSeriesMetric.objects.filter(
            group_id=group_id,
            field_name__in=[field_name for field_name, _ in field_keys],
        ).values("field_name", "field_scope", "scope_id")

        # 构建 scope_id 到 scope_name 的映射（用于已有指标）
        scope_id_to_name = {scope.id: scope.scope_name for scope in all_scopes}
        scope_id_to_name[TimeSeriesMetric.DISABLE_SCOPE_ID] = None

        existing_metric_scope_map = {
            (metric["field_name"], metric["field_scope"]): scope_id_to_name.get(metric["scope_id"])
            for metric in existing_metrics
        }

        scope_name_to_metrics = defaultdict(list)
        # 已存在的指标忽略 create_from_default
        scope_name_to_dimensions = defaultdict(lambda: {"dimensions": set(), "create_from_default": False})

        for metric_info in metric_info_list:
            field_name = metric_info.get("field_name")
            if not field_name:
                continue

            field_scope = metric_info.get("field_scope", TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME)
            tag_list = metric_info.get("tag_value_list") or metric_info.get("tag_list") or {}

            scope_name = existing_metric_scope_map.get((field_name, field_scope))
            # 对 scope_id 为 DISABLE_SCOPE_ID 的记录（disabled 指标），需要通过 _determine_scope_name_for_new_metric 找到 scope_name
            if not scope_name:
                scope_name, create_from_default = cls._determine_scope_name_for_new_metric(
                    field_name,
                    field_scope,
                    prefix_to_obj,
                    metric_group_dimensions,
                )
                scope_name_to_dimensions[scope_name]["create_from_default"] = create_from_default

            scope_name_to_metrics[scope_name].append(metric_info)
            scope_name_to_dimensions[scope_name]["dimensions"].update(tag_list.keys())

        # 检查并补充缺失的默认分组
        checked_prefixes = set()
        for scope_name in list(scope_name_to_dimensions.keys()):
            prefix = cls.get_scope_name_prefix(scope_name)
            if prefix and prefix not in checked_prefixes:
                checked_prefixes.add(prefix)
                default_scope_name = f"{prefix}||{TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME}"
                if default_scope_name not in scope_name_to_dimensions:
                    scope_name_to_dimensions[default_scope_name] = {
                        "dimensions": set(),
                        "create_from_default": True,
                    }

        return scope_name_to_metrics, scope_name_to_dimensions

    @classmethod
    def _do_bulk_refresh_ts_scopes(cls, group_id: int, scope_name_to_dimensions: dict):
        # 1. 获取已存在的 scope
        scope_name_to_obj = {
            scope.scope_name: scope
            for scope in cls.objects.filter(group_id=group_id, scope_name__in=scope_name_to_dimensions.keys())
        }

        # 2. 分别处理已存在的和不存在的 scope
        scopes_to_update = []
        scopes_to_create = []

        for scope_name, scope_info in scope_name_to_dimensions.items():
            dimensions = scope_info["dimensions"]
            create_from_default = scope_info["create_from_default"]
            scope = scope_name_to_obj.get(scope_name)

            if scope:
                # 已存在的 scope：更新维度配置
                dimension_config = scope.dimension_config or {}
                new_dims = {dim for dim in dimensions if dim not in dimension_config}
                if new_dims:
                    dimension_config.update({dim: {} for dim in new_dims})
                    scope.dimension_config = dimension_config
                    scopes_to_update.append(scope)
            else:
                # 不存在的 scope：创建新的 scope
                dimension_config = {dim: {} for dim in dimensions}
                # 根据是否为默认分组决定 create_from 字段
                create_from = cls.CREATE_FROM_DEFAULT if create_from_default else cls.CREATE_FROM_DATA
                new_scope = cls(
                    group_id=group_id,
                    scope_name=scope_name,
                    dimension_config=dimension_config,
                    auto_rules=[],
                    create_from=create_from,
                )
                scopes_to_create.append(new_scope)

        # 3. 批量创建和更新
        if scopes_to_create:
            cls.objects.bulk_create(scopes_to_create, batch_size=BULK_CREATE_BATCH_SIZE)
        if scopes_to_update:
            cls.objects.bulk_update(scopes_to_update, ["dimension_config"], batch_size=BULK_UPDATE_BATCH_SIZE)

    @classmethod
    def bulk_refresh_ts_scopes(cls, group, metric_info_list: list) -> list:
        """批量刷新 scope 并返回包含 scope_id 的指标列表

        :param group: 自定义时序数据源
        :param metric_info_list: 指标信息列表
        :return: 包含 scope_id 的新指标列表
        """
        scope_name_to_metrics, scope_name_to_dimensions = cls._collect_metrics_and_dimensions(
            group.time_series_group_id, metric_info_list, group.metric_group_dimensions
        )

        cls._do_bulk_refresh_ts_scopes(group.time_series_group_id, scope_name_to_dimensions)

        # 获取所有 scope 并构建 scope_name 到 scope_id 的映射
        all_scopes = cls.objects.filter(
            group_id=group.time_series_group_id, scope_name__in=scope_name_to_dimensions.keys()
        )
        scope_name_to_id = {scope.scope_name: scope.id for scope in all_scopes}

        # 为每个指标添加 scope_id
        new_metric_info_list = []
        for scope_name, metrics in scope_name_to_metrics.items():
            scope_id = scope_name_to_id.get(scope_name)
            for metric_info in metrics:
                # 创建新的 metric_info 副本并添加 scope_id
                new_metric_info = metric_info.copy()
                new_metric_info["scope_id"] = scope_id
                new_metric_info_list.append(new_metric_info)

        return new_metric_info_list

    @classmethod
    def _check_single_group_id(cls, bk_tenant_id, group_id):
        """检查单个 group_id 是否存在且属于当前租户

        :param bk_tenant_id: 租户ID
        :param group_id: 自定义时序数据源ID
        """

        group = TimeSeriesGroup.objects.filter(
            time_series_group_id=group_id, bk_tenant_id=bk_tenant_id, is_delete=False
        ).first()

        if not group:
            raise ValueError(_("自定义时序分组不存在，请确认后重试: group_id={}").format(group_id))

    @classmethod
    def _check_scopes_for_create(cls, bk_tenant_id: str, group_id: int, scopes: list[dict]):
        """检查批量创建的分组数据

        :param bk_tenant_id: 租户ID
        :param group_id: 自定义时序数据源ID
        :param scopes: 批量创建的分组列表
        """
        cls._check_single_group_id(bk_tenant_id, group_id)

        # 1.1 检查是否有重复的 scope_name
        final_scope_names = [scope_data.get("scope_name") for scope_data in scopes]

        existing_scopes = {
            s.scope_name: s for s in cls.objects.filter(group_id=group_id, scope_name__in=final_scope_names)
        }
        duplicate_scopes = []
        for scope_name in final_scope_names:
            if scope_name in existing_scopes:
                duplicate_scopes.append(f"{group_id}:{scope_name}")
        if duplicate_scopes:
            raise ValueError(_("指标分组名已存在，请确认后重试: {}").format(", ".join(duplicate_scopes)))

        # 1.3 检查批次内部是否有重复的 scope_name（同一 group_id 下）
        # 构建批次内的最终 scope_name 映射：{final_scope_name: [index1, index2, ...]}
        batch_scope_names = {}
        for idx, scope_name in enumerate(final_scope_names):
            batch_scope_names.setdefault(scope_name, []).append(idx)

        # 检查批次内是否有重复
        for scope_name, indices in batch_scope_names.items():
            if len(indices) > 1:
                raise ValueError(
                    _("批次内存在重复的分组名: group_id={}, scope_name={}, 位置索引={}").format(
                        group_id, scope_name, ", ".join(map(str, indices))
                    )
                )

    @classmethod
    def _create_scope_data(cls, group_id: int, scopes: list[dict]) -> dict:
        """创建分组数据

        :param group_id: 自定义时序数据源ID
        :param scopes: 批量创建的分组列表
        :return: 创建的分组字典 {scope_name: scope_obj}
        """
        # 2.1 批量创建新记录
        scopes_to_create = []
        for scope_data in scopes:
            scope_obj = cls(
                group_id=group_id,
                scope_name=scope_data.get("scope_name"),
                dimension_config=scope_data.get("dimension_config", {}),
                auto_rules=scope_data.get("auto_rules", []),
                create_from=cls.CREATE_FROM_USER,
            )
            scopes_to_create.append(scope_obj)

        if scopes_to_create:
            cls.objects.bulk_create(scopes_to_create, batch_size=BULK_CREATE_BATCH_SIZE)

        # 2.2 查询已创建的对象并返回
        final_scope_names = [s.scope_name for s in scopes_to_create]
        created_scopes = {
            s.scope_name: s for s in cls.objects.filter(group_id=group_id, scope_name__in=final_scope_names)
        }

        return created_scopes

    @classmethod
    def _build_scope_results(cls, scopes: list[dict], scope_objects: dict) -> list[dict]:
        """构建分组结果列表

        :param scopes: 原始分组列表
        :param scope_objects: 分组对象字典，可能是 {scope_id: scope_obj} 或 {scope_name: scope_obj}
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
                time_series_scope = scope_objects[scope_data.get("scope_name")]

            results.append(
                {
                    "scope_id": time_series_scope.id,
                    "group_id": time_series_scope.group_id,
                    "scope_name": time_series_scope.scope_name,
                    "dimension_config": time_series_scope.dimension_config,
                    "auto_rules": time_series_scope.auto_rules,
                    "create_from": time_series_scope.create_from,
                }
            )
        return results

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def bulk_create_or_update_scopes(
        cls,
        bk_tenant_id: str,
        group_id: int,
        scopes: list[dict],
    ) -> list[dict]:
        """批量创建或更新自定义时序指标分组

        :param bk_tenant_id: 租户ID
        :param group_id: 自定义时序数据源ID
        :param scopes: 批量创建或更新的分组列表，格式:
            [{
                "scope_id": 1,  # 可选，如果提供则更新，否则创建
                "scope_name": "test_scope",
                "dimension_config": {},
                "auto_rules": [],
            }]
        :return: 创建或更新结果列表
        """
        # 分离创建和更新的分组（通过 scope_id 判断）
        scopes_to_create = []
        scopes_to_update = []

        for scope_data in scopes:
            scope_id = scope_data.get("scope_id")
            if scope_id:
                # scope_id 存在，执行更新操作
                scopes_to_update.append(scope_data)
            else:
                # scope_id 不存在，执行创建操作
                scopes_to_create.append(scope_data)

        results = []

        # 批量创建
        if scopes_to_create:
            # 第一步：检查
            cls._check_scopes_for_create(bk_tenant_id, group_id, scopes_to_create)
            # 第二步：创建
            created_scopes = cls._create_scope_data(group_id, scopes_to_create)
            # 第三步：构建结果
            create_results = cls._build_scope_results(scopes_to_create, created_scopes)
            results.extend(create_results)

        # 批量更新
        if scopes_to_update:
            # 第一步：检查
            existing_scopes = cls._check_scopes_for_modify(bk_tenant_id, group_id, scopes_to_update)
            # 第二步：更新
            updated_scopes = cls._update_scopes_data(scopes_to_update, existing_scopes)
            # 第三步：构建结果
            update_results = cls._build_scope_results(scopes_to_update, updated_scopes)
            results.extend(update_results)

        return results

    @classmethod
    def _check_scopes_for_modify(cls, bk_tenant_id: str, group_id: int, scopes: list[dict]) -> dict:
        """检查批量修改的分组数据

        :param bk_tenant_id: 租户ID
        :param group_id: 自定义时序数据源ID
        :param scopes: 批量修改的分组列表
        :return: existing_scopes 现有分组对象字典 {scope_id: scope_obj}
        """
        cls._check_single_group_id(bk_tenant_id, group_id)

        # 批量查询要更新的记录
        scope_ids = [scope_data["scope_id"] for scope_data in scopes]
        existing_scopes = {s.id: s for s in cls.objects.filter(id__in=scope_ids)}

        # 检查 scope 是否存在并验证 group_id
        missing_scope_ids = set(scope_ids) - set(existing_scopes.keys())
        if missing_scope_ids:
            raise ValueError(
                _("指标分组不存在，请确认后重试: scope_id={}").format(", ".join(map(str, missing_scope_ids)))
            )

        for scope_id, scope_obj in existing_scopes.items():
            if scope_obj.group_id != group_id:
                raise ValueError(
                    _("指标分组的 group_id 不匹配: scope_id={}, 期望 group_id={}, 实际 group_id={}").format(
                        scope_id, group_id, scope_obj.group_id
                    )
                )

        # 检查批次内部是否有重复的 scope_name
        batch_scope_names = {}
        for scope_data in scopes:
            scope_obj = existing_scopes[scope_data["scope_id"]]
            final_scope_name = scope_data.get("scope_name") or scope_obj.scope_name
            batch_scope_names.setdefault(final_scope_name, []).append(scope_data["scope_id"])

        for scope_name, sids in batch_scope_names.items():
            if len(sids) > 1:
                raise ValueError(
                    _("批次内存在重复的分组名: scope_name={}, scope_ids={}").format(
                        scope_name, ", ".join(map(str, sids))
                    )
                )

        # 批量查询该 group 下已存在的 scope_name（排除本批次）
        existing_scope_names = set(
            cls.objects.filter(group_id=group_id).exclude(id__in=scope_ids).values_list("scope_name", flat=True)
        )

        # 检查分组名修改的合法性
        for scope_data in scopes:
            new_scope_name = scope_data.get("scope_name")
            if not new_scope_name:
                continue

            scope_obj = existing_scopes[scope_data["scope_id"]]
            if new_scope_name == scope_obj.scope_name:
                continue

            if scope_obj.is_create_from_data_or_default():
                raise ValueError(
                    _("数据自动创建的分组不允许修改分组名: scope_id={}, scope_name={}").format(
                        scope_obj.id, scope_obj.scope_name
                    )
                )

            if new_scope_name in existing_scope_names:
                raise ValueError(_("指标分组名已存在: scope_name={}").format(new_scope_name))

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
            if scope_data.get("scope_name") is not None:
                final_new_scope_name = scope_data.get("scope_name")
                if final_new_scope_name != scope_obj.scope_name:
                    scope_obj.scope_name = final_new_scope_name
                    update_fields.add("scope_name")
                    has_updates = True

            # 更新 dimension_config
            if scope_data.get("dimension_config") is not None:
                scope_obj.dimension_config = scope_data["dimension_config"]
                update_fields.add("dimension_config")
                has_updates = True

            # 更新 auto_rules
            auto_rules = scope_data.get("auto_rules")
            if auto_rules is not None:
                scope_obj.auto_rules = auto_rules
                update_fields.add("auto_rules")
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
    def bulk_delete_scopes(cls, bk_tenant_id: str, group_id: int, scopes: list[dict]):
        cls._check_single_group_id(bk_tenant_id, group_id)

        # 获取 TimeSeriesGroup 以获取 metric_group_dimensions
        try:
            time_series_group = TimeSeriesGroup.objects.get(time_series_group_id=group_id)
            metric_group_dimensions = time_series_group.metric_group_dimensions
        except TimeSeriesGroup.DoesNotExist:
            raise ValueError(_("指标分组不存在: {}").format(group_id))

        # 批量获取要删除的 TimeSeriesScope
        requested_scope_names = {scope_data.get("scope_name") for scope_data in scopes}
        time_series_scopes = list(cls.objects.filter(group_id=group_id, scope_name__in=requested_scope_names))

        # 检查是否所有 scope 都存在
        if missing := requested_scope_names - {s.scope_name for s in time_series_scopes}:
            raise ValueError(_("指标分组不存在，请确认后重试: {}").format(", ".join(missing)))

        # 检查是否有数据自动创建的分组，不允许删除
        data_created_scopes = [s.scope_name for s in time_series_scopes if s.is_create_from_data_or_default()]
        if data_created_scopes:
            raise ValueError(_("不允许删除数据自动创建的分组: {}").format(", ".join(data_created_scopes)))

        # 迁移指标和维度配置到默认分组
        scope_moves = {}
        for source_scope in time_series_scopes:
            # 1. 使用 get_default_scope_info 方法获取默认分组信息（基于 metric_group_dimensions）
            default_scope_name = TimeSeriesGroup.get_default_scope_info(
                source_scope.scope_name, metric_group_dimensions
            )[1]

            # 2. 获取或创建默认分组
            default_scope = cls.objects.get(group_id=group_id, scope_name=default_scope_name)

            # 3. 查询该分组下的所有指标
            moved_metrics = list(
                TimeSeriesMetric.objects.filter(group_id=group_id, scope_id=source_scope.id).select_for_update()
            )

            # 4. 收集需要迁移的信息
            if moved_metrics:
                scope_moves[(source_scope, default_scope)] = moved_metrics

        # 5. 批量更新指标的 scope_id 和维度配置
        cls.update_dimension_config_and_metrics_scope_id(scope_moves)

        # 删除分组（在维度配置更新之后）
        cls.objects.filter(pk__in=[s.id for s in time_series_scopes]).delete()


class TimeSeriesMetric(models.Model):
    """
    自定义时序指标表
    """

    TARGET_DIMENSION_NAME = "target"

    DEFAULT_DATA_SCOPE_NAME = "default"  # 默认分组
    DISABLE_SCOPE_ID = 0  # 禁用分组的 id，实际上不存在该分组记录

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
        "alias",  # 别名
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
    # 关联到 TimeSeriesScope 的主键 id，用于标识指标所属的分组
    scope_id = models.IntegerField(verbose_name="时序分组ID", null=True, blank=True, db_index=True)
    table_id = models.CharField(verbose_name="table名", default="", max_length=255)
    field_scope = models.CharField(
        verbose_name="指标字段数据分组名", default=DEFAULT_DATA_SCOPE_NAME, max_length=255, db_collation="utf8_bin"
    )
    field_name = models.CharField(verbose_name="指标字段名称", max_length=255, db_collation="utf8_bin")
    tag_list = JsonField(verbose_name="Tag列表", default=[])

    # 字段其他配置，可配置的字段 key 需要在 MetricConfigFields 中定义
    field_config = models.JSONField(verbose_name="字段其他配置", default=dict)

    create_time = models.DateTimeField(verbose_name="创建时间", auto_now_add=True, null=True)
    last_modify_time = models.DateTimeField(verbose_name="最后更新时间", auto_now=True)

    label = models.CharField(verbose_name="指标监控对象", default="", max_length=255, db_index=True)
    is_active = models.BooleanField(verbose_name="是否活跃", default=True, db_index=True, help_text="指标是否活跃")

    # 已废弃，已转为从 bkbase 获取数据，consul 会逐步下线
    last_index = models.IntegerField(verbose_name="上次consul的modify_index", default=0)

    class Meta:
        # 同一个数据源，同一个分组下，不可以存在同样的指标字段名称
        unique_together = ("group_id", "field_scope", "field_name")
        verbose_name = "自定义时序描述记录"
        verbose_name_plural = "自定义时序描述记录表"

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
    def _bulk_create_metrics(
        cls,
        metrics_dict: dict,
        need_create_metrics: list | set,
        group_id: int,
        table_id: str,
        is_auto_discovery: bool,
    ) -> bool:
        """批量创建指标"""
        records = []

        for field_name, field_scope in need_create_metrics:
            metric_info = metrics_dict.get((field_name, field_scope))
            # 如果获取不到指标数据，则跳过
            if not metric_info:
                continue
            # 当指标是禁用的, 如果开启自动发现 则需要时间设置为 1970; 否则，跳过记录
            if not metric_info.get("is_active", True) and not is_auto_discovery:
                continue
            tag_list = cls.get_metric_tag_from_metric_info(metric_info)
            params = {
                "field_name": field_name,
                "group_id": group_id,
                "table_id": f"{table_id.split('.')[0]}.{field_name}",
                "tag_list": tag_list,
                "field_scope": field_scope,
                "scope_id": metric_info.get("scope_id"),
                "is_active": True,  # 新创建的指标在返回列表中，标记为活跃
            }
            logger.info("create ts metric data: %s", json.dumps(params))
            records.append(cls(**params))

        # 开始批量创建指标
        cls.objects.bulk_create(records, batch_size=BULK_CREATE_BATCH_SIZE)
        return True

    @classmethod
    def _bulk_update_metrics(
        cls,
        metrics_dict: dict,
        need_update_metrics: list | set,
        group_id: int,
        is_auto_discovery: bool,
    ) -> bool:
        """批量更新指标，针对记录仅更新最后更新时间和 tag 字段"""
        records = []
        white_list_disabled_metric = set()
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

            metric_info = metrics_dict.get((obj.field_name, obj.field_scope))
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
                    white_list_disabled_metric.add(obj.id)

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
            tag_list = cls.get_metric_tag_from_metric_info(metric_info)
            if set(obj.tag_list or []) != set(tag_list):
                is_need_update = True
                obj.tag_list = tag_list

            # 如果指标从 disabled 状态恢复，需要更新 scope_id 和清空 field_config
            if obj.scope_id == cls.DISABLE_SCOPE_ID:
                is_need_update = True
                obj.scope_id = metric_info.get("scope_id")
                obj.field_config = {}

            # 更新 is_active 字段：指标在返回列表中，标记为活跃
            if not obj.is_active:
                logger.info(
                    "_bulk_update_metrics: set active metrics for group_id->[%s], metric->[%s]",
                    group_id,
                    obj.field_name,
                )
                is_need_update = True
                obj.is_active = True

            if is_need_update:
                records.append(obj)

        # 白名单模式，如果存在需要禁用的指标，则需要删除；应该不会太多，直接删除
        if white_list_disabled_metric:
            cls.objects.filter(group_id=group_id, field_id__in=white_list_disabled_metric).delete()
        logger.info("white list disabled metric: %s, group_id: %s", json.dumps(white_list_disabled_metric), group_id)

        # 批量更新指定的字段
        cls.objects.bulk_update(
            records,
            ["last_modify_time", "tag_list", "scope_id", "field_config", "is_active"],
            batch_size=BULK_UPDATE_BATCH_SIZE,
        )
        return need_push_router

    @classmethod
    def bulk_refresh_ts_metrics(
        cls,
        group_id: int,
        table_id: str,
        metric_info_list: list,
        is_auto_discovery: bool,
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
        _metrics_dict = {
            (m["field_name"], m.get("field_scope", TimeSeriesMetric.DEFAULT_DATA_SCOPE_NAME)): m
            for m in metric_info_list
            if m.get("field_name")
        }

        old_metric_to_ids = {
            (m[1], m[2]): m[0]
            for m in cls.objects.filter(group_id=group_id).values_list("field_id", "field_name", "field_scope")
        }
        old_records = set(old_metric_to_ids.keys())
        new_records = set(_metrics_dict.keys())

        # 计算需要创建和更新的记录
        need_create_metrics = new_records - old_records
        need_update_metrics = new_records & old_records

        # NOTE: 针对创建或者时间变动时，推送路由数据
        need_push_router = False
        # 如果存在，则批量创建
        if need_create_metrics:
            need_push_router = cls._bulk_create_metrics(
                _metrics_dict, need_create_metrics, group_id, table_id, is_auto_discovery
            )
        # 批量更新
        if need_update_metrics:
            need_push_router |= cls._bulk_update_metrics(
                _metrics_dict, need_update_metrics, group_id, is_auto_discovery
            )

        # 处理不在返回列表中的已存在指标，设置为非活跃
        inactive_metrics = old_records - new_records
        if inactive_metrics:
            # 批量更新不在返回列表中的指标为非活跃状态
            field_ids = [old_metric_to_ids.get(k) for k in inactive_metrics]
            cls.objects.filter(group_id=group_id, field_id__in=field_ids, is_active=True).update(is_active=False)
            logger.info(
                "bulk_refresh_ts_metrics: set inactive metrics for group_id->[%s], metrics->[%s]",
                group_id,
                json.dumps(list(inactive_metrics)),
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

    def to_metric_info_with_label(self, group: TimeSeriesGroup, field_map=None, scope_map=None):
        """
         {
            "field_name": "mem_usage",
            "description": "mem_usage_2",  # 优先使用 field_config["alias"]
            "unit": "M",  # 优先使用 field_config["unit"]
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

        # 优先使用 field_config，如果不存在才使用 orm_field
        field_config = self.field_config or {}
        orm_field = orm_field_map[self.field_name]
        result["table_id"] = self.table_id
        result["description"] = field_config.get("alias", orm_field["description"])
        result["unit"] = field_config.get("unit", orm_field["unit"])
        result["type"] = orm_field["field_type"]

        # 获取当前 metric 对应的 scope 的 dimension_config
        dimension_config = {}
        if scope_map and self.scope_id and self.scope_id in scope_map:
            scope = scope_map[self.scope_id]
            dimension_config = scope.dimension_config or {}

        for tag in self.tag_list:
            item = {"field_name": tag, "description": ""}
            # 如果维度不存在了，则表示字段可能已经被删除了
            if tag in orm_field_map:
                orm_field = orm_field_map[tag]
                item["description"] = orm_field["description"]
                item["unit"] = orm_field["unit"]
                item["type"] = orm_field["field_type"]

            if tag in dimension_config:
                item["description"] = dimension_config[tag].get("alias", item["description"])

            result["tag_list"].append(item)

        return result

    def to_metric_info(self, field_map=None, group=None, scope_map=None):
        """
         {
            "field_name": "mem_usage",
            "description": "mem_usage_2",  # 优先使用 field_config["alias"]
            "unit": "M",  # 优先使用 field_config["unit"]
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

        # 优先使用 field_config，如果不存在才使用 orm_field
        field_config = self.field_config or {}
        orm_field = orm_field_map[self.field_name]
        result["table_id"] = self.table_id
        result["description"] = field_config.get("alias", orm_field["description"])
        result["unit"] = field_config.get("unit", orm_field["unit"])
        result["type"] = orm_field["field_type"]
        result["is_disabled"] = field_config.get("disabled", orm_field["is_disabled"])

        # 获取当前 metric 对应的 scope 的 dimension_config
        dimension_config = {}
        if scope_map and self.scope_id and self.scope_id in scope_map:
            scope = scope_map[self.scope_id]
            dimension_config = scope.dimension_config or {}

        # 遍历维度填充维度信息
        for tag in self.tag_list:
            item = {"field_name": tag, "description": ""}
            # 如果维度不存在了，则表示字段可能已经被删除了
            if tag in orm_field_map:
                orm_field = orm_field_map[tag]
                item["description"] = orm_field["description"]
                item["unit"] = orm_field["unit"]
                item["type"] = orm_field["field_type"]

            if tag in dimension_config:
                item["description"] = dimension_config[tag].get("alias", item["description"])

            result["tag_list"].append(item)

        return result

    @classmethod
    @atomic
    def batch_create_or_update(cls, metrics_data: list, bk_tenant_id: str, group_id: int):
        """批量创建或更新时序指标

        :param metrics_data: 指标数据列表，每个元素包含字段信息
        :param bk_tenant_id: 租户ID
        :param group_id: 自定义时序数据源ID
        """
        # 验证group_id是否存在
        time_series_group = TimeSeriesGroup.objects.filter(
            time_series_group_id=group_id,
            bk_tenant_id=bk_tenant_id,
            is_delete=False,
        ).first()

        if not time_series_group:
            raise ValueError(f"自定义时序分组不存在，请确认后重试。分组ID: {group_id}")

        table_id = time_series_group.table_id

        # 批量查找已存在的指标
        field_ids = [m.get("field_id") for m in metrics_data if m.get("field_id")]
        existing_metrics_map = {
            metric.field_id: metric for metric in cls.objects.filter(field_id__in=field_ids, group_id=group_id)
        }

        existing_disabled_metrics_map = {
            (metric.field_name, metric.field_scope): metric
            for metric in cls.objects.filter(group_id=group_id, scope_id=cls.DISABLE_SCOPE_ID)
        }

        # 分离需要创建和更新的指标
        metrics_to_create = []
        metrics_to_update = []

        for metric_data in metrics_data:
            metric_data_copy = metric_data.copy()
            field_id = metric_data_copy.get("field_id")
            metric = existing_metrics_map.get(field_id) if field_id else None

            # 如果指标存在，准备更新
            if metric is not None:
                metrics_to_update.append((metric, metric_data_copy))
                continue

            # 检查是否有禁用的指标需要重启
            field_name = metric_data_copy.get("field_name")
            field_scope = metric_data_copy.get("field_scope", cls.DEFAULT_DATA_SCOPE_NAME)
            disabled_metric = existing_disabled_metrics_map.get((field_name, field_scope))

            # 如果有禁用的指标
            if disabled_metric:
                metric_data_copy["field_config"].update({"disabled": False})
                metrics_to_update.append((disabled_metric, metric_data_copy))
                continue

            # 准备创建新指标
            metrics_to_create.append(metric_data_copy)

        scopes_dict = {scope.id: scope for scope in TimeSeriesScope.objects.filter(group_id=group_id)}
        scopes_dict[TimeSeriesMetric.DISABLE_SCOPE_ID] = TimeSeriesScope(
            id=TimeSeriesMetric.DISABLE_SCOPE_ID,
            group_id=-1,
            scope_name="DISABLE_SCOPE_ID",
            create_from=TimeSeriesScope.CREATE_FROM_DEFAULT,
        )

        # 批量创建新指标
        if metrics_to_create:
            cls._batch_create_metrics(metrics_to_create, group_id, table_id, scopes_dict)

        # 批量更新现有指标
        if metrics_to_update:
            cls._batch_update_metrics(metrics_to_update, scopes_dict)

    @classmethod
    def _batch_create_metrics(cls, metrics_to_create, group_id, table_id, scopes_dict):
        # 检查字段名称冲突
        cls._validate_field_name_conflicts(metrics_to_create)

        # 准备批量创建的数据
        records_to_create = []
        scope_moves = defaultdict(list)

        for metric_data in metrics_to_create:
            tag_list = metric_data.get("tag_list") or []
            target_dimension = cls.TARGET_DIMENSION_NAME

            if target_dimension not in tag_list:
                metric_data["tag_list"] = tag_list + [target_dimension]

            database_name = table_id.rsplit(".", 1)[0]
            metric_data["table_id"] = f"{database_name}.{metric_data['field_name']}"

            scope_id = metric_data.get("scope_id")
            scope = scopes_dict.get(scope_id)
            if scope is None:
                raise ValueError(f"指标分组不存在，请确认后重试。分组ID: {scope_id}")

            metric_obj = cls(
                table_id=metric_data["table_id"],
                field_name=metric_data["field_name"],
                field_scope=metric_data.get("field_scope", cls.DEFAULT_DATA_SCOPE_NAME),
                group_id=group_id,
                scope_id=scope_id,
                tag_list=metric_data.get("tag_list", []),
                field_config=metric_data.get("field_config", {}),
                label=metric_data.get("label", ""),
            )
            records_to_create.append(metric_obj)
            scope_moves[(None, scope)].append(metric_obj)

        # 批量创建
        cls.objects.bulk_create(records_to_create, batch_size=BULK_CREATE_BATCH_SIZE)

        TimeSeriesScope.update_dimension_config_and_metrics_scope_id(scope_moves=scope_moves, need_update_metrics=False)

    @classmethod
    def _batch_update_metrics(cls, metrics_to_update, scopes_dict):
        updatable_fields = ["field_config", "label", "tag_list", "scope_id", "last_modify_time"]
        records_to_update = []
        scope_moves = defaultdict(list)

        for metric, validated_request_data in metrics_to_update:
            # 保存原始的 tag_list 和 scope_id，用于检测变化
            original_tag_list = metric.tag_list or []
            original_scope_id = metric.scope_id

            # 统一更新字段值 updatable_fields
            for field in updatable_fields:
                setattr(metric, field, validated_request_data.get(field, getattr(metric, field)))

            # 更新最后修改时间
            metric.last_modify_time = tz_now()

            # 如果 field_config 中 disabled 为 true，将 scope_id 置为 DISABLE_SCOPE_ID, 并跳过维度配置更新
            field_config = validated_request_data.get("field_config") or metric.field_config or {}
            if field_config.get("disabled", False):
                metric.scope_id = cls.DISABLE_SCOPE_ID
                records_to_update.append(metric)
                continue

            records_to_update.append(metric)

            scope_id = validated_request_data.get("scope_id")
            new_scope = scopes_dict.get(scope_id)
            if new_scope is None:
                raise ValueError(f"指标分组不存在，请确认后重试。分组ID: {scope_id}")

            # 检测是否需要记录移动的指标
            scope_changed = new_scope and original_scope_id != new_scope.id
            source_scope = scopes_dict.get(original_scope_id)

            # 如果 scope 是 data 类型，不允许修改 scope_id
            if scope_changed and source_scope.create_from == TimeSeriesScope.CREATE_FROM_DATA:
                raise ValueError(f"数据自动创建的指标分组不允许修改，请确认后重试。分组ID: {original_scope_id}")

            tag_list_changed = set(original_tag_list) != set(metric.tag_list or [])

            # 如果 scope 发生变化或者 tag_list 发生变化，记录需要移动的指标
            if scope_changed or tag_list_changed:
                scope_moves[(source_scope, new_scope)].append(metric)

        # 批量更新所有指标的字段
        if records_to_update:
            cls.objects.bulk_update(records_to_update, updatable_fields, batch_size=BULK_UPDATE_BATCH_SIZE)

        TimeSeriesScope.update_dimension_config_and_metrics_scope_id(scope_moves=scope_moves)

    @classmethod
    def _validate_field_name_conflicts(cls, metrics_to_create):
        """检查字段名称冲突"""
        # 收集所有字段名
        field_names = []
        for metric_data in metrics_to_create:
            field_name = metric_data.get("field_name")
            if not field_name:
                raise ValueError("创建指标时，field_name为必填项")
            field_names.append(field_name)

        # 检查同一批次内是否有重复的字段名
        unique_field_names = set(field_names)
        if len(field_names) != len(unique_field_names):
            # 找出重复的字段名
            seen = set()
            batch_conflicting_names = []
            for name in field_names:
                if name in seen and name not in batch_conflicting_names:
                    batch_conflicting_names.append(name)
                seen.add(name)
            raise ValueError(f"同一批次内指标字段名称[{', '.join(batch_conflicting_names)}]重复，请使用其他名称")

        # todo 检查跨批次的字段名冲突, 现在直接依赖数据库的唯一索引来保证


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

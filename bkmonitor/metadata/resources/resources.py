"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import json
import logging
import tempfile
import time
import uuid
from itertools import chain
from typing import Any

import yaml
from confluent_kafka import Consumer as ConfluentConsumer
from confluent_kafka import KafkaError, KafkaException
from confluent_kafka import TopicPartition as ConfluentTopicPartition
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db.models.query import QuerySet
from django.utils.translation import gettext as _
from kafka import KafkaConsumer, TopicPartition
from kubernetes import utils
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from tenacity import RetryError

from bkmonitor.utils import consul
from bkmonitor.utils.k8s_metric import get_built_in_k8s_events, get_built_in_k8s_metrics
from bkmonitor.utils.request import get_app_code_by_request, get_request, get_request_tenant_id
from bkmonitor.utils.serializers import TenantIdField
from constants.common import DEFAULT_TENANT_ID
from constants.data_source import DATA_LINK_V4_VERSION_NAME
from core.drf_resource import Resource, api
from metadata import config, models
from metadata.config import (
    ES_ROUTE_ALLOW_URL,
    cluster_custom_metric_name,
    k8s_event_name,
    k8s_metric_name,
)
from metadata.models.bcs import (
    BCSClusterInfo,
    LogCollectorInfo,
    PodMonitorInfo,
    ServiceMonitorInfo,
)
from metadata.models.constants import (
    DT_TIME_STAMP_NANO,
    EPOCH_MILLIS_FORMAT,
    NANO_FORMAT,
    STRICT_NANO_ES_FORMAT,
    DataIdCreatedFromSystem,
)
from metadata.models.data_link.constants import BKBASE_NAMESPACE_BK_LOG
from metadata.models.data_link.data_link_configs import DataIdConfig
from metadata.models.data_link.utils import (
    compose_bkdata_data_id_name,
    get_bkbase_raw_data_name_for_v3_datalink,
    get_data_source_related_info,
)
from metadata.models.result_table import ResultTableOption
from metadata.models.space.constants import SPACE_UID_HYPHEN, EtlConfigs, SpaceTypes
from metadata.models.space.space_table_id_redis import SpaceTableIDRedis
from metadata.service.data_source import (
    modify_data_id_source,
    stop_or_enable_datasource,
)
from metadata.service.storage_details import ResultTableAndDataSource
from metadata.task.bcs import refresh_dataid_resource
from metadata.utils.bcs import get_bcs_dataids
from metadata.utils.bkbase import sync_bkbase_result_table_meta
from metadata.utils.data_link import get_record_rule_metrics_by_biz_id
from metadata.utils.es_tools import get_client

logger = logging.getLogger("metadata")


class FieldSerializer(serializers.Serializer):
    field_name = serializers.CharField(required=True, label="字段名")
    field_type = serializers.CharField(required=True, label="字段类型")
    tag = serializers.CharField(required=True, label="字段类型，指标或维度")
    unit = serializers.CharField(required=False, allow_blank=True, default="", label="字段单位")
    description = serializers.CharField(required=False, allow_blank=True, default="", label="字段描述")
    alias_name = serializers.CharField(required=False, label="字段别名", default="", allow_blank=True)
    option = serializers.DictField(required=False, label="字段选项", default={})
    is_reserved_check = serializers.BooleanField(required=False, label="是否进行保留字检查", default=True)


class QueryAliasSettingSerializer(serializers.Serializer):
    field_name = serializers.CharField(required=True, label="字段名", help_text="需要设置查询别名的字段名")
    query_alias = serializers.CharField(required=True, label="查询别名", help_text="字段的查询别名")


class CreateDataIDResource(Resource):
    """创建数据源ID"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
        data_name = serializers.CharField(required=True, label="数据源名称")
        etl_config = serializers.CharField(required=True, label="清洗模板配置")
        operator = serializers.CharField(required=True, label="操作者")
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID")
        mq_cluster = serializers.IntegerField(required=False, label="数据源使用的消息集群", default=None)
        mq_config = serializers.DictField(required=False, label="数据源消息队列配置", default={})
        data_description = serializers.CharField(required=False, label="数据源描述")
        is_custom_source = serializers.BooleanField(required=False, label="是否用户自定义数据源", default=True)
        source_label = serializers.CharField(required=True, label="数据源标签")
        type_label = serializers.CharField(required=True, label="数据类型标签")
        option = serializers.DictField(required=False, label="数据源配置项")
        custom_label = serializers.CharField(required=False, label="自定义标签")
        transfer_cluster_id = serializers.CharField(required=False, label="transfer集群ID")
        space_uid = serializers.CharField(label="空间英文名称", required=False, default="")
        authorized_spaces = serializers.JSONField(required=False, label="授权使用的空间 ID 列表", default=[])
        is_platform_data_id = serializers.BooleanField(required=False, label="是否为平台级 ID", default=False)
        space_type_id = serializers.CharField(required=False, label="数据源所属类型", default=SpaceTypes.ALL.value)

    def perform_request(self, validated_request_data):
        space_uid = validated_request_data.pop("space_uid", None)

        if space_uid:
            try:
                validated_request_data["space_type_id"], validated_request_data["space_id"] = space_uid.split(
                    SPACE_UID_HYPHEN
                )
                validated_request_data["space_uid"] = space_uid
            except ValueError:
                raise ValueError(_("空间唯一标识{}错误").format(space_uid))

        request = get_request(peaceful=True)
        bk_app_code = get_app_code_by_request(request) if request else None
        # 当请求的 app_code 为空时，记录请求，用于后续优化处理
        if not bk_app_code:
            logger.error(
                "app_code is null when create data source, request params: %s", json.dumps(validated_request_data)
            )

        # 默认来源系统标识
        default_source_system = "unknown"
        validated_request_data["source_system"] = bk_app_code or default_source_system

        new_data_source = models.DataSource.create_data_source(**validated_request_data)

        return {"bk_data_id": new_data_source.bk_data_id}


class GetOrCreateAgentEventDataIdResource(Resource):
    """
    获取/创建 Agent事件 数据ID
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data.get("bk_biz_id")
        space_uid = f"{SpaceTypes.BKCC.value}__{bk_biz_id}"
        etl_config = EtlConfigs.BK_MULTI_TENANCY_AGENT_EVENT_ETL_CONFIG.value
        logger.info(
            "GetOrCreateAgentEventDataIdResource: try to get_or_create agent event data id,bk_biz_id->[%s]", bk_biz_id
        )
        try:
            data_source = models.DataSource.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"], space_uid=space_uid, etl_config=etl_config
            )
            return {"bk_data_id": data_source.bk_data_id}
        except models.DataSource.DoesNotExist:  # 若不存在,则进行申请新建
            pass
        except Exception as e:  # pylint: disable=broad-except
            logger.error("GetOrCreateAgentEventDataIdResource: unexpected error occurred,bk_biz_id->[%s]", bk_biz_id)
            raise e  # 非不存在类报错,直接Raise

        logger.info("GetOrCreateAgentEventDataIdResource: try to create agent event data id,bk_biz_id->[%s]", bk_biz_id)

        data_name = f"base_{bk_biz_id}_agent_event"  # UNIQUE KEY

        logger.info(
            "GetOrCreateAgentEventDataIdResource: try to create agent event data id for bk_biz_id->[%s],"
            "use data_name->[%s]",
            bk_biz_id,
            data_name,
        )

        # 调用DataSource模型类方法,事务
        new_data_source = models.DataSource.create_data_source(
            bk_tenant_id=validated_request_data["bk_tenant_id"],
            data_name=data_name,
            etl_config=etl_config,
            operator="system",
            source_label="bk_monitor",
            type_label="event",
            space_uid=space_uid,
            bk_biz_id=bk_biz_id,
        )

        return {"bk_data_id": new_data_source.bk_data_id}


class ModifyDatasourceResultTable(Resource):
    """切换结果表与数据源的关联关系"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        bk_data_id = serializers.IntegerField(required=True, label="数据源ID")

    def perform_request(self, validated_request_data):
        models.DataSourceResultTable.modify_table_id_datasource(**validated_request_data)


class CreateResultTableResource(Resource):
    """创建结果表"""

    class RequestSerializer(serializers.Serializer):
        # 豁免space_uid 注入
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.IntegerField(required=True, label="数据源ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        table_name_zh = serializers.CharField(required=True, label="结果表中文名")
        bk_biz_id_alias = serializers.CharField(required=False, label="过滤条件业务ID别名")
        is_custom_table = serializers.BooleanField(required=True, label="是否用户自定义结果表")
        schema_type = serializers.CharField(required=True, label="结果表字段配置方案")
        operator = serializers.CharField(required=True, label="操作者")
        default_storage = serializers.CharField(required=True, label="默认存储方案")
        default_storage_config = serializers.DictField(required=False, label="默认存储参数")
        field_list = FieldSerializer(many=True, required=False, label="字段列表")
        query_alias_settings = QueryAliasSettingSerializer(
            many=True, required=False, label="查询别名设置", help_text="字段查询别名的配置"
        )
        bk_biz_id = serializers.IntegerField(required=False, label="结果表所属ID", default=0)
        label = serializers.CharField(required=False, label="结果表标签", default=models.Label.RESULT_TABLE_LABEL_OTHER)
        external_storage = serializers.JSONField(required=False, label="额外存储配置", default=None)
        is_time_field_only = serializers.BooleanField(required=False, label="是否仅需要提供时间默认字段", default=False)
        option = serializers.JSONField(required=False, label="结果表选项内容", default=None)
        time_alias_name = serializers.CharField(required=False, label="时间节点")
        time_option = serializers.DictField(required=False, label="时间字段选项配置", default=None)
        is_sync_db = serializers.BooleanField(required=False, label="是否需要同步创建真实表", default=True)
        data_label = serializers.CharField(required=False, label="数据标签", default="")

    def perform_request(self, request_data):
        query_alias_settings = request_data.pop("query_alias_settings", [])
        table_id = request_data.get("table_id", None)
        operator = request_data.get("operator", None)
        bk_tenant_id = request_data["bk_tenant_id"]

        if query_alias_settings:
            try:
                logger.info(
                    "CreateResultTableResource: try to manage alias_settings,table_id->[%s],query_alias_settings->["
                    "%s],bk_tenant_id->[%s]",
                    table_id,
                    query_alias_settings,
                    bk_tenant_id,
                )
                models.ESFieldQueryAliasOption.manage_query_alias_settings(
                    table_id=table_id,
                    query_alias_settings=query_alias_settings,
                    operator=operator,
                    bk_tenant_id=bk_tenant_id,
                )
            except Exception as e:  # pylint: disable=broad-except
                logger.warning(
                    "CreateResultTableResource: manage alias_settings failed,table_id->[%s],query_alias_settings->["
                    "%s],error->[%s]",
                    table_id,
                    query_alias_settings,
                    e,
                )
        try:
            new_result_table = models.ResultTable.create_result_table(**request_data)
        except RetryError as e:
            logger.error(
                "CreateResultTableResource: create table failed, table_id->[%s], error->[%s]", table_id, e.__cause__
            )
            raise e
        except Exception as e:
            logger.error("CreateResultTableResource: create table failed, table_id->[%s], error->[%s]", table_id, e)
            raise e
        return {"table_id": new_result_table.table_id}


class PageSerializer(serializers.Serializer):
    page = serializers.IntegerField(default=1, required=False, label="页数", min_value=1)
    page_size = serializers.IntegerField(default=0, required=False, label="页长")


# TODO 这个接口需要确认，后续应该不允许全业务查询
class ListResultTableResource(Resource):
    """查询返回结果表"""

    class RequestSerializer(PageSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        datasource_type = serializers.CharField(required=False, label="过滤的结果表类型", default=None)
        bk_biz_id = serializers.IntegerField(required=False, label="获取指定业务下的结果表信息", default=None)
        with_option = serializers.BooleanField(required=False, label="是否包含option字段信息", default=True)
        is_public_include = serializers.IntegerField(required=False, label="是否包含全业务结果表", default=None)
        is_config_by_user = serializers.BooleanField(
            required=False, label="是否需要包含非用户定义的结果表", default=True
        )

    def perform_request(self, request_data):
        bk_tenant_id = request_data["bk_tenant_id"]

        # 获取bcs相关的dataid
        data_ids, _ = get_bcs_dataids()

        # 使用datasource排除掉dataid,得到table_id列表
        table_ids = [
            item["table_id"]
            for item in models.DataSourceResultTable.objects.filter(bk_tenant_id=bk_tenant_id)
            .exclude(bk_data_id__in=data_ids)
            .values("table_id")
            .distinct()
        ]

        # 只查询不属于bcs指标的信息
        result_table_queryset = models.ResultTable.objects.filter(
            bk_tenant_id=bk_tenant_id, is_deleted=False, table_id__in=table_ids
        )

        # 判断是否有结果表类型的过滤
        datasource_type = request_data["datasource_type"]
        if datasource_type is not None:
            result_table_queryset = result_table_queryset.filter(table_id__startswith=f"{datasource_type}.")

        # 判断是否有全业务和单业务的过滤需求
        bk_biz_id = []
        if request_data["is_public_include"] is not None and request_data["is_public_include"]:
            bk_biz_id.append(0)

        if request_data["bk_biz_id"] is not None:
            bk_biz_id.append(request_data["bk_biz_id"])

        record_rule_metrics = []
        if len(bk_biz_id) != 0:
            result_table_queryset = result_table_queryset.filter(bk_biz_id__in=bk_biz_id)
            # 拼接预计算指标信息
            logger.info("ListResultTableResource: try to get precal metrics for bk_biz_ids->[%s]", bk_biz_id)
            for biz_id in bk_biz_id:
                logger.info("ListResultTableResource: try to get precal metrics for bk_biz_id->[%s]", biz_id)
                try:
                    precal_metrics = get_record_rule_metrics_by_biz_id(bk_biz_id=biz_id)
                except Exception as e:
                    logger.error(
                        "ListResultTableResource: get_record_rule_metrics_by_biz_id failed, "
                        "bk_biz_id->[%s], error->[%s]",
                        bk_biz_id,
                        e,
                    )
                    precal_metrics = []
                record_rule_metrics.extend(precal_metrics)

        # 判断是否需要带上非用户字段的内容
        if request_data["is_config_by_user"]:
            result_table_queryset = result_table_queryset.filter(~Q(table_id__endswith="_cmdb_level"))

        if request_data["page_size"] > 0:
            # page_size > 0 才分页
            count = result_table_queryset.count()
            limit = request_data["page_size"]
            offset = (request_data["page"] - 1) * request_data["page_size"]

            result_table_id_list = list(
                result_table_queryset.values_list("table_id", flat=True)[offset : offset + limit]
            )
            result_list = models.ResultTable.batch_to_json(
                bk_tenant_id=bk_tenant_id,
                result_table_id_list=result_table_id_list,
                with_option=request_data["with_option"],
            )
            return {"count": count, "info": result_list}

        result_table_id_list = list(result_table_queryset.values_list("table_id", flat=True))
        result_list = models.ResultTable.batch_to_json(
            bk_tenant_id=bk_tenant_id,
            result_table_id_list=result_table_id_list,
            with_option=request_data["with_option"],
        )

        if record_rule_metrics:
            logger.info("ListResultTableResource: bk_biz_ids->[%s] get precal metrics,try to extend them", bk_biz_id)
            result_list.extend(record_rule_metrics)
        return result_list


class ModifyResultTableResource(Resource):
    """修改结果表"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        operator = serializers.CharField(required=True, label="操作者")
        bk_biz_id_alias = serializers.CharField(required=False, label="过滤条件业务ID别名")
        field_list = FieldSerializer(many=True, required=False, label="字段列表", default=None)
        query_alias_settings = QueryAliasSettingSerializer(
            many=True, required=False, label="查询别名设置", help_text="字段查询别名的配置"
        )
        table_name_zh = serializers.CharField(required=False, label="结果表中文名")
        default_storage = serializers.CharField(required=False, label="默认存储方案")
        label = serializers.CharField(required=False, label="结果表标签", default=None)
        external_storage = serializers.DictField(required=False, label="额外存储", default=None)
        option = serializers.JSONField(required=False, label="结果表选项内容", default=None)
        is_enable = serializers.BooleanField(required=False, label="是否启用结果表", default=None)
        is_time_field_only = serializers.BooleanField(required=False, label="默认字段仅有time", default=False)
        is_reserved_check = serializers.BooleanField(required=False, label="检查内置字段", default=True)
        time_option = serializers.DictField(required=False, label="时间字段选项配置", default=None, allow_null=True)
        data_label = serializers.CharField(required=False, label="数据标签", default=None)
        need_delete_storages = serializers.DictField(required=False, label="需要删除的额外存储", default=None)

    def perform_request(self, validated_request_data: dict[str, Any]) -> dict[str, Any]:
        """执行结果表修改请求"""
        table_id = validated_request_data.pop("table_id")
        query_alias_settings = validated_request_data.pop("query_alias_settings", None)
        operator = validated_request_data.get("operator", None)
        bk_tenant_id = validated_request_data.pop("bk_tenant_id")

        # 处理查询别名设置
        self._handle_query_alias_settings(table_id, query_alias_settings, operator, bk_tenant_id)

        # 检查ES集群迁移状态
        is_moving_cluster = self._check_es_cluster_migration(table_id, validated_request_data, bk_tenant_id)

        # 修改结果表信息
        result_table = self._modify_result_table(table_id, validated_request_data, bk_tenant_id)

        # 处理ES存储相关的逻辑
        if result_table.default_storage == models.ClusterInfo.TYPE_ES:
            # 处理ES存储索引更新
            self._handle_es_storage_index_update(table_id, validated_request_data, bk_tenant_id, is_moving_cluster)

            # 通知数据平台信息变更，目前只有es类型需要通知
            self._notify_bkdata_if_needed(table_id, result_table, bk_tenant_id)

            # 推送路由 (关联的虚拟RT）
            self._push_es_route(result_table, bk_tenant_id)

        return result_table.to_json()

    def _handle_query_alias_settings(
        self, table_id: str, query_alias_settings: Any, operator: str | None, bk_tenant_id: str
    ) -> None:
        """处理查询别名设置"""
        if query_alias_settings is None:
            return

        try:
            logger.info(
                "ModifyResultTableResource: try to manage alias_settings,table_id->[%s],query_alias_settings->[%s]",
                table_id,
                query_alias_settings,
            )
            models.ESFieldQueryAliasOption.manage_query_alias_settings(
                table_id=table_id,
                query_alias_settings=query_alias_settings,
                operator=operator,
                bk_tenant_id=bk_tenant_id,
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.warning(
                "ModifyResultTableResource: manage alias_settings failed,table_id->[%s],query_alias_settings->["
                "%s],error->[%s]",
                table_id,
                query_alias_settings,
                e,
            )

    def _check_es_cluster_migration(
        self, table_id: str, validated_request_data: dict[str, Any], bk_tenant_id: str
    ) -> bool:
        """检查ES集群是否发生迁移"""
        is_moving_cluster = False
        external_storage = validated_request_data.get("external_storage") or {}

        if external_storage.get(models.ClusterInfo.TYPE_ES):
            es_storage = models.ESStorage.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
            if es_storage:
                param_cluster_id = external_storage[models.ClusterInfo.TYPE_ES].get("storage_cluster_id")
                if es_storage.storage_cluster_id != param_cluster_id:
                    logger.info(
                        "ModifyResultTableResource: table_id->[%s] moved es cluster from old->[%s] to new->[%s]",
                        table_id,
                        es_storage.storage_cluster_id,
                        param_cluster_id,
                    )
                    is_moving_cluster = True

        return is_moving_cluster

    def _modify_result_table(
        self, table_id: str, validated_request_data: dict[str, Any], bk_tenant_id: str
    ) -> models.ResultTable:
        """修改结果表信息"""
        try:
            result_table = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
            result_table.modify(**validated_request_data)
        except RetryError as e:
            logger.error(
                "ModifyResultTableResource: modify table failed,table_id->[%s],error->[%s]", table_id, e.__cause__
            )
            raise e.__cause__ if e.__cause__ else e
        except Exception as e:  # pylint: disable=broad-except
            logger.error("ModifyResultTableResource: modify table failed,table_id->[%s],error->[%s]", table_id, e)
            raise e

        # 刷新一波对象，防止存在缓存等情况
        result_table.refresh_from_db()
        return result_table

    def _handle_es_storage_index_update(
        self, table_id: str, validated_request_data: dict[str, Any], bk_tenant_id: str, is_moving_cluster: bool
    ) -> None:
        """处理ES存储索引更新"""
        if validated_request_data.get("field_list") is None:
            return

        es_storage = models.ESStorage.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
        if es_storage:
            logger.info(
                "ModifyResultTableResource: table_id->[%s] has es storage,update index,is_moving_cluster->[%s]",
                table_id,
                is_moving_cluster,
            )
            es_storage.update_index_and_aliases(ahead_time=0, is_moving_cluster=is_moving_cluster)

    def _notify_bkdata_if_needed(self, table_id: str, result_table: models.ResultTable, bk_tenant_id: str) -> None:
        """如果需要，通知bkdata数据变更"""
        bk_data_id = models.DataSourceResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id).bk_data_id
        ds = models.DataSource.objects.get(bk_data_id=bk_data_id)

        # 如果数据源没有接入BKDATA，则不需要通知bkdata
        if ds.created_from != DataIdCreatedFromSystem.BKDATA.value:
            return

        # 如果是主动配置的V4链路，不再需要通知bkdata
        # bklog需要存在rtoption，并且option中存在 OPTION_ENABLE_V4_LOG_DATA_LINK且值为True
        # custom_event需要存在rtoption，并且option中存在 OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK且值为True
        v4_option_names = [
            ResultTableOption.OPTION_ENABLE_V4_LOG_DATA_LINK,
            ResultTableOption.OPTION_ENABLE_V4_EVENT_GROUP_DATA_LINK,
        ]
        options = models.ResultTableOption.objects.filter(
            table_id=table_id, bk_tenant_id=bk_tenant_id, name__in=v4_option_names
        )
        if options and any(option.get_value() for option in options):
            return

        try:
            result_table.notify_bkdata_log_data_id_changed(data_id=bk_data_id)
            logger.info(
                "ModifyResultTableResource: notify bkdata successfully,table_id->[%s],data_id->[%s]",
                table_id,
                bk_data_id,
            )
        except RetryError as e:
            logger.warning("notify_log_data_id_changed error, table_id->[%s],error->[%s]", table_id, e.__cause__)
        except Exception as e:  # pylint: disable=broad-except
            logger.warning("notify_log_data_id_changed error, table_id->[%s],error->[%s]", table_id, e)

    def _push_es_route(self, result_table: models.ResultTable, bk_tenant_id: str) -> None:
        """推送ES路由信息"""
        # 获取关联的虚拟RT列表
        virtual_rt_list = list(
            models.ESStorage.objects.filter(origin_table_id=result_table.table_id).values_list("table_id", flat=True)
        )
        table_ids = [result_table.table_id] + virtual_rt_list

        logger.info(
            "ModifyResultTableResource: all things done, now try to push es route,table_id->[%s]",
            json.dumps(table_ids),
        )

        client = SpaceTableIDRedis()
        client.push_es_table_id_detail(table_id_list=table_ids, bk_tenant_id=bk_tenant_id)


class AccessBkDataByResultTableResource(Resource):
    """
    接入计算平台（根据结果表）
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        is_access_now = serializers.BooleanField(default=False, label="是否立即接入")

    def perform_request(self, validated_request_data):
        if not settings.IS_ACCESS_BK_DATA:
            return

        bk_tenant_id = validated_request_data.pop("bk_tenant_id")
        table_id = validated_request_data.pop("table_id")
        try:
            models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        except models.ResultTable.DoesNotExist:
            raise ValueError(_("结果表%s不存在，请确认后重试") % table_id)

        models.BkDataStorage.create_table(
            bk_tenant_id=bk_tenant_id,
            table_id=table_id,
            is_access_now=validated_request_data["is_access_now"],
        )


class IsDataLabelExistResource(Resource):
    """
    判断结果表中是否存在指定data_label
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.IntegerField(required=False, default=None)
        data_label = serializers.CharField(required=True, label="数据标签")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_data_id = validated_request_data.pop("bk_data_id")
        data_label = validated_request_data.pop("data_label")

        if not data_label:
            raise ValueError(_("data_label不能为空"))

        qs = models.ResultTable.objects.filter(data_label=data_label, bk_tenant_id=bk_tenant_id)
        if bk_data_id:
            # 相同data_id的result_table使用的data_label允许重复
            table_ids = models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id).values_list(
                "table_id", flat=True
            )
            qs = qs.exclude(table_id__in=table_ids)

        return qs.exists()


class CreateDownSampleDataFlowResource(Resource):
    """
    创建统计节点（按指定的降采样频率）
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        agg_interval = serializers.IntegerField(label="统计周期", default=60)

    def perform_request(self, validated_request_data):
        if not settings.IS_ACCESS_BK_DATA:
            return

        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data.pop("table_id")
        agg_interval = validated_request_data.get("agg_interval") or 60
        try:
            models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        except models.ResultTable.DoesNotExist:
            raise ValueError(_("结果表%s不存在，请确认后重试") % table_id)

        from metadata.task import tasks

        # TODO：这里是否需要租户ID
        tasks.create_statistics_data_flow.delay(table_id, agg_interval)


class QueryDataSourceResource(Resource):
    """查询数据源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID", default=None)
        data_name = serializers.CharField(required=False, label="数据源名称", default=None)
        with_rt_info = serializers.BooleanField(required=False, label="是否需要ResultTable信息", default=True)

    def perform_request(self, request_data):
        if request_data["bk_data_id"] is not None:  # 指定bk_data_id时，无需添加租户过滤条件
            data_source = models.DataSource.objects.get(bk_data_id=request_data["bk_data_id"])
        elif request_data["data_name"] is not None:
            data_source = models.DataSource.objects.get(
                data_name=request_data["data_name"], bk_tenant_id=request_data["bk_tenant_id"]
            )
        else:
            raise ValueError(_("找不到请求参数，请确认后重试"))

        return data_source.to_json(with_rt_info=request_data["with_rt_info"])


class ModifyDataSource(Resource):
    """修改数据源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        operator = serializers.CharField(required=True, label="操作者")
        data_id = serializers.IntegerField(required=True, label="数据源ID")
        data_name = serializers.CharField(required=False, label="数据源名称", default=None)
        data_description = serializers.CharField(required=False, label="数据源描述", default=None)
        option = serializers.DictField(required=False, label="数据源配置项")
        is_enable = serializers.BooleanField(required=False, label="是否启用数据源", default=None)
        is_platform_data_id = serializers.BooleanField(required=False, label="是否为平台级 ID", default=None)
        authorized_spaces = serializers.JSONField(required=False, label="授权使用的空间 ID 列表", default=None)
        space_type_id = serializers.CharField(required=False, label="数据源所属类型", default=None)
        etl_config = serializers.CharField(required=False, label="清洗模板配置")

    def perform_request(self, request_data):
        # 指定data_id的情况下，无需使用租户ID进行二次过滤
        try:
            data_source = models.DataSource.objects.get(
                bk_tenant_id=request_data["bk_tenant_id"], bk_data_id=request_data["data_id"]
            )

        except models.DataSource.DoesNotExist:
            raise ValueError(_("数据源不存在，请确认后重试"))

        # 不允许更改已经创建的数据源的隶属租户信息
        data_source.update_config(
            operator=request_data["operator"],
            data_name=request_data["data_name"],
            data_description=request_data["data_description"],
            option=request_data.get("option"),
            is_enable=request_data["is_enable"],
            is_platform_data_id=request_data["is_platform_data_id"],
            authorized_spaces=request_data["authorized_spaces"],
            space_type_id=request_data["space_type_id"],
            etl_config=request_data.get("etl_config"),
        )
        return data_source.to_json()


class StopOrEnableDatasource(Resource):
    """批量启停数据源
    1. 设置数据源的状态为启停
    2. 增删transfer依赖的consul配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        data_id_list = serializers.ListField(required=True, child=serializers.IntegerField(), label="数据源列表")
        is_enabled = serializers.BooleanField(required=False, label="是否启用数据源", default=True)

    def perform_request(self, validated_request_data):
        # 指定data_id的情况下，无需使用租户ID进行二次过滤
        stop_or_enable_datasource(
            bk_tenant_id=validated_request_data["bk_tenant_id"],
            data_id_list=validated_request_data["data_id_list"],
            is_enabled=validated_request_data["is_enabled"],
        )


class ModifyDataIdSource(Resource):
    """更改数据源来源"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        data_id_list = serializers.ListField(required=True, child=serializers.IntegerField(), label="数据源列表")
        source_system = serializers.CharField(required=True, label="数据源ID来源平台")

        def validate_source_system(self, source_system: str) -> str:
            if source_system not in [DataIdCreatedFromSystem.BKDATA.value, DataIdCreatedFromSystem.BKGSE.value]:
                raise ValidationError("source_system must be one of [bkdata, bkgse]")
            return source_system

    def perform_request(self, validated_request_data):
        # 指定data_id的情况下，无需使用租户ID进行二次过滤
        modify_data_id_source(
            bk_tenant_id=validated_request_data["bk_tenant_id"],
            data_id_list=validated_request_data["data_id_list"],
            source_type=validated_request_data["source_system"],
        )


class QueryDataSourceBySpaceUidResource(Resource):
    """
    根据space_uid查询data_source
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        space_uid_list = serializers.ListField(required=True, label="数据源所属空间uid列表")
        is_platform_data_id = serializers.BooleanField(required=False, label="是否为平台级 ID", default=True)

    def perform_request(self, validated_request_data):
        data_sources = models.DataSource.objects.filter(
            space_uid__in=validated_request_data["space_uid_list"],
            is_platform_data_id=validated_request_data["is_platform_data_id"],
            bk_tenant_id=validated_request_data["bk_tenant_id"],
        ).values("data_name", "bk_data_id")

        return list(data_sources)


class QueryResultTableSourceResource(Resource):
    """查询结果表"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")

    def perform_request(self, validated_request_data):
        result_table = models.ResultTable.get_result_table(
            table_id=validated_request_data["table_id"], bk_tenant_id=validated_request_data["bk_tenant_id"]
        )
        return result_table.to_json()


class UpgradeResultTableResource(Resource):
    """结果表升级为全局业务表"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        operator = serializers.CharField(required=True, label="操作者")
        table_id_list = serializers.ListField(required=True, label="结果表ID列表")

    def perform_request(self, validated_request_data):
        result_table_list = []

        for table_id in validated_request_data["table_id_list"]:
            result_table = models.ResultTable.get_result_table(
                table_id=table_id, bk_tenant_id=validated_request_data["bk_tenant_id"]
            )
            result_table_list.append(result_table)

        for result_table in result_table_list:
            result_table.upgrade_result_table()

        return


class FullCmdbNodeInfoResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")

    def perform_request(self, validated_request_data):
        if not settings.IS_ACCESS_BK_DATA:
            return

        table_id = validated_request_data["table_id"]
        try:
            models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=validated_request_data["bk_tenant_id"])
        except models.ResultTable.DoesNotExist:
            raise ValueError(_("结果表%s不存在，请确认后重试") % table_id)

        from metadata.task.tasks import create_full_cmdb_level_data_flow

        create_full_cmdb_level_data_flow.delay(table_id=table_id, bk_tenant_id=validated_request_data["bk_tenant_id"])


class CreateResultTableMetricSplitResource(Resource):
    """创建结果表的CMDB层级拆分记录"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        operator = serializers.CharField(required=True, label="操作者")
        table_id = serializers.CharField(required=True, label="结果表ID列表")
        cmdb_level = serializers.CharField(required=True, label="CMDB拆分层级目标")

    def perform_request(self, validated_request_data):
        try:
            result_table = models.ResultTable.objects.get(
                table_id=validated_request_data["table_id"],
                is_deleted=False,
                bk_tenant_id=validated_request_data["bk_tenant_id"],
            )
        except models.ResultTable.DoesNotExist:
            raise ValueError(_("结果表不存在，请确认后重试"))

        result = result_table.set_metric_split(
            cmdb_level=validated_request_data["cmdb_level"], operator=validated_request_data["operator"]
        )

        return {"bk_data_id": result.bk_data_id, "table_id": result.target_table_id}


class CleanResultTableMetricSplitResource(Resource):
    """清理结果表的CMDB层级拆分记录"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        operator = serializers.CharField(required=True, label="操作者")
        table_id = serializers.CharField(required=True, label="结果表ID列表")
        cmdb_level = serializers.CharField(required=True, label="CMDB拆分层级目标")

    def perform_request(self, validated_request_data):
        try:
            result_table = models.ResultTable.objects.get(
                table_id=validated_request_data["table_id"],
                is_deleted=False,
                bk_tenant_id=validated_request_data["bk_tenant_id"],
            )
        except models.ResultTable.DoesNotExist:
            raise ValueError(_("结果表不存在，请确认后重试"))

        result_table.clean_metric_split(
            cmdb_level=validated_request_data["cmdb_level"], operator=validated_request_data["operator"]
        )

        return


class LabelResource(Resource):
    """返回所有的标签内容"""

    class RequestSerializer(serializers.Serializer):
        include_admin_only = serializers.BooleanField(required=True, label="是否展示管理员可见标签")
        label_type = serializers.CharField(required=False, label="标签类型", default=None)
        level = serializers.IntegerField(required=False, label="标签层级", default=None)
        is_plain_text = serializers.BooleanField(required=False, label="是否明文展示", default=False)

    def perform_request(self, validated_request_data):
        return models.Label.get_label_info(
            include_admin_only=validated_request_data["include_admin_only"],
            label_type=validated_request_data["label_type"],
            level=validated_request_data["level"],
        )


class GetResultTableStorageResult(Resource):
    """返回一个结果表指定存储的数据"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        result_table_list = serializers.CharField(required=True, label="结果表列表")
        storage_type = serializers.CharField(required=True, label="存储类型")
        is_plain_text = serializers.BooleanField(required=False, label="是否明文显示链接信息")

    def perform_request(self, validated_request_data):
        # 判断请求的存储类型是否有效
        storage_type = validated_request_data["storage_type"]
        if storage_type not in models.ResultTable.REAL_STORAGE_DICT:
            raise ValueError(_("请求存储类型暂不支持，请确认"))

        # 遍历判断所有的存储信息
        result_table_list = validated_request_data["result_table_list"].split(",")
        storage_class = models.ResultTable.REAL_STORAGE_DICT[storage_type]
        result = {}

        for result_table in result_table_list:
            try:
                storage_info = storage_class.objects.get(
                    table_id=result_table, bk_tenant_id=validated_request_data["bk_tenant_id"]
                )
            except storage_class.DoesNotExist:
                continue

            result[result_table] = storage_info.consul_config

            # 判断是否需要明文返回链接信息
            if not validated_request_data["is_plain_text"]:
                result[result_table]["auth_info"] = base64.b64encode(
                    json.dumps(result[result_table]["auth_info"]).encode("utf-8")
                )

        # 返回
        return result


class QueryEventGroupResource(Resource):
    class RequestSerializer(PageSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        label = serializers.CharField(required=False, label="事件分组标签", default=None)
        event_group_name = serializers.CharField(required=False, label="事件分组名称", default=None)
        bk_biz_id = serializers.CharField(required=False, label="业务ID", default=None)
        bk_data_ids = serializers.ListField(
            required=False, label="数据源ID列表", default=[], child=serializers.IntegerField(label="数据源ID")
        )

    def perform_request(self, validated_request_data):
        # 默认都是返回已经删除的内容
        query_set = models.EventGroup.objects.filter(
            is_delete=False, bk_tenant_id=validated_request_data["bk_tenant_id"]
        )

        label = validated_request_data["label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        event_group_name = validated_request_data["event_group_name"]
        bk_data_ids = validated_request_data.get("bk_data_ids")

        if label is not None:
            query_set = query_set.filter(label=label)

        if bk_biz_id is not None:
            query_set = query_set.filter(bk_biz_id=bk_biz_id)

        if event_group_name is not None:
            query_set = query_set.filter(event_group_name=event_group_name)

        if bk_data_ids:
            query_set = query_set.filter(bk_data_id__in=bk_data_ids)

        # 分页返回
        page_size = validated_request_data["page_size"]
        if page_size > 0:
            count = query_set.count()
            offset = (validated_request_data["page"] - 1) * page_size
            paginated_queryset = query_set[offset : offset + page_size]
            events = self._compose_in_event(paginated_queryset)
            return {"count": count, "info": events}

        # 组装数据
        return self._compose_in_event(query_set)

    def _compose_in_event(self, event_query_set: QuerySet) -> list:
        """组装数据, 添加内置事件"""
        built_events = get_built_in_k8s_events()
        built_event_map = {event["event_name"]: event for event in built_events}
        ret_data = []
        for qs in event_query_set:
            data = qs.to_json()
            # 仅针对 k8s 事件添加内置事件; 其它直接返回事件
            # NOTE: 现阶段按照名称以 `bcs_BCS-K8S-` 作为匹配条件
            if not data["event_group_name"].startswith("bcs_BCS-K8S-"):
                ret_data.append(data)
                continue
            event_info_list = data.get("event_info_list") or []
            event_name_list = [event["event_name"] for event in event_info_list]
            # 如果指标不存在，则补充内置指标
            for event_name in set(built_event_map.keys()) - set(event_name_list):
                item = built_event_map.get(event_name)
                if not item:
                    continue
                event_info_list.append(item)
            data["event_info_list"] = event_info_list
            ret_data.append(data)

        return ret_data


class CreateEventGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(required=True, label="数据源ID")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        event_group_name = serializers.CharField(required=True, label="事件分组名")
        label = serializers.CharField(required=True, label="事件分组标签")
        operator = serializers.CharField(required=True, label="创建者")
        event_info_list = serializers.ListField(required=False, label="事件列表", default=None)
        data_label = serializers.CharField(label="数据标签", required=False, default="")

    def perform_request(self, validated_request_data):
        # 默认都是返回已经删除的内容
        event_group = models.EventGroup.create_event_group(**validated_request_data)
        return event_group.to_json()


class ModifyEventGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        event_group_id = serializers.IntegerField(required=True, label="事件分组ID")
        operator = serializers.CharField(required=True, label="修改者")
        event_group_name = serializers.CharField(required=False, label="事件分组名", default=None)
        label = serializers.CharField(required=False, label="事件分组标签")
        event_info_list = serializers.ListField(required=False, label="事件列表", default=None)
        is_enable = serializers.BooleanField(required=False, label="是否启用事件分组", default=None)
        data_label = serializers.CharField(label="数据标签", required=False, default=None)

    def perform_request(self, validated_request_data):
        try:  # 指定group_id的情况下，无需再次对租户ID进行过滤
            event_group = models.EventGroup.objects.get(
                # 将事件分组的ID去掉
                event_group_id=validated_request_data.pop("event_group_id"),
                is_delete=False,
                bk_tenant_id=validated_request_data.pop("bk_tenant_id"),
            )
        except models.EventGroup.DoesNotExist:
            raise ValueError(_("事件分组不存在，请确认后重试"))

        event_group.modify_event_group(**validated_request_data)
        event_group.refresh_from_db()

        return event_group.to_json()


class DeleteEventGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        event_group_id = serializers.IntegerField(required=True, label="事件分组ID")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需再次对租户ID进行过滤
        try:
            event_group = models.EventGroup.objects.get(
                # 将事件分组的ID去掉
                event_group_id=validated_request_data.pop("event_group_id"),
                is_delete=False,
                bk_tenant_id=validated_request_data["bk_tenant_id"],
            )
        except models.EventGroup.DoesNotExist:
            raise ValueError(_("事件分组不存在，请确认后重试"))

        event_group.delete_event_group(validated_request_data["operator"])
        return


class GetEventGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        event_group_id = serializers.IntegerField(required=True, label="事件分组ID")
        with_result_table_info = serializers.BooleanField(required=False, label="是否需要带结果表信息")
        need_refresh = serializers.BooleanField(required=False, label="是否需要实时刷新", default=False)
        event_infos_limit = serializers.IntegerField(required=False, default=None, label="事件信息列表上限")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需再次对租户ID进行过滤
        try:
            event_group = models.EventGroup.objects.get(
                # 将事件分组的ID去掉
                event_group_id=validated_request_data.pop("event_group_id"),
                is_delete=False,
                bk_tenant_id=validated_request_data["bk_tenant_id"],
            )
        except models.EventGroup.DoesNotExist:
            raise ValueError(_("事件分组不存在，请确认后重试"))

        if validated_request_data.pop("need_refresh"):
            # 立即更新事件分组的事件及维度信息内容
            event_group.update_event_dimensions_from_es()

        if not validated_request_data["with_result_table_info"]:
            return event_group.to_json(validated_request_data["event_infos_limit"])

        result = event_group.to_json(validated_request_data["event_infos_limit"])

        # 查询增加结果表信息
        result_table = models.ResultTable.objects.get(
            table_id=event_group.table_id, bk_tenant_id=event_group.bk_tenant_id
        )
        result["shipper_list"] = [real_table.consul_config for real_table in result_table.real_storage_list]

        return result


class QueryLogGroupResource(Resource):
    """
    查询日志分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        label = serializers.CharField(required=False, label="日志分组标签", default=None)
        log_group_name = serializers.CharField(required=False, label="日志分组名称", default=None)
        bk_biz_id = serializers.CharField(required=False, label="业务ID", default=None)

    def perform_request(self, validated_request_data):
        # 查询条件
        label = validated_request_data["label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        log_group_name = validated_request_data["log_group_name"]

        # 查询
        query_set = models.LogGroup.objects.filter(is_delete=False, bk_tenant_id=validated_request_data["bk_tenant_id"])
        if label is not None:
            query_set = query_set.filter(label=label)
        if bk_biz_id is not None:
            query_set = query_set.filter(bk_biz_id=bk_biz_id)
        if log_group_name is not None:
            query_set = query_set.filter(log_group_name=log_group_name)

        # 响应
        return [log_group.to_json() for log_group in query_set]


class GetLogGroupResource(Resource):
    """
    获取单个日志分组信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        log_group_id = serializers.IntegerField(required=True, label="日志分组ID")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        # 获取日志分组
        try:
            log_group = models.LogGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"],
                log_group_id=validated_request_data.pop("log_group_id"),
                is_delete=False,
            )
        except models.LogGroup.DoesNotExist:
            raise ValueError(_("日志分组不存在，请确认后重试"))

        # 直接返回
        return log_group.to_json(with_token=True)


class CreateLogGroupResource(Resource):
    """
    创建日志分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(required=True, label="数据源ID")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        log_group_name = serializers.CharField(required=True, label="日志分组名")
        label = serializers.CharField(required=True, label="日志分组标签")
        operator = serializers.CharField(required=True, label="创建者")
        max_rate = serializers.IntegerField(required=False, label="最大上报速率", default=-1)

    def perform_request(self, validated_request_data):
        log_group = models.LogGroup.create_log_group(**validated_request_data)
        return log_group.to_json(with_token=True)


class ModifyLogGroupResource(Resource):
    """
    更新日志分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        log_group_id = serializers.IntegerField(required=True, label="日志分组ID")
        operator = serializers.CharField(required=True, label="修改者")
        label = serializers.CharField(required=False, label="事件分组标签")
        is_enable = serializers.BooleanField(required=False, label="是否启用日志分组", default=None)
        max_rate = serializers.IntegerField(required=False, label="最大上报速率")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        # 获取日志分组
        try:
            log_group = models.LogGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"],
                log_group_id=validated_request_data.pop("log_group_id"),
                is_delete=False,
            )
        except models.LogGroup.DoesNotExist:
            raise ValueError(_("日志分组不存在，请确认后重试"))

        # 修改信息
        log_group.modify_log_group(**validated_request_data)
        log_group.refresh_from_db()

        # 响应
        return log_group.to_json(with_token=True)


class DeleteLogGroupResource(Resource):
    """
    删除日志分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        log_group_id = serializers.IntegerField(required=True, label="日志分组ID")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        # 获取日志分组
        try:
            log_group = models.LogGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"],
                log_group_id=validated_request_data.pop("log_group_id"),
                is_delete=False,
            )
        except models.LogGroup.DoesNotExist:
            raise ValueError(_("日志分组不存在，请确认后重试"))

        # 删除
        log_group.delete_log_group(validated_request_data["operator"])


class CreateTimeSeriesGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.CharField(required=True, label="数据源ID")
        bk_biz_id = serializers.CharField(required=True, label="业务ID")
        time_series_group_name = serializers.CharField(required=True, label="自定义时序分组名")
        label = serializers.CharField(required=True, label="自定义时序分组标签")
        operator = serializers.CharField(required=True, label="创建者")
        metric_info_list = serializers.ListField(required=False, label="自定义时序metric列表", default=None)
        table_id = serializers.CharField(required=False, label="结果表id")
        is_split_measurement = serializers.BooleanField(required=False, label="是否启动自动分表逻辑", default=False)
        default_storage_config = serializers.DictField(required=False, label="默认存储参数")
        additional_options = serializers.DictField(required=False, label="附带创建的ResultTableOption")
        data_label = serializers.CharField(label="数据标签", required=False, default="")

    def perform_request(self, validated_request_data):
        # 默认都是返回已经删除的内容
        time_series_group = models.TimeSeriesGroup.create_time_series_group(**validated_request_data)
        return time_series_group.to_json()


class ModifyTimeSeriesGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序分组ID")
        operator = serializers.CharField(required=True, label="修改者")
        time_series_group_name = serializers.CharField(required=False, label="自定义时序分组名", default=None)
        label = serializers.CharField(required=False, label="自定义时序分组标签")
        field_list = serializers.ListField(required=False, label="字段列表", default=None)
        is_enable = serializers.BooleanField(required=False, label="是否启用自定义分组", default=None)
        metric_info_list = serializers.ListField(required=False, label="metric信息", default=None)
        enable_field_black_list = serializers.BooleanField(required=False, label="黑名单的启用状态", default=None)
        data_label = serializers.CharField(label="数据标签", required=False, default=None)

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data.pop("bk_tenant_id")
        # 指定group_id的情况下，无需使用租户ID再次过滤
        try:
            time_series_group = models.TimeSeriesGroup.objects.get(
                bk_tenant_id=bk_tenant_id,
                time_series_group_id=validated_request_data.pop("time_series_group_id"),
                is_delete=False,
            )
        except models.TimeSeriesGroup.DoesNotExist:
            raise ValueError(_("自定义时序分组不存在，请确认后重试"))

        time_series_group.modify_time_series_group(**validated_request_data)
        time_series_group.refresh_from_db()

        return time_series_group.to_json()


class DeleteTimeSeriesGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义分组ID")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        try:
            time_series_group = models.TimeSeriesGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"],
                time_series_group_id=validated_request_data.pop("time_series_group_id"),
                is_delete=False,
            )
        except models.TimeSeriesGroup.DoesNotExist:
            raise ValueError(_("自定义时序分组不存在，请确认后重试"))

        time_series_group.delete_time_series_group(validated_request_data["operator"])
        return


class GetTimeSeriesGroupResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序分组ID")
        with_result_table_info = serializers.BooleanField(required=False, label="是否需要带结果表信息")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        try:
            time_series_group = models.TimeSeriesGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"],
                time_series_group_id=validated_request_data.pop("time_series_group_id"),
                is_delete=False,
            )
        except models.TimeSeriesGroup.DoesNotExist:
            raise ValueError(_("自定义时序分组不存在，请确认后重试"))

        # 统一转换为列表形式数据
        results = time_series_group.to_json_v2()

        if not validated_request_data["with_result_table_info"]:
            return results

        # 查询增加结果表信息
        result_table = models.ResultTable.objects.get(
            table_id=time_series_group.table_id, bk_tenant_id=time_series_group.bk_tenant_id
        )
        for result in results:
            result["shipper_list"] = [real_table.consul_config for real_table in result_table.real_storage_list]

        return results


class GetTimeSeriesMetricsResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")

    def perform_request(self, validated_request_data):
        # 指定group_id的情况下，无需使用租户ID再次过滤
        table_id = validated_request_data.pop("table_id")
        try:
            time_series_group = models.TimeSeriesGroup.objects.get(
                bk_tenant_id=validated_request_data["bk_tenant_id"], table_id=table_id
            )
        except models.TimeSeriesGroup.DoesNotExist:
            raise ValueError(_("自定义时序分组不存在，请确认后重试"))

        return {"metric_info_list": time_series_group.get_metric_info_list()}


class QueryTimeSeriesGroupResource(Resource):
    class RequestSerializer(PageSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        label = serializers.CharField(required=False, label="自定义分组标签", default=None)
        time_series_group_name = serializers.CharField(required=False, label="自定义分组名称", default=None)
        bk_biz_id = serializers.CharField(required=False, label="业务ID", default=None)

    def perform_request(self, validated_request_data):
        # 屏蔽bcs相关的dataid
        data_ids, data_id_cluster_map = get_bcs_dataids()
        # 默认都是返回未删除的内容
        query_set = models.TimeSeriesGroup.objects.filter(
            is_delete=False,
            bk_tenant_id=validated_request_data["bk_tenant_id"],
        ).exclude(bk_data_id__in=data_ids)

        label = validated_request_data["label"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        time_series_group_name = validated_request_data["time_series_group_name"]

        if label is not None:
            query_set = query_set.filter(label=label)

        if bk_biz_id is not None:
            query_set = query_set.filter(bk_biz_id=bk_biz_id)

        if time_series_group_name is not None:
            query_set = query_set.filter(time_series_group_name=time_series_group_name)

        page_size = validated_request_data["page_size"]
        if page_size > 0:
            count = query_set.count()
            offset = (validated_request_data["page"] - 1) * page_size
            paginated_query_set = query_set[offset : offset + page_size]
            results = list(chain.from_iterable(instance.to_json_v2() for instance in paginated_query_set))
            return {"count": count, "info": results}

        return list(chain.from_iterable(instance.to_json_v2() for instance in query_set))


class QueryBCSMetricsResource(Resource):
    """查询bcs相关指标"""

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_ids = serializers.ListField(
            required=False, label="业务ID", default=None, child=serializers.IntegerField()
        )
        cluster_ids = serializers.ListField(required=False, label="BCS集群ID", default=None)
        dimension_name = serializers.CharField(required=False, label="指标名称", default="")
        dimension_value = serializers.CharField(required=False, label="指标取值", default="")

    def perform_request(self, validated_request_data):
        # 基于BCS集群信息获取dataid列表，用于过滤
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        # TODO: 这里需要校验业务ID是否属于当前租户
        bk_biz_ids = validated_request_data["bk_biz_ids"]
        cluster_ids = validated_request_data["cluster_ids"]
        # 注意参数 维度名称和维度值 必须同时存在
        dimension_name = validated_request_data.get("dimension_name", "")
        dimension_value = validated_request_data.get("dimension_value", "")
        metric_datas = {}
        # 通过文件获取内置指标数据
        k8s_metrics = get_built_in_k8s_metrics()

        # 业务id为0时，获取 k8s 系统内置指标
        # NOTE: 当业务列表存在，业务列表包含 0 业务，且参数维度名称或值不存在时，直接获取内置指标
        if bk_biz_ids and 0 in bk_biz_ids and not (dimension_name and dimension_value):
            self._refine_built_in_metric_dimensions(metric_datas, k8s_metrics)

        built_in_metric_field_list = [metric["field_name"] for metric in k8s_metrics]
        # 获取自定义及内置指标
        self._refine_metric_dimensions_from_redis(
            bk_tenant_id,
            bk_biz_ids,
            cluster_ids,
            dimension_name,
            dimension_value,
            metric_datas,
            built_in_metric_field_list,
        )

        # 将数据填充好
        results = []
        for metric_data in metric_datas.values():
            # 删除临时维度集合，节约流量
            del metric_data["tag_names"]
            results.append(metric_data)

        return results

    def _refine_built_in_metric_dimensions(self, metric_datas: dict, k8s_metrics: list):
        """获取 k8s 内置指标和维度"""
        for metric in k8s_metrics:
            field_name = metric["field_name"]
            metric_datas[field_name] = {
                "field_name": field_name,
                "description": metric.get("description", ""),
                "unit": metric.get("unit", ""),
                "type": metric.get("type", "float"),
                "bk_biz_ids": {0},
                "bk_data_ids": set(),
                "cluster_ids": set(),
                "dimensions": metric["tag_list"],
                "label": metric.get("label", "kubernetes"),
                "tag_names": {tag["field_name"] for tag in metric["tag_list"]},
            }

    def _refine_metric_dimensions_from_redis(
        self,
        bk_tenant_id: str,
        bk_biz_ids: list,
        cluster_ids: list,
        dimension_name: str,
        dimension_value: str,
        metric_datas: dict,
        built_in_metric_field_list: list,
    ):
        """通过 redis 中获取指标和维度"""
        # 当参数 指标名称和指标值 的内容全部存在时，查询内置和自定义指标
        # both: 标识需要内置和自定义指标
        # custom: 标识仅需要过滤自定义指标
        metric_mode = "both" if (dimension_name and dimension_value) else "custom"
        data_ids, data_id_cluster_map = get_bcs_dataids(bk_biz_ids, cluster_ids, metric_mode)

        query_set = models.TimeSeriesGroup.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_data_id__in=data_ids, is_delete=False
        )

        for time_series_group in query_set:
            # 基于group的dataid，对数据补充集群id字段
            cluster_id = data_id_cluster_map[time_series_group.bk_data_id]
            metrics = time_series_group.get_metric_info_list_with_label(dimension_name, dimension_value)
            # 获取是否为内置指标，用于判断是否存在于文件白名单中
            is_built_in_metric = time_series_group.bk_data_id in data_id_cluster_map["built_in_metric_data_id_list"]
            # 遍历该group自定义k8s指标，记录其cluster_id和维度信息
            for metric in metrics:
                field_name = metric["field_name"]
                # 如果为内置指标，但是不在文件白名单中，则忽略
                if is_built_in_metric and field_name not in built_in_metric_field_list:
                    continue
                if field_name not in metric_datas.keys():
                    item = {
                        "field_name": field_name,
                        "description": metric["description"],
                        "unit": metric["unit"],
                        "type": metric["type"],
                        "bk_biz_ids": {time_series_group.bk_biz_id},
                        "bk_data_ids": {time_series_group.bk_data_id},
                        "cluster_ids": {cluster_id},
                        "dimensions": metric["tag_list"],
                        "label": metric["label"],
                    }
                    # tag_names为临时维度集合
                    tag_names = set()
                    for tag in metric["tag_list"]:
                        tag_names.add(tag["field_name"])
                    item["tag_names"] = tag_names
                    metric_datas[field_name] = item
                else:
                    item = metric_datas[field_name]
                    item["bk_biz_ids"].add(time_series_group.bk_biz_id)
                    item["bk_data_ids"].add(time_series_group.bk_data_id)
                    item["cluster_ids"].add(cluster_id)
                    # 如果之前有指标记录了维度，这里取并集
                    pre_tag_list = item["dimensions"]
                    pre_tag_names = item["tag_names"]
                    for new_tag in metric["tag_list"]:
                        if new_tag["field_name"] not in pre_tag_names:
                            pre_tag_list.append(new_tag)
                            pre_tag_names.add(new_tag["field_name"])
                    item["dimensions"] = pre_tag_list
                    item["tag_names"] = pre_tag_names
                    metric_datas[field_name] = item


class QueryTagValuesResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        tag_name = serializers.CharField(required=True, label="dimension/tag名称")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data.pop("table_id")
        tag_name = validated_request_data.pop("tag_name")
        try:
            rt = models.ResultTable.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
        except models.ResultTable.DoesNotExist:
            raise ValueError(f"结果表{table_id}不存在，请确认后重试")

        return {"tag_values": rt.get_tag_values(tag_name=tag_name)}


class ListTransferClusterResource(Resource):
    """
    获取所有transfer集群信息
    """

    def perform_request(self, validated_request_data):
        consul_client = consul.BKConsul()

        _, node_list = consul_client.kv.get(config.CONSUL_TRANSFER_PATH, keys=True)
        node_child_name = set()
        for node in node_list or []:
            name, _, _ = node[len(config.CONSUL_TRANSFER_PATH) :].partition("/")
            node_child_name.add(name)

        black_transfer_cluster_id = settings.TRANSFER_BUILTIN_CLUSTER_ID or ""
        black_transfer_cluster_id_list = black_transfer_cluster_id.split(",")
        return [{"cluster_id": i} for i in node_child_name if i not in black_transfer_cluster_id_list]


class CheckOrCreateKafkaStorageResource(Resource):
    """
    检查对应结果表的kafka存储是否存在，不存在则创建
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=True, label="结果表IDs")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_ids = validated_request_data["table_ids"]
        exists_table_ids = models.KafkaStorage.objects.filter(
            table_id__in=table_ids, bk_tenant_id=bk_tenant_id
        ).values_list("table_id", flat=True)
        need_create_table_ids = list(set(table_ids) - set(exists_table_ids))
        for table_id in need_create_table_ids:
            models.storage.KafkaStorage.create_table(table_id, is_sync_db=True, **{"expired_time": 1800000})
            models.ResultTable.objects.get(table_id=table_id).refresh_etl_config()


class RegisterBCSClusterResource(Resource):
    """
    将BCS集群信息注册到metadata，并进行一系列初始化操作
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        cluster_id = serializers.CharField(required=True, label="bcs集群id")
        project_id = serializers.CharField(required=True, label="bcs项目id")
        creator = serializers.CharField(required=True, label="操作人")
        domain_name = serializers.CharField(required=False, label="bcs域名")
        port = serializers.IntegerField(required=False, label="bcs端口")
        api_key_type = serializers.CharField(required=False, label="api密钥类型")
        api_key_prefix = serializers.CharField(required=False, label="api密钥前缀")
        is_skip_ssl_verify = serializers.BooleanField(required=False, label="是否跳过ssl认证")
        transfer_cluster_id = serializers.CharField(required=False, label="transfer集群id")
        bk_env = serializers.CharField(required=False, default="", label="配置来源标签")

    def perform_request(self, validated_request_data):
        # 注册集群
        cluster = BCSClusterInfo.register_cluster(**validated_request_data)
        cluster.init_resource()
        # 异步刷新集群内的resource数据
        refresh_dataid_resource.delay(cluster_id=cluster.cluster_id, data_id=cluster.CustomMetricDataID)


class ModifyBCSResourceInfoResource(Resource):
    """
    修改bcs的resource内容，通常为调整dataid
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.CharField(required=True, label="bcs集群id")
        resource_type = serializers.CharField(required=True, label="resource类型")
        resource_name = serializers.CharField(required=True, label="resource名称")
        data_id = serializers.IntegerField(required=True, label="修改后的目标dataid")

    def perform_request(self, validated_request_data):
        # 指定集群ID的情况下，无需使用租户ID再次过滤
        resource_type = validated_request_data["resource_type"]

        # TODO: 这些表没有多租户字段
        type_to_class = {
            ServiceMonitorInfo.PLURAL: ServiceMonitorInfo,
            PodMonitorInfo.PLURAL: PodMonitorInfo,
            LogCollectorInfo.PLURAL: LogCollectorInfo,
        }
        resource_cls = type_to_class.get(resource_type)
        if resource_cls is None:
            raise ValueError(f"unknown resource type:{resource_type}")

        target_resource = resource_cls.objects.get(
            cluster_id=validated_request_data["cluster_id"], name=validated_request_data["resource_name"]
        )

        if target_resource:
            target_resource.change_data_id(data_id=validated_request_data["data_id"])
        else:
            raise ValueError("unknown target resource")


class ListBCSResourceInfoResource(Resource):
    """
    提供录入metadata的dataid resource信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_ids = serializers.ListField(required=False, label="bcs集群id", default=[])
        resource_type = serializers.CharField(required=True, label="resource类型")

    def perform_request(self, validated_request_data):
        # 指定集群ID的情况下，无需使用租户ID再次过滤
        cluster_list = validated_request_data["cluster_ids"]
        resource_type = validated_request_data["resource_type"]

        # TODO: 这些表没有多租户字段
        type_to_class = {
            ServiceMonitorInfo.PLURAL: ServiceMonitorInfo,
            PodMonitorInfo.PLURAL: PodMonitorInfo,
            LogCollectorInfo.PLURAL: LogCollectorInfo,
        }

        resources = []
        for resource_type in resource_type.split(","):
            if not resource_type:
                continue

            resource_cls = type_to_class.get(resource_type)
            if resource_cls is None:
                raise ValueError(f"unknown resource type:{resource_type}")

            if len(cluster_list) != 0:
                resources += list(resource_cls.objects.filter(cluster_id__in=cluster_list))
            else:
                resources += list(resource_cls.objects.all())

        results = []
        for item in resources:
            results.append(item.to_json())
        return results


class ListBCSClusterInfoResource(Resource):
    """
    查询bcs集群信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(label="业务ID", required=False)
        cluster_ids = serializers.ListField(label="集群ID", child=serializers.CharField(), required=False)

    def perform_request(self, validated_request_data):
        clusters = BCSClusterInfo.objects.filter(bk_tenant_id=validated_request_data["bk_tenant_id"])

        if "bk_biz_id" in validated_request_data:
            clusters = clusters.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        if validated_request_data.get("cluster_ids"):
            clusters = clusters.filter(cluster_id__in=validated_request_data["cluster_ids"])

        return [cluster.to_json() for cluster in clusters]


class ListBCSClusterInfoByBizResource(Resource):
    """
    查询指定业务下的bcs集群信息,用于用户查询
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, validated_request_data):
        clusters = BCSClusterInfo.objects.filter(
            bk_tenant_id=validated_request_data["bk_tenant_id"], bk_biz_id=validated_request_data["bk_biz_id"]
        )
        return [cluster.to_json_for_user() for cluster in clusters]


class ApplyYamlToBCSClusterResource(Resource):
    """
    应用yaml配置到指定集群
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.CharField(required=True, label="bcs集群id")
        namespace = serializers.CharField(default="default", label="命名空间")
        yaml_content = serializers.CharField(required=True, label="yaml文本内容")

    def perform_request(self, validated_request_data):
        # 指定集群ID的情况下，无需使用租户ID再次过滤
        cluster_id = validated_request_data["cluster_id"]
        try:
            cluster = BCSClusterInfo.objects.get(
                cluster_id=cluster_id, bk_tenant_id=validated_request_data["bk_tenant_id"]
            )
        except BCSClusterInfo.DoesNotExist:
            logger.error("apply resource to cluster_id(%s) failed, because cluster not exists", cluster_id)
            return False

        yaml_content = validated_request_data["yaml_content"]
        try:
            yaml_objects = yaml.safe_load_all(yaml_content)
        except:  # noqa
            logger.error("resource check failed, check your yaml_content, cluster_id(%s)", cluster_id)
            return False

        utils.create_from_yaml(
            cluster.api_client, yaml_objects=yaml_objects, namespace=validated_request_data["namespace"]
        )
        return True


class CreateEsSnapshotRepositoryResource(Resource):
    """
    创建Es快照仓库
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=True, label="ES存储集群ID")
        snapshot_repository_name = serializers.CharField(required=True, label="快照仓库名称")
        es_config = serializers.DictField(required=True, label="快照仓库配置")
        alias = serializers.CharField(required=True, label="别名")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRepository.create_repository(**validated_request_data).to_json()


class ModifyEsSnapshotRepositoryResource(Resource):
    """
    修改Es快照仓库
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=True, label="ES存储集群ID")
        snapshot_repository_name = serializers.CharField(required=True, label="快照仓库名称")
        alias = serializers.CharField(required=True, label="别名")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        models.EsSnapshotRepository.modify_repository(**validated_request_data)
        return validated_request_data


class DeleteEsSnapshotRepositoryResource(Resource):
    """
    删除Es快照仓库
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=True, label="ES存储集群ID")
        snapshot_repository_name = serializers.CharField(required=True, label="快照仓库名称")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        models.EsSnapshotRepository.delete_repository(**validated_request_data)
        return validated_request_data


class VerifyEsSnapshotRepositoryResource(Resource):
    """
    验证Es集群访问快照仓库情况
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=True, label="ES存储集群ID")
        snapshot_repository_name = serializers.CharField(required=True, label="快照仓库名称")

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRepository.verify_repository(**validated_request_data)


class EsSnapshotRepositoryResource(Resource):
    """
    集群快照仓库信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_id = serializers.IntegerField(required=True, label="ES存储集群ID")

    def perform_request(self, validated_request_data):
        queryset = models.EsSnapshotRepository.objects.filter(
            is_deleted=False, bk_tenant_id=validated_request_data["bk_tenant_id"]
        )
        return [repository.to_json() for repository in queryset.filter(cluster_id=validated_request_data["cluster_id"])]


class ListEsSnapshotRepositoryResource(Resource):
    """
    集群快照仓库信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        cluster_ids = serializers.ListField(required=False, label="ES存储集群ID")

    def perform_request(self, validated_request_data):
        cluster_ids = validated_request_data.get("cluster_ids")
        queryset = models.EsSnapshotRepository.objects.filter(
            is_deleted=False, bk_tenant_id=validated_request_data["bk_tenant_id"]
        )
        if cluster_ids:
            queryset = queryset.filter(cluster_id__in=cluster_ids)
        return [repository.to_json() for repository in queryset]


class CreateResultTableSnapshotResource(Resource):
    """
    Es结果表快照配置创建
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        target_snapshot_repository_name = serializers.CharField(required=True, label="目标es集群快照仓库")
        snapshot_days = serializers.IntegerField(required=True, label="快照存储时间配置", min_value=0)
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        return models.EsSnapshot.create_snapshot(**validated_request_data).to_json()


class ModifyResultTableSnapshotResource(Resource):
    """
    Es结果表快照配置修改
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        snapshot_days = serializers.IntegerField(required=True, label="快照存储时间配置", min_value=0)
        operator = serializers.CharField(required=True, label="操作者")
        status = serializers.CharField(required=False, label="操作者")

    def perform_request(self, validated_request_data):
        models.EsSnapshot.modify_snapshot(**validated_request_data)
        return validated_request_data


class DeleteResultTableSnapshotResource(Resource):
    """
    删除es快照配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        is_sync = serializers.BooleanField(required=False, label="是否需要同步", default=False)

    def perform_request(self, validated_request_data):
        models.EsSnapshot.delete_snapshot(**validated_request_data)
        return validated_request_data


class RetryResultTableSnapshotResource(Resource):
    """
    重试es快照配置
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        is_sync = serializers.BooleanField(required=False, label="是否需要同步", default=False)

    def perform_request(self, validated_request_data):
        models.EsSnapshot.retry_snapshot(**validated_request_data)
        return validated_request_data


class ListResultTableSnapshotResource(Resource):
    """
    Es结果表快照列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=False, label="结果表IDs")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_ids = validated_request_data.get("table_ids")
        result_queryset = models.EsSnapshot.objects.filter(bk_tenant_id=bk_tenant_id)
        if table_ids:
            result_queryset = result_queryset.filter(table_id__in=table_ids)
        table_ids = [snapshot.table_id for snapshot in result_queryset]
        all_doc_count_and_store_size = models.EsSnapshotIndice.all_doc_count_and_store_size(
            bk_tenant_id=bk_tenant_id, table_ids=table_ids
        )
        result = []
        for snapshot in result_queryset:
            snapshot_json = snapshot.to_self_json()
            table_id_doc_count_and_store_size = all_doc_count_and_store_size.get(snapshot.table_id, {})
            snapshot_json["doc_count"] = table_id_doc_count_and_store_size.get("doc_count", 0)
            snapshot_json["store_size"] = table_id_doc_count_and_store_size.get("store_size", 0)
            snapshot_json["index_count"] = table_id_doc_count_and_store_size.get("index_count", 0)
            result.append(snapshot_json)
        return result


class ListResultTableSnapshotIndicesResource(Resource):
    """
    Es结果表快照含物理索引
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=True, label="结果表ID")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_ids = validated_request_data.get("table_ids")
        es_snapshots = models.EsSnapshot.objects.filter(table_id__in=table_ids, bk_tenant_id=bk_tenant_id)
        return [es_snapshot.to_json() for es_snapshot in es_snapshots]


class GetResultTableSnapshotStateResource(Resource):
    """
    Es结果表快照状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=True, label="结果表ids")

    def perform_request(self, validated_request_data):
        return models.EsSnapshot.batch_get_state(
            bk_tenant_id=validated_request_data["bk_tenant_id"], table_ids=validated_request_data["table_ids"]
        )


class GetResultTableSnapshotRecentStateResource(Resource):
    """
    Es结果表最近一次快照状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=True, label="结果表ids")

    def perform_request(self, validated_request_data):
        return models.EsSnapshot.batch_get_recent_state(**validated_request_data)


class RestoreResultTableSnapshotResource(Resource):
    """
    创建快照恢复接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=True, label="结果表ID")
        start_time = serializers.DateTimeField(required=True, label="数据开始时间", format="%Y-%m-%d %H:%M:%S")
        end_time = serializers.DateTimeField(required=True, label="数据结束时间", format="%Y-%m-%d %H:%M:%S")
        expired_time = serializers.DateTimeField(required=True, label="指定过期时间", format="%Y-%m-%d %H:%M:%S")
        operator = serializers.CharField(required=True, label="操作者")
        is_sync = serializers.BooleanField(required=False, label="是否需要同步", default=False)

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRestore.create_restore(**validated_request_data)


class ModifyRestoreResultTableSnapshotResource(Resource):
    """
    修改快照恢复接口
    """

    class RequestSerializer(serializers.Serializer):
        restore_id = serializers.IntegerField(required=True, label="回溯id")
        expired_time = serializers.DateTimeField(required=True, label="指定过期时间", format="%Y-%m-%d %H:%M:%S")
        operator = serializers.CharField(required=True, label="操作者")

    def perform_request(self, validated_request_data):
        # 若开启多租户模式，需要获取租户ID
        if settings.ENABLE_MULTI_TENANT_MODE:
            bk_tenant_id = get_request_tenant_id()
            logger.info(
                "ModifyRestoreResultTableSnapshotResource: enable multi tenant mode,bk_tenant_id->[%s]", bk_tenant_id
            )
        else:
            bk_tenant_id = DEFAULT_TENANT_ID

        validated_request_data["bk_tenant_id"] = bk_tenant_id

        models.EsSnapshotRestore.modify_restore(**validated_request_data)
        return validated_request_data


class DeleteRestoreResultTableSnapshotResource(Resource):
    """
    快照恢复删除接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        restore_id = serializers.IntegerField(required=True, label="快照恢复任务id")
        operator = serializers.CharField(required=True, label="操作者")
        is_sync = serializers.BooleanField(required=False, label="是否需要同步", default=False)

    def perform_request(self, validated_request_data):
        models.EsSnapshotRestore.delete_restore(**validated_request_data)
        return validated_request_data


class RetryRestoreResultTableSnapshotResource(Resource):
    """
    快照恢复重试接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        restore_id = serializers.IntegerField(required=True, label="快照恢复任务id")
        operator = serializers.CharField(required=True, label="操作者")
        indices = serializers.ListField(required=False, label="重试索引列表", default=[])
        is_sync = serializers.BooleanField(required=False, label="是否需要同步", default=False)
        is_force = serializers.BooleanField(required=False, label="是否强制重试", default=False)

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRestore.retry_restore(**validated_request_data)


class ListRestoreResultTableSnapshotResource(Resource):
    """
    快照恢复任务list接口
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_ids = serializers.ListField(required=False, label="结果表ID", default=[])

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        querysets = models.EsSnapshotRestore.objects.filter(is_deleted=False, bk_tenant_id=bk_tenant_id)
        if validated_request_data["table_ids"]:
            querysets = querysets.filter(table_id__in=validated_request_data["table_ids"])
        return [queryset.to_json() for queryset in querysets]


class GetRestoreResultTableSnapshotStateResource(Resource):
    """
    rt快照状态
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        restore_ids = serializers.ListField(required=True, label="快照回溯任务ids")

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRestore.batch_get_state(
            bk_tenant_id=validated_request_data["bk_tenant_id"], restore_ids=validated_request_data["restore_ids"]
        )


class GetRestoreResultTableSnapshotIndicesResource(Resource):
    """
    快照回溯任务索引回溯详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        restore_ids = serializers.ListField(required=True, label="快照回溯任务ids")

    def perform_request(self, validated_request_data):
        return models.EsSnapshotRestore.batch_get_indices(**validated_request_data)


class EsRouteResource(Resource):
    """
    传发ES GET请求
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        es_storage_cluster = serializers.IntegerField(label="es存储集群id", required=True)
        url = serializers.CharField(label="es请求url", required=True)

    def validate_url(self, url: str):
        url = url.lstrip("/")
        for allow_url_prefix in ES_ROUTE_ALLOW_URL:
            if url.startswith(allow_url_prefix):
                if "format=" not in url and "?" not in url:
                    return f"{url}?format=json"
                if "format=" not in url:
                    return f"{url}&format=json"
                return url
        raise ValidationError(_("非法的url路径"))

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        es_client = get_client(bk_tenant_id=bk_tenant_id, cluster_id=validated_request_data["es_storage_cluster"])
        url = validated_request_data["url"]
        if not url.startswith("/"):
            url = "/" + url
        return es_client.transport.perform_request("GET", url)


class KafkaTailResource(Resource):
    """
    根据table_id消费kafka数据
    Note: 由于存在第三方Kafka的场景（如计算平台Kafka），接口中使用了confluent_kafka和kafka_python两个SDK，使用时需要注意Confluent和kafka的函数调用
    如Consumer和ConfluentConsumer，其中confluent_kafka相关主要针对2.4+版本的Kafka鉴权，如SCRAM-SHA-512
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        table_id = serializers.CharField(required=False, label="结果表ID")
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID")
        size = serializers.IntegerField(required=False, label="拉取条数", default=10)
        namespace = serializers.CharField(required=False, label="命名空间", default="bkmonitor")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_data_id = validated_request_data.get("bk_data_id")
        result_table = None

        # 参数处理,result_table / datasource
        if bk_data_id:
            logger.info("KafkaTailResource: got bk_data_id->[%s],try to tail kafka", bk_data_id)
            datasource = models.DataSource.objects.get(bk_tenant_id=bk_tenant_id, bk_data_id=bk_data_id)
            dsrt = models.DataSourceResultTable.objects.filter(bk_data_id=bk_data_id).first()
            if dsrt:
                result_table = models.ResultTable.objects.get(table_id=dsrt.table_id)
        else:
            table_id = validated_request_data["table_id"]
            logger.info("KafkaTailResource: got table_id->[%s],try to tail kafka", table_id)
            result_table = models.ResultTable.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
            if not result_table:
                return []
            datasource = result_table.data_source

        size = validated_request_data["size"]
        mq_ins = models.ClusterInfo.objects.get(cluster_id=datasource.mq_cluster_id)

        # Kafka是否需要进行鉴权,如SCRAM-SHA-512协议
        if mq_ins.is_auth:
            result = self._consume_with_confluent_kafka(mq_ins, datasource, size)
        # 是否是V4数据链路
        elif datasource.datalink_version == DATA_LINK_V4_VERSION_NAME:
            # 若开启特性开关且存在RT且非日志数据，则V4链路使用BkBase侧的Kafka采样接口拉取数据
            if result_table and datasource.etl_config == EtlConfigs.BK_STANDARD_V2_EVENT.value:
                data_id_config_name = compose_bkdata_data_id_name(datasource.data_name)
                try:
                    data_id_config = DataIdConfig.objects.get(
                        bk_tenant_id=bk_tenant_id,
                        namespace=BKBASE_NAMESPACE_BK_LOG,
                        name=data_id_config_name,
                    )
                except DataIdConfig.DoesNotExist:
                    logger.warning(
                        "KafkaTailResource: DataIdConfig not found, bk_tenant_id->[%s], namespace->[%s], name->[%s]",
                        bk_tenant_id,
                        BKBASE_NAMESPACE_BK_LOG,
                        data_id_config_name,
                    )
                    return []
                res = api.bkdata.tail_kafka_data(
                    bk_tenant_id=bk_tenant_id,
                    namespace=BKBASE_NAMESPACE_BK_LOG,
                    name=data_id_config.name,
                    limit=size,
                )
                result = [json.loads(data) for data in res]
            elif result_table and datasource.etl_config != "bk_flat_batch":
                logger.info("KafkaTailResource: using bkdata kafka tail api,bk_data_id->[%s]", datasource.bk_data_id)
                # TODO: 获取计算平台数据名称,待数据一致性实现后,统一通过BkBaseResultTable获取,不再进行复杂转换
                vm_record = models.AccessVMRecord.objects.get(
                    bk_tenant_id=bk_tenant_id, result_table_id=result_table.table_id
                )
                data_id_name = vm_record.bk_base_data_name
                namespace = validated_request_data["namespace"]
                if not data_id_name:
                    data_id_name = get_bkbase_raw_data_name_for_v3_datalink(
                        bk_tenant_id=bk_tenant_id, bkbase_data_id=vm_record.bk_base_data_id
                    )
                logger.info(
                    "KafkaTailResource: using bkdata kafka tail api,table_id->[%s],namespace->[%s],name->[%s]",
                    result_table.table_id,
                    namespace,
                    data_id_name,
                )
                res = api.bkdata.tail_kafka_data(
                    bk_tenant_id=bk_tenant_id, namespace=namespace, name=data_id_name, limit=size
                )
                result = [json.loads(data) for data in res]
            else:
                result = self._consume_with_gse_config(datasource, size)
        else:  # 其他情况使用kafka-python库,适配边缘存查链路等带证书鉴权的Kafka集群
            result = self._consume_with_kafka_python(datasource=datasource, mq_ins=mq_ins, size=size)

        result.reverse()
        return result

    def _consume_with_confluent_kafka(self, mq_ins, datasource, size):
        """
        使用confluent_kafka库消费kafka数据，针对2.4+鉴权认证的集群，如SCRAM-SHA-512
        """
        consumer_config = {
            "bootstrap.servers": f"{datasource.mq_cluster.domain_name}:{datasource.mq_cluster.port}",
            "group.id": f"bkmonitor-{uuid.uuid4()}",
            "session.timeout.ms": 6000,
            "auto.offset.reset": "latest",
            "security.protocol": mq_ins.security_protocol,
            "sasl.mechanisms": mq_ins.sasl_mechanisms,
            "sasl.username": datasource.mq_cluster.username,
            "sasl.password": datasource.mq_cluster.password,
        }

        consumer = ConfluentConsumer(consumer_config)
        topic = datasource.mq_config.topic

        # 获取该主题的所有分区
        metadata = consumer.list_topics(topic)
        partitions = metadata.topics[topic].partitions.keys()
        topic_partitions = [ConfluentTopicPartition(topic, partition) for partition in partitions]

        # 分配指定的分区
        consumer.assign(topic_partitions)

        # 在 assign 之后调用一次 poll 使 consumer 进入正确的状态
        consumer.poll(0.5)

        result = []
        errors = []

        for tp in topic_partitions:
            # 获取该分区最大偏移量
            low, high = consumer.get_watermark_offsets(tp)
            end_offset = high
            if not end_offset:
                continue

            # 设置消息消费偏移量
            if end_offset >= size:
                consumer.seek(ConfluentTopicPartition(topic, tp.partition, end_offset - size))
            else:
                consumer.seek(ConfluentTopicPartition(topic, tp.partition, 0))

            while len(result) < size:
                messages = consumer.consume(num_messages=size - len(result), timeout=1.0)
                if not messages:
                    break

                for msg in messages:
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            break
                        else:
                            errors.append(msg.error())  # 记录错误信息
                    else:
                        try:
                            result.append(json.loads(msg.value().decode()))
                        except Exception:  # pylint: disable=broad-except
                            pass
                    if msg.offset() == end_offset - 1:
                        break

        consumer.close()

        # 检查是否有错误并且没有成功读取到数据
        if not result and errors:
            raise KafkaException(errors)

        return result

    def _consume_with_kafka_python(self, datasource, mq_ins, size):
        """
        使用kafka-python库消费kafka数据，针对PLAIN认证的集群，适用于边缘存查联路等证书鉴权Kafka
        @param datasource: 数据源实例
        @param mq_ins: 集群实例
        @param size: 拉取条数
        """
        logger.info("KafkaTailResource: using kafka-python to tail,bk_data_id->[%s]", datasource.bk_data_id)

        mq_config = models.KafkaTopicInfo.objects.get(id=datasource.mq_config_id)
        topic = mq_config.topic
        logger.info(
            "KafkaTailResource: using kafka-python to tail,bk_data_id->[%s],topic->[%s]", datasource.bk_data_id, topic
        )

        if mq_ins.is_ssl_verify:  # SSL验证是否强验证
            server = mq_ins.extranet_domain_name if mq_ins.extranet_domain_name else mq_ins.domain_name
            port = mq_ins.port
            kafka_server = server + ":" + str(port)

            security_protocol = "SASL_SSL" if mq_ins.username else "SSL"
            sasl_mechanism = mq_ins.consul_config.get("sasl_mechanisms") or ("PLAIN" if mq_ins.username else None)

            # SSL认证证书相关，需要保存到临时文件以获取Consumer
            ssl_cafile = mq_ins.ssl_certificate_authorities
            ssl_certfile = mq_ins.ssl_certificate
            ssl_keyfile = mq_ins.ssl_certificate_key

            if ssl_cafile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_cafile)
                    ssl_cafile = fd.name

            if ssl_certfile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_certfile)
                    ssl_certfile = fd.name

            if ssl_keyfile:
                with tempfile.NamedTemporaryFile(mode="w", delete=False) as fd:
                    fd.write(ssl_keyfile)
                    ssl_keyfile = fd.name

            # 创建Consumer消费实例
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=kafka_server,
                security_protocol=security_protocol,
                sasl_mechanism=sasl_mechanism,
                sasl_plain_username=mq_ins.username,
                sasl_plain_password=mq_ins.password,
                request_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
                consumer_timeout_ms=settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
                ssl_cafile=ssl_cafile,
                ssl_certfile=ssl_certfile,
                ssl_keyfile=ssl_keyfile,
                ssl_check_hostname=not mq_ins.ssl_insecure_skip_verify,
            )
        else:
            param = {
                "bootstrap_servers": f"{datasource.mq_cluster.domain_name}:{datasource.mq_cluster.port}",
                "request_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
                "consumer_timeout_ms": settings.KAFKA_TAIL_API_TIMEOUT_SECONDS,
            }
            if datasource.mq_cluster.username:
                param["sasl_plain_username"] = datasource.mq_cluster.username
                param["sasl_plain_password"] = datasource.mq_cluster.password
                param["security_protocol"] = "SASL_PLAINTEXT"
                param["sasl_mechanism"] = "PLAIN"
            consumer = KafkaConsumer(topic, **param)

        max_retries = settings.KAFKA_TAIL_API_RETRY_TIMES
        retry_delay = settings.KAFKA_TAIL_API_RETRY_INTERVAL_SECONDS
        for attempt in range(max_retries):  # 边缘存查集群存在首次连接拉取时异常问题，添加重试机制
            consumer.poll(size)
            topic_partitions = consumer.partitions_for_topic(topic)
            if topic_partitions:
                break
            logger.warning(
                "KafkaTailResource: Failed to get partitions for topic->[%s],attempt->[%s],retrying.", topic, attempt
            )
            time.sleep(retry_delay)
        else:
            raise ValueError("failed to get partitions")
        result = []
        for partition in topic_partitions:
            # 获取该分区最大偏移量
            tp = TopicPartition(topic=datasource.mq_config.topic, partition=partition)
            end_offset = consumer.end_offsets([tp])[tp]
            if not end_offset:
                continue

            # 设置消息消费偏移量
            if end_offset >= size:
                consumer.seek(tp, end_offset - size)
            else:
                consumer.seek_to_beginning()
            for msg in consumer:
                try:
                    result.append(json.loads(msg.value.decode()))
                except Exception:  # pylint: disable=broad-except
                    pass
                if len(result) >= size:
                    return result
                if msg.offset == end_offset - 1:
                    break

        return result

    def _consume_with_gse_config(self, datasource, size):
        """
        从gse获取V4链路的kafka集群信息
        """
        route_params = {
            "condition": {"channel_id": datasource.bk_data_id, "plat_name": config.DEFAULT_GSE_API_PLAT_NAME},
            "operation": {"operator_name": settings.COMMON_USERNAME},
        }

        route_info_list = api.gse.query_route(**route_params)
        stream_to_id = None
        topic = None
        for route_list in route_info_list:
            # Todo: 当前只有1条route
            if route_list:
                route = route_list["route"][0]
                stream_to = route.get("stream_to", {}) if isinstance(route, dict) else {}
                stream_to_id = stream_to.get("stream_to_id")
                topic = stream_to.get("kafka", {}).get("topic_name")
                if stream_to_id and topic:
                    break

        if not (stream_to_id and topic):
            return []

        kafka_params = {
            "condition": {
                "stream_to_id": stream_to_id,
                "plat_name": config.DEFAULT_GSE_API_PLAT_NAME,
            },
            "operation": {"operator_name": settings.COMMON_USERNAME},
        }

        kafka_config_list = api.gse.query_stream_to(**kafka_params)

        # Todo: 当前只有1条kafka_addr
        kafka_addr = None
        for kafka_config in kafka_config_list:
            kafka_addr_list = kafka_config.get("kafka", {}).get("storage_address", [])
            if kafka_addr_list:
                kafka_addr = kafka_addr_list[0]
                break
        if not (isinstance(kafka_addr, dict) and kafka_addr.get("ip") and kafka_addr.get("port")):
            return []

        consumer_config = {
            "bootstrap_servers": f"{kafka_addr['ip']}:{kafka_addr['port']}",
            "request_timeout_ms": 1000,
            "consumer_timeout_ms": 1000,
        }

        consumer = KafkaConsumer(topic, **consumer_config)
        consumer.poll(size)
        topic_partitions = consumer.partitions_for_topic(topic)
        if not topic_partitions:
            raise ValueError(_("partition获取失败"))
        result = []
        for partition in topic_partitions:
            # 获取该分区最大偏移量
            tp = TopicPartition(topic=topic, partition=partition)
            end_offset = consumer.end_offsets([tp])[tp]
            if not end_offset:
                continue

            # 设置消息消费偏移量
            if end_offset >= size:
                consumer.seek(tp, end_offset - size)
            else:
                consumer.seek_to_beginning()
            for msg in consumer:
                try:
                    result.append(json.loads(msg.value.decode()))
                except Exception:  # pylint: disable=broad-except
                    pass
                if len(result) >= size:
                    return result
                if msg.offset == end_offset - 1:
                    break

        return result


class GetBCSClusterRelatedDataLinkResource(Resource):
    """
    获取BCS集群关联的数据链路（K8SMetric、CustomMetric、K8SEvent）
    返回关联的DataId、ResultTable、VMResultTable
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    def perform_request(self, validated_request_data):
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id", None)
        if not bcs_cluster_id:
            logger.info(
                "GetBCSClusterRelatedDataLinkResource: get bcs_cluster_id failed for request_data->[%s]",
                validated_request_data,
            )
            raise ValidationError(_("集群ID不能为空"))

        logger.info(
            "GetBCSClusterRelatedDataLinkResource: try to get cluster related data_link infos for bcs_cluster_id->[%s]",
            bcs_cluster_id,
        )
        cluster_ins = BCSClusterInfo.objects.get(
            cluster_id=bcs_cluster_id, bk_tenant_id=validated_request_data["bk_tenant_id"]
        )

        k8s_metric_data_id = cluster_ins.K8sMetricDataID
        custom_metric_data_id = cluster_ins.CustomMetricDataID
        k8s_event_data_id = cluster_ins.K8sEventDataID

        result = {
            k8s_metric_name: get_data_source_related_info(k8s_metric_data_id),
            cluster_custom_metric_name: get_data_source_related_info(custom_metric_data_id),
            k8s_event_name: get_data_source_related_info(k8s_event_data_id),
        }
        return result


class QueryResultTableStorageDetailResource(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID")
        table_id = serializers.CharField(required=False, label="结果表ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")

    def perform_request(self, validated_request_data):
        source = ResultTableAndDataSource(
            bk_tenant_id=validated_request_data["bk_tenant_id"],
            table_id=validated_request_data.get("table_id", None),
            bk_data_id=validated_request_data.get("bk_data_id", None),
            bcs_cluster_id=validated_request_data.get("bcs_cluster_id", None),
        )
        return source.get_detail()


class NotifyEsDataLinkAdaptNano(Resource):
    """
    通知监控平台，V4日志链路变更为纳秒，需要进行特殊适配操作
    新增dtEventTimeStampNanos，且其为 strict_date_optional_time_nanos||epoch_millis
    调整原有的dtEventTimeStamp,其es_format变为 strict_date_optional_time_nanos||epoch_millis
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_data_id = serializers.IntegerField(required=False, label="数据源ID")
        table_id = serializers.CharField(required=False, label="结果表ID")
        force_rotate = serializers.BooleanField(required=False, default=False, label="是否强制轮转索引")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        table_id = validated_request_data.get("table_id", None)
        bk_data_id = validated_request_data.get("bk_data_id", None)
        force_rotate = validated_request_data.get("force_rotate", False)

        if not table_id and not bk_data_id:
            raise ValidationError(_("table_id和bk_data_id不能同时为空"))

        if table_id:
            pass
        elif bk_data_id:
            table_id = models.DataSourceResultTable.objects.get(
                bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id
            ).table_id

        logger.info("NotifyEsDataLinkAdaptNano: table_id->[%s] changes to date_nanos,will adapt metadata", table_id)

        result_table = models.ResultTable.objects.filter(table_id=table_id, bk_tenant_id=bk_tenant_id).first()
        if not result_table:
            raise ValidationError(_("结果表不存在"))

        # 更改元数据
        try:
            with transaction.atomic():
                # ResultTableField新增 dtEventTimestampNanos
                models.ResultTableField.objects.create(
                    table_id=table_id,
                    field_name=DT_TIME_STAMP_NANO,
                    field_type="timestamp",
                    description="数据时间",
                    tag="dimension",
                    is_config_by_user=True,
                    bk_tenant_id=bk_tenant_id,
                )

                # 通过复制的方式,生成dtEventTimestampNanos的option
                original_objects = models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="dtEventTimeStamp", bk_tenant_id=bk_tenant_id
                )

                # 创建新对象，修改 field_name 为 'dtEventTimeStampNanos'
                for obj in original_objects:
                    # 使用 get_or_create 以确保不会重复创建相同的记录
                    new_obj, created = models.ResultTableFieldOption.objects.update_or_create(
                        table_id=obj.table_id,
                        field_name="dtEventTimeStampNanos",  # 更新 field_name
                        name=obj.name,
                        defaults={  # 如果记录不存在，才会使用 defaults 来创建新的记录
                            "value_type": obj.value_type,
                            "value": obj.value,
                            "creator": obj.creator,
                            "bk_tenant_id": obj.bk_tenant_id,
                        },
                    )
                    logger.info(
                        "NotifyEsDataLinkAdaptNano: create_field->[%s] for table_id->[%s] created->[%s]",
                        new_obj.field_name,
                        new_obj.table_id,
                        created,
                    )

                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="dtEventTimeStampNanos", name="es_type", bk_tenant_id=bk_tenant_id
                ).update(value=NANO_FORMAT)

                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="dtEventTimeStampNanos", name="es_format", bk_tenant_id=bk_tenant_id
                ).update(value=STRICT_NANO_ES_FORMAT)

                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="time", name="es_format", bk_tenant_id=bk_tenant_id
                ).update(value=EPOCH_MILLIS_FORMAT)

                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="dtEventTimeStamp", name="es_format", bk_tenant_id=bk_tenant_id
                ).update(value=EPOCH_MILLIS_FORMAT)

                models.ResultTableFieldOption.objects.filter(
                    table_id=table_id, field_name="dtEventTimeStamp", name="es_type", bk_tenant_id=bk_tenant_id
                ).update(value="date")

        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "NotifyEsDataLinkAdaptNano: table_id->[%s] failed to adapt metadata for date_nano,error->[%s]",
                table_id,
                e,
            )
            raise e

        # 索引轮转
        logger.info(
            "NotifyEsDataLinkAdaptNano: table_id->[%s] now try to rotate index,force_rotate->[%s]",
            table_id,
            force_rotate,
        )

        try:
            es_storage = models.ESStorage.objects.get(table_id=table_id, bk_tenant_id=bk_tenant_id)
            es_storage.update_index_v2(force_rotate=force_rotate)
            es_storage.create_or_update_aliases(force_rotate=force_rotate)
        except Exception as e:  # pylint: disable=broad-except
            logger.exception(
                "NotifyEsDataLinkAdaptNano: table_id->[%s] failed to rotate index,error->[%s]", table_id, e
            )
            raise e

        return result_table.to_json().get("field_list")


class GetDataLabelsMapResource(Resource):
    """
    获取结果表 ID 与其 DataLabel 的映射关系
    """

    class RequestSerializer(serializers.Serializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.CharField(label="业务ID")
        table_or_labels = serializers.ListField(
            child=serializers.CharField(), label="结果表ID列表", default=[], min_length=1
        )

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        data_labels_map = {}
        table_or_labels: list[str] = validated_request_data["table_or_labels"]
        data_labels_queryset = models.ResultTable.objects.filter(
            Q(
                bk_biz_id__in=[0, validated_request_data["bk_biz_id"]],
                data_label__in=table_or_labels,
                bk_tenant_id=bk_tenant_id,
            )
            | Q(table_id__in=table_or_labels, bk_tenant_id=bk_tenant_id)
        ).values("table_id", "data_label")
        for item in data_labels_queryset:
            data_labels_map[item["table_id"]] = item["data_label"]
            if item["data_label"]:
                # 不为空才建立映射关系，避免写入 empty=empty，
                data_labels_map[item["data_label"]] = item["data_label"]
        return data_labels_map


class SyncBkBaseRtMetaByBizIdResource(Resource):
    """
    同步单个业务的计算平台RT元信息
    """

    class RequestSerializer(PageSerializer):
        bk_biz_id = serializers.CharField(label="业务ID")

    def perform_request(self, validated_request_data):
        # 同步BKDATA元信息,单业务实时触发同步
        bk_biz_id = validated_request_data["bk_biz_id"]
        # 同步指定存储类型的数据
        storages = settings.SYNC_BKBASE_META_SUPPORTED_STORAGE_TYPES
        logger.info("SyncBkBaseRtMetaByBizIdResource: start sync bkbase meta for biz_id->[%s]", bk_biz_id)
        bkbase_rt_meta_list = api.bkdata.bulk_list_result_table(bk_biz_id=[bk_biz_id], storages=storages)
        sync_bkbase_result_table_meta(round_iter=0, bkbase_rt_meta_list=bkbase_rt_meta_list, biz_id_list=[bk_biz_id])
        logger.info("SyncBkBaseRtMetaByBizIdResource: end sync bkbase meta for biz_id->[%s]", bk_biz_id)


class ListBkBaseRtInfoByBizIdResource(Resource):
    class RequestSerializer(PageSerializer):
        bk_tenant_id = TenantIdField(label="租户ID")
        bk_biz_id = serializers.CharField(label="业务ID")

    def perform_request(self, validated_request_data):
        bk_tenant_id = validated_request_data["bk_tenant_id"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        logger.info("ListBkBaseRtInfoByBizIdResource: start query bkbase rts for biz_id->[%s]", bk_biz_id)
        bkbase_rts = models.ResultTable.objects.filter(
            bk_biz_id=bk_biz_id, default_storage=models.ClusterInfo.TYPE_BKDATA, bk_tenant_id=bk_tenant_id
        )

        # 分页返回
        page_size = validated_request_data["page_size"]
        if page_size > 0:
            count = bkbase_rts.count()
            offset = (validated_request_data["page"] - 1) * page_size
            paginated_queryset = bkbase_rts[offset : offset + page_size]
            results = [rt.to_json() for rt in paginated_queryset]
            return {"count": count, "info": results}

        # 如果不分页，返回所有结果
        results = [rt.to_json() for rt in bkbase_rts]
        return results

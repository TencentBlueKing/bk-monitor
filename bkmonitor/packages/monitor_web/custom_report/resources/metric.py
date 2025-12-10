"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
import time
import re
import copy
from collections import defaultdict
from typing import Any
from functools import reduce

import arrow
from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkmonitor.models import MetricListCache, QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkmonitor.utils.user import get_admin_username
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from core.errors.custom_report import (
    CustomValidationLabelError,
    CustomValidationNameError,
)
from monitor_web.constants import ETL_CONFIG
from monitor_web.custom_report.constants import UNGROUP_SCOPE_NAME, CustomTSMetricType
from monitor_web.custom_report.serializers import (
    CustomTSGroupingRuleSerializer,
    CustomTSScopeSerializer,
    CustomTSTableSerializer,
    MetricSerializer,
    DimensionConfigSerializer,
    MetricConfigSerializer,
)
from monitor_web.models.custom_report import (
    CustomTSField,
    CustomTSGroupingRule,
    CustomTSTable,
)
from monitor_web.strategies.resources import GetMetricListV2Resource

logger = logging.getLogger(__name__)


def get_label_display_dict():
    label_display_dict = {}
    try:
        labels = resource.commons.get_label()
        for label in labels:
            for child in label["children"]:
                label_display_dict[child["id"]] = [label["name"], child["name"]]
    except Exception:
        pass
    return label_display_dict


def count_rt_bound_strategies(table_ids, data_source_label, data_type_label, bk_biz_id: int | None = None):
    """
    统计与结果表绑定的策略数量
    """
    if not table_ids:
        return {}

    # 先查询策略ID（当有业务过滤条件时）
    strategy_ids = None
    if bk_biz_id:
        strategy_ids = set(StrategyModel.objects.filter(bk_biz_id=bk_biz_id).values_list("pk", flat=True))

    # 查询自定义时间序列类型的查询配置
    query_configs_queryset = (
        QueryConfigModel.objects.annotate(result_table_id=models.F("config__result_table_id"))
        .filter(
            data_source_label=data_source_label,
            data_type_label=data_type_label,
        )
        .values("result_table_id", "strategy_id")
    )

    # 如果有业务过滤条件，进一步筛选query_configs
    if strategy_ids:
        query_configs_queryset = query_configs_queryset.filter(strategy_id__in=strategy_ids)

    query_configs = list(query_configs_queryset)

    # 构建结果表ID到策略ID的映射关系
    table_id_strategy_mapping = defaultdict(set)
    table_ids = set(table_ids)
    for query_config in query_configs:
        result_table_id = query_config["result_table_id"]
        if result_table_id in table_ids:
            table_id_strategy_mapping[query_config["result_table_id"]].add(query_config["strategy_id"])

    return {key: len(value) for key, value in table_id_strategy_mapping.items()}


class ProxyHostInfo(Resource):
    """
    Proxy主机信息
    """

    DEFAULT_PROXY_PORT = 10205

    def get_listen_port(self):
        return getattr(settings, "BK_MONITOR_PROXY_LISTEN_PORT", ProxyHostInfo.DEFAULT_PROXY_PORT)

    def perform_request(self, validated_request_data):
        port = self.get_listen_port()
        proxy_host_info = []
        bk_biz_id = validated_request_data["bk_biz_id"]
        proxy_hosts = []
        try:
            proxy_hosts = api.node_man.get_proxies_by_biz(bk_biz_id=bk_biz_id)
        except NoRelatedResourceError:
            logger.warning("bk_biz_id: %s not found related resource", bk_biz_id)
        except Exception as e:
            logger.warning("get proxies by bk_biz_id(%s) error, %s", bk_biz_id, e)

        for host in proxy_hosts:
            bk_cloud_id = int(host["bk_cloud_id"])
            # 默认云区域上报proxy，以settings配置为准！
            if bk_cloud_id == 0:
                continue
            ip = host.get("conn_ip") or host.get("inner_ip")
            proxy_host_info.append({"ip": ip, "bk_cloud_id": bk_cloud_id, "port": port})

        default_cloud_display = settings.CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN or settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        for proxy_ip in default_cloud_display:
            proxy_host_info.append({"ip": proxy_ip, "bk_cloud_id": 0, "port": port})
        return proxy_host_info


class ValidateCustomTsGroupName(Resource):
    """
    校验自定义指标名称是否合法
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            custom_ts_groups = api.metadata.query_time_series_group(
                time_series_group_name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("time_series_group_id"):
                custom_ts_groups = [
                    g
                    for g in custom_ts_groups
                    if g["time_series_group_id"] != validated_request_data["time_series_group_id"]
                ]
            is_exist = bool(custom_ts_groups)
        except Exception:
            queryset = CustomTSTable.objects.filter(
                name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("time_series_group_id"):
                queryset = queryset.exclude(time_series_group_id=validated_request_data["time_series_group_id"])
            is_exist = queryset.exists()
        if is_exist:
            raise CustomValidationNameError(msg=_("自定义指标名称已存在"))
        return True


class CreateCustomTimeSeries(Resource):
    """
    创建自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    CUSTOM_TS_NAME = "custom_time_series"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), required=True)
        name = serializers.CharField(label=_("名称"), required=True, max_length=128)
        scenario = serializers.CharField(label=_("对象"), required=True)
        table_id = serializers.CharField(label=_("表名"), required=False, default="")
        metric_info_list = serializers.ListField(label=_("预定义表结构"), required=False, default=[])
        is_platform = serializers.BooleanField(label=_("平台级"), required=False, default=False)
        data_label = serializers.CharField(label=_("数据标签"), required=True)
        protocol = serializers.CharField(label=_("上报协议"), required=False, default="json")
        desc = serializers.CharField(label=_("说明"), required=False, default="", allow_blank=True)
        is_split_measurement = serializers.BooleanField(label=_("是否启动自动分表逻辑"), required=False, default=True)

        def validate(self, attrs):
            ValidateCustomTsGroupName().request(name=attrs["name"], bk_biz_id=attrs["bk_biz_id"])
            ValidateCustomTsGroupLabel().request(data_label=attrs["data_label"], bk_biz_id=attrs["bk_biz_id"])
            return attrs

    def data_name(self, bk_biz_id, ts_name):
        return f"{bk_biz_id}_{self.CUSTOM_TS_NAME}_{ts_name}"

    def table_id(self, bk_biz_id, data_id):
        database_name = f"{bk_biz_id}_{self.CUSTOM_TS_NAME}_{data_id}"
        return "{}.{}".format(database_name, "base")

    @staticmethod
    def get_data_id(bk_biz_id: int, data_name: str, operator: str, space_uid: str | None = None):
        try:
            data_id_info = api.metadata.get_data_id({"data_name": data_name, "with_rt_info": False})
        except BKAPIError:
            param = {
                "bk_biz_id": bk_biz_id,
                "data_name": data_name,
                "etl_config": ETL_CONFIG.CUSTOM_TS,
                "operator": operator,
                "data_description": data_name,
                "type_label": DataTypeLabel.TIME_SERIES,
                "source_label": DataSourceLabel.CUSTOM,
                "option": {"inject_local_time": True},
            }
            if space_uid:
                param.update(space_uid=space_uid)
            data_id_info = api.metadata.create_data_id(param)
        else:
            raise CustomValidationNameError(
                data=data_id_info["bk_data_id"], msg=_("数据源名称[{}]已存在").format(data_name)
            )
        bk_data_id = data_id_info["bk_data_id"]
        return bk_data_id

    @staticmethod
    def get_space_uid(bk_biz_id):
        """
        获取空间uid
        :param bk_biz_id:
        :return:
        """
        if bk_biz_id > 0:
            space_uid = f"{SpaceTypeEnum.BKCC.value}__{bk_biz_id}"
        else:
            space_data = api.metadata.get_space_detail({"id": abs(bk_biz_id)})
            space_uid = space_data.get("space_uid", "")
        return space_uid

    @atomic()
    def perform_request(self, validated_request_data):
        # 如果是平台级，则ts_group 及对应表的业务id为0
        # 当前业务为关联的平台级业务id，内置到data_id的data_name里面
        # data_id有个业务归属，而对应的table可以在各业务下使用
        input_bk_biz_id = 0 if validated_request_data["is_platform"] else validated_request_data["bk_biz_id"]
        operator = get_request_username() or get_admin_username(bk_tenant_id=get_request_tenant_id())

        # 当前业务
        data_name = self.data_name(validated_request_data["bk_biz_id"], validated_request_data["name"])
        # 如果 bk_biz_id 为 0，意味着是全局业务配置，这种情况不需要空间
        space_uid = (
            None
            if validated_request_data["bk_biz_id"] == 0
            else self.get_space_uid(int(validated_request_data["bk_biz_id"]))
        )
        try:
            # 保证 data id 已存在
            bk_data_id = self.get_data_id(
                bk_biz_id=validated_request_data["bk_biz_id"],
                data_name=data_name,
                operator=operator,
                space_uid=space_uid,
            )
        except CustomValidationNameError as e:
            # dataid 已存在，判定 ts 是否存在：
            bk_data_id = e.data
            if api.metadata.query_time_series_group(
                time_series_group_name=validated_request_data["name"], bk_biz_id=input_bk_biz_id
            ):
                # ts group 已存在，不需要再额外创建
                raise CustomValidationNameError(msg=_("数据源名称[{}]已存在").format(data_name))

        # data_id 存在，但 ts group 不存在，继续执行
        # 2. 调用接口创建 time_series_group
        params = {
            "operator": operator,
            "bk_data_id": bk_data_id,
            # 平台级接入，ts_group 业务id对应为0
            "bk_biz_id": input_bk_biz_id,
            "time_series_group_name": validated_request_data["name"],
            "label": validated_request_data["scenario"],
            "metric_info_list": validated_request_data["metric_info_list"],
            "is_split_measurement": validated_request_data["is_split_measurement"],
            "data_label": validated_request_data["data_label"],
        }
        if validated_request_data["table_id"]:
            params["table_id"] = validated_request_data["table_id"]
        group_info = api.metadata.create_time_series_group(params)

        CustomTSTable.objects.create(
            bk_tenant_id=get_request_tenant_id(),
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=group_info["time_series_group_id"],
            scenario=group_info["label"],
            name=group_info["time_series_group_name"],
            bk_data_id=group_info["bk_data_id"],
            table_id=group_info["table_id"],
            is_platform=validated_request_data["is_platform"],
            data_label=validated_request_data["data_label"],
            protocol=validated_request_data["protocol"],
            desc=validated_request_data["desc"],
        )
        return {"time_series_group_id": group_info["time_series_group_id"], "bk_data_id": group_info["bk_data_id"]}


class ModifyCustomTimeSeries(Resource):
    """
    修改自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), required=True)
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"), required=True)

        name = serializers.CharField(label=_("名称"), required=False, max_length=128)
        is_platform = serializers.BooleanField(required=False, label=_("平台级"))
        data_label = serializers.CharField(label=_("数据标签"), required=False)
        desc = serializers.CharField(label=_("说明"), required=False, allow_blank=True)
        auto_discover = serializers.BooleanField(required=False, label=_("自动发现"))

        class MetricListSerializer(serializers.Serializer):
            class FieldSerializer(serializers.Serializer):
                unit = serializers.CharField(label=_("字段单位"), required=True, allow_blank=True)
                name = serializers.CharField(label=_("字段名"), required=True)
                description = serializers.CharField(label=_("字段描述"), required=True, allow_blank=True)
                monitor_type = serializers.CharField(label=_("字段类型，指标或维度"), required=True)

            fields = FieldSerializer(label=_("字段信息"), required=True, many=True)

        # 向前兼容字段，后续页面不再使用
        metric_json = serializers.ListField(label=_("指标配置"), child=MetricListSerializer(), required=False)

        def validate(self, attrs):
            if attrs.get("name"):
                ValidateCustomTsGroupName().request(
                    name=attrs["name"], bk_biz_id=attrs["bk_biz_id"], time_series_group_id=attrs["time_series_group_id"]
                )
            if attrs.get("data_label"):
                ValidateCustomTsGroupLabel().request(
                    data_label=attrs["data_label"],
                    bk_biz_id=attrs["bk_biz_id"],
                    time_series_group_id=attrs["time_series_group_id"],
                )
            return attrs

    def update_fields(self, table: CustomTSTable, params: dict):
        """
        更新自定义时序字段信息
        """
        if "metric_json" not in params:
            return

        exists_fields = {
            (item.name, item.type): item
            for item in CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id)
        }
        need_update_fields = []
        need_create_fields = []
        current_fields: set[tuple[str, str]] = set()
        for field in params["metric_json"][0]["fields"]:
            if (field["name"], field["monitor_type"]) in exists_fields:
                field = exists_fields.get((field["name"], field["monitor_type"]))
                field.description = field["description"]
                field.config.update({"unit": field["unit"]})
                need_update_fields.append(field)
            else:
                need_create_fields.append(
                    CustomTSField(
                        time_series_group_id=table.time_series_group_id,
                        type=field["monitor_type"],
                        name=field["name"],
                        description=field["description"],
                        config={"unit": field["unit"]},
                    )
                )

        CustomTSField.objects.bulk_create(need_create_fields, batch_size=500)
        CustomTSField.objects.bulk_update(need_update_fields, ["config", "description"], batch_size=500)

        need_delete_fields = set(exists_fields.keys()) - current_fields
        if need_delete_fields:
            CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id).filter(
                reduce(lambda x, y: x | y, (Q(name=name, type=type) for name, type in need_delete_fields))
            ).delete()

    @atomic()
    def perform_request(self, params: dict):
        table = CustomTSTable.objects.filter(
            bk_biz_id=params["bk_biz_id"],
            time_series_group_id=params["time_series_group_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {params['bk_biz_id']},"
                f" time_series_group_id: {params['time_series_group_id']}"
            )

        # 更新自定义时序表信息
        update_fields = ["name", "is_platform", "data_label", "desc", "auto_discover"]
        for field in update_fields:
            if field in params:
                setattr(table, field, params[field])
        table.save()

        # 更新自定义时序字段信息
        self.update_fields(table, params)

        # 更新metadata指标信息
        table.save_to_metadata(with_fields="metric_json" in params)

        return resource.custom_report.custom_time_series_detail(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=table.time_series_group_id
        )


class DeleteCustomTimeSeries(Resource):
    """
    删除自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), required=True)
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"), required=True)

    @atomic()
    def perform_request(self, params: dict):
        table = CustomTSTable.objects.filter(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"]
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )
        operator = get_request_username()
        api.metadata.delete_time_series_group(
            {"operator": operator, "time_series_group_id": table.time_series_group_id}
        )

        CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id).delete()
        table.delete()
        return {"time_series_group_id": params["time_series_group_id"]}


class CustomTimeSeriesList(Resource):
    """
    自定义时序列表
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"), default=0)
        search_key = serializers.CharField(label=_("名称"), required=False)
        page_size = serializers.IntegerField(label=_("获取的条数"), default=10)
        page = serializers.IntegerField(label=_("页数"), default=1)
        # 新增参数用以判定是否需要查询平台级 dataid
        is_platform = serializers.BooleanField(label=_("是否平台级"), required=False)

    def perform_request(self, validated_request_data):
        queryset = CustomTSTable.objects.filter(bk_tenant_id=get_request_tenant_id()).order_by("-update_time")
        context = {"request_bk_biz_id": validated_request_data["bk_biz_id"]}
        # 区分本空间 和 全平台
        if validated_request_data.get("is_platform"):
            # 只查全平台, 不关注业务
            queryset = queryset.filter(is_platform=True)

        elif validated_request_data.get("bk_biz_id"):
            # 非全平台，查当前业务(0表示全部业务)
            queryset = queryset.filter(bk_biz_id=validated_request_data["bk_biz_id"])

        if validated_request_data.get("search_key"):
            search_key = validated_request_data["search_key"]
            conditions = models.Q(name__contains=search_key)
            try:
                search_key = int(search_key)
            except ValueError:
                pass
            else:
                conditions = conditions | models.Q(pk=search_key) | models.Q(bk_data_id=search_key)
            queryset = queryset.filter(conditions)
        paginator = Paginator(queryset, validated_request_data["page_size"])
        serializer = CustomTSTableSerializer(paginator.page(validated_request_data["page"]), many=True, context=context)
        tables = serializer.data

        table_ids = [table["table_id"] for table in tables]
        strategy_count_mapping = count_rt_bound_strategies(
            table_ids,
            data_source_label=DataSourceLabel.CUSTOM,
            data_type_label=DataTypeLabel.TIME_SERIES,
            bk_biz_id=validated_request_data.get("bk_biz_id"),
        )

        label_display_dict = get_label_display_dict()
        for table in tables:
            table["scenario_display"] = label_display_dict.get(table["scenario"], [table["scenario"]])
            table["related_strategy_count"] = strategy_count_mapping.get(table["table_id"], 0)
        return {
            "list": tables,
            "total": queryset.count(),
        }


class CustomTimeSeriesDetail(Resource):
    """
    自定义时序详情
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))
        model_only = serializers.BooleanField(label=_("是否只查询自定义时序表信息"), default=False)
        with_target = serializers.BooleanField(label=_("是否查询 target"), default=False)
        with_metrics = serializers.BooleanField(label=_("是否查询指标信息"), default=True)
        empty_if_not_found = serializers.BooleanField(
            label=_("是否返回空数据"),
            required=False,
            default=False,
            help_text=_("如果自定义时序表不存在，是否返回空数据"),
        )

    def perform_request(self, params: dict[str, Any]):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表信息
        config: CustomTSTable | None = CustomTSTable.objects.filter(
            bk_biz_id=bk_biz_id, pk=time_series_group_id
        ).first()
        if not config:
            # 如果自定义时序表不存在，则返回空数据
            if params.get("empty_if_not_found"):
                return {}
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")

        # 如果是平台自定义时序，则需要校验业务是否匹配
        if not config.is_platform and config.bk_biz_id != bk_biz_id:
            raise ValidationError(f"custom time series not found, bk_biz_id: {bk_biz_id}")

        # 序列化自定义时序表信息
        data = CustomTSTableSerializer(config, context={"request_bk_biz_id": bk_biz_id}).data

        # 如果只查询自定义时序表信息，则直接返回
        if params.get("model_only"):
            return data

        data["scenario_display"] = get_label_display_dict().get(data["scenario"], [data["scenario"]])
        data["access_token"] = config.token

        # 如果需要查询指标信息，则将指标信息写入到metric_json中
        data["metric_json"] = [{"fields": config.get_metric_fields()}] if params.get("with_metrics") else []
        # 新增查询target参数，自定义指标详情页面不需要target，默认不查询
        data["target"] = config.query_target(bk_biz_id=bk_biz_id) if params.get("with_target") else []

        return data


class GetCustomTsFields(Resource):
    """
    获取自定义指标字段
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        ts_table: CustomTSTable | None = CustomTSTable.objects.filter(
            bk_biz_id=bk_biz_id,
            time_series_group_id=time_series_group_id,
        ).first()
        if not ts_table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {bk_biz_id}, "
                f"time_series_group_id: {time_series_group_id}"
            )

        dimensions: list[dict[str, Any]] = []
        metrics: list[dict[str, Any]] = []
        for scope_dict in ts_table.query_time_series_scope:
            scope_id: int | None = scope_dict.get("scope_id")
            scope_name: str = scope_dict.get("scope_name", "")
            for metric_dict in scope_dict.get("metric_list", []):
                field_config: dict[str, Any] = metric_dict.get("field_config", {})
                if field_config.get("disabled"):
                    continue
                metrics.append(
                    {
                        "scope_id": scope_id,
                        "scope_name": scope_name,
                        "field_id": metric_dict.get("field_id"),
                        "name": metric_dict.get("metric_name", ""),
                        "type": CustomTSMetricType.METRIC,
                        "alias": field_config.get("alias", ""),
                        "disabled": field_config.get("disabled", False),
                        "unit": field_config.get("unit", ""),
                        "hidden": field_config.get("hidden", False),
                        "aggregate_method": field_config.get("aggregate_method", ""),
                        "function": field_config.get("function", {}),
                        "interval": field_config.get("interval", 0),
                        "dimensions": metric_dict.get("tag_list", []),
                        "create_time": metric_dict.get("create_time", None),
                        "update_time": metric_dict.get("last_modify_time", None),
                    }
                )
            for dimension_name, dimension_dict in scope_dict.get("dimension_config", {}).items():
                dimensions.append(
                    {
                        "scope_id": scope_id,
                        "scope_name": scope_name,
                        "name": dimension_name,
                        "type": CustomTSMetricType.DIMENSION,
                        "alias": dimension_dict.get("alias", ""),
                        "disabled": False,
                        "hidden": dimension_dict.get("hidden", False),
                        "common": dimension_dict.get("common", False),
                        "create_time": None,
                        "update_time": None,
                    }
                )
        return {"dimensions": dimensions, "metrics": metrics}


class ModifyCustomTsFields(Resource):
    """
    修改自定义指标字段
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))

        class BaseFieldSerializer(serializers.Serializer):
            type = serializers.ChoiceField(label=_("字段类型"), choices=CustomTSMetricType.choices())
            name = serializers.CharField(label=_("字段名"))
            scope_id = serializers.IntegerField(label=_("分组 ID"))
            scope_name = serializers.CharField(label=_("分组名称"), allow_blank=True)
            field_id = serializers.IntegerField(label=_("字段 ID"), required=False, allow_null=True)

            def validate(self, attrs):
                if attrs["type"] == CustomTSMetricType.METRIC and "field_id" not in attrs:
                    raise serializers.ValidationError({"field_id": _("metric 类型必须提供有效的 field_id")})
                return super().validate(attrs)

        class FieldSerializer(BaseFieldSerializer):
            config = serializers.DictField(label=_("字段配置"), default={})

            def to_internal_value(self, data: dict[str, Any]) -> dict[str, Any]:
                validated_data = super().to_internal_value(data)
                if validated_data["type"] == CustomTSMetricType.DIMENSION:
                    config_serializer = DimensionConfigSerializer(data=data)
                else:
                    config_serializer = MetricConfigSerializer(data=data)
                config_serializer.is_valid(raise_exception=True)
                validated_data["config"].update(config_serializer.validated_data)
                return validated_data

        update_fields = serializers.ListField(label=_("更新字段列表"), child=FieldSerializer(), default=list)
        delete_fields = serializers.ListField(label=_("删除字段列表"), child=BaseFieldSerializer(), default=list)

    def perform_request(self, params: dict[str, Any]):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        ts_table = CustomTSTable.objects.filter(bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id).first()
        if not ts_table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {bk_biz_id}, "
                f"time_series_group_id: {time_series_group_id}"
            )

        # 构建原始数据
        metric_dict_by_field_id: dict[int, dict[str, Any]] = {}
        dimension_config_by_scope_id: dict[int, dict[str, Any]] = {}
        scope_list: list[dict[str, Any]] = copy.deepcopy(ts_table.query_time_series_scope)
        for scope_dict in scope_list:
            for metric_dict in scope_dict.get("metric_list", []):
                metric_dict_by_field_id[metric_dict["field_id"]] = metric_dict
            dimension_config_by_scope_id[scope_dict["scope_id"]] = scope_dict.get("dimension_config", {})

        # 删除字段
        need_delete_metric_dict: dict[int, dict[str, Any]] = {}
        delete_dimensions_by_scope_id: dict[int, list[dict[str, Any]]] = {}
        delete_fields: list[dict[str, Any]] = params["delete_fields"]
        for field_dict in delete_fields:
            if field_dict["type"] == CustomTSMetricType.METRIC:
                field_id: int = field_dict["field_id"]
                if field_id not in metric_dict_by_field_id:
                    continue
                origin_metric_dict: dict[str, Any] = metric_dict_by_field_id[field_id]
                origin_field_config: dict[str, Any] = origin_metric_dict.get("field_config", {})
                origin_field_config["disabled"] = True
                need_delete_metric_dict[field_id] = {
                    "field_id": field_id,
                    "field_config": origin_field_config,
                }
            else:
                delete_dimensions_by_scope_id.setdefault(field_dict["scope_id"], []).append(field_dict)

        # 更新字段
        need_create_metrics: list[dict[str, Any]] = []
        need_update_metrics: list[dict[str, Any]] = []
        update_dimensions_by_scope_id: dict[str, list[dict[str, Any]]] = {}
        update_fields: list[dict[str, Any]] = params["update_fields"]
        for field_dict in update_fields:
            scope_name: str = field_dict["scope_name"]
            if field_dict["type"] == CustomTSMetricType.METRIC:
                field_id: int | None = field_dict["field_id"]
                if field_id is None:
                    # 创建场景
                    need_create_metrics.append(
                        {
                            "scope_name": field_dict["scope_name"],
                            "field_name": field_dict["name"],
                            "field_config": field_dict["config"],
                        }
                    )
                    continue
                elif field_id not in metric_dict_by_field_id or field_id in need_delete_metric_dict:
                    continue
                # 更新场景
                origin_field_config: dict[str, Any] = metric_dict_by_field_id[field_id].get("field_config", {})
                origin_field_config.update(field_dict["config"])
                need_update_metrics.append(
                    {
                        "field_id": field_id,
                        "scope_name": scope_name,
                        "field_config": origin_field_config,
                    }
                )
            else:
                update_dimensions_by_scope_id.setdefault(field_dict["scope_id"], []).append(field_dict)

        update_dimensions: list[dict[str, Any]] = []
        for scope_id in set(delete_dimensions_by_scope_id.keys()) | set(update_dimensions_by_scope_id.keys()):
            delete_dimension_names: set[str] = {
                field_dict["name"] for field_dict in delete_dimensions_by_scope_id.get(scope_id, [])
            }

            origin_dimension_config = {
                k: v
                for k, v in dimension_config_by_scope_id.get(scope_id, {}).items()
                if k not in delete_dimension_names
            }
            for update_field_dict in update_dimensions_by_scope_id.get(scope_id, []):
                field_name = update_field_dict["name"]
                field_config = update_field_dict["config"]
                if field_name in origin_dimension_config:
                    origin_dimension_config[field_name].update(field_config)
                else:
                    origin_dimension_config[field_name] = field_config
            update_dimensions.append({"scope_id": scope_id, "dimension_config": origin_dimension_config})

        # 更新维度
        if update_dimensions:
            api.metadata.create_or_update_time_series_scope(group_id=time_series_group_id, scopes=update_dimensions)
        # 更新指标
        if list(need_delete_metric_dict) or need_update_metrics or need_create_metrics:
            api.metadata.create_or_update_time_series_metric(
                group_id=time_series_group_id,
                metrics=list(need_delete_metric_dict.values()) + need_update_metrics + need_create_metrics,
            )


class ValidateCustomTsGroupLabel(Resource):
    """
    校验自定义指标数据名称是否合法
    1. 创建场景：调用metadata接口校验是否与存量ResultTable的data_label重复
    2. 编辑场景：除了time_series_group_id参数对应CustomTSTable的data_label外，是否与存量ResultTable的data_label重复
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        time_series_group_id = serializers.IntegerField(required=False)
        data_label = serializers.CharField(required=True)

    METRIC_DATA_LABEL_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_\.]*$")

    def perform_request(self, params: dict):
        if params["data_label"].strip() == "":
            raise CustomValidationLabelError(msg=_("自定义指标英文名不允许为空"))

        data_labels = params["data_label"].strip().split(",")
        for dl in data_labels:
            if not self.METRIC_DATA_LABEL_PATTERN.match(dl):
                raise CustomValidationLabelError(
                    msg=_("自定义指标英文名仅允许包含字母、数字、下划线、点号，且必须以字母开头")
                )
        params["data_label"] = ",".join(data_labels)
        return True


class AddCustomMetricResource(Resource):
    """
    添加自定义指标
    1. 由于获取指标列表存在过滤失效问题，先确认该指标是否存在
    2. 请求metadata api添加该指标
    3. 新增至指标缓存，并返回metric item
    """

    class RequestSerializer(serializers.Serializer):
        metric_field = serializers.CharField(required=True, label=_("指标名"))
        result_table_id = serializers.CharField(required=True, label=_("结果表 ID"))
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))

    def perform_request(self, params: dict):
        queryset = CustomTSTable.objects.filter(bk_biz_id=params["bk_biz_id"])

        # 查询该任务是否已有执行任务
        table = queryset.filter(table_id__startswith=params["result_table_id"])
        if not table.exists():
            table = queryset.filter(data_label=params["result_table_id"])
            if not table.exists():
                raise ValidationError(f"结果表或datalabel({params['result_table_id']})不存在")

        # 手动添加的自定义指标metric_md5特殊处理为0
        filter_params = {
            "data_source_label": DataSourceLabel.CUSTOM,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "bk_biz_id": params["bk_biz_id"],
            "result_table_id": table.first().table_id,
            "bk_tenant_id": get_request_tenant_id(),
        }
        metric_list = MetricListCache.objects.filter(**filter_params)
        if metric_list.filter(metric_field=params["metric_field"]).exists():
            raise ValidationError(f"指标({params['result_table_id']}.{params['metric_field']})已存在")
        create_params = {
            "metric_field": params["metric_field"],
            "metric_field_name": params["metric_field"],
            "metric_md5": "0",
            "data_label": table.first().data_label,
            **filter_params,
        }
        if metric_list.first():
            extra_params = {
                "result_table_label_name": metric_list.first().result_table_label_name,
                "result_table_name": metric_list.first().result_table_name,
                "result_table_label": metric_list.first().result_table_label,
                "related_name": metric_list.first().related_name,
                "related_id": metric_list.first().related_id,
                "extend_fields": metric_list.first().extend_fields,
            }
        else:
            extra_params = {
                "result_table_label_name": table.first().scenario,
                "result_table_name": table.first().name,
                "result_table_label": table.first().scenario,
                "related_name": table.first().name,
                "related_id": table.first().time_series_group_id,
                "extend_fields": {"bk_data_id": table.first().bk_data_id},
            }
        create_params.update(extra_params)
        new_metric = MetricListCache(**create_params)
        new_metric.save()
        return GetMetricListV2Resource.get_metric_list(
            params["bk_biz_id"], MetricListCache.objects.filter(id=new_metric.id)
        )


class CustomTsGroupingRuleList(Resource):
    """
    获取自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表
        ts_table: CustomTSTable | None = CustomTSTable.objects.filter(
            bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id
        ).first()
        if not ts_table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")
        result: list[dict[str, Any]] = []
        scope_list: list[dict[str, Any]] = ts_table.query_time_series_scope
        for scope_dict in scope_list:
            metric_list: list[dict[str, Any]] = scope_dict.get("metric_list", [])
            result.append(
                {
                    "scope_id": scope_dict["scope_id"],
                    "name": scope_dict["scope_name"],
                    "metric_list": [{"field_id": m["field_id"], "metric_name": m["metric_name"]} for m in metric_list],
                    "auto_rules": scope_dict.get("auto_rules", []),
                    "metric_count": len(metric_list),
                    "create_from": scope_dict["create_from"],
                }
            )
        return result


class ModifyCustomTsGroupingRuleList(Resource):
    """
    修改全量自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))
        group_list = serializers.ListField(label=_("分组列表"), child=CustomTSGroupingRuleSerializer(), default=list)

    def perform_request(self, params: dict):
        # 获取自定义时序表
        table = CustomTSTable.objects.get(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"]
        )
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        group_rules = {}
        for index, group in enumerate(params["group_list"]):
            # 校验分组名称唯一
            if group_rules.get(group["name"]):
                raise CustomValidationLabelError(msg=_("自定义指标分组名{}不可重复").format(group["name"]))

            group["index"] = index
            group_rules[group["name"]] = group

        # 获取存量分组规则
        exist_group_rules = CustomTSGroupingRule.objects.filter(time_series_group_id=params["time_series_group_id"])

        need_update_rules: list[CustomTSGroupingRule] = []
        need_delete_rules: list[CustomTSGroupingRule] = []
        need_create_rules: list[CustomTSGroupingRule] = []
        # 遍历分组规则，判断是否需要更新或删除
        exists_group_rule_names = set()
        for exist_group_rule in exist_group_rules:
            # 记录分组规则名称
            exists_group_rule_names.add(exist_group_rule.name)

            current_group_rule: dict | None = group_rules.get(exist_group_rule.name)
            # 如果分组规则不存在，则删除
            if not current_group_rule:
                need_delete_rules.append(exist_group_rule)
                continue

            # 如果分组规则存在，则判断是否需要更新
            change = False
            if exist_group_rule.manual_list != current_group_rule.get("manual_list", []):
                change = True
            if exist_group_rule.auto_rules != current_group_rule.get("auto_rules", []):
                change = True
            if exist_group_rule.index != current_group_rule["index"]:
                change = True
            if change:
                need_update_rules.append(exist_group_rule)

        # 生成需要创建的分组规则
        for group_rule in group_rules.values():
            if group_rule["name"] not in exists_group_rule_names:
                need_create_rules.append(CustomTSGroupingRule(**group_rule))

        # 执行批量操作
        CustomTSGroupingRule.objects.bulk_create(need_create_rules, batch_size=200)
        CustomTSGroupingRule.objects.filter(id__in=need_delete_rules).delete()
        CustomTSGroupingRule.objects.bulk_update(
            need_update_rules,
            fields=["manual_list", "auto_rules"],
            batch_size=200,
        )

        # 分组匹配现存指标
        table.renew_metric_labels(need_update_rules + need_create_rules, delete=False, clean=True)

        return resource.custom_report.custom_ts_grouping_rule_list(time_series_group_id=params["time_series_group_id"])


class CreateOrUpdateGroupingRule(Resource):
    """
    更新自定义指标分组规则
    """

    class RequestSerializer(CustomTSGroupingRuleSerializer):
        class MetricSerializer(serializers.Serializer):
            field_id = serializers.IntegerField(label=_("指标 ID"))
            metric_name = serializers.CharField(label=_("指标名称"))

        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))
        metric_list = serializers.ListField(label=_("指标列表"), child=MetricSerializer(), required=False)

    def perform_request(self, params: dict):
        bk_biz_id = params["bk_biz_id"]
        time_series_group_id = params["time_series_group_id"]
        # 获取自定义时序表
        ts_table: CustomTSTable = CustomTSTable.objects.get(
            bk_biz_id=bk_biz_id, time_series_group_id=time_series_group_id
        )
        if not ts_table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")
        request_scope_id: int | None = params.get("scope_id")
        request_scope_dict: dict[str, Any] = {}
        if request_scope_id is not None:
            request_scope_dict["scope_id"] = request_scope_id

        request_scope_dict["scope_name"] = params["name"]
        request_scope_dict["auto_rules"] = params["auto_rules"]

        scope_id = api.metadata.create_or_update_time_series_scope(
            group_id=time_series_group_id, scopes=[request_scope_dict]
        )[0]["scope_id"]

        scope_dict = api.metadata.query_time_series_scope(group_id=time_series_group_id, scope_id=scope_id)[0]

        origin_field_ids: set[int] = {metric_dict["field_id"] for metric_dict in scope_dict["metric_list"]}
        update_field_ids: set[int] = {metric_dict["field_id"] for metric_dict in params["metric_list"]}
        remove_field_ids: set[int] = origin_field_ids - update_field_ids
        update_field_ids: set[int] = update_field_ids - origin_field_ids
        metrics: list[dict[str, Any]] = []
        for field_id in remove_field_ids:
            metrics.append(
                {
                    "field_id": field_id,
                    "scope_name": UNGROUP_SCOPE_NAME,
                }
            )
        for field_id in update_field_ids:
            metrics.append({"field_id": field_id, "scope_name": scope_dict["scope_name"]})
        api.metadata.create_or_update_time_series_metric(group_id=time_series_group_id, metrics=metrics)
        scope_dict = api.metadata.query_time_series_scope(group_id=time_series_group_id, scope_id=scope_id)[0]

        return {
            "time_series_group_id": scope_dict["group_id"],
            "scope_id": scope_dict["scope_id"],
            "name": scope_dict["scope_name"],
            "dimension_config": scope_dict["dimension_config"],
            "auto_rules": scope_dict["auto_rules"],
            "metric_list": MetricSerializer(scope_dict["metric_list"], many=True).data,
            "create_from": scope_dict["create_from"],
        }


class PreviewGroupingRule(Resource):
    """
    预览自定义指标分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))
        auto_rules = serializers.ListField(label=_("自动分组的匹配规则列表"), default=list)

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表信息
        ts_table: CustomTSTable = CustomTSTable.objects.filter(
            time_series_group_id=time_series_group_id,
            bk_biz_id=bk_biz_id,
        ).first()
        if not ts_table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")

        # 预编译正则表达式
        rule_compile_map: dict[str, re.Pattern] = {rule: re.compile(rule) for rule in params["auto_rules"]}

        scope_list: list[dict[str, Any]] = ts_table.query_time_series_scope
        auto_metrics: dict[str, list[str]] = defaultdict(list)
        for scope_dict in scope_list:
            for metric_dict in scope_dict["metric_list"]:
                if metric_dict.get("field_config", {}).get("disabled"):
                    continue
                metric_name: str = metric_dict["metric_name"]
                for rule, pattern in rule_compile_map.items():
                    if pattern.match(metric_name):
                        auto_metrics[rule].append(metric_name)

        return {
            "auto_metrics": [
                {
                    "auto_rule": auto_rule,
                    "metrics": metrics,
                }
                for auto_rule, metrics in auto_metrics.items()
            ],
        }


class DeleteGroupingRule(Resource):
    """
    删除自定义指标分组规则
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))
        name = serializers.CharField(label=_("分组规则名称"))

    def perform_request(self, params: dict):
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表
        table = CustomTSTable.objects.filter(
            time_series_group_id=time_series_group_id,
            bk_biz_id=params["bk_biz_id"],
        ).first()
        if not table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")
        api.metadata.delete_time_series_scope(group_id=time_series_group_id, scopes=[{"scope_name": params["name"]}])


class UpdateGroupingRuleOrder(Resource):
    """
    更新自定义指标分组规则排序
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))
        group_names = serializers.ListField(required=True, label=_("分组规则名称列表"))

    def perform_request(self, params: dict):
        # 获取自定义时序表
        table = CustomTSTable.objects.get(
            time_series_group_id=params["time_series_group_id"],
            bk_biz_id=params["bk_biz_id"],
        )
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 获取分组规则
        group_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=params["time_series_group_id"],
        ).order_by("index")

        exists_group_rules = {group_rule.name: group_rule for group_rule in group_rules}

        # 去除不存在的分组
        group_names = [group_name for group_name in params["group_names"] if group_name in exists_group_rules]

        # 未出现的分组
        no_order_group_rules = [group_rule.name for group_rule in group_rules if group_rule.name not in group_names]

        index = 0

        # 更新分组规则排序
        for group_name in group_names:
            exists_group_rules[group_name].index = index
            index += 1

        # 未出现的分组，排序为最后
        for group_name in no_order_group_rules:
            exists_group_rules[group_name].index = index
            index += 1

        # 批量更新分组规则排序
        CustomTSGroupingRule.objects.bulk_update(
            list(exists_group_rules.values()),
            fields=["index"],
            batch_size=200,
        )


class ImportCustomTimeSeriesFields(Resource):
    """
    导入自定义时序字段信息
    """

    class RequestSerializer(serializers.Serializer):
        FieldSerializer = ModifyCustomTsFields.RequestSerializer.FieldSerializer
        bk_biz_id = serializers.IntegerField(label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(label=_("自定义时序 ID"))
        scopes = serializers.ListField(label=_("分组列表"), child=CustomTSScopeSerializer())
        dimensions = serializers.ListField(label=_("维度列表"), child=FieldSerializer())
        metrics = serializers.ListField(label=_("指标列表"), child=FieldSerializer())

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表
        ts_table = CustomTSTable.objects.get(
            time_series_group_id=time_series_group_id,
            bk_biz_id=bk_biz_id,
        )
        if not ts_table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")
        # 导入分组规则
        for scope_dict in params["scopes"]:
            resource.custom_report.create_or_update_grouping_rule(
                bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"], **scope_dict
            )

        # 导入字段信息
        resource.custom_report.modify_custom_ts_fields(
            bk_biz_id=bk_biz_id,
            time_series_group_id=time_series_group_id,
            update_fields=[*params["dimensions"], *params["metrics"]],
        )


class ExportCustomTimeSeriesFields(Resource):
    """
    导出自定义时序字段信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label=_("业务 ID"))
        time_series_group_id = serializers.IntegerField(required=True, label=_("自定义时序 ID"))

    def perform_request(self, params: dict):
        bk_biz_id: int = params["bk_biz_id"]
        time_series_group_id: int = params["time_series_group_id"]
        # 获取自定义时序表
        ts_table: CustomTSTable | None = CustomTSTable.objects.filter(
            time_series_group_id=time_series_group_id,
            bk_biz_id=bk_biz_id,
        ).first()
        if not ts_table:
            raise ValidationError(f"custom time series table not found, time_series_group_id: {time_series_group_id}")
        result = {"scopes": ts_table.query_time_series_scope}
        return result


class GetCustomTimeSeriesLatestDataByFields(Resource):
    """
    查询自定义时序数据最新的一条数据
    """

    class RequestSerializer(serializers.Serializer):
        result_table_id = serializers.CharField(required=True, label="结果表ID")
        metric_list = serializers.ListField(label=_("指标列表"), child=MetricSerializer(), default=[])

    def perform_request(self, validated_request_data):
        # TODO: 修改响应格式
        result_table_id = validated_request_data["result_table_id"]
        fields_list = [str(i) for i in validated_request_data["metric_list"]]

        result = {}
        field_values, latest_time = self.get_latest_data(table_id=result_table_id, fields_list=fields_list)
        result["fields_value"] = field_values
        result["last_time"] = latest_time
        result["table_id"] = result_table_id
        return result

    @classmethod
    def get_latest_data(cls, table_id, fields_list):
        if not fields_list:
            return {}, None

        now_timestamp = int(time.time())
        data = api.unify_query.query_data_by_table(
            table_id=table_id,
            keys=fields_list,
            start_time=now_timestamp - 300,
            end_time=now_timestamp,
            limit=1,
            slimit=0,
        )

        result = {}
        latest_time = ""

        if data["series"]:
            for row in data["series"]:
                for point in row["values"]:
                    for key, value in zip(row["columns"], point):
                        if key == "time" or key in result or value is None:
                            continue

                        if key in ["value", "metric_value"] and row["metric_name"]:
                            result[row["metric_name"]] = value
                            continue

                        result[key] = value

                for key, value in zip(row["group_keys"], row["group_values"]):
                    if key in result or value is None:
                        continue
                    result[key] = value

                if row["values"]:
                    time_value = row["values"][-1][0]
                    if latest_time < time_value:
                        latest_time = time_value

        if latest_time:
            latest_time = arrow.get(latest_time).timestamp
        else:
            latest_time = None
        return result, latest_time


class ModifyCustomTimeSeriesDesc(Resource):
    """
    修改自定义时序描述信息
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        desc = serializers.CharField(max_length=1024, default="", label="描述信息")

    class ResponseSerializer(serializers.ModelSerializer):
        class Meta:
            model = CustomTSTable
            fields = "__all__"

    def perform_request(self, validated_request_data):
        ts_table = CustomTSTable.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        ).first()
        if not ts_table:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        ts_table.desc = validated_request_data["desc"]
        ts_table.save()
        return ts_table

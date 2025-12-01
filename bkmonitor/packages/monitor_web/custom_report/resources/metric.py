import copy
import logging
import re
from collections import defaultdict
from functools import reduce

from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Max, Q
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkmonitor.models import MetricListCache, QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request_tenant_id, get_request_username
from bkmonitor.utils.user import get_admin_username
from constants.data_source import DataSourceLabel, DataTypeLabel, MetricType
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from core.errors.custom_report import (
    CustomValidationLabelError,
    CustomValidationNameError,
)
from monitor_web.constants import ETL_CONFIG
from monitor_web.custom_report.serializers import (
    CustomTSGroupingRuleSerializer,
    CustomTSTableSerializer,
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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, max_length=128, label="名称")
        scenario = serializers.CharField(required=True, label="对象")
        table_id = serializers.CharField(required=False, label="表名", default="")
        metric_info_list = serializers.ListField(required=False, default=[], label="预定义表结构")
        is_platform = serializers.BooleanField(required=False, label="平台级", default=False)
        data_label = serializers.CharField(required=True, label="数据标签")
        protocol = serializers.CharField(required=False, label="上报协议", default="json")
        desc = serializers.CharField(required=False, label="说明", default="", allow_blank=True)
        is_split_measurement = serializers.BooleanField(required=False, label="是否启动自动分表逻辑", default=True)

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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

        name = serializers.CharField(required=False, max_length=128, label="名称")
        is_platform = serializers.BooleanField(required=False, label="平台级")
        data_label = serializers.CharField(required=False, label="数据标签")
        desc = serializers.CharField(required=False, label="说明", allow_blank=True)
        auto_discover = serializers.BooleanField(required=False, label="自动发现")

        class MetricListSerializer(serializers.Serializer):
            class FieldSerializer(serializers.Serializer):
                unit = serializers.CharField(required=True, label="字段单位", allow_blank=True)
                name = serializers.CharField(required=True, label="字段名")
                description = serializers.CharField(required=True, label="字段描述", allow_blank=True)
                monitor_type = serializers.CharField(required=True, label="字段类型，指标或维度")

            fields = FieldSerializer(required=True, label="字段信息", many=True)

        # 向前兼容字段，后续页面不再使用
        metric_json = serializers.ListField(label="指标配置", child=MetricListSerializer(), required=False)

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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

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
        bk_biz_id = serializers.IntegerField(label="业务ID", default=0)
        search_key = serializers.CharField(label="名称", required=False)
        page_size = serializers.IntegerField(default=10, label="获取的条数")
        page = serializers.IntegerField(default=1, label="页数")
        # 新增参数用以判定是否需要查询平台级 dataid
        is_platform = serializers.BooleanField(required=False)

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
        bk_biz_id = serializers.IntegerField(required=True)
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        model_only = serializers.BooleanField(required=False, default=False, label="是否只查询自定义时序表信息")
        with_target = serializers.BooleanField(required=False, default=False, label="是否查询target")
        with_metrics = serializers.BooleanField(required=False, default=True, label="是否查询指标信息")
        empty_if_not_found = serializers.BooleanField(
            required=False, default=False, label="如果自定义时序表不存在，是否返回空数据"
        )

    def perform_request(self, params):
        # 获取自定义时序表信息
        config = CustomTSTable.objects.filter(bk_biz_id=params["bk_biz_id"], pk=params["time_series_group_id"]).first()
        if not config:
            # 如果自定义时序表不存在，则返回空数据
            if params.get("empty_if_not_found"):
                return {}
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 如果是平台自定义时序，则需要校验业务是否匹配
        if not config.is_platform and config.bk_biz_id != params["bk_biz_id"]:
            raise ValidationError(f"custom time series not found, bk_biz_id: {params['bk_biz_id']}")

        # 序列化自定义时序表信息
        data = CustomTSTableSerializer(config, context={"request_bk_biz_id": params["bk_biz_id"]}).data

        # 如果只查询自定义时序表信息，则直接返回
        if params.get("model_only"):
            return data

        data["scenario_display"] = get_label_display_dict().get(data["scenario"], [data["scenario"]])
        data["access_token"] = config.token

        # 如果需要查询指标信息，则将指标信息写入到metric_json中
        if params.get("with_metrics"):
            metrics = copy.deepcopy(config.get_metrics())
            data["metric_json"] = [{"fields": list(metrics.values())}]
        else:
            data["metric_json"] = []

        # 新增查询target参数，自定义指标详情页面不需要target，默认不查询
        if params.get("with_target"):
            data["target"] = config.query_target(bk_biz_id=params["bk_biz_id"])
        else:
            data["target"] = []
        return data


class GetCustomTsFields(Resource):
    """
    获取自定义指标字段
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, params: dict):
        table = CustomTSTable.objects.filter(
            bk_biz_id=params["bk_biz_id"],
            time_series_group_id=params["time_series_group_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {params['bk_biz_id']}, "
                f"time_series_group_id: {params['time_series_group_id']}"
            )

        dimensions = []
        metrics = []
        for item in CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id):
            if item.type == MetricType.DIMENSION:
                dimensions.append(
                    {
                        "name": item.name,
                        "type": MetricType.DIMENSION,
                        "description": item.description,
                        "disabled": item.disabled,
                        "hidden": item.config.get("hidden", False),
                        "common": item.config.get("common", False),
                        "create_time": item.create_time.timestamp() if item.create_time else None,
                        "update_time": item.update_time.timestamp() if item.update_time else None,
                    }
                )
            else:
                metrics.append(
                    {
                        "name": item.name,
                        "type": MetricType.METRIC,
                        "description": item.description,
                        "disabled": item.disabled,
                        "unit": item.config.get("unit", ""),
                        "hidden": item.config.get("hidden", False),
                        "aggregate_method": item.config.get("aggregate_method", ""),
                        "function": item.config.get("function", {}),
                        "interval": item.config.get("interval", 0),
                        "label": item.config.get("label", []),
                        "dimensions": item.config.get("dimensions", []),
                        "create_time": item.create_time.timestamp() if item.create_time else None,
                        "update_time": item.update_time.timestamp() if item.update_time else None,
                    }
                )
        return {"dimensions": dimensions, "metrics": metrics}


class ModifyCustomTsFields(Resource):
    """
    修改自定义指标字段
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

        class FieldSerializer(serializers.Serializer):
            name = serializers.CharField(required=True, label="字段名")
            type = serializers.CharField(required=True, label="字段类型")
            description = serializers.CharField(required=False, label="字段描述", allow_blank=True)
            disabled = serializers.BooleanField(required=False, label="是否禁用")

            # 维度属性
            common = serializers.BooleanField(required=False, label="是否常用字段")

            # 指标属性
            unit = serializers.CharField(required=False, label="字段单位", allow_blank=True)
            hidden = serializers.BooleanField(required=False, label="是否隐藏")
            aggregate_method = serializers.CharField(required=False, label="聚合方法", allow_blank=True)
            function = serializers.JSONField(required=False, label="指标函数")
            interval = serializers.IntegerField(required=False, label="指标周期")

        update_fields = serializers.ListField(label="更新字段列表", child=FieldSerializer(), default=list)
        delete_fields = serializers.ListField(label="删除字段列表", child=FieldSerializer(), default=list)

    def perform_request(self, params: dict):
        table = CustomTSTable.objects.filter(
            bk_biz_id=params["bk_biz_id"],
            time_series_group_id=params["time_series_group_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {params['bk_biz_id']}, "
                f"time_series_group_id: {params['time_series_group_id']}"
            )

        # 删除字段
        if params["delete_fields"]:
            CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id).filter(
                reduce(
                    lambda x, y: x | y, (Q(name=field["name"], type=field["type"]) for field in params["delete_fields"])
                )
            ).delete()

        if not params["update_fields"]:
            return

        # 获取存量字段
        fields = CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id).filter(
            reduce(lambda x, y: x | y, (Q(name=field["name"], type=field["type"]) for field in params["update_fields"]))
        )
        field_map = {(item.name, item.type): item for item in fields}

        # 需要更新的字段
        need_update_fields = []
        # 需要创建的字段
        need_create_fields = []
        for update_field in params["update_fields"]:
            field = field_map.get((update_field["name"], update_field["type"]))

            # 根据字段类型，生成 config
            if update_field["type"] == MetricType.DIMENSION:
                field_keys = CustomTSField.DimensionConfigFields
            else:
                field_keys = CustomTSField.MetricConfigFields
            field_config = {field_key: update_field[field_key] for field_key in field_keys if field_key in update_field}

            # 如果字段存在，则更新字段
            if field:
                field.config.update(field_config)
                if "description" in update_field:
                    field.description = update_field["description"]
                if "disabled" in update_field:
                    field.disabled = update_field["disabled"]
                need_update_fields.append(field)
            else:
                # 如果字段不存在，则创建字段
                need_create_fields.append(
                    CustomTSField(
                        time_series_group_id=table.time_series_group_id,
                        type=update_field["type"],
                        name=update_field["name"],
                        description=update_field.get("description", ""),
                        disabled=update_field.get("disabled", False),
                        config=field_config,
                    )
                )

        # 批量创建字段
        CustomTSField.objects.bulk_create(need_create_fields, batch_size=500)
        # 批量更新字段
        CustomTSField.objects.bulk_update(need_update_fields, ["description", "disabled", "config"], batch_size=500)

        # 同步metadata
        table.save_to_metadata(with_fields=True)


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
        metric_field = serializers.CharField(required=True, label="指标名")
        result_table_id = serializers.CharField(required=True, label="结果表ID")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, params: dict):
        # 获取自定义时序表
        table = CustomTSTable.objects.get(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"]
        )
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 获取指标信息
        metrics = CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id, type=MetricType.METRIC)
        # 分组计数
        group_metric_count = defaultdict(int)
        for metric in metrics:
            for group in metric.config.get("label", []):
                group_metric_count[group] += 1

        # 获取分组规则
        grouping_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=params["time_series_group_id"]
        ).order_by("index")
        result = CustomTSGroupingRuleSerializer(grouping_rules, many=True).data
        for rule in result:
            rule["metric_count"] = group_metric_count[rule["name"]]
        return result


class ModifyCustomTsGroupingRuleList(Resource):
    """
    修改全量自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        group_list = serializers.ListField(label="分组列表", child=CustomTSGroupingRuleSerializer(), default=list)

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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, params: dict):
        # 获取自定义时序表
        table = CustomTSTable.objects.get(
            bk_biz_id=params["bk_biz_id"], time_series_group_id=params["time_series_group_id"]
        )
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 获取分组规则
        group_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=params["time_series_group_id"],
            name=params["name"],
        )

        with atomic():
            if not group_rules:
                # 获取当前分组规则index最大值
                max_index = (
                    CustomTSGroupingRule.objects.filter(time_series_group_id=params["time_series_group_id"]).aggregate(
                        Max("index")
                    )["index__max"]
                    or 0
                )
                params["index"] = max_index + 1
                # 创建分组规则
                grouping_rule = CustomTSGroupingRule.objects.create(
                    time_series_group_id=params["time_series_group_id"],
                    name=params["name"],
                    manual_list=params["manual_list"],
                    auto_rules=params["auto_rules"],
                    index=params["index"],
                )
            else:
                grouping_rule = group_rules[0]
                # 更新分组信息
                if params.get("manual_list"):
                    grouping_rule.manual_list = params["manual_list"]
                if params.get("auto_rules"):
                    grouping_rule.auto_rules = params["auto_rules"]
                grouping_rule.save()

            # 分组匹配现存指标
            table.renew_metric_labels([grouping_rule], delete=False)

        return grouping_rule.to_json()


class PreviewGroupingRule(Resource):
    """
    预览自定义指标分组
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        manual_list = serializers.ListField(label="手动分组的指标列表", default=list)
        auto_rules = serializers.ListField(label="自动分组的匹配规则列表", default=list)

    def perform_request(self, params: dict):
        # 获取自定义时序表信息
        table = CustomTSTable.objects.filter(
            time_series_group_id=params["time_series_group_id"],
            bk_biz_id=params["bk_biz_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 获取指标信息
        metrics = CustomTSField.objects.filter(time_series_group_id=table.time_series_group_id, type=MetricType.METRIC)

        manual_metrics = []
        auto_metrics = defaultdict(list)
        for metric in metrics:
            if metric.name in params["manual_list"]:
                manual_metrics.append(metric.name)

            for auto_rule in params["auto_rules"]:
                if re.match(auto_rule, metric.name):
                    auto_metrics[auto_rule].append(metric.name)

        return {
            "manual_metrics": manual_metrics,
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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        name = serializers.CharField(required=True, label="分组规则名称")

    def perform_request(self, params: dict):
        # 获取自定义时序表
        table = CustomTSTable.objects.filter(
            time_series_group_id=params["time_series_group_id"],
            bk_biz_id=params["bk_biz_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )

        # 查询分组规则
        try:
            group_rule = CustomTSGroupingRule.objects.get(
                time_series_group_id=params["time_series_group_id"], name=params["name"]
            )
        except CustomTSGroupingRule.DoesNotExist:
            group_rule = CustomTSGroupingRule(name=params["name"], time_series_group_id=params["time_series_group_id"])

        # 更新指标分组
        table.renew_metric_labels([group_rule], delete=True)

        # 删除分组规则
        if group_rule.id:
            group_rule.delete()


class UpdateGroupingRuleOrder(Resource):
    """
    更新自定义指标分组规则排序
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        group_names = serializers.ListField(required=True, label="分组规则名称列表")

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
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

        group_rules = CustomTSGroupingRuleSerializer(required=True, label="分组列表", many=True, allow_empty=True)
        dimensions = ModifyCustomTsFields.RequestSerializer.FieldSerializer(
            required=True, label="维度列表", many=True, allow_empty=True
        )
        metrics = ModifyCustomTsFields.RequestSerializer.FieldSerializer(
            required=True, label="指标列表", many=True, allow_empty=True
        )

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

        # 导入字段信息
        resource.custom_report.modify_custom_ts_fields(
            bk_biz_id=params["bk_biz_id"],
            time_series_group_id=params["time_series_group_id"],
            update_fields=[*params["dimensions"], *params["metrics"]],
        )

        # 导入分组规则
        for group_rule in params["group_rules"]:
            resource.custom_report.create_or_update_grouping_rule(
                bk_biz_id=params["bk_biz_id"],
                time_series_group_id=params["time_series_group_id"],
                name=group_rule["name"],
                manual_list=group_rule.get("manual_list", []),
                auto_rules=group_rule.get("auto_rules", []),
            )


class ExportCustomTimeSeriesFields(Resource):
    """
    导出自定义时序字段信息
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

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

        # 导出字段信息
        result = resource.custom_report.get_custom_ts_fields(
            bk_biz_id=params["bk_biz_id"],
            time_series_group_id=params["time_series_group_id"],
        )

        # 导出分组规则
        group_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=params["time_series_group_id"],
        )

        result["group_rules"] = CustomTSGroupingRuleSerializer(group_rules, many=True).data
        return result

import copy
import logging
import re
import time
from collections import defaultdict
from functools import reduce
from typing import Dict, Optional

import arrow
from django.conf import settings
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from bkm_space.define import SpaceTypeEnum
from bkm_space.errors import NoRelatedResourceError
from bkmonitor.models import MetricListCache, QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request_username
from constants.data_source import DataSourceLabel, DataTypeLabel
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
    MetricListSerializer,
)
from monitor_web.models.custom_report import (
    CustomTSGroupingRule,
    CustomTSItem,
    CustomTSTable,
)
from monitor_web.plugin.constant import PluginType
from monitor_web.strategies.resources import GetMetricListV2Resource
from monitor_web.tasks import append_custom_ts_metric_list_cache

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
            ValidateCustomTsGroupLabel().request(data_label=attrs["data_label"])
            return attrs

    def data_name(self, bk_biz_id, ts_name):
        return "{}_{}_{}".format(bk_biz_id, self.CUSTOM_TS_NAME, ts_name)

    def table_id(self, bk_biz_id, data_id):
        database_name = "{}_{}_{}".format(bk_biz_id, self.CUSTOM_TS_NAME, data_id)
        return "{}.{}".format(database_name, "base")

    @staticmethod
    def get_data_id(data_name, operator, space_uid=None):
        try:
            data_id_info = api.metadata.get_data_id({"data_name": data_name, "with_rt_info": False})
        except BKAPIError:
            param = {
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
            raise CustomValidationNameError(data=data_id_info["bk_data_id"], msg=_("数据源名称[{}]已存在").format(data_name))
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
        operator = get_request_username() or settings.COMMON_USERNAME

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
            bk_data_id = self.get_data_id(data_name, operator, space_uid)
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
        metric_json = serializers.ListField(label="指标配置", child=MetricListSerializer(), default=[])
        is_platform = serializers.BooleanField(required=False, label="平台级")
        data_label = serializers.CharField(required=False, label="数据标签")
        operator = serializers.CharField(label="操作者", required=False, default="")

        def validate(self, attrs):
            if attrs.get("name"):
                ValidateCustomTsGroupName().request(
                    name=attrs["name"], bk_biz_id=attrs["bk_biz_id"], time_series_group_id=attrs["time_series_group_id"]
                )
            if attrs.get("data_label"):
                ValidateCustomTsGroupLabel().request(
                    data_label=attrs["data_label"], time_series_group_id=attrs["time_series_group_id"]
                )
            return attrs

    @atomic()
    def perform_request(self, validated_request_data):
        operator = get_request_username() or validated_request_data["operator"]
        table = CustomTSTable.objects.filter(
            bk_biz_id=validated_request_data["bk_biz_id"],
            time_series_group_id=validated_request_data["time_series_group_id"],
        ).first()
        if not table:
            raise ValidationError(
                f"custom time series table not found, bk_biz_id: {validated_request_data['bk_biz_id']},"
                f" time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        fields = []
        metric_labels = {}
        for field in validated_request_data["metric_json"][0]["fields"]:
            fields.append(
                {
                    "field_name": field["name"],
                    "tag": field["monitor_type"],
                    "field_type": field["type"],
                    "description": field["description"],
                    "unit": field["unit"],
                }
            )
            if field["monitor_type"] == "metric":
                metric_labels[field["name"]] = field.get("label", [])

        # 更新metadata指标信息
        params = {
            "operator": operator,
            "time_series_group_id": table.time_series_group_id,
            "field_list": fields,
            "time_series_group_name": validated_request_data["name"],
            "label": table.scenario,
            "data_label": validated_request_data["data_label"],
        }
        api.metadata.modify_time_series_group(params)
        table.name = validated_request_data["name"]
        table.is_platform = validated_request_data["is_platform"]
        table.data_label = validated_request_data["data_label"]
        table.save()

        return resource.custom_report.custom_time_series_detail(
            bk_biz_id=validated_request_data["bk_biz_id"], time_series_group_id=table.time_series_group_id
        )


class DeleteCustomTimeSeries(Resource):
    """
    删除自定义时序
    注: esb 开放接口，需要维持入参出参一致性
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    @atomic()
    def perform_request(self, validated_request_data):
        table = CustomTSTable.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        ).first()
        if not table:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )
        operator = get_request_username()
        params = {"operator": operator, "time_series_group_id": table.time_series_group_id}
        api.metadata.delete_time_series_group(params)

        CustomTSItem.objects.filter(table=table).delete()
        table.delete()
        return {"time_series_group_id": validated_request_data["time_series_group_id"]}


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

    @staticmethod
    def get_strategy_count(table_ids, request_bk_biz_id: Optional[int] = None):
        """
        获取绑定的策略数
        """
        if not table_ids:
            return {}

        query_configs = (
            QueryConfigModel.objects.annotate(result_table_id=models.F("config__result_table_id"))
            .filter(
                reduce(lambda x, y: x | y, (Q(result_table_id=table_id) for table_id in table_ids)),
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.TIME_SERIES,
            )
            .values("result_table_id", "strategy_id")
        )

        strategy_ids = []
        if request_bk_biz_id:
            strategy_ids = StrategyModel.objects.filter(bk_biz_id=request_bk_biz_id).values_list("pk", flat=True)

        table_id_strategy_mapping = defaultdict(set)
        for query_config in query_configs:
            # 当存在 biz 请求条件且策略 id 未命中时不纳入统计
            if request_bk_biz_id and query_config["strategy_id"] not in strategy_ids:
                continue

            table_id_strategy_mapping[query_config["result_table_id"]].add(query_config["strategy_id"])

        return {key: len(value) for key, value in table_id_strategy_mapping.items()}

    def perform_request(self, validated_request_data):
        queryset = CustomTSTable.objects.all().order_by("-update_time")
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
        strategy_count_mapping = self.get_strategy_count(table_ids, validated_request_data.get("bk_biz_id"))

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
        model_only = serializers.BooleanField(required=False, default=False)
        with_target = serializers.BooleanField(required=False, default=False)

    def perform_request(self, params):
        config = CustomTSTable.objects.filter(pk=params["time_series_group_id"]).first()
        if not config:
            raise ValidationError(
                f"custom time series table not found, time_series_group_id: {params['time_series_group_id']}"
            )
        if not config.is_platform and config.bk_biz_id != params["bk_biz_id"]:
            raise ValidationError(f"custom time series not found, bk_biz_id: {params['bk_biz_id']}")
        serializer = CustomTSTableSerializer(config, context={"request_bk_biz_id": params["bk_biz_id"]})
        data = serializer.data
        if params.get("model_only"):
            return data
        label_display_dict = get_label_display_dict()
        data["scenario_display"] = label_display_dict.get(data["scenario"], [data["scenario"]])
        data["access_token"] = config.token
        metrics = copy.deepcopy(config.get_metrics())
        data["metric_json"] = [{"fields": list(metrics.values())}]
        data["target"] = []
        # 新增查询target参数，自定义指标详情页面不需要target，默认不查询
        if params.get("with_target"):
            data["target"] = config.query_target(bk_biz_id=params["bk_biz_id"])

        append_custom_ts_metric_list_cache.delay(params["time_series_group_id"])
        return data


class ValidateCustomTsGroupLabel(Resource):
    """
    校验自定义指标数据名称是否合法
    1. 创建场景：调用metadata接口校验是否与存量ResultTable的data_label重复
    2. 编辑场景：除了time_series_group_id参数对应CustomTSTable的data_label外，是否与存量ResultTable的data_label重复
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=False)
        data_label = serializers.CharField(required=True)

    def perform_request(self, validated_request_data):
        data_label = validated_request_data["data_label"].strip()
        data_label_filter_params = {"data_label": data_label}
        data_label_unique_qs = CustomTSTable.objects
        # 获取插件类型前缀列表，自定义指标data_label前缀不可与插件类型data_label前缀重名
        # process采集 复用自定义创建逻辑
        plugin_type_list = [
            f"{getattr(PluginType, attr).lower()}_"
            for attr in dir(PluginType)
            if not callable(getattr(PluginType, attr)) and not attr.startswith("__") and attr != "PROCESS"
        ]
        label_pattern = re.compile(r'^(?!' + '|'.join(plugin_type_list) + r')[a-zA-Z][a-zA-Z0-9_]*$')
        if data_label == "":
            raise CustomValidationLabelError(msg=_("自定义指标英文名不允许为空"))
        if not label_pattern.match(data_label):
            raise CustomValidationLabelError(msg=_("自定义指标英文名仅允许包含字母、数字、下划线，且必须以字母开头，前缀不可与插件类型重名"))
        queryset = data_label_unique_qs.filter(**data_label_filter_params)
        if validated_request_data.get("time_series_group_id"):
            queryset = queryset.exclude(time_series_group_id=validated_request_data["time_series_group_id"])
        is_exist = queryset.exists()
        if is_exist:
            raise CustomValidationLabelError(msg=_("自定义指标英文名已存在"))
        return True


class GetCustomTimeSeriesLatestDataByFields(Resource):
    """
    查询自定义时序数据最新的一条数据
    """

    class RequestSerializer(serializers.Serializer):
        result_table_id = serializers.CharField(required=True, label="结果表ID")
        fields_list = serializers.ListField(label="字段列表", allow_empty=True, default=[])

    def perform_request(self, validated_request_data):
        result_table_id = validated_request_data["result_table_id"]
        fields_list = validated_request_data["fields_list"] or []
        fields_list = [str(i) for i in fields_list]

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


class CustomTsGroupingRuleList(Resource):
    """
    获取自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, validated_request_data):
        grouping_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
        serializer = CustomTSGroupingRuleSerializer(grouping_rules, many=True)
        return serializer.data


class ModifyCustomTsGroupingRuleList(Resource):
    """
    修改全量自定义指标分组规则列表
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        group_list = serializers.ListField(label="分组列表", child=CustomTSGroupingRuleSerializer(), default=[])

    def perform_request(self, validated_request_data):
        # 校验分组名称唯一
        group_names = {}
        for group in validated_request_data["group_list"]:
            if group_names.get(group["name"]):
                raise CustomValidationLabelError(msg=_("自定义指标分组名{}不可重复").format(group['name']))
            group_names[group["name"]] = group

        # 清除残余分组记录
        grouping_rules = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
        grouping_rules.exclude(name__in=list(group_names.keys())).delete()

        # 更新已存在的分组
        for grouping_rule in grouping_rules:
            should_save = False
            new_grouping_rule = group_names.pop(grouping_rule.name, {})
            if grouping_rule.manual_list != new_grouping_rule.get("manual_list", []):
                grouping_rule.manual_list = new_grouping_rule.get("manual_list", [])
                should_save = True
            if grouping_rule.auto_rules != new_grouping_rule.get("auto_rules", []):
                grouping_rule.auto_rules = new_grouping_rule.get("auto_rules", [])
                should_save = True

            if should_save:
                grouping_rule.save()
        # 创建不存在的分组
        CustomTSGroupingRule.objects.bulk_create(
            [
                CustomTSGroupingRule(time_series_group_id=validated_request_data["time_series_group_id"], **grouping)
                for _, grouping in group_names.items()
            ],
            batch_size=200,
        )
        return resource.custom_report.group_custom_ts_item(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )


class CreateOrUpdateGroupingRule(Resource):
    """
    更新自定义指标分组规则
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        name = serializers.CharField(required=True, label="分组名称")
        manual_list = serializers.ListField(required=False, label="手动分组的指标列表")
        auto_rules = serializers.ListField(required=False, label="自动分组的匹配规则列表")

    def perform_request(self, validated_request_data):
        # 校验分组名称
        group_names = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        ).values_list("name", flat=True)
        group_name = validated_request_data["name"]
        if group_name not in group_names:
            # 创建分组规则
            grouping_rule = CustomTSGroupingRule.objects.create(**validated_request_data)
        else:
            # 更新分组信息
            grouping_rule = CustomTSGroupingRule.objects.get(name=group_name)
            if validated_request_data.get("manual_list"):
                grouping_rule.manual_list = validated_request_data["manual_list"]
            if validated_request_data.get("auto_rules"):
                grouping_rule.manual_list = validated_request_data["auto_rules"]
            grouping_rule.save()
        return grouping_rule.to_json()


class GroupCustomTSItem(Resource):
    """
    分组匹配自定义时序指标
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")

    def perform_request(self, validated_request_data):
        # 分组匹配现存指标
        groups = CustomTSGroupingRule.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )
        metrics = CustomTSItem.objects.filter(table_id=validated_request_data["time_series_group_id"])
        for metric in metrics:
            metric_labels = set()
            for group in groups:
                if metric.metric_name in group.manual_list:
                    metric_labels.add(group.name)
                for rule in group.auto_rules:
                    if re.search(rule, metric.metric_name):
                        metric_labels.add(group.name)
            if metric.label == list(metric_labels):
                continue
            metric.label = list(metric_labels)
            metric.save()

        return resource.custom_report.custom_ts_grouping_rule_list(
            time_series_group_id=validated_request_data["time_series_group_id"]
        )


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

    def perform_request(self, validated_request_data):
        # 查询该任务是否已有执行任务
        table = CustomTSTable.objects.filter(table_id__startswith=validated_request_data['result_table_id'])
        if not table.exists():
            table = CustomTSTable.objects.filter(data_label=validated_request_data['result_table_id'])
            if not table.exists():
                raise ValidationError(f"结果表或datalabel({validated_request_data['result_table_id']})不存在")
        # 手动添加的自定义指标metric_md5特殊处理为0
        filter_params = {
            "data_source_label": DataSourceLabel.CUSTOM,
            "data_type_label": DataTypeLabel.TIME_SERIES,
            "bk_biz_id": validated_request_data["bk_biz_id"],
            "result_table_id": table.first().table_id,
        }
        metric_list = MetricListCache.objects.filter(**filter_params)
        if metric_list.filter(metric_field=validated_request_data["metric_field"]).exists():
            raise ValidationError(
                f"指标({validated_request_data['result_table_id']}." f"{validated_request_data['metric_field']})已存在"
            )
        create_params = {
            "metric_field": validated_request_data["metric_field"],
            "metric_field_name": validated_request_data["metric_field"],
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
            validated_request_data["bk_biz_id"], MetricListCache.objects.filter(id=new_metric.id)
        )


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

    @atomic()
    def perform_request(self, validated_request_data):
        time_series_obj = CustomTSTable.objects.filter(
            time_series_group_id=validated_request_data["time_series_group_id"]
        ).first()
        if not time_series_obj:
            raise ValidationError(
                "custom time series table not found, "
                f"time_series_group_id: {validated_request_data['time_series_group_id']}"
            )

        time_series_obj.desc = validated_request_data["desc"]
        time_series_obj.save()
        return time_series_obj


class PreviewCustomMetricGroup(Resource):
    """
    预览自定义指标分组
    """

    class RequestSerializer(serializers.Serializer):
        time_series_group_id = serializers.IntegerField(required=True, label="自定义时序ID")
        manual_list = serializers.ListField(required=False, label="手动分组的指标列表")
        auto_rules = serializers.ListField(required=False, label="自动分组的匹配规则列表")

    def perform_request(self, params: Dict):
        """
        TODO: 预览自定义指标分组
        """
        return []

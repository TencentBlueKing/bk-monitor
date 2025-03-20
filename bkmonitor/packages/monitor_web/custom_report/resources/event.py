import logging
import re
from collections import defaultdict
from functools import reduce
from typing import Dict, Optional

from django.conf import settings
from django.core.paginator import Paginator
from django.db import models, transaction
from django.db.models import Q
from django.db.transaction import atomic
from django.utils.translation import gettext as _
from rest_framework import serializers

from bkmonitor.data_source import load_data_source
from bkmonitor.models import QueryConfigModel, StrategyModel
from bkmonitor.utils.request import get_request_username
from bkmonitor.utils.time_tools import date_convert, parse_time_range
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import api, resource
from core.drf_resource.base import Resource
from core.errors.api import BKAPIError
from core.errors.custom_report import (
    CustomEventValidationError,
    CustomValidationLabelError,
    CustomValidationNameError,
)
from monitor_web.constants import ETL_CONFIG, EVENT_TYPE
from monitor_web.custom_report.serializers import (
    CustomEventGroupDetailSerializer,
    CustomEventGroupSerializer,
    EventInfoSerializer,
)
from monitor_web.models.custom_report import CustomEventGroup, CustomEventItem

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


class ValidateCustomEventGroupName(Resource):
    """
    校验自定义事件名称是否合法
    """

    class RequestSerializer(serializers.Serializer):
        bk_event_group_id = serializers.IntegerField(required=False)
        name = serializers.CharField(required=True)
        bk_biz_id = serializers.IntegerField(required=True)

    def perform_request(self, validated_request_data):
        try:
            event_groups = api.metadata.query_event_group(
                event_group_name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("bk_event_group_id"):
                event_groups = [
                    g for g in event_groups if g["event_group_id"] != validated_request_data["bk_event_group_id"]
                ]
            is_exist = bool(event_groups)
        except Exception:
            # 如果接口调用失败，则使用 SaaS 配置，作为补偿机制
            queryset = CustomEventGroup.objects.filter(
                name=validated_request_data["name"], bk_biz_id=validated_request_data["bk_biz_id"]
            )
            if validated_request_data.get("bk_event_group_id"):
                queryset = queryset.exclude(bk_event_group_id=validated_request_data["bk_event_group_id"])
            is_exist = queryset.exists()
        if is_exist:
            raise CustomValidationNameError(msg=_("自定义事件名称已存在"))
        return True


class ValidateCustomEventGroupLabel(Resource):
    """
    校验自定义事件数据标签是否合法
    1. 创建场景：调用metadata接口校验是否与存量ResultTable的data_label重复
    2. 编辑场景：除了bk_event_group_id参数对应CustomEventGroup的data_label外，是否与存量ResultTable的data_label重复
    """

    class RequestSerializer(serializers.Serializer):
        bk_event_group_id = serializers.IntegerField(required=False)
        data_label = serializers.CharField(required=True)

    def perform_request(self, validated_request_data):
        data_label = validated_request_data["data_label"].strip()
        data_label_filter_params = {"data_label": data_label}
        data_label_unique_qs = CustomEventGroup.objects
        label_pattern = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
        if data_label == "":
            raise CustomValidationLabelError(msg=_("自定义事件英文名不允许为空"))
        if not label_pattern.match(data_label):
            raise CustomValidationLabelError(msg=_("自定义事件英文名允许包含字母、数字、下划线，且必须以字母开头"))
        queryset = data_label_unique_qs.filter(**data_label_filter_params)
        if validated_request_data.get("bk_event_group_id"):
            queryset = queryset.exclude(bk_event_group_id=validated_request_data["bk_event_group_id"])
        is_exist = queryset.exists()
        if is_exist:
            raise CustomValidationLabelError(msg=_("自定义事件英文名已存在"))
        return True


class QueryCustomEventGroup(Resource):
    """
    自定义事件列表
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", default=0)
        search_key = serializers.CharField(label="名称", required=False)
        page_size = serializers.IntegerField(default=10, label="获取的条数")
        page = serializers.IntegerField(default=1, label="页数")
        is_platform = serializers.BooleanField(required=False)
        table_id = serializers.CharField(label="结果表 ID", required=False)

    @classmethod
    def get_strategy_count_for_each_group(cls, table_ids, request_bk_biz_id: Optional[int] = None):
        """
        获取事件分组绑定的策略数
        """
        if not table_ids:
            return {}

        query_configs = (
            QueryConfigModel.objects.annotate(result_table_id=models.F("config__result_table_id"))
            .filter(
                reduce(lambda x, y: x | y, (Q(result_table_id=table_id) for table_id in table_ids)),
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.EVENT,
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
        queryset = CustomEventGroup.objects.filter(type=EVENT_TYPE.CUSTOM_EVENT).order_by("-update_time")
        context = {"request_bk_biz_id": validated_request_data["bk_biz_id"]}

        if validated_request_data.get("table_id"):
            # 1）单 Table ID 查询场景
            queryset = queryset.filter(table_id=validated_request_data["table_id"]).filter(
                Q(bk_biz_id=validated_request_data.get("bk_biz_id", 0)) | Q(is_platform=True)
            )
        elif validated_request_data.get("is_platform"):
            # 2）只查全平台, 不关注业务
            queryset = queryset.filter(is_platform=True)

        elif validated_request_data.get("bk_biz_id"):
            # 3）非全平台，查当前业务(0表示全部业务)
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
        serializer = CustomEventGroupSerializer(
            paginator.page(validated_request_data["page"]), many=True, context=context
        )
        groups = serializer.data

        table_ids = [group["table_id"] for group in groups]
        strategy_count_mapping = self.get_strategy_count_for_each_group(
            table_ids, validated_request_data.get("bk_biz_id")
        )

        label_display_dict = get_label_display_dict()
        for group in groups:
            group["scenario_display"] = label_display_dict.get(group["scenario"], [group["scenario"]])
            group["related_strategy_count"] = strategy_count_mapping.get(group["table_id"], 0)
        return {
            "list": groups,
            "total": queryset.count(),
        }


class GetCustomEventGroup(Resource):
    """
    获取单个自定义事件详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_event_group_id = serializers.IntegerField(required=True, label="事件分组ID")
        time_range = serializers.CharField(required=True, label="时间范围")
        need_refresh = serializers.BooleanField(required=False, label="是否需要实时刷新", default=False)
        bk_biz_id = serializers.IntegerField(required=True)
        event_infos_limit = serializers.IntegerField(required=False, default=1000, label="事件信息列表上限")

    def perform_request(self, validated_request_data):
        event_group_id = validated_request_data["bk_event_group_id"]
        need_refresh = validated_request_data["need_refresh"]
        event_infos_limit = validated_request_data["event_infos_limit"]
        # 用户页面主动请求相关逻辑，不应该插入耗时过长的逻辑。
        # append_event_metric_list_cache(event_group_id)
        config = CustomEventGroup.objects.prefetch_related("event_info_list").get(pk=event_group_id)
        serializer = CustomEventGroupDetailSerializer(
            config, context={"request_bk_biz_id": validated_request_data["bk_biz_id"]}
        )
        data = serializer.data
        event_info_list = api.metadata.get_event_group.request.refresh(
            event_group_id=event_group_id, need_refresh=need_refresh, event_infos_limit=event_infos_limit
        )
        data["event_info_list"] = list()

        # 如果自定义事件有人访问，则结束休眠策略
        username = get_request_username()
        if event_info_list.get("status") == "sleep":
            try:
                api.metadata.modify_event_group({"event_group_id": event_group_id, "operator": username})
            except BKAPIError:
                pass

        # 查询事件关联策略ID
        related_query_configs = (
            QueryConfigModel.objects.filter(
                data_source_label=DataSourceLabel.CUSTOM,
                data_type_label=DataTypeLabel.EVENT,
                config__result_table_id=data["table_id"],
            )
            .values("strategy_id")
            .annotate(custom_event_name=models.F("config__custom_event_name"))
        )
        related_strategies = defaultdict(set)
        for query_config in related_query_configs:
            related_strategies[query_config["custom_event_name"]].add(query_config["strategy_id"])

        for item in event_info_list["event_info_list"]:
            event_info = {
                "custom_event_name": item["event_name"],
                "bk_event_group_id": event_info_list["event_group_id"],
                "custom_event_id": item["event_id"],
                "related_strategies": list(related_strategies[item["event_name"]]),
                "dimension_list": [{"dimension_name": dimension} for dimension in item["dimension_list"]],
            }
            data["event_info_list"].append(event_info)

        label_display_dict = get_label_display_dict()
        data["scenario_display"] = label_display_dict.get(data["scenario"], [data["scenario"]])
        data["access_token"] = self.get_token(data["bk_data_id"])

        event_detail = self.query_event_detail(data["table_id"], validated_request_data["time_range"])
        for event in data["event_info_list"]:
            event.update(event_detail[event["custom_event_name"]])
        return data

    @staticmethod
    def get_token(bk_data_id):
        data_id_info = api.metadata.get_data_id({"bk_data_id": bk_data_id, "with_rt_info": False})
        return data_id_info["token"]

    @staticmethod
    def query_event_detail(result_table_id, time_range) -> Dict[str, Dict]:
        result = defaultdict(
            lambda: {
                "event_count": 0,
                "target_count": 0,
                "last_change_time": "",
                "last_event_content": {},
            }
        )
        start, end = parse_time_range(time_range)
        data_source = load_data_source(DataSourceLabel.CUSTOM, DataTypeLabel.EVENT)(table=result_table_id)
        q = data_source._get_queryset(
            metrics=[
                {"field": "target", "method": "distinct", "alias": "target_count"},
                {"field": "time", "method": "max", "alias": "last_change_timestamp"},
            ],
            table=data_source.table,
            group_by=["event_name"],
            where=data_source.filter_dict,
            time_field=data_source.time_field,
            start_time=start * 1000,
            end_time=end * 1000,
            interval=end - start,
            time_align=False,
        ).dsl_group_hits(1)

        for record in q.raw_data:
            result[record["event_name"]]["event_count"] += record.get("hits_total", 0)
            result[record["event_name"]]["target_count"] = max(
                record["target_count"], result[record["event_name"]]["target_count"]
            )
            result[record["event_name"]]["last_change_time"] = date_convert(
                int(record["last_change_timestamp"] // 1000), "datetime"
            )
            hits = record.get("hits", [])
            if hits:
                result[record["event_name"]]["last_event_content"] = hits[0]

        return result


class QueryCustomEventTarget(Resource):
    """
    获取单个自定义事件详情
    """

    class RequestSerializer(serializers.Serializer):
        bk_event_group_id = serializers.IntegerField(required=True, label="事件分组ID")

    def perform_request(self, params):
        group = CustomEventGroup.objects.get(bk_event_group_id=params["bk_event_group_id"])
        return list(set(group.query_target()))


class CreateCustomEventGroup(Resource):
    """
    创建自定义事件
    """

    CUSTOM_EVENT_DATA_NAME = "custom_event"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        name = serializers.CharField(required=True, max_length=128, label="名称")
        scenario = serializers.CharField(required=True, label="对象")
        event_info_list = EventInfoSerializer(required=False, many=True, allow_empty=True)
        is_platform = serializers.BooleanField(required=False, label="平台级", default=False)
        data_label = serializers.CharField(required=True, label="数据标签")

        def validate(self, attrs):
            ValidateCustomEventGroupName().request(name=attrs["name"], bk_biz_id=attrs["bk_biz_id"])
            ValidateCustomEventGroupLabel().request(data_label=attrs["data_label"])
            return attrs

    def get_custom_event_data_id(self, bk_biz_id, operator, event_group_name):
        data_name = "{}_{}_{}".format(self.CUSTOM_EVENT_DATA_NAME, event_group_name, bk_biz_id)
        try:
            data_id_info = api.metadata.get_data_id({"data_name": data_name, "with_rt_info": False})
        except BKAPIError:
            param = {
                "data_name": data_name,
                "etl_config": ETL_CONFIG.CUSTOM_EVENT,
                "operator": operator,
                "data_description": data_name,
                "type_label": DataTypeLabel.EVENT,
                "source_label": DataSourceLabel.CUSTOM,
                "option": {"inject_local_time": True},
            }
            data_id_info = api.metadata.create_data_id(param)
        else:
            if not CustomEventGroup.objects.filter(
                bk_data_id=data_id_info["bk_data_id"], bk_event_group_id=-data_id_info["bk_data_id"]
            ):
                raise CustomEventValidationError(msg=_("数据源名称[{}]已存在").format(data_name))
        bk_data_id = data_id_info["bk_data_id"]
        return bk_data_id

    def perform_request(self, validated_request_data):
        operator = get_request_username() or settings.COMMON_USERNAME
        input_bk_biz_id = validated_request_data["bk_biz_id"]
        if validated_request_data["is_platform"]:
            input_bk_biz_id = 0
        # 1. 查询或创建业务的 data_id
        bk_data_id = self.get_custom_event_data_id(
            validated_request_data["bk_biz_id"], operator, validated_request_data["name"]
        )

        # 2. 创建或查询数据记录
        group, is_created = CustomEventGroup.objects.get_or_create(bk_data_id=bk_data_id, bk_event_group_id=-bk_data_id)
        # 3. 调用接口创建 event_group
        params = {
            "operator": operator,
            "bk_data_id": bk_data_id,
            "bk_biz_id": input_bk_biz_id,
            "event_group_name": validated_request_data["name"],
            "label": validated_request_data["scenario"],
            "event_info_list": [],
        }
        group_info = api.metadata.create_event_group(params)

        # 4. 结果回写数据库
        with transaction.atomic():
            group.delete()
            group = CustomEventGroup.objects.create(
                bk_biz_id=validated_request_data["bk_biz_id"],
                bk_event_group_id=group_info["event_group_id"],
                scenario=group_info["label"],
                name=group_info["event_group_name"],
                bk_data_id=group_info["bk_data_id"],
                table_id=group_info["table_id"],
                is_platform=validated_request_data["is_platform"],
                data_label=validated_request_data["data_label"],
            )

        return {"bk_event_group_id": group.bk_event_group_id}


class ModifyCustomEventGroup(Resource):
    """
    修改自定义事件
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bk_event_group_id = serializers.IntegerField(required=True, label="事件分组ID")
        name = serializers.CharField(required=False, max_length=128, label="名称")
        scenario = serializers.CharField(required=False, label="对象")
        event_info_list = EventInfoSerializer(required=False, many=True, allow_empty=True)
        is_enable = serializers.BooleanField(required=False)
        is_platform = serializers.BooleanField(required=False, label="平台级")
        data_label = serializers.CharField(required=False, label="数据标签")

        def validate(self, attrs):
            if attrs.get("name"):
                ValidateCustomEventGroupName().request(
                    name=attrs["name"], bk_biz_id=attrs["bk_biz_id"], bk_event_group_id=attrs["bk_event_group_id"]
                )
            if attrs.get("data_label"):
                ValidateCustomEventGroupLabel().request(
                    data_label=attrs["data_label"], bk_event_group_id=attrs["bk_event_group_id"]
                )
            return attrs

    @atomic()
    def perform_request(self, validated_request_data):
        operator = get_request_username()
        group = CustomEventGroup.objects.get(
            bk_biz_id=validated_request_data["bk_biz_id"],
            bk_event_group_id=validated_request_data["bk_event_group_id"],
        )
        # 1. 调用接口修改 event_group
        params = {
            "operator": operator,
            "event_group_id": validated_request_data["bk_event_group_id"],
            "event_group_name": validated_request_data.get("name"),
            "label": validated_request_data.get("scenario"),
            "is_enable": validated_request_data.get("is_enable"),
            "event_info_list": [],
        }
        params = {key: value for key, value in list(params.items()) if value is not None}
        group_info = api.metadata.modify_event_group(params)

        # 2. 结果回写数据库
        group.scenario = group_info["label"]
        group.name = group_info["event_group_name"]
        group.is_enable = group_info["is_enable"]
        if validated_request_data.get("is_platform"):
            group.is_platform = validated_request_data["is_platform"]
        if validated_request_data.get("data_label"):
            group.data_label = validated_request_data["data_label"]
        group.save()
        return {"bk_event_group_id": group.bk_event_group_id}


class DeleteCustomEventGroup(Resource):
    """
    删除自定义事件
    """

    class RequestSerializer(serializers.Serializer):
        bk_event_group_id = serializers.IntegerField(required=True, label="事件分组ID")

    @atomic()
    def perform_request(self, validated_request_data):
        operator = get_request_username()
        group = CustomEventGroup.objects.get(bk_event_group_id=validated_request_data["bk_event_group_id"])
        # 1. 调用接口删除 event_group
        api.metadata.delete_event_group(event_group_id=group.bk_event_group_id, operator=operator)
        # 2. 结果回写数据库
        group.delete()
        CustomEventItem.objects.filter(bk_event_group_id=group.bk_event_group_id).delete()
        return {"bk_event_group_id": validated_request_data["bk_event_group_id"]}

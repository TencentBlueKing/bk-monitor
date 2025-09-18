"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import operator
import time
from collections import defaultdict
from functools import reduce
from typing import Any

from django.db.models import Q
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bkmonitor.documents.alert import AlertDocument
from bkmonitor.documents.base import BulkActionType
from bkmonitor.iam.action import ActionEnum
from bkmonitor.iam.permission import Permission
from bkmonitor.models import Event, Shield
from bkmonitor.utils.common_utils import logger
from bkmonitor.utils.request import get_request, get_request_tenant_id, get_request_username
from bkmonitor.utils.time_tools import (
    DEFAULT_FORMAT,
    localtime,
    now,
    parse_time_range,
    str2datetime,
    strftime_local,
    utc2biz_str,
)
from bkmonitor.utils.user import get_global_user
from bkmonitor.views import serializers
from constants.shield import ScopeType, ShieldCategory, ShieldStatus
from core.drf_resource import resource
from core.drf_resource.base import Resource
from core.errors.shield import DuplicateQuickShieldError, ShieldNotExist
from fta_web.alert.handlers.base import AlertDimensionFormatter
from monitor_web.alert_events.resources import EventDimensionMixin
from monitor_web.shield.serializers import SHIELD_SERIALIZER
from monitor_web.shield.utils import ShieldDetectManager


# 屏蔽列表页的serializer
class ShieldListSerializer(serializers.Serializer):
    bk_biz_id = serializers.IntegerField(required=False, label="业务ID")
    is_active = serializers.BooleanField(required=False, default=True, label="是否处于屏蔽中")
    order = serializers.ChoiceField(
        required=False,
        default="-id",
        label="排序字段",
        choices=["-id", "id", "begin_time", "-begin_time", "failure_time", "-failure_time"],
    )
    categories = serializers.ListField(required=False, label="屏蔽类型", default=[])
    conditions = serializers.ListField(required=False, child=serializers.DictField(), default=[], label="条件")
    time_range = serializers.CharField(required=False, label="时间范围", allow_blank=True, allow_null=True)
    page = serializers.IntegerField(required=False, label="页码")
    page_size = serializers.IntegerField(required=False, label="每页条数")


from django.db.models.query_utils import DeferredAttribute


class ShieldListResource(Resource):
    """
    告警屏蔽列表（通用）
    """

    def __init__(self):
        super().__init__()

    RequestSerializer = ShieldListSerializer

    def perform_request(self, data):
        bk_biz_id = data.get("bk_biz_id")
        is_active = data.get("is_active")
        order = data.get("order")
        categories = data.get("categories")
        source = data.get("source")
        time_range = data.get("time_range")
        page = data.get("page", 0)
        page_size = data.get("page_size", 0)
        conditions = data.get("conditions", [])

        q_list = []

        if bk_biz_id:
            q_list.append(Q(bk_biz_id=bk_biz_id))
        else:
            q_list.append(Q(bk_biz_id__in=resource.space.get_bk_biz_ids_by_user(get_request().user)))

        # 过滤条件
        if categories:
            if "event" in categories:
                # 兼容event查询的场景
                categories.append("alert")

            q_list.append(Q(category__in=categories))

        # 屏蔽来源
        if source:
            q_list.append(Q(source=source))
        shields = Shield.objects.filter(reduce(operator.and_, q_list))

        filter_dict = defaultdict(list)
        enabled_fields = [field for field, value in Shield.__dict__.items() if isinstance(value, DeferredAttribute)]
        for condition in conditions:
            # 支持多条件匹配
            key = condition["key"].lower()
            if key not in enabled_fields:
                # 不在里面的，直接忽略
                continue

            # description 特殊处理，支持模糊搜索
            if key == "description":
                filter_dict["description__icontains"] = condition["value"]
                continue

            value = condition["value"]
            if not isinstance(value, list):
                value = [value]
            filter_dict[f"{key}__in"].extend(value)
        if filter_dict:
            try:
                shields = shields.filter(**filter_dict)
            except ValueError:
                shields = shields.none()
        shields = shields.order_by(order)

        # 筛选屏蔽中，根据范围进行筛选
        if is_active:
            shields = [shield for shield in shields if shield.status == ShieldStatus.SHIELDED]
            if time_range:
                start, end = parse_time_range(data["time_range"])
                shields = [shield for shield in shields if start <= shield.begin_time.timestamp() <= end]
        else:
            shields = [shield for shield in shields if shield.status != ShieldStatus.SHIELDED]
            if time_range:
                start, end = parse_time_range(data["time_range"])
                shields = [shield for shield in shields if start <= shield.failure_time.timestamp() <= end]

        # 统计数目
        count = len(shields)

        # 分页
        # fmt: off
        if all([page, page_size]):
            shields = shields[(page - 1) * page_size: page * page_size]
        # fmt: on
        shield_list = []
        for shield in shields:
            shield_list.append(
                {
                    "id": shield.id,
                    "bk_biz_id": shield.bk_biz_id,
                    "category": shield.category,
                    "status": shield.status,
                    "begin_time": strftime_local(shield.begin_time, DEFAULT_FORMAT),
                    "end_time": strftime_local(shield.end_time, DEFAULT_FORMAT),
                    "failure_time": strftime_local(shield.failure_time, DEFAULT_FORMAT),
                    "is_enabled": shield.is_enabled,
                    "scope_type": shield.scope_type,
                    "dimension_config": shield.dimension_config,
                    "content": shield.content,
                    "cycle_config": shield.cycle_config,
                    "shield_notice": True if shield.notice_config else False,
                    "notice_config": shield.notice_config if shield.notice_config else "{}",
                    "description": shield.description,
                    "source": shield.source,
                    "update_user": shield.update_user,
                    "label": shield.label,
                }
            )

        return {"count": count, "shield_list": shield_list}


class ShieldDetailResource(Resource):
    """
    告警屏蔽详情（通用）
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="屏蔽id")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, data):
        try:
            shield = Shield.objects.get(id=data["id"])
        except Shield.DoesNotExist:
            raise ShieldNotExist({"msg": data["id"]})

        shield_detail = {
            "id": shield.id,
            "bk_biz_id": shield.bk_biz_id,
            "is_enabled": shield.is_enabled,
            "category": shield.category,
            "status": shield.status,
            "scope_type": shield.scope_type,
            "description": shield.description,
            "begin_time": utc2biz_str(shield.begin_time),
            "end_time": utc2biz_str(shield.end_time),
            "shield_notice": True if shield.notice_config else False,
            "notice_config": shield.notice_config,
            "cycle_config": shield.cycle_config,
            "dimension_config": shield.dimension_config,
            "source": shield.source,
            "create_time": utc2biz_str(shield.create_time),
            "update_time": utc2biz_str(shield.update_time),
            "create_user": shield.create_user,
            "update_user": shield.update_user,
            "label": shield.label,
        }
        return shield_detail


class AddShieldResource(Resource, EventDimensionMixin):
    """
    新增屏蔽（通用）
    """

    def validate_request_data(self, request_data: dict[str, Any]):
        # 额外验证用户权限，用于apigw 场景
        if request_data.get("verify_user_permission"):
            username = get_request_username()
            if not username:
                raise ValidationError({"verify_user_permission": "无法获取当前用户"})
            if not request_data.get("bk_biz_id"):
                raise ValidationError({"verify_user_permission": "业务id不能为空"})
            p = Permission(username=username, bk_tenant_id=get_request_tenant_id())
            p.skip_check = False
            if not p.is_allowed_by_biz(request_data["bk_biz_id"], ActionEnum.MANAGE_DOWNTIME):
                raise ValidationError(
                    {"verify_user_permission": f"当前用户无权限新增{request_data['bk_biz_id']}业务屏蔽配置"}
                )

        if "category" not in request_data:
            raise ValidationError(detail={"request_data_invalid": "category not exist"})
        self.RequestSerializer = SHIELD_SERIALIZER[request_data["category"]]
        request_serializer = self.RequestSerializer(data=request_data, many=self.many_request_data)
        self._request_serializer = request_serializer
        is_valid_request = request_serializer.is_valid()
        if not is_valid_request:
            raise ValidationError({self.get_resource_name(): {"request_data_invalid": request_serializer.errors}})
        return request_serializer.validated_data

    @staticmethod
    def handle_scope(data):
        scope_key_mapping = {
            ScopeType.INSTANCE: "service_instance_id",
            ScopeType.IP: "bk_target_ip",
            ScopeType.NODE: "bk_topo_node",
            ScopeType.DYNAMIC_GROUP: "dynamic_group",
        }
        scope_type = data["dimension_config"]["scope_type"]
        dimension_config = {}
        if scope_type in scope_key_mapping:
            target = data["dimension_config"]["target"]
            if scope_type == ScopeType.IP:
                for t in target:
                    t["bk_target_ip"] = t.pop("ip")
                    t["bk_target_cloud_id"] = t.pop("bk_cloud_id")
            dimension_config = {scope_key_mapping.get(scope_type): target}
        if "metric_id" in data["dimension_config"]:
            dimension_config["metric_id"] = data["dimension_config"]["metric_id"]
        return dimension_config

    def handle_strategy(self, data):
        strategy_ids = data["dimension_config"]["id"]
        if not isinstance(strategy_ids, list):
            strategy_ids = [strategy_ids]
        match_info = {"strategy_id": strategy_ids}
        shield_manager = ShieldDetectManager(data["bk_biz_id"], "strategy")
        match_result = shield_manager.check_shield_status(match_info)
        if match_result["is_shielded"]:
            raise DuplicateQuickShieldError({"category": _("策略")})
        level = self.get_strategy_level(data)
        dimension_config = {
            "strategy_id": strategy_ids,
            "level": list(level),
            "dimension_conditions": data["dimension_config"].get("dimension_conditions", []),
        }

        # 处理范围配置
        if data["dimension_config"].get("target", []):
            dimension_config.update(self.handle_scope(data))
        return dimension_config

    @staticmethod
    def get_strategy_level(data):
        level = data["dimension_config"].get("level", [])
        if not level:
            level = [Event.EVENT_LEVEL_FATAL, Event.EVENT_LEVEL_WARNING, Event.EVENT_LEVEL_REMIND]
        return level

    @staticmethod
    def handle_alert(data):
        alert_id = data["dimension_config"]["alert_id"] or data["dimension_config"]["alert_ids"][0]
        alert = AlertDocument.get(alert_id)

        dimension_keys = data.get("dimension_keys")
        dimension_config = {}
        shield_dimensions = []
        for dimension in alert.dimensions:
            dimension_data = dimension.to_dict()
            # 若传递了dimension_keys，则只保留dimension_keys中指定的维度，用于前端动态删除维度信息
            if dimension_keys is None or dimension_data["key"] in dimension_keys:
                dimension_config[dimension_data["key"]] = dimension_data["value"]
                shield_dimensions.append(dimension)
        dimension_config.update(
            {
                "_alert_id": alert.id,
                "strategy_id": alert.strategy_id,
                "_severity": alert.severity,
                "_alert_message": getattr(alert.event, "description", ""),
                "_dimensions": AlertDimensionFormatter.get_dimensions_str(shield_dimensions),
            }
        )

        # 更新alerts的屏蔽状态
        alert_document = AlertDocument(id=alert_id, is_shielded=True, update_time=int(time.time()))
        AlertDocument.bulk_create([alert_document], action=BulkActionType.UPDATE)
        return dimension_config

    @staticmethod
    def handle_dimension(data):
        dimension_config = data["dimension_config"]
        dimension_config.update({"_strategy_id": dimension_config.pop("strategy_id", 0)})
        return dimension_config

    @classmethod
    def get_alert_dimension_string(cls, display_dimensions):
        """
        告警维度字符串
        """
        # 拓扑维度特殊处理
        dimension_string_list = []

        for key, value in display_dimensions.items():
            dimension_string_list.append(f"{key}={value}")

        dimension_string = ",".join(dimension_string_list)

        return dimension_string

    def perform_request(self, data):
        data["category"] = ShieldCategory.ALERT if data["category"] == ShieldCategory.EVENT else data["category"]

        shield_handler = {
            ShieldCategory.SCOPE: self.handle_scope,
            ShieldCategory.STRATEGY: self.handle_strategy,
            ShieldCategory.ALERT: self.handle_alert,
            ShieldCategory.DIMENSION: self.handle_dimension,
        }
        dimension_config = shield_handler[data["category"]](data)
        # 处理notice_config
        if data["shield_notice"]:
            data["notice_config"]["notice_receiver"] = [
                "{}#{}".format(item["type"], item["id"]) for item in data["notice_config"]["notice_receiver"]
            ]

        # 处理时间数据
        time_result = handle_shield_time(data["begin_time"], data["end_time"], data["cycle_config"])
        shield_obj = Shield.objects.create(
            bk_biz_id=data["bk_biz_id"],
            category=data["category"],
            begin_time=time_result["begin_time"],
            end_time=time_result["end_time"],
            failure_time=time_result["end_time"],
            scope_type=data["dimension_config"].get("scope_type", ""),
            cycle_config=data.get("cycle_config", {}),
            dimension_config=dimension_config,
            notice_config=data["notice_config"] if data["shield_notice"] else {},
            description=data.get("description", ""),
            is_quick=data["is_quick"],
            source=data.get("source", ""),
            label=data.get("label"),
        )
        return {"id": shield_obj.id}


class BulkAddAlertShieldResource(AddShieldResource):
    """
    {
      "bk_biz_id": 2,
      "category": "alert",
      "begin_time": "2024-09-03 17:31:48",
      "end_time": "2024-09-03 18:01:48",
      "dimension_config": {
        "alert_ids": [
          "111", "100"
        ]
        # 编辑了维度后， 则将告警对应的剩下的维度的key放进来。 作为字典， key是告警id， value是剩下的维度key列表
        "dimensions": {"111": ["xxx", "yyy"], "100": ["xxx", "yyy"],
        "bk_topo_node": {
            "111": [{"bk_obj_id": "set","bk_inst_id": 3}, {"bk_obj_id": "module","bk_inst_id": 4}]
            "100": [{"bk_obj_id": "set","bk_inst_id": 3}, {"bk_obj_id": "module","bk_inst_id": 4}]
            }
        },
      },
      "shield_notice": false,
      "description": "test",
      "cycle_config": {
        "begin_time": "",
        "type": 1,
        "day_list": [],
        "week_list": [],
        "end_time": ""
      }
    }
    """

    def handle_alerts(self, data):
        alert_ids = data["dimension_config"]["alert_ids"] or [data["dimension_config"]["alert_id"]]
        # dimension_config.dimensions 标记告警保留需要匹配的屏蔽维度
        target_dimension_config: dict = data["dimension_config"].get("dimensions", {})
        target_bk_topo_node: dict = data["dimension_config"].get("bk_topo_node", {})
        alerts = AlertDocument.mget(ids=alert_ids)
        dimension_configs = []

        alert_documents = []
        now_time = int(time.time())

        for alert in alerts:
            """
            获取 bk_topo_node和 dimensions
            if bk_topo_node 有值:
                传入 bk_topo_node, 
                并修改 屏蔽的category 要改成范围屏蔽 
                # Shield.SHIELD_CATEGROY[0][0] -> "scope"
            elif dimensions 有值:
                按传入(维度)值处理
            elif dimensions 无值:
                按默认所有维度配置
            """

            dimension_config = {
                # 下划线的配置，不参与屏蔽逻辑。
                "_alert_id": alert.id,
                "strategy_id": alert.strategy_id,
                "_severity": alert.severity,
                "_alert_message": getattr(alert.event, "description", ""),
            }

            bk_topo_node: list = target_bk_topo_node.get(str(alert.id), [])
            target_dimensions: list[str] | None = target_dimension_config.get(str(alert.id), None)
            shield_dimensions = []

            if bk_topo_node:
                dimension_config["bk_topo_node"] = bk_topo_node
                data["category"] = "scope"
            else:
                for dimension in alert.dimensions:
                    dimension_data: dict = dimension.to_dict()
                    if target_dimensions is None or dimension_data["key"] in target_dimensions:
                        dimension_config[dimension_data["key"]] = dimension_data["value"]
                        shield_dimensions.append(dimension)

            dimension_config["_dimensions"] = AlertDimensionFormatter.get_dimensions_str(shield_dimensions)

            alert_documents.append(AlertDocument(id=alert.id, is_shielded=True, update_time=now_time))
            dimension_configs.append(dimension_config)

        # 更新alerts的屏蔽状态
        AlertDocument.bulk_create(alert_documents, action=BulkActionType.UPDATE)

        return dimension_configs

    def perform_request(self, data):
        dimension_configs = self.handle_alerts(data)
        # 处理notice_config
        if data["shield_notice"]:
            data["notice_config"]["notice_receiver"] = [
                "{}#{}".format(item["type"], item["id"]) for item in data["notice_config"]["notice_receiver"]
            ]
        # 处理时间数据
        time_result = handle_shield_time(data["begin_time"], data["end_time"], data["cycle_config"])
        source = data.get("source", "")
        shields = []
        shield_operator = get_request_username()
        for dimension_config in dimension_configs:
            shields.append(
                Shield(
                    bk_biz_id=data["bk_biz_id"],
                    category=data["category"],
                    create_user=shield_operator,
                    update_user=shield_operator,
                    begin_time=time_result["begin_time"],
                    end_time=time_result["end_time"],
                    failure_time=time_result["end_time"],
                    scope_type=data["dimension_config"].get("scope_type", ""),
                    cycle_config=data.get("cycle_config", {}),
                    dimension_config=dimension_config,
                    notice_config=data["notice_config"] if data["shield_notice"] else {},
                    description=data.get("description", ""),
                    is_quick=data["is_quick"],
                    source=source,
                    label=data.get("label"),
                )
            )
        Shield.objects.bulk_create(shields)
        return {"message": "success"}


class EditShieldResource(Resource):
    """
    编辑屏蔽（通用）
    """

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="屏蔽id")
        bk_biz_id = serializers.IntegerField(required=True, label="业务id")
        begin_time = serializers.CharField(required=True, label="屏蔽开始时间")
        end_time = serializers.CharField(required=True, label="屏蔽结束时间")
        level = serializers.ListField(required=False, label="策略的屏蔽等级")
        cycle_config = serializers.DictField(required=True, label="周期配置")
        shield_notice = serializers.BooleanField(required=True, label="是否有屏蔽通知")
        notice_config = serializers.DictField(required=False, label="通知配置")
        description = serializers.CharField(required=False, label="屏蔽原因", allow_blank=True)
        label = serializers.CharField(required=False, label="标签", default=None, allow_blank=True)

    def perform_request(self, data):
        try:
            shield = Shield.objects.get(id=data["id"])
        except Shield.DoesNotExist:
            raise ShieldNotExist({"msg": data["id"]})

        # 处理时间数据
        time_result = handle_shield_time(data["begin_time"], data["end_time"], data["cycle_config"])
        shield.begin_time = time_result["begin_time"]
        shield.end_time = time_result["end_time"]
        shield.failure_time = time_result["end_time"]

        # 如果是策略屏蔽，因为会设置屏蔽等级，生成新的dimension_config
        if shield.category == ShieldCategory.STRATEGY:
            shield.dimension_config["level"] = data["level"]

        # 处理notice_config
        if data["shield_notice"]:
            data["notice_config"]["notice_receiver"] = [
                "{}#{}".format(item["type"], item["id"]) for item in data["notice_config"]["notice_receiver"]
            ]
            shield.notice_config = data["notice_config"]
        else:
            shield.notice_config = {}

        # 如果没有传入label，则使用原来的label
        if data.get("label") is not None:
            shield.label = data["label"]

        shield.cycle_config = data["cycle_config"]
        shield.description = data.get("description")
        shield.save()

        return {"id": shield.id}


class DisableShieldResource(Resource):
    """
    解除屏蔽（通用）
    """

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, allow_null=True, label="业务id")
        id = serializers.ListField(required=True, child=serializers.IntegerField(), min_length=1, label="屏蔽id列表")
        verify_user_permission = serializers.BooleanField(
            required=False, default=False, label="是否额外验证用户权限(apigw)"
        )

        def to_internal_value(self, data):
            data["id"] = data.get("id", [])
            # 确保"id"字段始终是一个列表
            if not isinstance(data["id"], list):
                data["id"] = [data["id"]]

            return super().to_internal_value(data)

    def perform_request(self, data):
        username = get_request_username()
        # 额外验证用户权限，用于apigw 场景
        if data.get("verify_user_permission"):
            if not username:
                raise ValidationError({"verify_user_permission": "无法获取当前用户"})
            if not data.get("bk_biz_id"):
                raise ValidationError({"verify_user_permission": "业务id不能为空"})
            p = Permission(username=username, bk_tenant_id=get_request_tenant_id())
            p.skip_check = False
            if not p.is_allowed_by_biz(data["bk_biz_id"], ActionEnum.MANAGE_DOWNTIME):
                raise ValidationError({"verify_user_permission": f"当前用户无权限解除{data['bk_biz_id']}业务屏蔽配置"})
        else:
            username = get_global_user() or "unknown"

        shields = Shield.objects.filter(pk__in=data["id"])
        if data.get("bk_biz_id"):
            shields = shields.filter(bk_biz_id=data["bk_biz_id"])

        update_shields = []
        for shield in shields:
            if shield.is_enabled:
                shield.is_enabled = False
                shield.failure_time = now()
                shield.update_user = username  # 记录最后的操作人
                update_shields.append(shield)
        Shield.objects.bulk_update(update_shields, ["is_enabled", "failure_time", "update_user"])

        # 检查是否有不存在的屏蔽对象ID
        existing_ids = {shield.id for shield in shields}
        missing_ids = set(data["id"]) - existing_ids

        if missing_ids:
            logger.warning(f"Alarm shield ids does not exist: {list(missing_ids)}")
        return "success"


def handle_shield_time(begin_time_str, end_time_str, cycle_config):
    if cycle_config.get("type", 1) != 1:
        begin_time_str = "{} {}".format(begin_time_str[0:10].strip(), cycle_config.get("begin_time"))
        end_time_str = "{} {}".format(end_time_str[0:10].strip(), cycle_config.get("end_time"))

    return {
        "begin_time": localtime(str2datetime(begin_time_str)),
        "end_time": localtime(str2datetime(end_time_str)),
    }

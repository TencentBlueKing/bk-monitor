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
import itertools
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Set

from rest_framework.exceptions import ValidationError

from bkmonitor.models import StrategyModel
from bkmonitor.utils.time_tools import localtime, now
from bkmonitor.views import serializers
from constants.shield import (
    SHIELD_STATUS_NAME_MAPPING,
    ScopeType,
    ShieldCategory,
    ShieldStatus,
)
from core.drf_resource import resource
from core.drf_resource.base import Resource
from monitor_web.shield.utils import ShieldDisplayManager

from .backend_resources import ShieldListSerializer


class FrontendShieldListResource(Resource):
    """
    告警屏蔽列表（前端）
    """

    class RequestSerializer(ShieldListSerializer):
        search = serializers.CharField(required=False, label="查询参数", allow_blank=True)

    @staticmethod
    def get_dimension_config(shield):
        if shield["category"] in [ShieldCategory.STRATEGY, ShieldCategory.EVENT, ShieldCategory.ALERT]:
            return {
                "id": (
                    shield["dimension_config"].get("strategy_id")
                    or shield["dimension_config"].get("_event_id")
                    or shield["dimension_config"].get("_alert_id")
                )
            }
        return {}

    @staticmethod
    def get_status_name(status):
        return SHIELD_STATUS_NAME_MAPPING.get(status)

    def perform_request(self, data):
        page = data.get("page", 0)
        page_size = data.get("page_size", 0)
        bk_biz_id: Optional[int] = data.get("bk_biz_id")
        is_active: bool = data["is_active"]
        search_terms = set()
        conditions = []
        strategy_ids = []
        for condition in data.get("conditions", []):
            if condition["key"] == "query":
                search_terms.add(condition["value"])
            elif condition["key"] == "strategy_id":
                # 查询策略关联的屏蔽配置
                if isinstance(condition["value"], list):
                    strategy_ids.extend(condition["value"])
                else:
                    strategy_ids.append(condition["value"])
            else:
                conditions.append(condition)

        # 策略id必须是数字
        try:
            strategy_ids = [int(strategy_id) for strategy_id in strategy_ids]
        except (ValueError, TypeError):
            raise ValidationError("condition strategy_id must be integer")

        if data.get("search"):
            search_terms.add(data["search"])

        params = {
            "bk_biz_id": bk_biz_id,
            "is_active": is_active,
            "order": data.get("order"),
            "categories": data.get("categories"),
            "conditions": conditions,
            "time_range": data.get("time_range"),
        }
        # 如果不执行模糊搜索，则由后端分页，避免后续多余处理
        if not search_terms and not strategy_ids:
            params.update({"page": page, "page_size": page_size})

        # 获取屏蔽列表
        result = resource.shield.shield_list(**params)
        shields = self.enrich_shields(bk_biz_id, result["shield_list"], strategy_ids)

        # 模糊搜索和分页处理
        if search_terms:
            shields = self.search(search_terms, shields, is_active)

        # 如果执行模糊搜索或过滤策略id，则需要手动分页
        if search_terms or strategy_ids:
            total = len(shields)
            if page and page_size:
                shields = shields[(page - 1) * page_size : page * page_size]
        else:
            total = result["count"]

        return {"count": total, "shield_list": shields}

    @staticmethod
    def search(search_terms: Set[str], shields: list, is_active: bool) -> list:
        """模糊搜索屏蔽列表。"""
        active_fields = [
            "id",
            "category_name",
            "content",
            "begin_time",
            "cycle_duration",
            "description",
            "status_name",
            "label",
        ]
        inactive_fields = ["id", "category_name", "content", "failure_time", "description", "status_name", "label"]
        search_fields = active_fields if is_active else inactive_fields

        def match(shield):
            for field, term in itertools.product(search_fields, search_terms):
                if term in str(shield.get(field, "")):
                    return True
            return False

        return [shield for shield in shields if match(shield)]

    def enrich_shields(self, bk_biz_id: Optional[int], shields: List, strategy_ids: List[int]) -> List:
        """补充屏蔽记录的数据便于展示。"""
        if not shields:
            return []

        manager = ShieldDisplayManager(bk_biz_id)

        # 过滤策略id
        strategy_ids = set(strategy_ids)
        shields = [
            shield for shield in shields if (set(manager.get_strategy_ids(shield)) & strategy_ids) or not strategy_ids
        ]

        # 获取关联策略名
        shield_strategy_ids = {strategy_id for shield in shields for strategy_id in manager.get_strategy_ids(shield)}

        strategy_id_to_name = {
            strategy.id: strategy.name
            for strategy in StrategyModel.objects.filter(id__in=shield_strategy_ids).only("name")
        }

        with ThreadPoolExecutor(max_workers=20) as executor:
            formatted_shields = list(
                executor.map(
                    lambda shield: {
                        "id": shield["id"],
                        "bk_biz_id": shield["bk_biz_id"],
                        "category": shield["category"],
                        "category_name": manager.get_category_name(shield),
                        "status": shield["status"],
                        "status_name": self.get_status_name(shield["status"]),
                        "dimension_config": self.get_dimension_config(shield),
                        "content": shield["content"] or manager.get_shield_content(shield, strategy_id_to_name),
                        "begin_time": shield["begin_time"],
                        "failure_time": shield["failure_time"],
                        "cycle_duration": manager.get_cycle_duration(shield),
                        "description": shield["description"],
                        "source": shield["source"],
                        "update_user": shield["update_user"],
                        "label": shield["label"],
                    },
                    shields,
                )
            )

        return formatted_shields


class FrontendShieldDetailResource(Resource):
    """
    告警屏蔽详情（前端）
    """

    def __init__(self):
        super(FrontendShieldDetailResource, self).__init__()
        self.bk_biz_id = None

    class RequestSerializer(serializers.Serializer):
        id = serializers.IntegerField(required=True, label="屏蔽id")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def handle_notice_config(self, notice_config):
        from monitor_web.notice_group.resources.front import NoticeGroupDetailResource

        notice_receivers = []
        for receiver in notice_config["notice_receiver"]:
            receiver_id = receiver.split("#", 1)[1]
            receiver_type = receiver.split("#", 1)[0]
            notice_receivers.append({"id": receiver_id, "type": receiver_type})

        usernames = set()
        for receiver in notice_receivers:
            if receiver["type"] == "user":
                usernames.add(receiver["id"])

        users_info = NoticeGroupDetailResource.get_users_info(list(usernames))
        notify_roles = resource.cc.get_notify_roles()
        for receiver in notice_receivers:
            if receiver["type"] == "user" and receiver["id"] in users_info:
                receiver["display_name"] = users_info[receiver["id"]]["display_name"]
                receiver["logo"] = users_info[receiver["id"]]["logo"] or ""
            elif receiver["type"] == "group" and receiver["id"] in notify_roles:
                receiver["display_name"] = notify_roles[receiver["id"]]
                receiver["logo"] = ""
            else:
                receiver["display_name"] = receiver["id"]

        notice_config["notice_receiver"] = notice_receivers
        return notice_config

    def handle_dimension_config(self, shield):
        dimension_config = {}
        shield_display_manager = ShieldDisplayManager(self.bk_biz_id)
        if shield.get("scope_type"):
            if shield["scope_type"] == ScopeType.INSTANCE:
                target = shield_display_manager.get_service_name_list(
                    self.bk_biz_id, shield["dimension_config"].get("service_instance_id")
                )
            elif shield["scope_type"] == ScopeType.IP:
                target = [ip["bk_target_ip"] for ip in shield["dimension_config"].get("bk_target_ip")]
            elif shield["scope_type"] == ScopeType.NODE:
                target = shield_display_manager.get_node_path_list(
                    self.bk_biz_id, shield["dimension_config"].get("bk_topo_node")
                )
                target = ["/".join(item) for item in target]
            elif shield["scope_type"] == ScopeType.DYNAMIC_GROUP:
                target = shield_display_manager.get_dynamic_group_name_list(
                    self.bk_biz_id, shield["dimension_config"].get("dynamic_group") or []
                )
            else:
                business = shield_display_manager.get_business_name(shield["bk_biz_id"])
                target = [business]

            dimension_config.update({"scope_type": shield["scope_type"], "target": target})

        if "strategy_id" in shield["dimension_config"]:
            strategy_ids = shield["dimension_config"]["strategy_id"]
            if not isinstance(strategy_ids, list):
                strategy_ids = [strategy_ids]
            strategies = list(
                StrategyModel.objects.filter(id__in=strategy_ids, bk_biz_id=self.bk_biz_id).values("id", "name")
            )
            dimension_config.update({"strategies": strategies})

        if shield["category"] == ShieldCategory.STRATEGY:
            dimension_config.update(
                {
                    "level": shield["dimension_config"]["level"],
                    "dimension_conditions": shield["dimension_config"].get("dimension_conditions", []),
                }
            )
        elif shield["category"] == ShieldCategory.EVENT:
            dimension_config.update(
                {
                    "level": shield["dimension_config"]["_level"],
                    "event_message": shield["dimension_config"]["_event_message"],
                    "dimensions": shield["dimension_config"]["_dimensions"],
                }
            )
        elif shield["category"] == ShieldCategory.ALERT:
            dimension_config.update(
                {
                    "level": shield["dimension_config"]["_severity"],
                    "event_message": shield["dimension_config"].get("_alert_message", ""),
                    "dimensions": shield["dimension_config"]["_dimensions"],
                }
            )
        elif shield["category"] == ShieldCategory.DIMENSION:
            dimension_config.update(
                {
                    "dimension_conditions": shield["dimension_config"]["dimension_conditions"],
                    "strategy_id": shield["dimension_config"].get("_strategy_id", 0),
                }
            )
        return dimension_config

    def perform_request(self, data):
        result = resource.shield.shield_detail(**data)
        self.bk_biz_id = data["bk_biz_id"]
        dimension_config = self.handle_dimension_config(result)
        notice_config = self.handle_notice_config(result["notice_config"]) if result["notice_config"] else {}
        result.update(dimension_config=dimension_config, notice_config=notice_config)
        return result


class ShieldSnapshotResource(FrontendShieldDetailResource):
    """
    告警屏蔽详情（快照）
    """

    def __init__(self):
        super(ShieldSnapshotResource, self).__init__()

    class RequestSerializer(serializers.Serializer):
        config = serializers.DictField(required=True, label="屏蔽快照")

    @staticmethod
    def get_shield_status(config):
        now_time = localtime(now())
        end_time = localtime(config["end_time"])
        if config["is_enabled"]:
            if now_time > end_time:
                return ShieldStatus.EXPIRED
            else:
                return ShieldStatus.SHIELDED
        else:
            return ShieldStatus.REMOVED

    def perform_request(self, data):
        config = data["config"]
        self.bk_biz_id = config["bk_biz_id"]
        config["shield_notice"] = True if config["notice_config"] else False
        config["status"] = self.get_shield_status(config)
        config["begin_time"] = config["begin_time"].strftime("%Y-%m-%d %H:%M:%S")
        config["end_time"] = config["end_time"].strftime("%Y-%m-%d %H:%M:%S")
        dimension_config = self.handle_dimension_config(config)
        notice_config = self.handle_notice_config(config["notice_config"]) if config["notice_config"] else {}
        config.update(dimension_config=dimension_config, notice_config=notice_config)
        return config


class FrontendCloneInfoResource(FrontendShieldDetailResource):
    """获取屏蔽克隆信息（前端）"""

    def perform_request(self, data):
        result = resource.shield.shield_detail(**data)
        self.bk_biz_id = data["bk_biz_id"]
        dimension_config = self.handle_dimension_config(result)
        dimension_config.update(result["dimension_config"])

        notice_config = self.handle_notice_config(result["notice_config"]) if result["notice_config"] else {}
        result.update(dimension_config=dimension_config, notice_config=notice_config)
        return result

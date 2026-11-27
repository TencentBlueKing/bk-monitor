"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import logging
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import chain

from django.db import router, transaction
from rest_framework import serializers

from bkmonitor.action.alert_assign import AlertAssignMatchManager
from bkmonitor.action.serializers import (
    AssignGroupSlz,
    AssignRuleSlz,
    BatchAssignRulesSlz,
    BatchSaveAssignRulesSlz,
)
from bkmonitor.action.serializers.assign import split_dispatch_actions
from bkmonitor.documents import AlertDocument
from bkmonitor.models import AlertAssignGroup, AlertAssignRule
from bkmonitor.utils.common_utils import count_md5
from constants.action import ASSIGN_CONDITION_KEYS, AssignMode
from core.drf_resource import Resource, api
from fta_web.alert.handlers.alert import AlertQueryHandler
from fta_web.alert.handlers.translator import MetricTranslator
from fta_web.constants import GLOBAL_BIZ_ID

logger = logging.getLogger("root")


class BatchUpdateResource(Resource, metaclass=abc.ABCMeta):
    class RequestSerializer(BatchSaveAssignRulesSlz):
        assign_group_id = serializers.IntegerField(label="规则组ID", required=True)
        name = serializers.CharField(label="规则组名称", required=False)
        settings = serializers.JSONField(label="属性配置", default={}, required=False)

    def perform_request(self, validated_request_data):
        with transaction.atomic(using=router.db_for_write(AlertAssignGroup)):
            group_id = validated_request_data["assign_group_id"]
            group = AlertAssignGroup.objects.select_for_update().get(id=group_id)
            result = BatchSaveAssignRulesSlz.save_rules(group, validated_request_data["rules"])
            group.name = validated_request_data.get("group_name") or group.name
            group.priority = validated_request_data["priority"]
            group.settings = validated_request_data.get("settings", {})
            group.hash = ""
            group.snippet = ""
            group.save()
            return result


class MatchDebugResource(Resource, metaclass=abc.ABCMeta):
    class RequestSerializer(BatchAssignRulesSlz):
        assign_group_id = serializers.IntegerField(label="规则组ID", required=False, allow_null=True, default=None)
        exclude_groups = serializers.ListField(label="排除的规则组", child=serializers.IntegerField(), default=[])
        days = serializers.IntegerField(label="调试周期", default=7)
        start_time = serializers.IntegerField(label="调试开始时间", default=0)
        end_time = serializers.IntegerField(label="调试结束时间", default=0)
        max_alert_count = serializers.IntegerField(label="调试告警数量", default=1000)

    @staticmethod
    def compare_rules(group_id, debug_rules):
        existed_rules = {
            rule["id"]: rule
            for rule in AssignRuleSlz(
                instance=AlertAssignRule.objects.filter(assign_group_id=group_id), many=True, context={"for_match": True}
            ).data
        }
        for rule in debug_rules:
            if not rule.get("id") or rule["id"] not in existed_rules:
                # 如果不存在DB，则表示发生了变化
                rule.update(is_changed=True)
                continue
            rule_md5 = count_md5(rule)
            # 单条规则读取含 user_type 等批量编辑器不写的字段；只比较本次实际提交内容。
            rule_db_md5 = count_md5({key: existed_rules[rule["id"]].get(key) for key in rule})
            if rule_md5 != rule_db_md5:
                rule.update(is_changed=True)
            else:
                rule.update(is_changed=False)

    @staticmethod
    def get_cmdb_attributes(bk_biz_id):
        hosts = {
            str(host.bk_host_id or host.host_id): host for host in api.cmdb.get_host_by_topo_node(bk_biz_id=bk_biz_id)
        }
        sets = {str(bk_set.bk_set_id): bk_set for bk_set in api.cmdb.get_set(bk_biz_id=bk_biz_id)}
        modules = {str(bk_module.bk_module_id): bk_module for bk_module in api.cmdb.get_module(bk_biz_id=bk_biz_id)}

        return hosts, sets, modules

    def get_alert_cmdb_attributes(self, alert):
        if not self.hosts:
            return None
        try:
            host = self.hosts.get(str(alert.event.bk_host_id))
            if not host:
                host = self.hosts.get(f"{alert.event.ip}|{alert.event.bk_cloud_id}")
        except Exception as error:
            # 非主机的可能会抛出异常
            logger.info("[match_debug]get debug host info failed: %s", str(error))
            return None
        if not host:
            return None
        sets = []
        modules = []
        alert_cmdb_attributes = {"host": host, "sets": sets, "modules": modules}
        for bk_set_id in host.bk_set_ids:
            biz_set = self.sets.get(str(bk_set_id))
            if biz_set:
                sets.append(biz_set)

        for bk_module_id in host.bk_module_ids:
            biz_module = self.modules.get(str(bk_module_id))
            if biz_module:
                modules.append(biz_module)
        return alert_cmdb_attributes

    def perform_request(self, validated_request_data):
        bk_biz_id = validated_request_data["bk_biz_id"]
        self.hosts, self.sets, self.modules = self.get_cmdb_attributes(validated_request_data["bk_biz_id"])
        # step1 获取最近1周内产生的前1000条告警数据？，所有数据默认为abnormal
        current_time = datetime.now()
        search_params = {
            "bk_biz_ids": [bk_biz_id],
            "page_size": validated_request_data["max_alert_count"],
            "ordering": ["-create_time"],
            "start_time": validated_request_data["start_time"]
            or int((current_time - timedelta(days=validated_request_data["days"])).timestamp()),
            "end_time": validated_request_data["end_time"] or int(current_time.timestamp()),
        }
        handler = AlertQueryHandler(**search_params)
        search_result, _ = handler.search_raw()
        alerts = [AlertDocument(**hit.to_dict()) for hit in search_result]

        # step2 获取当前DB存储的所有规则，并替换掉当前的告警规则
        # 2.1 获取到所有的规则组内容
        group_id = validated_request_data.get("assign_group_id")
        group_name = validated_request_data.get("group_name", "")
        priority = validated_request_data.get("priority", 0)
        exclude_groups = validated_request_data.get("exclude_groups") or []

        groups_queryset = AlertAssignGroup.objects.filter(bk_biz_id__in=[bk_biz_id, GLOBAL_BIZ_ID]).order_by(
            "-priority"
        )

        if exclude_groups:
            groups_queryset = groups_queryset.exclude(id__in=validated_request_data["exclude_groups"])
        groups = {group["id"]: group for group in AssignGroupSlz(instance=groups_queryset, many=True).data}
        for group in groups.values():
            group.pop("id", None)

        group_rules = defaultdict(list)
        priority_rules = defaultdict(list)
        draft_rules = validated_request_data["rules"]
        if group_id in groups or (group_id is None and draft_rules):
            if group_id is None:
                groups[None] = {}
                for rule in draft_rules:
                    rule["is_changed"] = True
            else:
                self.compare_rules(group_id, draft_rules)
            group_rules[group_id] = draft_rules
            groups[group_id].update(priority=priority, name=group_name)
            for index, rule in enumerate(draft_rules, start=1):
                # 尚未保存的草稿没有数据库 ID，用请求内唯一负值关联调试明细。
                if not rule.get("id"):
                    rule["id"] = -index
                rule.update(priority=priority, group_name=group_name)
            priority_rules[priority].extend(draft_rules)

        # 2.2 获取所有的规则
        saved_group_ids = [saved_id for saved_id in groups if saved_id != group_id]
        rules_queryset = AlertAssignRule.objects.filter(
            bk_biz_id__in=[bk_biz_id, GLOBAL_BIZ_ID], assign_group_id__in=saved_group_ids
        )
        rules = AssignRuleSlz(instance=rules_queryset, many=True, context={"for_match": True}).data

        # 2.3 通过优先级和组名进行排序
        for rule in rules:
            rule.update(groups[rule["assign_group_id"]])
            rule["group_name"] = groups[rule["assign_group_id"]]["name"]
            priority_rules[rule["priority"]].append(rule)
            group_rules[rule["assign_group_id"]].append(rule)
        sorted_priorities = sorted(priority_rules.keys(), reverse=True)
        sorted_priority_rules = [priority_rules[sorted_priority] for sorted_priority in sorted_priorities]

        # step3 对告警进行规则适配 ?? 是否需要后台任务支持
        matched_alerts = []
        # 组级命中统计与规则级明细保持同一口径：同一告警命中组内多条规则时逐次累加（不按告警去重），
        # 否则组头「共 N 条」会小于组内各规则「命中 N 条」之和
        rule_alerts = defaultdict(list)
        suppressed_alerts = defaultdict(list)
        dynamic_group_hosts = {}
        for alert in alerts:
            origin_severity = alert.severity
            alert_manager = AlertAssignMatchManager(
                alert,
                notice_users=alert.assignee,
                group_rules=sorted_priority_rules,
                assign_mode=[AssignMode.BY_RULE],
                cmdb_attrs=self.get_alert_cmdb_attributes(alert),
                explain=True,
                dynamic_group_hosts=dynamic_group_hosts,
            )
            # 调试根据当前草稿重新判定；历史命中快照只用于线上通知重试。
            alert_manager.rule_snaps = {}
            alert_manager.run_match()
            if not alert_manager.matched_rules:
                # 没有适配到任何规则
                continue
            alert_info = {
                "id": alert.id,
                "origin_severity": origin_severity,
                "severity": alert.severity,
                "alert_name": alert.alert_name,
                "content": getattr(alert.event, "description", ""),
                "metrics": [{"id": metric_id} for metric_id in alert.event.metric],
            }
            effective_rule_ids = {rule.rule_id for rule in alert_manager.matched_rules}
            for decision in alert_manager.matched_rule_info["matched_rules"]:
                bucket = rule_alerts if decision["rule_id"] in effective_rule_ids else suppressed_alerts
                bucket[decision["rule_id"]].append(
                    {
                        **alert_info,
                        "action_types": decision["action_types"],
                        "suppressed_actions": decision["suppressed_actions"],
                        "dispatch_result": alert_manager.matched_rule_info["dispatch_result"],
                    }
                )
            matched_alerts.append(alert_info)

        MetricTranslator(bk_biz_ids=[bk_biz_id]).translate_from_dict(
            list(chain(*[alert["metrics"] for alert in matched_alerts])), "id", "name"
        )
        # step4 返回所有的规则信息
        response_data = []
        for sorted_priority in sorted_priorities:
            for rule_group_id, rules in group_rules.items():
                group_info = groups.get(rule_group_id, {})
                if group_info["priority"] != sorted_priority:
                    continue
                for rule in rules:
                    rule_id = rule["id"]
                    rule["alerts"] = rule_alerts[rule_id]
                    rule["suppressed_alerts"] = suppressed_alerts[rule_id]
                    rule["actions"], rule["dispatch_config"] = split_dispatch_actions(rule.get("actions", []))
                    if rule_id < 0:
                        rule.pop("id")
                response_data.append(
                    {
                        "group_id": rule_group_id,
                        "alerts_count": sum(len(rule["alerts"]) for rule in rules),
                        "group_name": group_info.get("name", rule_group_id),
                        "priority": group_info.get("priority", 0),
                        "rules": rules,
                    }
                )
        return response_data


class GetAssignConditionKeysResource(Resource, metaclass=abc.ABCMeta):
    def perform_request(self, validated_request_data):
        assign_condition_keys = []
        for key, display_key in ASSIGN_CONDITION_KEYS.items():
            assign_condition_keys.append({"key": key, "display_key": display_key})
        return assign_condition_keys


class SearchObjectAttributeResource(Resource, metaclass=abc.ABCMeta):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID", required=True)
        bk_obj_id = serializers.CharField(label="模型ID", required=True)

    def perform_request(self, validated_request_data):
        return api.cmdb.search_object_attribute(validated_request_data)

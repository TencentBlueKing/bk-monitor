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
import json
import logging
import time
import urllib.parse
from collections import defaultdict
from typing import List

from django.utils.translation import ugettext as _

import settings
from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.range import load_condition_instance
from constants.action import ActionPluginType, AssignMode, UserGroupType
from constants.alert import EVENT_SEVERITY_DICT

logger = logging.getLogger("fta_action.run")


class UpgradeRuleMatch:
    """
    升级适配
    """

    def __init__(self, upgrade_config):
        self.upgrade_config = upgrade_config
        self.is_upgrade = False

    @property
    def is_upgrade_enable(self):
        return self.upgrade_config.get("is_enabled", False)

    def need_upgrade(self, notice_interval, last_group_index=None):
        # 判断是否已经达到了升级的条件
        if not self.is_upgrade_enable:
            # 不需要升级的或者告警为空，直接返回False
            return False
        upgrade_interval = self.upgrade_config.get("upgrade_interval", 0) * 60
        if upgrade_interval <= notice_interval:
            # 时间间隔满足了之后, 判断是否已经全部通知完
            _, group_index = self.get_upgrade_user_group(last_group_index)
            return group_index != last_group_index
        return False

    def get_upgrade_user_group(self, last_group_index=None, need_upgrade=True):
        """
        获取时间间隔已经满足的情况下是否还有关注人未通知
        :param last_group_index: 上一次的通知记录
        :param need_upgrade: 是否满足间隔条件
        :return:
        """
        upgrade_user_groups = self.upgrade_config.get("user_groups", [])
        if last_group_index is None and need_upgrade:
            # 第一次升级，返回第一组
            self.is_upgrade = True
            return [upgrade_user_groups[0]], 0
        if need_upgrade and last_group_index + 1 < len(upgrade_user_groups):
            # 如果升级之后再次超过升级事件，且存在下一个告警组， 则直接通知下一组成员
            self.is_upgrade = True
            group_index = last_group_index + 1
            return [upgrade_user_groups[group_index]], group_index
        return [], last_group_index


class AssignRuleMatch:
    """分派规则适配"""

    def __init__(self, assign_rule, assign_rule_snap=None, alert: AlertDocument = None):
        """
        :param assign_rule:  规则ID
        :param assign_rule_snap:
        :return:
        """
        self.assign_rule = assign_rule
        self.assign_rule_snap = assign_rule_snap or {}
        self.dimension_check = None
        self.parse_dimension_conditions()
        self.alert = alert

    def parse_dimension_conditions(self):
        """
        根据配置的条件信息获取
        :return:
        """
        or_cond = []
        and_cond = []
        for condition in self.assign_rule["conditions"]:
            if condition.get("condition") == "or" and and_cond:
                or_cond.append(and_cond)
                and_cond = []
            and_cond.append(condition)
        if and_cond:
            or_cond.append(and_cond)
        self.dimension_check = load_condition_instance(or_cond, False)

    def assign_group(self):
        return {"group_id": self.assign_rule["assign_group_id"]}

    @property
    def rule_id(self):
        return self.assign_rule.get("id")

    @property
    def snap_rule_id(self):
        if self.assign_rule_snap:
            return self.assign_rule_snap.get("id")

    @property
    def is_changed(self):
        # 判断当前的分派规则是否已经发生了变化
        if self.is_new:
            return True
        # 比较分派的用户组和分派条件
        new_rule_md5 = count_md5(
            {
                "user_groups": self.assign_rule["user_groups"],
                "conditions": self.assign_rule["conditions"],
            }
        )
        snap_rule_md5 = count_md5(
            {
                "user_groups": self.assign_rule_snap["user_groups"],
                "conditions": self.assign_rule_snap["conditions"],
            }
        )
        return new_rule_md5 != snap_rule_md5

    @property
    def is_new(self):
        """
        是否为新增
        """
        if self.snap_rule_id is None:
            return True
        return self.snap_rule_id and self.rule_id and self.snap_rule_id != self.rule_id

    def is_matched(self, dimensions):
        """
        当前规则是否适配
        :param dimensions: 告警维度信息
        :return:
        """
        if self.is_changed:
            # 如果为新或者发生了变化，需要重新适配
            return self.dimension_check.is_match(dimensions)
        return True

    @property
    def user_groups(self):
        if not self.notice_action:
            # 如果没有通知配置，直接返回
            return []
        return self.assign_rule.get("user_groups", [])

    @property
    def notice_action(self):
        for action in self.assign_rule["actions"]:
            if not action.get("is_enabled"):
                logger.info("assign notice(%s) is not enabled", self.rule_id)
                continue
            if action["action_type"] == ActionPluginType.NOTICE:
                # 当有通知插件，并且开启了，才进行通知
                return action
        return {}

    @property
    def itsm_action(self):
        for action in self.assign_rule["actions"]:
            if action["action_type"] == ActionPluginType.ITSM and action.get("action_id"):
                return action

    @property
    def upgrade_rule(self):
        return UpgradeRuleMatch(self.notice_action.get("upgrade_config", {}))

    @property
    def additional_tags(self):
        return self.assign_rule.get("additional_tags", [])

    @property
    def alert_severity(self):
        return self.assign_rule.get("alert_severity", 0)

    @property
    def alert_duration(self):
        if self.alert:
            return self.alert.duration
        return 0

    @property
    def need_upgrade(self):
        current_time = int(time.time())

        last_upgrade_time = self.assign_rule_snap.get("last_upgrade_time", current_time)
        last_group_index = self.assign_rule_snap.get("last_group_index")
        latest_upgrade_interval = current_time - last_upgrade_time
        return self.upgrade_rule.need_upgrade(latest_upgrade_interval or self.alert_duration, last_group_index)

    def get_upgrade_user_group(self):
        """
        获取升级告警通知组
        :return:n
        """

        if not self.need_upgrade:
            # 不需要升级的情况下且从来没有过升级通知, 直接返回空
            return []

        last_group_index = self.assign_rule_snap.get("last_group_index")
        notice_groups, current_group_index = self.upgrade_rule.get_upgrade_user_group(
            last_group_index, self.need_upgrade
        )
        if last_group_index == current_group_index:
            # 如果已经完全升级通知了，则表示全部知会给升级负责人
            return []
        self.assign_rule["last_group_index"] = current_group_index
        self.assign_rule["last_upgrade_time"] = int(time.time())
        logger.info(
            "alert(%s) upgraded by rule(%s), current group index(%s), last_group_index(%s), last_upgrade_time(%s)",
            self.alert.id,
            self.assign_rule["id"],
            current_group_index,
            self.assign_rule_snap.get("last_group_index"),
            self.assign_rule_snap.get("last_upgrade_time"),
        )
        return notice_groups

    def notice_user_groups(self):
        """
        告警负责人
        """
        if not self.notice_action:
            # 没有通知事件，忽略
            return []
        return self.user_groups

    @property
    def user_type(self):
        """
        告警关注人
        """
        return self.assign_rule.get("user_type", UserGroupType.MAIN)


class AlertAssignMatchManager:
    """
    告警分派管理
    """

    def __init__(
        self,
        alert: AlertDocument,
        notice_users=None,
        group_rules: list = None,
        assign_mode=None,
        notice_type=None,
        cmdb_attrs=None,
    ):
        """
        :param alert: 告警
        :param notice_users: 通知人员
        :param group_rules: 指定的分派规则, 以优先级
        """
        self.alert = alert
        self.origin_severity = alert.severity
        # 仅通知情况下
        self.origin_notice_users_object = None
        self.notice_users = notice_users or []
        # 针对存量的数据，默认为通知+分派规则
        self.assign_mode = assign_mode or [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
        self.notice_type = notice_type
        self.cmdb_dimensions = self.get_match_cmdb_dimensions(cmdb_attrs)
        self.dimensions = self.get_match_dimensions()
        extra_info = self.alert.extra_info.to_dict() if self.alert.extra_info else {}
        self.rule_snaps = extra_info.get("rule_snaps") or {}
        self.bk_biz_id = self.alert.event.bk_biz_id
        self.group_rules = group_rules or []
        self.matched_rules: List[AssignRuleMatch] = []
        self.matched_rule_info = {
            "notice_upgrade_user_groups": [],
            "follow_groups": [],
            "notice_appointees": [],
            "itsm_actions": {},
            "severity": 0,
            "additional_tags": [],
            "rule_snaps": {},
            "group_info": {},
        }
        self.severity_source = ""

    def get_match_cmdb_dimensions(self, cmdb_attrs):
        """
        获取CMDB相关的维度信息
        """
        if not cmdb_attrs:
            return {}
        host = cmdb_attrs["host"]
        if not host:
            # 如果不存在主机，也不会存在拓扑信息，直接返回
            return {}
        cmdb_dimensions = defaultdict(list)
        for attr_key, attr_value in host.get_attrs().items():
            cmdb_dimensions[f"host.{attr_key}"].append(attr_value)
        for biz_set in cmdb_attrs["sets"]:
            if not biz_set:
                # 如果当前缓存获取的信息不正确，忽略属性，避免直接报错
                continue
            for attr_key, attr_value in biz_set.get_attrs().items():
                cmdb_dimensions[f"set.{attr_key}"].append(attr_value)
        for biz_module in cmdb_attrs["modules"]:
            if not biz_module:
                continue
            for attr_key, attr_value in biz_module.get_attrs().items():
                cmdb_dimensions[f"module.{attr_key}"].append(attr_value)
        return cmdb_dimensions

    def get_match_dimensions(self):
        """
        获取当前告警的维度
        :return:
        """
        # 第一部分： 告警的属性字段
        dimensions = {
            "alert.event_source": getattr(self.alert.event, "plugin_id", None),
            "alert.scenario": self.alert.strategy["scenario"] if self.alert.strategy else "",
            "alert.strategy_id": str(self.alert.strategy["id"]) if self.alert.strategy else "",
            "alert.name": self.alert.alert_name,
            "alert.metric": [m for m in self.alert.event.metric],
            "alert.labels": list(getattr(self.alert, "labels", [])),
            "labels": list(getattr(self.alert, "labels", [])),
            "is_empty_users": "true" if not self.notice_users else "false",
            "notice_users": self.notice_users,
            "ip": getattr(self.alert.event, "ip", None),
            "bk_cloud_id": str(self.alert.event.bk_cloud_id) if hasattr(self.alert.event, "bk_cloud_id") else None,
        }
        # 第二部分： 告警维度
        alert_dimensions = [d.to_dict() for d in self.alert.dimensions]
        dimensions.update(
            {d["key"][5:] if d["key"].startswith("tags.") else d["key"]: d.get("value", "") for d in alert_dimensions}
        )
        origin_alarm_dimensions = self.alert.origin_alarm["data"]["dimensions"] if self.alert.origin_alarm else {}
        dimensions.update(origin_alarm_dimensions)

        # 第三部分： 第三方接入告警，直接使用tags内容
        alert_tags = [d.to_dict() for d in self.alert.event.tags]
        dimensions.update({f'tags.{d["key"]}': d.get("value", "") for d in alert_tags})

        # 第四部分： cmdb相关的节点属性
        dimensions.update(self.cmdb_dimensions)

        return dimensions

    def get_matched_rules(self) -> List[AssignRuleMatch]:
        """
        适配分派规则
        :return:
        """
        matched_rules = []
        if AssignMode.BY_RULE not in self.assign_mode:
            # 如果不需要分派的，不要进行规则匹配
            return matched_rules
        for rules in self.group_rules:
            for rule in rules:
                if not rule.get("is_enabled"):
                    # 没有开启的直接返回
                    continue
                rule_match_obj = AssignRuleMatch(rule, self.rule_snaps.get(str(rule.get("id", ""))), self.alert)
                if rule_match_obj.is_matched(dimensions=self.dimensions):
                    matched_rules.append(rule_match_obj)
            if matched_rules:
                # 当前优先级下适配到分派规则，停止低优先级的适配
                break
        return matched_rules

    def get_itsm_actions(self):
        """
        获取流程的规则对应的通知组
        """
        itsm_user_groups = defaultdict(list)
        for rule_obj in self.matched_rules:
            if not rule_obj.itsm_action:
                continue
            itsm_user_groups[rule_obj.itsm_action["id"]].extend(rule_obj.user_groups)
        return itsm_user_groups

    def get_notice_user_groups(self):
        """
        获取适配的规则对应的通知组
        """
        notice_user_groups = []
        for rule_obj in self.matched_rules:
            rule_user_groups = [group_id for group_id in rule_obj.user_groups if group_id not in notice_user_groups]
            notice_user_groups.extend(rule_user_groups)
        return set(notice_user_groups)

    @property
    def severity(self):
        return self.matched_rule_info["severity"]

    @property
    def additional_tags(self):
        return self.matched_rule_info["additional_tags"]

    @property
    def new_rule_snaps(self):
        return self.matched_rule_info["rule_snaps"]

    @property
    def matched_group_info(self):
        return self.matched_rule_info["group_info"]

    def get_matched_rule_info(self):
        if not self.matched_rules:
            return
        notice_user_groups = []
        follow_groups = []
        itsm_user_groups = defaultdict(list)
        all_severity = []
        additional_tags = []
        new_rule_snaps = {}
        for rule_obj in self.matched_rules:
            additional_tags.extend(rule_obj.additional_tags)
            all_severity.append(rule_obj.alert_severity or self.alert.severity)

            # 当有升级变动的时候才真正进行升级获取和记录
            user_groups = rule_obj.get_upgrade_user_group() if self.notice_type == "upgrade" else rule_obj.user_groups
            if rule_obj.user_type == UserGroupType.FOLLOWER:
                follow_groups.extend([group_id for group_id in user_groups if group_id not in follow_groups])
            else:
                new_groups = [group_id for group_id in user_groups if group_id not in notice_user_groups]
                notice_user_groups.extend(new_groups)
            # 需要叠加更新
            rule_obj.assign_rule_snap.update(rule_obj.assign_rule)
            new_rule_snaps[str(rule_obj.rule_id)] = rule_obj.assign_rule_snap
            if rule_obj.itsm_action:
                itsm_user_groups[rule_obj.itsm_action["action_id"]].extend(rule_obj.user_groups)

        self.matched_rule_info = {
            "notice_appointees": notice_user_groups,
            "follow_groups": follow_groups,
            "itsm_actions": {action_id: user_groups for action_id, user_groups in itsm_user_groups.items()},
            "severity": min(all_severity),
            "additional_tags": additional_tags,
            "rule_snaps": new_rule_snaps,
            # 组名取一个即可
            "group_info": {
                "group_id": self.matched_rules[0].assign_rule["assign_group_id"],
                "group_name": self.matched_rules[0].assign_rule.get("group_name", ""),
            },
        }

    def run_match(self):
        """
        执行规则适配
        """
        self.matched_rules = self.get_matched_rules()
        if self.matched_rules:
            assign_severity = max([rule_obj.alert_severity for rule_obj in self.matched_rules])
            self.severity_source = AssignMode.BY_RULE if assign_severity > 0 else ""
            self.get_matched_rule_info()
            self.alert.severity = self.matched_rule_info["severity"] or self.alert.severity
            # 告警分派不维持原样的则为分派，优先级最高，其他场景位置
            self.alert.extra_info["severity_source"] = self.severity_source
            self.alert.extra_info["rule_snaps"] = self.matched_rule_info["rule_snaps"]
            self.update_assign_tags()

    def get_alert_log(self):
        """
        获取告警分派流水日志
        """
        if not self.matched_rules:
            # 如果没有适配到告警规则，忽略
            return
        current_time = int(time.time())
        if self.severity and self.severity != self.origin_severity:
            logger.info(
                "Change alert(%s) severity from %s to %s by rule", self.alert.id, self.origin_severity, self.severity
            )
            content = _("告警适配到自动分派规则组${}$, 级别由【{}】调整至【{}】").format(
                self.matched_group_info["group_name"],
                EVENT_SEVERITY_DICT.get(self.origin_severity, self.origin_severity),
                EVENT_SEVERITY_DICT.get(self.severity, self.severity),
            )
        else:
            content = _("告警适配到自动分派规则组${}$, 级别维持【{}】不变").format(
                self.matched_group_info["group_name"],
                EVENT_SEVERITY_DICT.get(self.origin_severity, self.origin_severity),
                EVENT_SEVERITY_DICT.get(self.severity, self.severity),
            )
        description = {
            "text": content,
            "url": urllib.parse.urljoin(
                settings.BK_MONITOR_HOST,
                "?bizId={bk_biz_id}#/alarm-dispatch?group_id={group_id}".format(
                    bk_biz_id=self.bk_biz_id, group_id=self.matched_group_info["group_id"]
                ),
            ),
            "action_plugin_type": "assign",
        }
        alert_log = dict(
            op_type=AlertLog.OpType.ACTION,
            event_id=current_time,
            alert_id=self.alert.id,
            severity=self.severity,
            description=json.dumps(description),
            create_time=current_time,
            time=current_time,
        )
        return alert_log

    def update_assign_tags(self):
        """
        更新分派的tags
        :return:
        """
        assign_tags = {item["key"]: item for item in self.alert.assign_tags}
        additional_tags = {item["key"]: item for item in self.matched_rule_info["additional_tags"]}
        assign_tags.update(additional_tags)
        self.alert.assign_tags = list(assign_tags.values())

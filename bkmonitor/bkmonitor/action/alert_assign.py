"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from collections import defaultdict
from functools import cached_property

from django.utils.translation import gettext as _

from bkmonitor.documents import AlertDocument, AlertLog
from bkmonitor.utils.common_utils import count_md5
from bkmonitor.utils.range import load_condition_instance
from constants.action import ActionPluginType, AssignActionType, AssignMode, UserGroupType
from constants.alert import AI_ANALYZE_TAG, EVENT_SEVERITY_DICT, NOISE_TAG
from core.drf_resource import api

logger = logging.getLogger("fta_action.run")

LEGACY_ACTION_TYPES = {ActionPluginType.NOTICE, ActionPluginType.ITSM}
ORDINARY_ACTION_TYPES = LEGACY_ACTION_TYPES | {AssignActionType.AI_ANALYSIS}


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
        self.assign_rule_snap = dict(assign_rule_snap or {})
        self.alert = alert
        self.matched_types = set()
        self.apply_attributes = False

    @cached_property
    def dimension_check(self):
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
        return load_condition_instance(or_cond, False)

    def assign_group(self):
        return {
            "group_id": self.assign_rule["assign_group_id"],
            "group_name": self.assign_rule.get("group_name", self.assign_rule.get("name", "")),
        }

    def snapshot(self, *, history_only=False):
        snapshot = {key: value for key, value in self.assign_rule.items() if key not in ("alerts", "suppressed_alerts")}
        if history_only:
            # 被压制的规则仅用于展示配置，无需复制动态组展开后的主机全集。
            if "configured_conditions" in snapshot:
                snapshot.pop("conditions")
        else:
            # 当前配置与同一生效规则的升级进度一起保存，供后续通知使用。
            for field in ("last_group_index", "last_upgrade_time"):
                if field in self.assign_rule_snap:
                    snapshot[field] = self.assign_rule_snap[field]
        return snapshot

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
                "user_groups": self.assign_rule.get("user_groups", []),
                "conditions": self.assign_rule["conditions"],
            }
        )
        snap_rule_md5 = count_md5(
            {
                "user_groups": self.assign_rule_snap.get("user_groups", []),
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

    @cached_property
    def actions(self):
        actions = {}
        for action in self.assign_rule.get("actions", []):
            kind = action["action_type"]
            if kind not in ORDINARY_ACTION_TYPES and kind != AssignActionType.NOISE:
                continue
            # 历史 ITSM 配置只存 action_id，没有 is_enabled。
            if not action.get("is_enabled", kind == ActionPluginType.ITSM):
                continue
            if kind == ActionPluginType.ITSM and not action.get("action_id"):
                continue
            actions.setdefault(kind, action)
        return actions

    @property
    def notice_action(self):
        return self.actions.get(ActionPluginType.NOTICE, {})

    @property
    def itsm_action(self):
        return self.actions.get(ActionPluginType.ITSM)

    @property
    def has_attributes(self):
        # 旧分派的级别、标签沿用第一个命中层。只有新增动作的规则不抢占这层。
        return bool(self.actions.keys() & LEGACY_ACTION_TYPES or self.alert_severity or self.additional_tags)

    @property
    def overrides_notice(self):
        return bool(self.matched_types & LEGACY_ACTION_TYPES or (self.apply_attributes and not self.actions))

    @property
    def upgrade_rule(self):
        return UpgradeRuleMatch(self.notice_action.get("upgrade_config", {}))

    @property
    def additional_tags(self):
        return [tag for tag in self.assign_rule.get("additional_tags", []) if tag["key"] != NOISE_TAG]

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
        self.assign_rule_snap["last_group_index"] = current_group_index
        self.assign_rule_snap["last_upgrade_time"] = int(time.time())
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


class AlertMatchContext:
    """告警条件匹配上下文，不包含分派规则或分派结果。"""

    def __init__(self, alert: AlertDocument, notice_users=None, cmdb_attrs=None):
        self.alert = alert
        self.origin_severity = alert.severity
        self.notice_users = notice_users or []
        self.bk_biz_id = self.alert.event.bk_biz_id
        self.cmdb_dimensions = self.get_match_cmdb_dimensions(cmdb_attrs)
        self.dimensions = self.get_match_dimensions()

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
            # 新增bk_host_id 用以匹配动态分组
            "bk_host_id": str(self.alert.event.bk_host_id) if hasattr(self.alert.event, "bk_host_id") else None,
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
        dimensions.update({f"tags.{d['key']}": d.get("value", "") for d in alert_tags})

        # 第四部分： cmdb相关的节点属性
        dimensions.update(self.cmdb_dimensions)

        return dimensions

    def get_host_ids_by_dynamic_groups(self, dynamic_group_ids):
        host_ids = set()
        dynamic_group_hosts = api.cmdb.batch_execute_dynamic_group(
            bk_biz_id=self.bk_biz_id, ids=dynamic_group_ids, bk_obj_id="host"
        )
        for dynamic_group_host in dynamic_group_hosts.values():
            for host in dynamic_group_host:
                host_ids.add(host.bk_host_id)

        return list(host_ids)


class AlertAssignMatchManager(AlertMatchContext):
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
        explain=False,
        dynamic_group_hosts=None,
    ):
        """
        :param alert: 告警
        :param notice_users: 通知人员
        :param group_rules: 指定的分派规则, 以优先级
        """
        super().__init__(alert, notice_users=notice_users, cmdb_attrs=cmdb_attrs)
        # 仅通知情况下
        self.origin_notice_users_object = None
        # 针对存量的数据，默认为通知+分派规则
        self.assign_mode = assign_mode or [AssignMode.ONLY_NOTICE, AssignMode.BY_RULE]
        self.notice_type = notice_type
        extra_info = self.alert.extra_info.to_dict() if self.alert.extra_info else {}
        self.rule_snaps = extra_info.get("rule_snaps") or {}
        self.group_rules = group_rules or []
        self.explain = explain
        self.dynamic_group_hosts = dynamic_group_hosts if dynamic_group_hosts is not None else {}
        self.matched_rules: list[AssignRuleMatch] = []
        self.matched_rule_info = {
            "notice_upgrade_user_groups": [],
            "follow_groups": [],
            "notice_appointees": [],
            "itsm_actions": {},
            "severity": 0,
            "additional_tags": [],
            "rule_snaps": {},
            "group_info": {},
            "dispatch_result": {"ai_analysis": None, "noise": False},
            "matched_rules": [],
        }
        self.severity_source = ""

    def iter_priority_rules(self):
        """调试使用调用方排好序的规则，后台按需从缓存取下一层。"""
        for rules in self.group_rules:
            if rules:
                yield rules[0].get("priority"), rules

    def resolve_conditions(self, rule):
        if not any(condition["field"] == "dynamic_group" for condition in rule["conditions"]):
            return rule
        conditions = []
        for condition in rule["conditions"]:
            if condition["field"] == "dynamic_group":
                group_ids = tuple(condition["value"])
                if group_ids not in self.dynamic_group_hosts:
                    self.dynamic_group_hosts[group_ids] = self.get_host_ids_by_dynamic_groups(list(group_ids))
                condition = {**condition, "value": self.dynamic_group_hosts[group_ids], "field": "bk_host_id"}
            conditions.append(condition)
        return {**rule, "conditions": conditions, "configured_conditions": rule["conditions"]}

    def get_matched_rules(self, *, record_history=False) -> list[AssignRuleMatch]:
        matched_rules = []
        self.matched_rule_info["matched_rules"] = []
        self.matched_rule_info["rule_snaps"] = {}
        if AssignMode.BY_RULE not in self.assign_mode:
            return matched_rules
        if record_history:
            self.matched_rule_info["history_complete"] = True
        explain = record_history or self.explain
        settled = False
        try:
            for rules, settled in self._match_priority_tiers(explain, record_history):
                matched_rules.extend(rules)
                if settled and not explain:
                    break
        except Exception:
            # 已裁决的动作不依赖后续层。补充历史失败时直接保留结果，避免重新取缓存。
            if not (settled and record_history):
                raise
            self._mark_history_incomplete()
        return matched_rules

    def _mark_history_incomplete(self):
        self.matched_rule_info["history_complete"] = False
        logger.exception("alert(%s) failed to collect full dispatch history", self.alert.id)

    def _match_priority_tiers(self, explain, record_history):
        resolved = set()
        attributes_resolved = False
        noise = AssignActionType.NOISE
        for priority, rules in self.iter_priority_rules():
            hits = []
            for rule in rules:
                if not rule.get("is_enabled"):
                    continue
                match = AssignRuleMatch(rule, self.rule_snaps.get(str(rule.get("id"))), self.alert)
                possible = match.actions.keys() - resolved
                if resolved & ORDINARY_ACTION_TYPES:
                    possible.discard(noise)
                needed = noise not in resolved and (possible or (not attributes_resolved and match.has_attributes))
                if not (needed or explain):
                    continue
                try:
                    match.assign_rule = self.resolve_conditions(rule)
                    if match.is_matched(self.dimensions):
                        hits.append(match)
                except Exception:
                    if needed or not record_history:
                        raise
                    # 本条规则已被压制，其他层仍可能有尚未裁决的动作。
                    self._mark_history_incomplete()

            tier_types = {kind for hit in hits for kind in hit.actions}
            winners = tier_types - resolved
            noise_reason = (
                "higher_priority_ordinary" if resolved & ORDINARY_ACTION_TYPES else "ordinary_at_same_priority"
            )
            if noise in resolved:
                winners.clear()
            elif (resolved | tier_types) & ORDINARY_ACTION_TYPES:
                winners.discard(noise)

            matched_rules = []
            for hit in hits:
                hit.matched_types = hit.actions.keys() & winners
                hit.apply_attributes = not attributes_resolved and noise not in resolved and hit.has_attributes
                if hit.matched_types or hit.apply_attributes:
                    matched_rules.append(hit)
                elif record_history:
                    self.matched_rule_info["rule_snaps"][str(hit.rule_id)] = hit.snapshot(history_only=True)
                suppressed = {}
                for kind in hit.actions.keys() - hit.matched_types:
                    if noise in resolved and kind != noise:
                        suppressed[kind] = "noise_won"
                    elif kind == noise and noise not in resolved:
                        suppressed[kind] = noise_reason
                    else:
                        suppressed[kind] = "higher_priority_same_type"
                self.matched_rule_info["matched_rules"].append(
                    {
                        "rule_id": hit.rule_id,
                        **hit.assign_group(),
                        "priority": priority,
                        "action_types": sorted(hit.matched_types),
                        "suppressed_actions": suppressed,
                    }
                )

            resolved.update(winners)
            attributes_resolved |= any(hit.apply_attributes for hit in hits)
            yield matched_rules, noise in resolved or ORDINARY_ACTION_TYPES <= resolved

    def get_itsm_actions(self):
        """
        获取流程的规则对应的通知组
        """
        return self.matched_rule_info["itsm_actions"]

    def get_notice_user_groups(self):
        """
        获取适配的规则对应的通知组
        """
        return set(self.matched_rule_info["notice_appointees"]) | set(self.matched_rule_info["follow_groups"])

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
        ai_groups = None
        noise = False
        for rule_obj in self.matched_rules:
            if rule_obj.apply_attributes:
                additional_tags.extend(rule_obj.additional_tags)
                all_severity.append(rule_obj.alert_severity or self.alert.severity)
                if rule_obj.alert_severity:
                    self.severity_source = AssignMode.BY_RULE
            if ActionPluginType.NOTICE in rule_obj.matched_types:
                groups = rule_obj.get_upgrade_user_group() if self.notice_type == "upgrade" else rule_obj.user_groups
                receivers = follow_groups if rule_obj.user_type == UserGroupType.FOLLOWER else notice_user_groups
                receivers.extend(groups)
            if ActionPluginType.ITSM in rule_obj.matched_types:
                itsm_user_groups[rule_obj.itsm_action["action_id"]].extend(rule_obj.user_groups)
            if AssignActionType.AI_ANALYSIS in rule_obj.matched_types:
                if ai_groups is None:
                    ai_groups = []
                ai_action = rule_obj.actions[AssignActionType.AI_ANALYSIS]
                ai_groups.extend(ai_action.get("user_groups", rule_obj.assign_rule.get("user_groups", [])))
            noise |= AssignActionType.NOISE in rule_obj.matched_types
            new_rule_snaps[str(rule_obj.rule_id)] = rule_obj.snapshot()

        if noise or ai_groups is not None:
            # 老规则通过追加标签触发 AI；显式动作裁决后由告警构造器统一写系统标签。
            additional_tags = [tag for tag in additional_tags if tag["key"] != AI_ANALYZE_TAG]
        self.matched_rule_info.update(
            {
                "notice_appointees": list(dict.fromkeys(notice_user_groups)),
                "follow_groups": list(dict.fromkeys(follow_groups)),
                "itsm_actions": {
                    action_id: list(dict.fromkeys(groups)) for action_id, groups in itsm_user_groups.items()
                },
                "dispatch_result": {
                    "ai_analysis": None if ai_groups is None else {"user_groups": list(dict.fromkeys(ai_groups))},
                    "noise": noise,
                },
                "severity": min(all_severity, default=0),
                "additional_tags": additional_tags,
                # 历史消费者只接受一个规则组，保留最高生效组。
                "group_info": self.matched_rules[0].assign_group(),
            }
        )
        # 重试和升级只继承生效规则。告警详情另存所有实际命中的配置。
        self.alert.extra_info["rule_snaps"] = new_rule_snaps
        self.matched_rule_info["rule_snaps"].update(new_rule_snaps)

    def run_match(self):
        """
        执行规则适配
        """
        self.matched_rules = self.get_matched_rules()
        if self.matched_rules:
            self.get_matched_rule_info()
            if self.severity:
                self.alert.severity = self.severity
                self.alert.extra_info["severity_source"] = self.severity_source
            self.update_assign_tags()

    def get_alert_log(self, evaluated_at=None):
        """
        获取告警分派流水日志
        """
        if not self.matched_rules:
            # 如果没有适配到告警规则，忽略
            return
        current_time = evaluated_at if evaluated_at is not None else int(time.time())
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
                EVENT_SEVERITY_DICT.get(self.alert.severity, self.alert.severity),
            )
        description = {
            "text": content,
            # ?bizId={bk_biz_id}#/alarm-dispatch?group_id={group_id}
            "router_info": {
                "router_name": "alarm-dispatch",
                "params": {"biz_id": self.bk_biz_id, "group_id": self.matched_group_info["group_id"]},
            },
            "action_plugin_type": "assign",
            "dispatch_evaluation": {
                "status": "matched",
                "evaluated_at": current_time,
                "matched_rules": self.matched_rule_info["matched_rules"],
                "dispatch_result": self.matched_rule_info["dispatch_result"],
            },
        }
        alert_log = dict(
            op_type=AlertLog.OpType.ACTION,
            event_id=current_time,
            alert_id=self.alert.id,
            severity=self.severity or self.alert.severity,
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

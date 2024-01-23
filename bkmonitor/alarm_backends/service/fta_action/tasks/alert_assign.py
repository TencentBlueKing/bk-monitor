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
import logging
import time
from collections import defaultdict
from typing import List

from alarm_backends.core.cache.assign import AssignCacheManager
from alarm_backends.core.context import ActionContext
from alarm_backends.service.fta_action import AlertAssignee
from bkmonitor.action.alert_assign import (
    AlertAssignMatchManager,
    AssignRuleMatch,
    UpgradeRuleMatch,
)
from bkmonitor.documents import AlertDocument
from constants.action import ActionNoticeType, AssignMode, UserGroupType

logger = logging.getLogger("fta_action.run")


class BackendAssignMatchManager(AlertAssignMatchManager):
    """
    后台告警分派管理
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
        if cmdb_attrs is None:
            action_context = ActionContext(action=None, alerts=[alert], use_alert_snap=True)
            cmdb_attrs = {
                "host": action_context.target.host,
                "sets": action_context.target.sets,
                "modules": action_context.target.modules,
            }
        super(BackendAssignMatchManager, self).__init__(
            alert, notice_users, group_rules, assign_mode, notice_type, cmdb_attrs
        )

    def get_matched_rules(self) -> List[AssignRuleMatch]:
        """
        适配分派规则, 后台通过缓存获取
        :return:
        """
        matched_rules = []
        if self.assign_mode is None or AssignMode.BY_RULE not in self.assign_mode:
            # 如果没有分派规则或者当前配置不需要分派的情况下，不做分派适配
            return matched_rules
        for priority_id in AssignCacheManager.get_assign_priority_by_biz_id(self.bk_biz_id):
            groups = AssignCacheManager.get_assign_groups_by_priority(self.bk_biz_id, priority_id)
            group_rules = []
            for group_id in groups:
                group_rules.extend(AssignCacheManager.get_assign_rules_by_group(self.bk_biz_id, group_id))
            for rule in group_rules:
                rule_match_obj = AssignRuleMatch(rule, self.rule_snaps.get(str(rule["id"])), self.alert)
                if rule_match_obj.is_matched(dimensions=self.dimensions):
                    matched_rules.append(rule_match_obj)
            if matched_rules:
                # 当前优先级下适配到分派规则，停止低优先级的适配
                break
        return matched_rules


class AlertAssigneeManager:
    """
    告警处理通知人管理模块
    """

    def __init__(
        self,
        alert: AlertDocument,
        notice_user_groups=None,
        assign_mode=None,
        upgrade_config=None,
        notice_type=None,
        user_type=UserGroupType.MAIN,
    ):
        self.alert = alert
        self.assign_mode = assign_mode or [AssignMode.ONLY_NOTICE]
        self.notice_type = notice_type
        self.upgrade_rule = UpgradeRuleMatch(upgrade_config=upgrade_config or {})
        self.user_type = user_type

        if self.notice_type == ActionNoticeType.UPGRADE:
            # 如果是升级通知，采用升级通知里的配置
            self.origin_notice_users_object = self.get_origin_supervisor_object()
        else:
            self.origin_notice_users_object = self.get_origin_notice_users_object(notice_user_groups)
        self.matched_group = None
        self.is_matched = False
        self.match_manager = self.get_match_manager()
        self.notice_appointees_object = self.get_notice_appointees_object()

    def get_match_manager(self):
        """
        生成告警分派管理对象
        :return:
        """
        if AssignMode.BY_RULE not in self.assign_mode:
            self.match_manager = None
            logger.info(
                "ignore to run assign match for alert(%s) because of by_rule not in assign_mode(%s)",
                self.alert.id,
                self.assign_mode,
            )
            return
        logger.info("start to run assign match for alert(%s)", self.alert.id)

        # 需要获取所有的通知人员信息，包含chatID
        manager = BackendAssignMatchManager(
            self.alert,
            self.get_origin_notice_all_receivers(),
            assign_mode=self.assign_mode,
            notice_type=self.notice_type,
        )
        manager.run_match()
        if manager.matched_rules:
            self.is_matched = True
        self.matched_group = manager.matched_group_info.get("group_id")
        logger.info(
            "end run assign match for alert(%s), matched_rule(%s), assign results(%s)",
            self.alert.id,
            len(manager.matched_rules),
            manager.matched_group_info.get("group_id"),
        )
        return manager

    def get_notify_info(self, user_type=UserGroupType.MAIN):
        """
        获取通知渠道和通知人员信息
        """
        notify_configs = defaultdict(list)
        if self.is_matched:
            # 如果适配到了，直接发送给分派的负责人
            if self.notice_appointees_object:
                self.notice_appointees_object.get_notice_receivers(notify_configs=notify_configs, user_type=user_type)
        elif self.origin_notice_users_object:
            # 有默认通知的话，就加上默认通知人员
            self.origin_notice_users_object.get_notice_receivers(notify_configs=notify_configs, user_type=user_type)
        return notify_configs

    def get_appointee_notify_info(self, notify_configs=None):
        """
        获取告警负责人的通知信息
        """
        notify_configs = notify_configs or defaultdict(list)
        if self.is_matched:
            # 如果适配到了，直接发送给分派的负责人
            if self.notice_appointees_object:
                self.notice_appointees_object.add_appointee_to_notify_group(notify_configs=notify_configs)
        elif self.origin_notice_users_object:
            # 有默认通知的话，就加上默认通知人员
            self.origin_notice_users_object.add_appointee_to_notify_group(notify_configs=notify_configs)
        return notify_configs

    def get_assignees(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        获取对应的通知人员 包含指派的通知人员 和 设置的通知人员
        """
        if self.is_matched:
            # 如果当前已经有分派适配，则只返回指派的人员
            return self.get_notice_appointees(by_group, user_type)
        else:
            return self.get_origin_notice_receivers(by_group, user_type)

    @property
    def itsm_actions(self):
        if self.match_manager:
            return self.match_manager.matched_rule_info["itsm_actions"]
        return {}

    def get_appointees(self, action_id=None, user_type=UserGroupType.MAIN):
        """
        # 获取分派的负责人
        """
        if action_id and action_id in self.itsm_actions:
            # 根据对应的动作配置找到负责人
            return AlertAssignee(self.alert, self.itsm_actions[action_id]).get_assignee_by_user_groups(
                user_type=user_type
            )

        return self.get_assignees(user_type=user_type)

    def get_supervisors(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        获取当前运行的升级人员
        """
        if not self.is_matched:
            # 如果没有适配到规则，用默认通知的关注人信息
            return self.get_origin_notice_supervisors(by_group, user_type=user_type)

        if self.notice_appointees_object:
            return self.notice_appointees_object.get_assignee_by_user_groups(by_group, user_type=user_type)
        return None

    def get_notice_appointees(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        获取分派的人员信息
        """
        # 获取通知分派的人员
        if self.notice_appointees_object:
            return self.notice_appointees_object.get_assignee_by_user_groups(by_group, user_type)
        return {} if by_group else []

    def get_notice_appointees_object(self):
        """
        获取通知分派人的获取对象
        :return:
        """
        if not self.is_matched:
            # 没有适配到，直接返回
            return
        matched_info = self.match_manager.matched_rule_info
        return AlertAssignee(self.alert, matched_info["notice_appointees"], matched_info["follow_groups"])

    def get_origin_notice_receivers(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        获取默认通知的所有接受人员
        """
        if self.origin_notice_users_object is None:
            return {} if by_group else []
        return self.origin_notice_users_object.get_assignee_by_user_groups(by_group, user_type=user_type)

    def get_origin_notice_all_receivers(self):
        """
        获取所有的原始告警的接收人员，包含机器人会话ID
        """
        if self.origin_notice_users_object is None:
            return {}
        return self.origin_notice_users_object.get_notice_receivers()

    def get_origin_supervisor_object(self):
        """
        获取原升级告警关注人员
        """
        if self.notice_type != ActionNoticeType.UPGRADE or AssignMode.ONLY_NOTICE not in self.assign_mode:
            # 没有设置通知的情况下，默认为空
            return None
        current_time = int(time.time())
        upgrade_notice = self.alert.extra_info.to_dict().get("upgrade_notice", {})
        last_group_index = upgrade_notice.get("last_group_index")
        last_upgrade_time = upgrade_notice.get("last_upgrade_time", current_time)
        latest_upgrade_interval = current_time - last_upgrade_time
        alert_duration = self.alert.duration or 0
        need_upgrade = self.upgrade_rule.need_upgrade(latest_upgrade_interval or alert_duration)
        if not need_upgrade:
            return None
        # 需要升级的时候
        user_groups, current_group_index = self.upgrade_rule.get_upgrade_user_group(last_group_index, need_upgrade)
        if current_group_index != last_group_index:
            logger.info(
                "alert(%s) upgraded by origin notice, current_group_index(%s), "
                "last_group_index(%s), last_upgrade_time(%s)",
                self.alert.id,
                current_group_index,
                last_group_index,
                last_upgrade_time,
            )
            self.alert.extra_info["upgrade_notice"] = {
                "last_group_index": current_group_index,
                "last_upgrade_time": current_time,
            }
        follow_groups = []
        if self.user_type == UserGroupType.FOLLOWER:
            follow_groups = user_groups
            user_groups = []
        return AlertAssignee(self.alert, user_groups=user_groups, follow_groups=follow_groups)

    def get_origin_notice_supervisors(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        获取默认通知的关注人员
        """
        empty_supervisors = {} if by_group else []
        if not self.origin_notice_users_object:
            # 没有设置通知的情况下，默认为空
            return empty_supervisors

        return self.origin_notice_users_object.get_assignee_by_user_groups(by_group, user_type=user_type)

    def get_origin_notice_users_object(self, user_groups):
        """
        获取仅通知的
        :param user_groups: 负责人
        :return:
        """
        if AssignMode.ONLY_NOTICE not in self.assign_mode:
            # 没有设置通知的情况下，默认为空
            return None

        follow_groups = []
        if self.user_type == UserGroupType.FOLLOWER:
            follow_groups = user_groups
            user_groups = []

        return AlertAssignee(self.alert, user_groups=user_groups, follow_groups=follow_groups)

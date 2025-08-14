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
import calendar
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import List

import pytz
from dateutil.relativedelta import relativedelta
from django.utils.translation import gettext as _

from alarm_backends.core.cache.cmdb.host import HostManager
from alarm_backends.core.cache.cmdb.module import ModuleManager
from alarm_backends.core.cache.key import ALERT_DETECT_RESULT
from alarm_backends.core.context import ActionContext
from alarm_backends.core.context.utils import (
    get_business_roles,
    get_notice_display_mapping,
)
from alarm_backends.core.i18n import i18n
from alarm_backends.service.converge.dimension import DimensionCalculator
from alarm_backends.service.converge.tasks import run_converge
from bkmonitor.documents import ActionInstanceDocument, AlertDocument
from bkmonitor.models import ActionInstance, DutyArrange, DutyPlan, UserGroup
from bkmonitor.utils import time_tools
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ActionNoticeType,
    ActionPluginType,
    ActionStatus,
    ConvergeType,
    NoticeChannel,
    NoticeType,
    NoticeWay,
    UserGroupType,
)

logger = logging.getLogger("fta_action.run")


class PushActionProcessor:
    @classmethod
    def push_actions_to_queue(
        cls, generate_uuid, alerts=None, is_shielded=False, need_noise_reduce=False, notice_config=None
    ):
        """推送处理事件至收敛队列"""
        if not alerts:
            logger.info(
                "[create actions]skip to create sub action for generate_uuid(%s) because of no alert",
                generate_uuid,
            )
            return []

        if is_shielded or need_noise_reduce:
            logger.info(
                "[create actions]alert(%s) is shielded(%s) or need_noise_reduce(%s), "
                "skip to create sub action for generate_uuid(%s)",
                alerts[0].id,
                is_shielded,
                need_noise_reduce,
                generate_uuid,
            )
        else:
            # 如果没有屏蔽，才创建子任务
            for action_instance in ActionInstance.objects.filter(generate_uuid=generate_uuid, is_parent_action=True):
                # 有父任务的事件，先需要创建对应的子任务
                sub_actions = action_instance.create_sub_actions()
                logger.info(
                    "[create actions]create sub notice actions %s for parent action(%s), exclude_notice_ways(%s)",
                    len(sub_actions),
                    action_instance.id,
                    "|".join(action_instance.inputs.get("exlude_notice_ways") or []),
                )

        action_instances = ActionInstance.objects.filter(generate_uuid=generate_uuid)
        if need_noise_reduce:
            action_instances = action_instances.filter(is_parent_action=False)
        action_instances = list(action_instances)
        cls.push_actions_to_converge_queue(action_instances, {generate_uuid: alerts}, notice_config)
        return [action.id for action in action_instances]

    @classmethod
    def push_actions_to_converge_queue(cls, action_instances, action_alert_relations, notice_config=None):
        """
        推送告警至收敛汇总队列
        """
        for action_instance in action_instances:
            converge_config = None
            alerts = action_alert_relations[action_instance.generate_uuid]

            if action_instance.inputs.get("notice_way") != NoticeWay.VOICE:
                # 当通知策略是语音通知的时候，不走收敛模块， 通过执行模块进行收敛
                # 从策略中匹配防御规则
                # TODO 当没有策略的情况下的告警推送
                strategy = action_instance.strategy
                if strategy:
                    for action in strategy.get("actions", []) + [strategy.get("notice")]:
                        if action and action["id"] == action_instance.strategy_relation_id:
                            converge_config = action["options"].get("converge_config")

                if (
                    not converge_config
                    and action_instance.action_plugin.get("plugin_type") == ActionPluginType.NOTICE
                    and notice_config
                ):
                    converge_config = notice_config.get("options", {}).get("converge_config")

            if not converge_config:
                # 当不存在收敛策略的时候，直接忽略收敛，主要是用于手动操作部分的内容
                cls.push_action_to_execute_queue(action_instance, alerts)
                continue

            converge_info = DimensionCalculator(
                action_instance, converge_config=converge_config, alerts=alerts
            ).calc_dimension()
            task_id = run_converge.delay(
                converge_config,
                action_instance.id,
                ConvergeType.ACTION,
                converge_info["converge_context"],
                alerts=[alert.to_dict() for alert in alerts],
            )
            logger.info(
                "[push_actions_to_converge_queue] push action(%s) to converge queue, converge_config %s,  task id %s",
                action_instance.id,
                converge_config,
                task_id,
            )

    @classmethod
    def push_action_to_execute_queue(
        cls, action_instance, alerts=None, countdown=0, callback_func="execute", kwargs=None
    ):
        """
        直接推送告警到执行队列
        :param kwargs:
        :param callback_func: 处理回调函数
        :param action_instance: 告警处理动作
        :param alerts: 告警快照
        :param countdown: 告警延时
        :return:
        """
        from alarm_backends.service.fta_action.tasks import (
            run_action,
            run_webhook_action,
        )

        action_info = {"id": action_instance.id, "function": callback_func, "alerts": alerts}
        if kwargs:
            action_info.update({"kwargs": kwargs})
        plugin_type = action_instance.action_plugin["plugin_type"]
        if plugin_type in [
            ActionPluginType.WEBHOOK,
            ActionPluginType.MESSAGE_QUEUE,
        ]:
            task_id = run_webhook_action.apply_async((plugin_type, action_info), countdown=countdown)
        else:
            task_id = run_action.apply_async((plugin_type, action_info), countdown=countdown)
        logger.info(
            "[create actions]push queue(execute): action(%s) (%s), alerts(%s), task_id(%s)",
            action_instance.id,
            plugin_type,
            action_instance.alerts,
            task_id,
        )


def to_document(action_instance: ActionInstance, current_time, alerts=None):
    """
    转存ES格式
    """
    create_timestamp = int(action_instance.create_time.timestamp())
    last_update_time = action_instance.end_time or current_time

    last_update_timestamp = int(last_update_time.timestamp())

    action_status = (
        action_instance.status if action_instance.status in ActionStatus.END_STATUS else ActionStatus.RUNNING
    )
    notice_way = action_instance.inputs.get("notice_way")
    notice_way = ",".join(notice_way) if isinstance(notice_way, list) else notice_way
    notice_way_display = get_notice_display_mapping(notice_way)
    notice_receiver = action_instance.inputs.get("notice_receiver") or []
    operator = notice_receiver if isinstance(notice_receiver, list) else [notice_receiver]
    status_display = ACTION_DISPLAY_STATUS_DICT.get(action_status)
    if action_status == ActionStatus.FAILURE:
        status_display = _("{}, 失败原因：{}").format(status_display, action_instance.ex_data.get("message", "--"))

    converge_info = getattr(action_instance, "converge_info", {})
    action_info = dict(
        id="{}{}".format(create_timestamp, action_instance.id),
        raw_id=action_instance.id,
        create_time=create_timestamp,
        update_time=int(action_instance.update_time.timestamp()),
        signal=action_instance.signal,
        strategy_id=action_instance.strategy_id,
        alert_level=int(action_instance.alert_level),
        alert_id=list(set(action_instance.alerts)),
        # 针对非结束状态的中间状态统一归为执行中
        status=action_status,
        ex_data=action_instance.ex_data,
        content=action_instance.get_content(
            **{
                "notice_way_display": notice_way_display,
                "status_display": status_display,
                "action_name": action_instance.action_config.get("name", ""),
            }
        ),
        bk_biz_id=action_instance.bk_biz_id,
        action_config=action_instance.action_config,
        action_config_id=action_instance.action_config_id,
        action_name=action_instance.action_config.get("name", ""),
        action_plugin=action_instance.action_plugin,
        action_plugin_type=action_instance.action_plugin.get("plugin_key", ""),
        outputs=action_instance.outputs,
        inputs=action_instance.inputs,
        operator=operator or action_instance.assignee,
        duration=max(last_update_timestamp - create_timestamp, 0),
        end_time=int(action_instance.end_time.timestamp()) if action_instance.end_time else None,
        is_parent_action=action_instance.is_parent_action,
        parent_action_id=action_instance.parent_action_id,
        op_type=ActionInstanceDocument.OpType.ACTION,
        execute_times=action_instance.execute_times,
        failure_type=action_instance.failure_type,
        converge_id=converge_info.get("converge_id") or action_instance.inputs.get("converge_id", 0),
        is_converge_primary=converge_info.get("is_primary", False),
    )
    try:
        target_info = get_target_info_from_ctx(action_instance, alerts)
    except BaseException as error:
        target_info = action_instance.outputs.get("target_info", {})
        logger.debug("get_target_info_from_ctx failed %s action_id %s", error, action_instance.id)

    if action_info["action_plugin_type"] == ActionPluginType.NOTICE:
        target_info["operate_target_string"] = notice_way_display
    action_info.update(target_info)
    converge_info = getattr(action_instance, "converge_info", {})
    action_info.update(converge_info)
    return ActionInstanceDocument(**action_info)


def get_target_info_from_ctx(action_instance: ActionInstance, alerts: List[AlertDocument]):
    """获取目标信息"""
    if action_instance.outputs.get("target_info"):
        return action_instance.outputs["target_info"]

    action_ctx = ActionContext(action_instance, alerts=alerts, use_alert_snap=True)
    target = action_ctx.target
    target_info = {
        "bk_biz_name": target.business.bk_biz_name,
        "bk_target_display": action_ctx.alarm.target_display,
        "dimensions": [d.to_dict() for d in action_ctx.alarm.new_dimensions.values()],
        "strategy_name": action_instance.strategy.get("name") or "--",
        "operate_target_string": action_ctx.action_instance.operate_target_string,
    }
    try:
        host = target.host
    except BaseException as error:
        logger.info("get target host for alert %s error: %s", action_instance.alerts, str(error))
        host = None

    target_info.update(
        dict(
            bk_set_ids=host.bk_set_ids,
            bk_set_names=host.set_string,
            bk_module_ids=host.bk_module_ids,
            bk_module_names=host.module_string,
        )
        if host
        else {}
    )
    logger.debug("get_target_info_from_ctx, target_info %s, action_id %s", target_info, action_instance.id)
    return target_info


def need_poll(action_instance: ActionInstance):
    """
    查询当前策略当前维度的检测结果缓存
    :param action_instance: 事件
    :return:
    """
    if (
        len(action_instance.alerts) != 1
        or (action_instance.parent_action_id > 0)
        or action_instance.inputs.get("notice_type") == ActionNoticeType.UPGRADE
    ):
        # 只有单告警动作才会存在周期通知
        # 子任务也不需要创建周期通知
        # 升级的通知也不会周期通知
        return False

    try:
        execute_config = action_instance.action_config["execute_config"]["template_detail"]
    except BaseException as error:
        logger.exception("get action config error : %s", str(error))
        return False

    if execute_config.get("need_poll", False) is False and action_instance.is_parent_action is False:
        # 非通知类的没有设置轮询，直接返回False
        return False

    detect_level = ALERT_DETECT_RESULT.client.get(ALERT_DETECT_RESULT.get_key(alert_id=action_instance.alerts[0]))
    if detect_level:
        # 当状态是异常的时候，才会反复发送通知, 记录下一次执行时间，并将信息写入缓存
        return True
    logger.info(
        "action %s(%s) clear interval because detect result of strategy(%s) is False",
        action_instance.name,
        action_instance.id,
        action_instance.strategy_id,
    )
    return False


class AlertAssignee:
    """
    告警负责人
    """

    def __init__(self, alert, user_groups, follow_groups=None):
        self.alert = alert
        self.user_groups = user_groups
        self.follow_groups = follow_groups or []
        self.biz_group_users = self.get_biz_group_users()
        self.all_group_users = defaultdict(list)
        self.wxbot_mention_users = defaultdict(list)
        self.get_all_group_users()

    @staticmethod
    def get_notify_item(notify_configs, bk_biz_id):
        """
        获取当前时间内的通知配置
        :param notify_configs:
        :param bk_biz_id
        :return:
        """
        # 设置业务时区
        i18n.set_biz(bk_biz_id)
        now_time = time_tools.strftime_local(datetime.now(), _format="%H:%M")
        notify_item = None
        for config in notify_configs:
            # 通知时间段有多个，需要逐一进行遍历
            alarm_start_time, alarm_end_time = config.get("time_range", "00:00--23:59").split("--")
            alarm_start_time = alarm_start_time.strip()[:5]
            alarm_end_time = alarm_end_time.strip()[:5]

            if alarm_start_time <= alarm_end_time:
                if alarm_start_time <= now_time <= alarm_end_time:
                    # 情况1：开始时间 <= 结束时间，属于同一天的情况
                    notify_item = config
                    break
            elif alarm_start_time <= now_time or now_time <= alarm_end_time:
                # 情况2：开始时间 > 结束时间，属于跨天的情况
                notify_item = config
                break
        if notify_item:
            for notify_config in notify_item["notify_config"]:
                # 转换一下数据格式为最新支持的数据类型
                UserGroup.translate_notice_ways(notify_config)
        return notify_item

    def get_group_notify_configs(self, notice_type, user_type):
        """
        获取通知组对应的通知方式内容
        @:param notice_type: alert_notice: 告警通知  action_notice： 执行通知配置
        """
        group_notify_items = defaultdict(dict)
        user_groups = self.user_groups if user_type == UserGroupType.MAIN else self.follow_groups
        for user_group in UserGroup.objects.filter(id__in=user_groups):
            group_notify_items[user_group.id] = {
                "notice_way": self.get_notify_item(getattr(user_group, notice_type, []), self.alert.event.bk_biz_id),
                "mention_users": self.get_group_mention_users(user_group),
            }
        return group_notify_items

    def get_all_group_users(
        self,
    ):
        """
        获取所有的用户组信息
        """
        # 统一获取信息，可以合并处理
        user_groups = list(set(self.user_groups + self.follow_groups))

        if not user_groups:
            # 如果告警组不存在，忽略
            return
        self.get_group_users_with_duty(user_groups)
        self.get_group_users_without_duty(user_groups)

    def get_group_users_without_duty(self, user_groups):
        """
        获取不带轮值功能的用户
        :return:
        """
        no_duty_groups = list(
            UserGroup.objects.filter(id__in=user_groups, need_duty=False).values_list("id", flat=True)
        )
        for duty in DutyArrange.objects.filter(user_group_id__in=no_duty_groups).order_by("id"):
            group_users = self.all_group_users[duty.user_group_id]
            if duty.user_group_id in no_duty_groups and group_users:
                # 如果没有启动轮值，获取到第一个即可
                continue
            for user in duty.users:
                if user["type"] == "group":
                    for username in self.biz_group_users.get(user["id"]) or []:
                        if username not in group_users:
                            group_users.append(username)
                elif user["type"] == "user" and user["id"] not in group_users:
                    group_users.append(user["id"])

    def get_group_mention_users(self, user_group):
        """
        获取用户组对应的提醒人员列表和chat_id
        """
        mention_users = []
        mention_list = user_group.mention_list
        if user_group.mention_type == 0 and not user_group.mention_list:
            mention_list = [{"type": "group", "id": "all"}]
            if user_group.channels and NoticeChannel.WX_BOT not in user_group.channels:
                # 如果已经设置了channels并且没有企业微信机器人，直接设置为空
                mention_list = []
        for user in mention_list:
            if user["type"] == "group":
                if user["id"] == "all":
                    mention_users.extend(self.all_group_users.get(user_group.id, []))
                    continue
                for username in self.biz_group_users.get(user["id"]) or []:
                    if username not in mention_users:
                        mention_users.append(username)
            elif user["type"] == "user" and user["id"] not in mention_users:
                mention_users.append(user["id"])
        return mention_users

    def get_group_users_with_duty(self, user_groups):
        """
        获取需要轮值的用户
        :return:
        """
        if not user_groups:
            return
        duty_groups = UserGroup.objects.filter(id__in=user_groups, need_duty=True).only("timezone", "id", "duty_rules")
        group_duty_plans = defaultdict(dict)
        for group in duty_groups:
            now = time_tools.datetime2str(datetime.now(tz=pytz.timezone(group.timezone)))
            for duty_plan in DutyPlan.objects.filter(
                user_group_id=group.id, is_effective=1, start_time__lte=now, finished_time__gte=now
            ).order_by("order"):
                rule_id = duty_plan.duty_rule_id
                group_duty_plans[group.id].setdefault(rule_id, []).append(duty_plan)

        for group in duty_groups:
            if group.id not in group_duty_plans:
                # 如果当前告警组没有值班计划，直接返回
                continue
            self.get_group_duty_users(group, group_duty_plans[group.id])

    def get_group_duty_users(self, group, group_duty_plans):
        """
        获取当前用户组的值班用户
        """
        for rule_id in group.duty_rules:
            is_rule_matched = False
            if rule_id not in group_duty_plans:
                # 如果当前规则不存在计划中，继续下一个规则
                continue

            alert_time = datetime.now(tz=pytz.timezone(group.timezone))

            for duty_plan in group_duty_plans[rule_id]:
                if not duty_plan.is_active_plan(data_time=time_tools.datetime2str(alert_time)):
                    # 当前计划没有生效则不获取
                    continue
                # 如果当前轮值规则适配生效，则需要终止下一个规则生效
                is_rule_matched = True
                group_users = self.all_group_users[duty_plan.user_group_id]
                for user in duty_plan.users:
                    if user["type"] == "group":
                        for username in self.biz_group_users.get(user["id"]) or []:
                            if username not in group_users:
                                group_users.append(username)
                    elif user["type"] == "user" and user["id"] not in group_users:
                        group_users.append(user["id"])
            if is_rule_matched and group.duty_notice.get("hit_first_duty", True):
                # 适配到了对应的轮值规则，中止
                logger.info("user group (%s) matched duty rule(%s) for alert(%s)", group.id, rule_id, self.alert.id)
                return

    def get_assignee_by_user_groups(self, by_group=False, user_type=UserGroupType.MAIN):
        """
        根据配置的用户组获取对应的处理人员
        """
        if by_group:
            return self.all_group_users
        all_assignee = []
        user_groups = self.user_groups if user_type == UserGroupType.MAIN else self.follow_groups
        for group_id in user_groups:
            for user in self.all_group_users[group_id]:
                if user not in all_assignee:
                    all_assignee.append(user)
        return all_assignee

    def get_notice_receivers(
        self,
        notice_type=NoticeType.ALERT_NOTICE,
        notice_phase=None,
        notify_configs=None,
        user_type=UserGroupType.MAIN,
    ):
        """
        根据用户组和告警获取通知方式和对应的处理人元信息
        :param notify_configs: 已有的通知配置
        :param notice_phase: 获取通知阶段配置
        :param notice_type:通知方式  alert_notice: 告警通知  action_notice： 执行通知配置
        :param user_type: 通知组类型
        :return:
        """
        # step 1 通过用户组获取对应时间段的通知渠道
        group_notify_items = self.get_group_notify_configs(notice_type, user_type)

        # step 3 根据通知方式和用户组进行关联配置
        notify_configs = defaultdict(list) if notify_configs is None else notify_configs
        notice_item_phase_key = "level" if notice_type == NoticeType.ALERT_NOTICE else "phase"
        notice_phase = notice_phase or self.alert.severity
        notify_configs["wxbot_mention_users"] = notify_configs.get("wxbot_mention_users", [])
        for group_id, notify_info in group_notify_items.items():
            notify_item = notify_info["notice_way"]
            mention_users = notify_info["mention_users"]
            if not notify_item:
                continue
            group_users = self.all_group_users.get(group_id, [])
            notice_ways = []
            for notify_config_item in notify_item["notify_config"]:
                # 通知配置的获取
                if notice_phase == notify_config_item[notice_item_phase_key]:
                    notice_ways = notify_config_item.get("notice_ways")
            for notice_way in notice_ways:
                notice_way_type = notice_way["name"]
                if notice_way_type == NoticeWay.VOICE:
                    # 如果是电话通知，需要额外处理
                    if group_users not in notify_configs[notice_way_type]:
                        # 电话通知通过用户列表去重
                        notify_configs[notice_way_type].append(group_users)
                    continue
                if notice_way.get("receivers"):
                    # 企业微信可以一次进行通知
                    if notice_way_type == NoticeWay.BK_CHAT:
                        # 如果是bkchat渠道对接，需要将隐藏的通知方式解开
                        for receiver in notice_way["receivers"]:
                            try:
                                real_notice_way, receiver_id = receiver.split("|")
                            except ValueError:
                                # 如果不符合格式，直接用bkchat的默认发送方式
                                notify_configs[notice_way_type].append(receiver)
                                continue
                            notify_configs[f"{notice_way_type}|{real_notice_way}"].append(receiver_id)
                    else:
                        # 企业微信机器人的，直接扩展
                        # 先去重
                        receivers = [
                            receiver
                            for receiver in notice_way["receivers"]
                            if receiver not in notify_configs[notice_way_type]
                        ]
                        if receivers:
                            notify_configs[notice_way_type].extend(receivers)

                        if mention_users:
                            # 如果当前对应的组有需要提醒的人员信息，保存起来
                            for receiver in notice_way["receivers"]:
                                self.wxbot_mention_users[receiver].extend(mention_users)
                    continue
                for group_user in group_users:
                    if group_user not in notify_configs[notice_way_type]:
                        notify_configs[notice_way_type].append(group_user)
        if self.wxbot_mention_users:
            notify_configs["wxbot_mention_users"].append(self.wxbot_mention_users)
        if not notify_configs["wxbot_mention_users"]:
            # 如果没有提醒人，不显示在配置中
            notify_configs.pop("wxbot_mention_users")
        return notify_configs

    def add_appointee_to_notify_group(self, notify_configs):
        """
        添加分派负责人至通知组
        :param notify_configs: 通知内容
        :return:
        """
        appointee = list(self.alert.appointee)
        if not appointee:
            return notify_configs

        for notice_way, users in notify_configs.items():
            if notice_way in [NoticeWay.WX_BOT, "wxbot_mention_users"]:
                continue
            if notice_way == NoticeWay.VOICE:
                # 如果是语音通知，判断整个列表是否存在
                if appointee not in users:
                    users.append(appointee)
                continue
            # 其他情况下，直接添加个人用户至列表中
            for user in appointee:
                if user not in users:
                    users.append(user)
        return notify_configs

    def get_biz_group_users(self):
        """
        通过业务信息获取对应的角色人员信息
        :return:
        """
        group_users = get_business_roles(self.alert.event.bk_biz_id)
        group_users.update(
            {
                "operator": [],
                "bk_bak_operator": [],
            }
        )
        try:
            if not self.alert.event.target_type:
                # 无监控对象， 不需要获取负责人
                return group_users

            host = HostManager.get_by_id(self.alert.event.bk_host_id)
            for operator_attr in ["operator", "bk_bak_operator"]:
                group_users[operator_attr] = self.get_host_operator(host, operator_attr)
        except AttributeError:
            pass
        return group_users

    @classmethod
    def get_host_operator(cls, host, operator_attr="operator"):
        """
        获取主机负责人，如果没有则尝试获取第一个模块负责人
        :param host: 主机
        :return: list
        """

        if not host:
            return []

        return getattr(host, operator_attr, []) or cls.get_host_module_operator(host)

    @classmethod
    def get_host_module_operator(cls, host, operator_attr="operator"):
        """
        获取主机第一个模块的负责人
        :param operator_attr: 模块负责人类型
                operator: 主机负责人
                bk_bak_operator： 主机备份人
        :param host: 主机
        :return: 人员列表
        """
        for bk_module_id in host.bk_module_ids:
            module = ModuleManager.get(bk_module_id)
            if module:
                return getattr(module, operator_attr, [])
        return []


class DutyCalendar:
    @classmethod
    def get_end_time(cls, end_date, handover_time):
        try:
            [hour, minute] = handover_time.split(":")
            hour = int(hour)
            minute = int(minute)
        except BaseException as error:
            logger.exception("[get_handover_time] split handover_time(%s) error, %s", handover_time, str(error))
            hour, minute = 0, 0
        end_time = datetime(year=end_date.year, month=end_date.month, day=end_date.day, hour=hour, minute=minute)
        return datetime.fromtimestamp(end_time.timestamp(), tz=timezone.utc)

    @staticmethod
    def get_daily_rotation_end_time(begin_time: datetime, handoff_time):
        begin_time = time_tools.localtime(begin_time)
        handover_time = handoff_time["time"]
        if handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            end_date = (begin_time + timedelta(days=1)).date()
        return DutyCalendar.get_end_time(end_date, handover_time)

    @staticmethod
    def get_weekly_rotation_end_time(begin_time: datetime, handoff_time):
        begin_time = time_tools.localtime(begin_time)
        begin_week_day = begin_time.isoweekday()
        handover_date = handoff_time["date"]
        handover_time = handoff_time["time"]
        if handover_date > begin_week_day:
            end_date = (begin_time + timedelta(days=handover_date - begin_week_day)).date()
        elif handover_date == begin_week_day and handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            end_date = (begin_time + timedelta(days=handover_date + 7 - begin_week_day)).date()
        return DutyCalendar.get_end_time(end_date, handover_time)

    @staticmethod
    def get_monthly_rotation_end_time(begin_time: datetime, handoff_time):
        begin_time = time_tools.localtime(begin_time)
        begin_month_day = begin_time.day
        handover_date = handoff_time["date"]
        handover_time = handoff_time["time"]
        _, max_current_month_day = calendar.monthrange(begin_time.year, begin_time.month)

        if max_current_month_day >= handover_date > begin_month_day:
            handover_date = min(handover_date, max_current_month_day)
            end_date = (begin_time + timedelta(days=(handover_date - begin_month_day))).date()
        elif handover_date == begin_month_day and handover_time > time_tools.strftime_local(begin_time, "%H:%M"):
            end_date = begin_time.date()
        else:
            next_month = begin_time.date() + relativedelta(months=1)
            _, max_month_day = calendar.monthrange(next_month.year, next_month.month)
            handover_date = min(handover_date, max_month_day)
            end_date = datetime(next_month.year, next_month.month, handover_date)
        return DutyCalendar.get_end_time(end_date, handover_time)

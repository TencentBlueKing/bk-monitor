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
import copy
import logging

from django.utils.translation import gettext as _

from alarm_backends.constants import CONST_MINUTES
from alarm_backends.service.converge.utils import (
    get_executed_actions,
    get_related_converge_action,
)
from alarm_backends.service.fta_action.tasks import run_action
from bkmonitor.models.fta import ActionInstance, ConvergeInstance
from constants.action import ActionPluginType, ActionStatus, ConvergeType
from constants.alert import EventSeverity

logger = logging.getLogger("fta_action.converge")


class ConvergeFunc:
    def __init__(
        self,
        current_instance,
        matched_related_ids,
        is_new,
        converge_instance: ConvergeInstance,
        converge_config=None,
        biz_converge_existed=False,
    ):
        self.current_instance = current_instance
        self.instance_id = self.current_instance.id
        self.matched_related_ids = matched_related_ids
        self.converge_instance = converge_instance
        self.instance_type = ConvergeType.ACTION
        if isinstance(self.current_instance, ConvergeInstance):
            self.instance_type = ConvergeType.CONVERGE
        self.is_new = is_new
        self.converge_config = converge_config
        self.biz_converge_existed = biz_converge_existed

    def skip_when_success(self):
        """
        成功后跳过

        触发规则后，如果有满足规则的其他告警自愈成功，则跳过当前告警。
        失败的话则继续自愈处理。

        可用于实现失败重试。
        """
        if self.instance_type == ConvergeType.CONVERGE:
            # 二级收敛的，不做成功后跳过
            logger.info("$%s:%s type of converge is not supported", self.instance_id, self.instance_type)
            return False

        other_converged_instances = get_executed_actions(self.converge_instance.id)
        if not other_converged_instances:
            logger.info("$%s:%s not other_converge_instances", self.instance_id, self.instance_type)
            return False

        if other_converged_instances.filter(status=ActionStatus.SUCCESS).exists():
            # 如果有成功，直接忽略
            return ActionStatus.SKIPPED

        if other_converged_instances.exclude(status__in=[ActionStatus.FAILURE, ActionStatus.SLEEP]).exists():
            # 等待的告警处理如果还在执行中
            return ActionStatus.SLEEP

        # 等待的告警处理失败，不收敛
        return False

    def approve_when_failed(self):
        """
        成功后跳过,失败时审批

        触发规则，如果有满足规则的其他告警自愈成功，则跳过当前告警。
        失败的话则发送审批由用户判断是否继续执行自愈处理。
        """
        result = self.skip_when_success()
        if result is False:
            return ActionStatus.WAITING
        return result

    def skip_when_proceed(self):
        """
        执行中跳过

        触发规则后，如果有满足规则的其他告警正在自愈
        则跳过当前告警。

        可用于避免重复告警
        """
        other_converge_instances = get_executed_actions(self.converge_instance.id)
        if not other_converge_instances.exists():
            logger.info("$%s:%s not other_converge_instances", self.instance_id, self.instance_type)
            return False

        if other_converge_instances.filter(status__in=ActionStatus.PROCEED_STATUS):
            return ActionStatus.SKIPPED

        if other_converge_instances.filter(status=ActionStatus.END_STATUS).exclude(status="failure"):
            # 如果在最近五分钟内刚完成的，直接收敛
            return ActionStatus.SKIPPED
        return False

    def wait_when_proceed(self):
        """
        执行中等待

        触发规则后，如果有满足规则的其他告警正在自愈，
        则等其他告警自愈完成后再继续处理当前告警。

        可用于互斥的告警处理，或有先后顺序依赖的告警处理。
        """
        other_converge_instances = get_executed_actions(self.converge_instance.id)
        if not other_converge_instances.exists():
            logger.info("$%s:%s not other_converge_instances", self.current_instance.id, self.instance_type)
            return False

        if other_converge_instances.filter(status__in=ActionStatus.PROCEED_STATUS).exists():
            return ActionStatus.SLEEP
        return False

    def defense(self):
        """
        异常防御需审批
        可用于防御大规模告警的异常，如发布未屏蔽，网络问题，机房故障等等。
        通过人工判断大量的告警是否需要处理。
        """

        if self.is_new:
            return False

        existed_converge_instances = get_executed_actions(self.converge_instance.id)
        if existed_converge_instances.count() < self.converge_config["count"]:
            # 如果当前没有创建收敛并且其他收敛对象小于设置的数量
            logger.info("$%s:%s not enough other_converge_instances", self.instance_id, self.instance_type)
            return False
        return ActionStatus.WAITING

    def skip_when_exceed(self):
        """
        超出后直接忽略
        """

        if self.is_new:
            return False

        if self.converge_instance is None:
            return False

        existed_converge_instances = get_executed_actions(self.converge_instance.id)
        if existed_converge_instances.count() < self.converge_config["count"]:
            # 如果当前没有创建收敛并且其他收敛对象小于设置的数量
            logger.info("$%s:%s not enough other_converge_instances", self.instance_id, self.instance_type)
            return False
        return ActionStatus.SKIPPED

    @staticmethod
    def relevance():
        """
        汇集相关事件

        触发规则后，不影响处理，只是把满足收敛规则的告警汇集在一起展示为同一个事件。

        在界面上把相关的告警汇集在一起展示，能更好自定义告警间的关联性。
        """
        return False  # 不收敛，关联事件，不影响处理

    def trigger(self):
        """
        收敛后处理

        与其他收敛规则相反。未触发规则时，配置的告警类型不处理。触发规则后，才开始处理。

        可以等告警数量超过一定阈值后才处理告警。
        或者一定时间内同时出现 A 告警和 B 告警的时候再开始处理。
        """
        if self.is_new:
            # 对于一个收敛事件，只不收敛一次,
            return False
        return ActionStatus.SKIPPED  # 不符合 trigger 类型触发条件时，跳过当前告警处理

    def collect_alarm(self):
        """ "
        汇总通知：在一段时间之内汇集所有的告警，在收敛窗口结束之后，直接汇总
        """
        if self.is_new:
            # 满足条件之后，立即执行汇总通知
            self.send_collect_action()
            #  如果是第一次创建， 需要创建一个汇总通知的任务
        return ActionStatus.SKIPPED

    def collect(self):
        """
        超出后汇总

        触发规则后，超出数量的告警将会收敛不处理，并发送汇总通知

        如果告警在一定时间内不断出现，超过某个阀值可以认为其有异常，
        则不再自愈，触发通知。
        """
        if self.is_new:
            # 根据汇总的周期，发送汇总的任务
            self.send_collect_action()
            return ActionStatus.SKIPPED if self.biz_converge_existed else False

        if self.biz_converge_existed:
            # 存在业务收敛的时候，直接返回
            logger.info(
                "$%s:%s already have business dimension converge instance", self.instance_id, self.instance_type
            )
            return ActionStatus.SKIPPED

        if self.converge_instance is None:
            # 如果当前的收敛不存在，则表示需要处理
            return False

        existed_converge_instances = get_executed_actions(self.converge_instance.id)

        if existed_converge_instances.count() < self.converge_config["count"]:
            # 如果当前已经创建收敛对象，但是实际收敛数量还不够，
            logger.info("$%s:%s not enough other_converge_instances", self.instance_id, self.instance_type)
            return False

        return ActionStatus.SKIPPED

    def send_collect_action(self, is_delay=True):
        """
        发送收敛汇总的通知
        """

        inputs = self.converge_config["converged_condition"]

        # 输入参数包含了对应的告警收敛匹配参数和对应的事件参数
        inputs.update({"converge_id": self.converge_instance.id, "converge_type": self.instance_type})

        related_action = (
            self.current_instance
            if self.instance_type == ConvergeType.ACTION
            else get_related_converge_action(self.current_instance.id)
        )
        collect_desc = _("汇总通知") if self.instance_type == ConvergeType.ACTION else _("业务汇总通知")

        action_name = "[{}]{}".format(
            collect_desc, related_action.action_config["name"] if related_action else _("告警通知")
        )

        # 汇总为内置的一种处理方式，因此不需要设置动作参数和动作插件
        action_config = copy.deepcopy(related_action.action_config) if related_action else {}
        action_config.update({"name": action_name})

        collect_action = ActionInstance.objects.create(
            signal="collect",
            strategy_id=0,
            alerts=[],
            alert_level=related_action.alert_level if related_action else EventSeverity.REMIND,
            status=ActionStatus.SLEEP,
            bk_biz_id=self.current_instance.bk_biz_id,
            inputs=inputs,
            action_config=action_config,
            action_config_id=action_config.get("id", 0),
            action_plugin={
                "plugin_type": ActionPluginType.COLLECT,
                "name": _("汇总通知"),
                "plugin_key": ActionPluginType.NOTICE,
            },
        )

        action_info = {
            "id": collect_action.id,
            "function": "collect",
        }

        # 汇总的结束，暂时以收敛事件发生的事件为起点，延时max_timedelta来进行
        delay_seconds = 0
        if is_delay:
            delay_seconds = CONST_MINUTES * 1

        run_action.apply_async(("collect", action_info), countdown=delay_seconds)

        logger.info("$%s put collect action（%s） into action queue: collect", self.instance_id, collect_action.id)

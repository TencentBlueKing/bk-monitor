"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.cache.key import FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY
from alarm_backends.core.context import ActionContext
from alarm_backends.core.context.utils import get_notice_display_mapping
from alarm_backends.core.i18n import i18n
from alarm_backends.service.converge.converge_manger import ConvergeManager
from alarm_backends.service.fta_action import BaseActionProcessor
from bkmonitor.models.fta import ActionInstance, ConvergeInstance
from bkmonitor.utils.send import Sender, BlockedError
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.action import ActionSignal, ActionStatus, ConvergeType, FailureType
from core.drf_resource.exceptions import CustomException
from core.errors.action import RelatedAlertNotFoundError
from core.errors.api import BKAPIError
from core.errors.iam import APIPermissionDeniedError

logger = logging.getLogger("fta_action.run")


class ActionProcessor(BaseActionProcessor):
    def __init__(self, action_id, alerts=None):
        self.action = ActionInstance.objects.get(id=action_id)
        i18n.set_biz(self.action.bk_biz_id)
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.action.bk_biz_id)
        self.alerts = alerts
        self.action_config = ActionConfigCacheManager.get_action_config_by_id(self.action.action_config_id)
        self.converge_instance = ConvergeInstance.objects.get(id=self.action.inputs["converge_id"])
        self.related_actions = self.converge_instance.converged_actions().filter(status=ActionStatus.SKIPPED)
        self.context = self.get_context()
        self.timeout = 0
        self.failed_retry = {}
        self.max_retry_times = self.failed_retry.get("max_retry_times", -1)
        self.retry_interval = self.failed_retry.get("retry_interval", 0)
        self.retry_times = 0
        self.notice_way_display = get_notice_display_mapping(self.context.get("notice_way", ""))
        self.converged_condition = self.converge_instance.converge_config["converged_condition"]
        if self.converge_instance.converge_type == ConvergeType.CONVERGE:
            # 如果是二级收敛，默认
            self.clear_biz_converge_lock()

    def get_context(self):
        return ActionContext(self.action, related_actions=self.related_actions, alerts=self.alerts).get_dictionary()

    def collect(self, **kwargs):
        # 获取汇总的对象ID
        node_execute_times_key = "node_execute_times_collect"
        node_execute_times = self.action.outputs.get(node_execute_times_key, 0) + 1
        try:
            self.update_action_status(
                ActionStatus.RUNNING,
                **{
                    "execute_times": self.action.execute_times + 1,
                    "outputs": {"retry_times": self.retry_times + 1, node_execute_times_key: node_execute_times},
                },
            )
            related_actions_count = self.related_actions.count()
            if (
                not related_actions_count
                or self.converge_instance.end_time
                or self.converge_instance.is_visible is False
            ):
                # 如果没有关联的处理记录或者已经结束了或者不可见，则不需要再发送收敛通知了
                logger.info(
                    "$%s|%s collect notice skipped due to related_actions_count(%s) "
                    "or is_finished(%s) or is_visible(%s)",
                    self.action.id,
                    self.converge_instance.id,
                    related_actions_count,
                    self.converge_instance.end_time is not None,
                    self.converge_instance.is_visible,
                )
                self.set_finished(ActionStatus.SKIPPED, message=_("当前汇总不需要发送通知，直接忽略"))
                if self.converge_instance.is_visible:
                    # 仅需要执行的收敛进行
                    ConvergeManager.end_converge_by_id(self.converge_instance.id, self.converge_instance)
                return
            if self.context["alert"] is None and related_actions_count:
                raise RelatedAlertNotFoundError(action_id=self.action.id)

            ConvergeManager.end_converge_by_id(self.converge_instance.id, self.converge_instance)

            collect_info = dict(notice_way=self.context["notice_way"], signal=self.related_actions.first().signal)

            # 如果不是同维度收敛并且大于一条需要发送的的，则按照业务汇总模板发送，否则按照事件发送
            collect_type = self.converge_instance.converge_type if related_actions_count > 1 else ConvergeType.ACTION
            self.send_collect_notice([self.context["notice_receiver"]], collect_info, collect_type)

        except (APIPermissionDeniedError, BKAPIError, CustomException) as error:
            logger.info("collect action(%s) request api error, %s", self.action.id, str(error))
            self.set_finished(
                to_status=ActionStatus.FAILURE,
                message=_("执行汇总通知失败: {}").format(str(error)),
                retry_func="collect",
                kwargs=kwargs,
            )
            return
        except RelatedAlertNotFoundError as error:
            # 当有关联的记录
            logger.warning(f"${self.action.id} run collect action failed , msg is {str(error)}")
            kwargs["node_execute_times"] = self.action.outputs.get(node_execute_times_key, 0)
            self.set_finished(
                ActionStatus.FAILURE,
                failure_type=FailureType.FRAMEWORK_CODE,
                message=_("执行汇总通知失败: {}").format(str(error)),
                retry_func="collect",
                kwargs=kwargs,
            )
            return
        except BaseException as error:
            logger.exception(f"${self.action.id} run collect action failed , msg is {str(error)}")
            kwargs["node_execute_times"] = self.action.outputs.get(node_execute_times_key, 0)
            self.set_finished(
                ActionStatus.FAILURE,
                failure_type=FailureType.FRAMEWORK_CODE,
                message=_("执行汇总通知失败: {}").format(str(error)),
                retry_func="collect",
                kwargs=kwargs,
            )
            return

    def send_collect_notice(self, receiver, collect_info, collect_type):
        """
        发送汇总的通知消息
        :param receiver: 接收人
        :param collect_info:
            {"notice_way":"mail", # 通知方式
            "signal":"abnormal"}    # 通知信号
        :param collect_type: 汇总方式，ACTION: 同维度事件汇总，CONVERGE：业务汇总
        :return:
        """
        i18n.set_biz(self.action.bk_biz_id)
        related_action_ids = [str(ai.id) for ai in self.related_actions]
        logger.info(
            "--${}|{} begin to send collect notice for actions({})".format(
                self.action.id, self.converge_instance.id, ",".join(related_action_ids)
            )
        )

        action_signal = (
            collect_info["signal"]
            if collect_info["signal"] not in [ActionSignal.MANUAL, ActionSignal.NO_DATA]
            else ActionSignal.ABNORMAL
        )

        msg_content_type = (
            "markdown"
            if collect_info["notice_way"] in settings.MD_SUPPORTED_NOTICE_WAYS
            else collect_info["notice_way"]
        )

        # 发送通知, 根据不同的通知渠道，选择不同的发送通知类
        sender_class = self.NOTICE_SENDER.get(self.context.get("notice_channel"), Sender)
        sender = sender_class(
            bk_tenant_id=self.bk_tenant_id,
            title_template_path="notice/{signal}/{collect_type}/{notice_way}_title.jinja".format(
                signal=action_signal,
                notice_way=collect_info["notice_way"],
                collect_type=collect_type,
            ),
            content_template_path=f"notice/{action_signal}/{collect_type}/{msg_content_type}_content.jinja",
            context=self.context,
        )

        # 熔断判定
        is_circuit_breaking = self.check_circuit_breaking_for_notice()
        if is_circuit_breaking:
            setattr(sender, "blocked", True)

        try:
            notice_result = sender.send(collect_info["notice_way"], receiver)[receiver[0]]
        except BlockedError as blocked_error:
            # 处理熔断异常
            logger.info(
                f"[circuit breaking] collect action({self.action.id}) strategy({self.action.strategy_id}) "
                f"blocked: {blocked_error.message}"
            )
            notice_result = {
                "result": False,
                "failure_type": FailureType.BLOCKED,
                "message": blocked_error.message,
                "retry_params": blocked_error.retry_params,
            }

        parent_actions = {action.parent_action_id for action in self.related_actions}
        # 更新当前汇总的发送内容
        self.action.outputs = {
            "title": sender.title,
            "message": sender.content,
            "related_actions": [action.id for action in self.related_actions],
            "related_parent_actions": parent_actions,
        }

        # 根据通知结果设置状态和扩展数据
        if notice_result["result"]:
            # 发送成功
            self.action.status = ActionStatus.SUCCESS
            self.action.ex_data = {"message": notice_result["message"]}
        else:
            # 发送失败或被熔断
            failure_type = notice_result.get("failure_type", FailureType.EXECUTE_ERROR)
            if failure_type == FailureType.BLOCKED:
                # 熔断状态
                self.action.status = ActionStatus.BLOCKED
                self.action.failure_type = FailureType.BLOCKED
                self.action.ex_data = {
                    "message": notice_result["message"],
                    "retry_params": notice_result.get("retry_params", []),
                }
            else:
                # 普通失败
                self.action.status = ActionStatus.FAILURE
                self.action.failure_type = failure_type
                self.action.ex_data = {"message": notice_result["message"]}

        related_alerts = []
        for action in self.related_actions:
            related_alerts.extend(action.alerts)
        # 获取关联的告警列表
        self.action.alerts = list(set(related_alerts))
        # 更新负责人（接收人）
        self.action.assignee = receiver
        # 更新结束时间
        self.action.end_time = datetime.now(tz=timezone.utc)
        # 保存指定的字段
        self.action.save(
            update_fields=["alerts", "assignee", "ex_data", "end_time", "status", "outputs", "failure_type"]
        )

        # 更新当前执行任务的内容
        self.related_actions.update(real_status=self.action.status)

        logger.info(
            "--${}|{} end to send collect notice for actions({})".format(
                self.action.id, self.converge_instance.id, ",".join(related_action_ids)
            )
        )

    def clear_biz_converge_lock(self):
        converge_label_info = {}
        for key, values in self.converged_condition.items():
            if values is None:
                values = ""
            if isinstance(values, list | set):
                values = "_".join([str(value) for value in values])
            else:
                values = str(values)
            converge_label_info[key] = values

        # 去除策略ID避免存储被路由到不同的redis
        converge_label_info.pop("strategy_id", None)
        biz_lock_key = FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY.get_key(**converge_label_info)
        FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY.client.delete(biz_lock_key)

    def replay_blocked_collect_notice(self):
        """
        重新发送被熔断的汇总通知
        """
        return self.action.replay_blocked_notice()

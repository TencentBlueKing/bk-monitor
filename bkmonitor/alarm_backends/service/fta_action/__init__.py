"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import inspect
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime

import jmespath
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from alarm_backends.core.context import ActionContext
from alarm_backends.core.i18n import i18n
from api.itsm.default import (
    CreateFastApprovalTicketResource,
    TicketApproveResultResource,
    TicketRevokeResource,
)
from bkmonitor.db_routers import backend_alert_router
from bkmonitor.documents import AlertDocument, AlertLog, EventDocument
from bkmonitor.models.fta import ActionInstance, ActionInstanceLog
from bkmonitor.utils.send import ChannelBkchatSender, Sender
from bkmonitor.utils.template import AlarmNoticeTemplate, Jinja2Renderer
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from constants.action import (
    ACTION_DISPLAY_STATUS_DICT,
    ACTION_STATUS_DICT,
    DEMO_CONTEXT,
    NOTIFY_STEP_ACTION_SIGNAL_MAPPING,
    STATUS_NOTIFY_DICT,
    ActionLogLevel,
    ActionPluginType,
    ActionSignal,
    ActionStatus,
    FailureType,
    NoticeChannel,
    NoticeType,
    NoticeWay,
    NotifyStep,
)

from .utils import (
    AlertAssignee,
    PushActionProcessor,
    get_notice_display_mapping,
    need_poll,
)
from alarm_backends.core.circuit_breaking.manager import ActionCircuitBreakingManager
from ...core.cache.circuit_breaking import NOTICE_PLUGIN_TYPES

logger = logging.getLogger("fta_action.run")


class ActionAlreadyFinishedError(BaseException):
    """
    已经结束
    """

    def __init__(self, *args, **kwargs):
        pass


class BaseActionProcessor:
    """
    Action 处理器
    {
        "action_id": instance_id,
        "run_times": run_times,
        "module": callback_module,
        "function": callback_func,
    }
    """

    NOTICE_SENDER = {NoticeChannel.BK_CHAT: ChannelBkchatSender}

    def __init__(self, action_id, alerts=None):
        self.action = ActionInstance.objects.get(id=action_id)
        i18n.set_biz(self.action.bk_biz_id)
        self.bk_tenant_id = bk_biz_id_to_bk_tenant_id(self.action.bk_biz_id)
        self.alerts = alerts
        self.retry_times = 0
        self.max_retry_times = 0
        self.retry_interval = 0
        self.is_finished = False
        self.notify_config = None

        # 插件和配置的基本信息
        self.action_config = ActionConfigCacheManager.get_action_config_by_id(self.action.action_config_id)
        if self.action.signal in [ActionSignal.DEMO, ActionSignal.MANUAL]:
            self.action_config = self.action.action_config
        if self.action_config.get("is_enabled", False) is False and self.action.signal != ActionSignal.DEMO:
            if self.action.execute_times == 0 or self.action.action_plugin["plugin_type"] in [
                ActionPluginType.NOTICE,
                ActionPluginType.WEBHOOK,
            ]:
                self.set_finished(ActionStatus.FAILURE, message=_("当前处理套餐配置已被停用或删除，按失败处理"))
                raise ActionAlreadyFinishedError(_("当前处理套餐配置已被停用或删除，按失败处理"))
            # 当处理套餐被禁用或者删除之后，对于之前已经处理中的任务，用快照来替代
            self.action_config = self.action.action_config

        # todo 非策略产生的告警(告警来源非监控) 支持通过告警分派进行通知
        if self.action.strategy:
            self.notify_config = self.action.strategy.get("notice")
        self.execute_config = self.action_config.get("execute_config", {})
        self.timeout_setting = self.execute_config.get("timeout")
        self.failed_retry = self.execute_config.get("failed_retry", {})
        self.max_retry_times = int(self.failed_retry.get("max_retry_times", -1))
        self.retry_interval = int(self.failed_retry.get("retry_interval", 0))

        # 当前的重试次数
        self.retry_times = self.action.outputs.get("retry_times", 0)

        self.context = self.get_context()
        self.notice_receivers = self.context.get("notice_receiver") or self.action.assignee
        self.notice_receivers = (
            self.notice_receivers if isinstance(self.notice_receivers, list) else [self.notice_receivers]
        )
        self.notice_way_display = get_notice_display_mapping(self.context.get("notice_way", ""))
        self.is_finished = self.action.status in ActionStatus.END_STATUS

        logger.info("load BaseActionProcessor for action(%s) finished", action_id)

    def get_context(self):
        """
        获取上下文
        :return:
        """
        if self.action.signal == ActionSignal.DEMO:
            # 如果是调试任务，则设置样例参数
            demo_context = copy.deepcopy(DEMO_CONTEXT)

            event = EventDocument(**{"bk_biz_id": 2, "ip": "127.0.0.1", "bk_cloud_id": 0})
            alert = AlertDocument(
                **{
                    "event": event,
                    "severity": 1,
                    "begin_time": int(time.time()),
                    "create_time": int(time.time()),
                    "latest_time": int(time.time()),
                    "duration": 60,
                    "common_dimensions": {},
                    "extra_info": {"strategy": {}},
                }
            )
            demo_context.update({"alert": alert})
            return demo_context
        return ActionContext(self.action, alerts=self.alerts).get_dictionary()

    @property
    def inputs(self):
        """
        输入数据
        """
        raise NotImplementedError

    def execute(self, failed_times=0):
        """
        执行入口
        :param failed_times: 执行失败的次数
        :return:
        """
        raise NotImplementedError

    @property
    def plugin_key(self):
        """
        获取plugin_key(plugin_type)
        """
        plugin_key = self.action.action_plugin.get("plugin_key")
        if not plugin_key:
            plugin_key = self.action.action_plugin.get("plugin_type")
        return plugin_key

    def can_func_call(self):
        """
        检查是否可以调用
        """
        plugin_type = self.plugin_key
        # 检查是否命中熔断规则
        logger.debug(
            f"[circuit breaking] [{plugin_type}] begin action({self.action.id}) strategy({self.action.strategy_id})"
        )
        can_continue = not self._check_circuit_breaking()
        logger.debug(
            f"[circuit breaking] [{plugin_type}] end action({self.action.id}) strategy({self.action.strategy_id})"
        )

        return can_continue

    def _check_circuit_breaking(self, plugin_type=None, skip_notice_check=True):
        """
        检查是否命中熔断规则

        :param plugin_type: 插件类型，默认使用 action 的插件类型
        :param skip_notice_check: 是否跳过通知类型检查，默认 True（执行阶段），False（通知阶段）
        :return: True 表示命中熔断规则，False 表示未命中
        """
        plugin_type = plugin_type or self.plugin_key

        # message_queue 类型在创建阶段已经检查过熔断，这里跳过
        if plugin_type == ActionPluginType.MESSAGE_QUEUE:
            return False

        # 通知在后续消息发送阶段进行熔断判断（仅在执行阶段跳过）
        if skip_notice_check and plugin_type in NOTICE_PLUGIN_TYPES:
            return False

        # 执行熔断检查
        try:
            is_circuit_breaking = self._do_circuit_breaking_check(plugin_type)

            if is_circuit_breaking:
                # 执行阶段熔断处理
                try:
                    self._handle_execution_circuit_breaking(plugin_type)
                    logger.info(
                        f"[circuit breaking] [{plugin_type}] action({self.action.id}) strategy({self.action.strategy_id}) "
                        f"execution circuit breaking"
                    )
                except Exception as e:
                    logger.exception(
                        f"[circuit breaking] [{plugin_type}] handle execution circuit breaking failed for "
                        f"action({self.action.id}) strategy({self.action.strategy_id}): {e}"
                    )
                return True

            return False
        except Exception as e:
            logger.exception(
                f"[circuit breaking] [{plugin_type}] circuit breaking check failed for "
                f"action({self.action.id}) strategy({self.action.strategy_id}): {e}"
            )
            return False

    def _do_circuit_breaking_check(self, plugin_type=None):
        """
        执行纯粹的熔断检查逻辑（不包含执行阶段处理）

        :param plugin_type: 插件类型，默认使用 action 的插件类型
        :return: True 表示命中熔断规则，False 表示未命中
        """
        plugin_type = plugin_type or self.plugin_key

        # 创建熔断管理器实例
        circuit_breaking_manager = ActionCircuitBreakingManager()

        if not circuit_breaking_manager:
            return False

        # 构建熔断检查的上下文信息
        context = {
            "strategy_id": self.action.strategy_id,
            "bk_biz_id": self.action.bk_biz_id,
            "plugin_type": plugin_type,
        }

        data_source_label = ""
        data_type_label = ""
        # 从策略配置中获取数据源信息
        if self.action.strategy and self.action.strategy.get("items"):
            query_config = self.action.strategy["items"][0]["query_configs"][0]
            data_source_label = query_config.get("data_source_label", "")
            data_type_label = query_config.get("data_type_label", "")
        context["data_source_label"] = data_source_label
        context["data_type_label"] = data_type_label

        # 检查是否命中熔断规则
        return circuit_breaking_manager.is_circuit_breaking(**context)

    def check_circuit_breaking_for_notice(self):
        """
        检查是否命中熔断规则（通知阶段）

        :return: True 表示命中熔断规则，False 表示未命中
        """
        plugin_type = self.plugin_key

        # message_queue 类型在创建阶段已经检查过熔断，这里跳过
        if plugin_type == ActionPluginType.MESSAGE_QUEUE:
            return False

        try:
            is_circuit_breaking = self._do_circuit_breaking_check(plugin_type)

            if is_circuit_breaking:
                logger.info(
                    f"[circuit breaking] [{plugin_type}] action({self.action.id}) strategy({self.action.strategy_id}) "
                    f"notice circuit breaking"
                )

            return is_circuit_breaking
        except Exception as e:
            logger.exception(
                f"[circuit breaking] [{plugin_type}] circuit breaking check failed for "
                f"action({self.action.id}) strategy({self.action.strategy_id}): {e}"
            )
            return False

    def _handle_execution_circuit_breaking(self, plugin_type: str):
        """
        处理执行阶段的熔断
        除去 message_queue, notice, collect 外，其他插件熔断处理流程
        :param plugin_type: 动作插件类型
        """

        # 更新动作状态为熔断
        self.is_finished = True
        self.update_action_status(
            to_status=ActionStatus.BLOCKED,
            end_time=datetime.now(tz=timezone.utc),
            need_poll=False,
            ex_data={
                "message": "套餐执行被熔断",
                "circuit_breaking": True,
            },
        )

        # 记录 action 执行日志
        self.insert_action_log(
            step_name=_("套餐执行熔断"),
            action_log=_("执行被熔断: 套餐执行被熔断"),
            level=ActionLogLevel.INFO,
        )

        # 插入熔断告警流水记录
        try:
            action_name = self.action_config.get("name", "")
            plugin_type = self.action.action_plugin.get("plugin_type", "")
            self.action.insert_alert_log(description=f"处理套餐{action_name}执行被熔断")
            logger.info(
                f"[circuit breaking] [{plugin_type}] created alert log for circuit breaking: "
                f"action({self.action.id}) strategy({self.action.strategy_id})"
            )
        except Exception as e:
            logger.exception(
                f"[circuit breaking] [{plugin_type}] create circuit breaking alert log failed: "
                f"action({self.action.id}) strategy({self.action.strategy_id}): {e}"
            )

    def wait_callback(self, callback_func, kwargs=None, delta_seconds=0):
        """
        等待回调或者轮询
        """
        kwargs = kwargs or {}
        callback_module = getattr(self, "CALLBACK_MODULE", "")
        if not callback_module:
            try:
                callback_module = inspect.getmodule(inspect.stack()[1][0]).__name__
            except BaseException as error:
                logger.exception("inspect module error %s", str(error))

        logger.info("$%s delay to run %s.%s wait(%s)", self.action.id, callback_module, callback_func, delta_seconds)

        PushActionProcessor.push_action_to_execute_queue(
            self.action, countdown=delta_seconds, callback_func=callback_func, kwargs=kwargs
        )

    def create_approve_ticket(self, **kwargs):
        """
        创建ITSM工单
        """

        content_template = AlarmNoticeTemplate.get_template("notice/fta_action/itsm_ticket_content.jinja")
        approve_content = Jinja2Renderer.render(content_template, self.context)
        ticket_data = {
            "creator": "fta-system",
            "fields": [
                {
                    "key": "title",
                    "value": _("[告警异常防御审批]:是否继续执行套餐【{}】").format(self.action_config["name"]),
                },
                {"key": "APPROVER", "value": ",".join(self.action.assignee)},
                {"key": "APPROVAL_CONTENT", "value": approve_content},
            ],
            "meta": {"callback_url": os.path.join(settings.BK_PAAS_INNER_HOST, "fta/action/instances/callback/")},
        }
        try:
            approve_info = CreateFastApprovalTicketResource().request(**ticket_data)
        except BaseException as error:
            self.set_finished(
                ActionStatus.FAILURE, message=_("创建异常防御审批单据失败,错误信息：{}").format(str(error))
            )
            return
        # 创建快速审批单据并且记录审批信息
        self.update_action_outputs({"approve_info": approve_info})

        # 创建快速审批单据后设置一个30分钟超时任务
        self.wait_callback("approve_timeout_callback", approve_info, delta_seconds=60 * 30)

        # 每隔1分钟之后获取记录
        self.wait_callback("get_approve_result", approve_info, delta_seconds=60)

        self.action.insert_alert_log(notice_way_display=self.notice_way_display)

    def get_approve_result(self, **kwargs):
        """
        获取审批结果 同意：推入队列，直接执行 拒绝
        """
        if self.action.status != ActionStatus.WAITING:
            logger.info("current status %s is forbidden to run", self.action.status)
            return

        sn = kwargs.get("sn") or self.action.outputs.get("approve_info", {}).get("sn")
        try:
            approve_result = TicketApproveResultResource().request(**{"sn": [sn]})[0]
        except BaseException as error:
            logger.exception("get approve result error : %s, request sn: %s", error, sn)
            self.set_finished(
                ActionStatus.FAILURE, message=_("获取异常防御审批结果出错，错误信息：{}").format(str(error))
            )
        else:
            self.approve_callback(**approve_result)

    def approve_callback(self, **kwargs):
        if self.action.status != ActionStatus.WAITING:
            logger.info("current status %s is forbidden to run", self.action.status)
            return

        approve_result = kwargs
        if approve_result["current_status"] == "RUNNING":
            # 还在执行中, 等待五分钟之后再次获取结果
            self.wait_callback("get_approve_result", {"sn": approve_result["sn"]}, delta_seconds=60)
            return
        if approve_result["current_status"] == "FINISHED" and approve_result["approve_result"] is True:
            # 结束并且通过的，直接入到执行队列
            self.update_action_status(ActionStatus.RUNNING)
            self.wait_callback("execute")
            self.insert_action_log(
                step_name=_("异常防御审批通过"),
                action_log=_("{}审批通过，继续执行处理动作，工单详情<a target = 'blank' href='{}'>{}<a/>").format(
                    approve_result["updated_by"], approve_result["sn"], approve_result["ticket_url"]
                ),
                level=ActionLogLevel.INFO,
            )
            return
        self.set_finished(
            ActionStatus.SKIPPED, message=_("审批不通过，忽略执行，审批人{}").format(approve_result["updated_by"])
        )

    def get_action_info(self, callback_module, callback_func, kwargs):
        return {
            "id": self.action.id,
            "failed_times": 0,
            "module": callback_module,
            "function": callback_func,
            "kwargs": kwargs,
        }

    def insert_action_log(self, step_name, action_log, level=ActionLogLevel.DEBUG):
        """
        记录操作事件日志
        """
        if getattr(settings, "INSERT_ACTION_LOG", False):
            ActionInstanceLog.objects.create(
                action_instance_id=self.action.id, step_name=step_name, content=action_log, level=level
            )

    def insert_alert_log(self, description=None):
        if self.action.parent_action_id or not self.action.alerts:
            # 如果为子任务，直接不插入日志记录
            return
        status_display = ACTION_DISPLAY_STATUS_DICT.get(self.action.status)
        if self.action.status == ActionStatus.FAILURE:
            status_display = _("{}, 失败原因：{}").format(status_display, self.action.ex_data.get("message", "--"))
        if description is None:
            description = json.dumps(
                self.action.get_content(
                    **{
                        "notice_way_display": get_notice_display_mapping(self.context.get("notice_way")),
                        "status_display": status_display,
                        "action_name": self.action.action_config.get("name", ""),
                    }
                )
            )

        action_log = dict(
            op_type=AlertLog.OpType.ACTION,
            alert_id=self.action.alerts,
            description=description,
            time=int(time.time()),
            create_time=int(time.time()),
            event_id=f"{int(self.action.create_time.timestamp())}{self.action.id}",
        )
        AlertLog.bulk_create([AlertLog(**action_log)])

    def set_start_to_execute(self):
        """
        标记开始执行任务
        """
        # step 1 发送自愈开始通知，创建流水
        execute_notify_result = None
        if getattr(self, "retry_times", 0) == 0:
            # 当前为第一次执行的时候，可以发送开始通知
            execute_notify_result = self.notify(NotifyStep.BEGIN)

        if STATUS_NOTIFY_DICT.get(self.action.status) == NotifyStep.BEGIN:
            # 开始执行任务的通知，仅在开始执行的时候发送
            try:
                if (
                    self.plugin_key
                    not in [
                        ActionPluginType.NOTICE,
                        ActionPluginType.WEBHOOK,
                    ]
                    and self.timeout_setting
                ):
                    # 设置了超时时间，则在一开始设置超时回调
                    self.wait_callback(callback_func="timeout_callback", delta_seconds=self.timeout_setting)
            except BaseException as error:
                logger.exception("run action: send notify error %s, action %s", error, self.action.id)

        # step 2 更新动作的状态以及执行次数
        self.update_action_status(
            ActionStatus.RUNNING,
            **{
                "execute_times": self.action.execute_times + 1,
                "outputs": {
                    "retry_times": self.retry_times + 1,
                    "execute_notify_result": execute_notify_result if execute_notify_result else {},
                    "target_info": self.get_target_info_from_ctx(),
                },
            },
        )

    def get_target_info_from_ctx(self):
        """获取目标信息"""
        action_instance = self.action
        action_ctx = self.context
        target = action_ctx["target"]
        try:
            target_info = {
                "bk_biz_name": target.business.bk_biz_name,
                "bk_target_display": action_ctx["alarm"].target_display,
                "dimensions": [d.to_dict() for d in action_ctx["alarm"].new_dimensions.values()],
                "strategy_name": action_instance.strategy.get("name") or "--",
                "operate_target_string": action_ctx["action_instance"].operate_target_string,
            }
        except BaseException as error:
            logger.info("get targe info failed: %s", str(error))
            return {}
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
        return target_info

    def is_action_finished(self, outputs: list, finished_rule):
        """
        根据配置的条件来判断任务是否结束
        """
        if not finished_rule:
            return False

        return self.business_rule_validate(outputs, finished_rule)

    def is_node_finished(self, outputs: list, finished_rule):
        """
        根据配置的条件来判断某一个步骤是否结束
        """
        if not finished_rule:
            return True

        return self.business_rule_validate(outputs, finished_rule)

    def is_action_success(self, outputs: list, success_rule):
        """
        根据配置的条件来判断任务是否成功
        """
        if not success_rule:
            return True

        return self.business_rule_validate(outputs, success_rule)

    def business_rule_validate(self, params, rule):
        """
        条件判断
        """

        logger.info("[action(%s)] business rule validate params %s, rule %s", self.action.id, params, rule)

        if rule["method"] == "equal":
            return jmespath.search(rule["key"], params) == rule["value"]

        if rule["method"] == "in":
            return jmespath.search(rule["key"], params) in rule["value"]

        if rule["method"] == "not in":
            return jmespath.search(rule["key"], params) not in rule["value"]

        return False

    def set_finished(
        self, to_status, failure_type="", message=_("执行任务成功"), retry_func="execute", kwargs=None, end_time=None
    ):
        """
        设置任务结束
        :param need_poll:
        :param to_status: 结束状态
        :param failure_type: 错误类型
        :param message: 结束日志信息
        :param retry_func: 重试函数
        :param kwargs: 需要重试调用参数
        :return:
        """
        if to_status not in ActionStatus.END_STATUS:
            logger.info("destination status %s is not in end status list", to_status)
            return
        if (
            to_status == ActionStatus.FAILURE
            and failure_type != FailureType.TIMEOUT
            and self.retry_times < self.max_retry_times
        ):
            # 当执行失败的时候，需要进行重试
            # 此处存在的问题： 重试从哪里开始，譬如标准运维的重试，很有可能需要调用重试的接口，
            # 目前延用自愈以前的方式通过通完全重试的方法来进行重试
            if self.retry_times == 0 and self.timeout_setting:
                self.wait_callback(callback_func="timeout_callback", delta_seconds=self.timeout_setting)

            self.is_finished = False
            self.wait_callback(retry_func, delta_seconds=self.retry_interval, kwargs=kwargs)
            return

        if (
            failure_type == FailureType.FRAMEWORK_CODE
            and kwargs.get("node_execute_times", 0) < 3
            and kwargs.get("ignore_error", False) is False
        ):
            # 如果是自愈系统异常并且当前说节点执行次数少于3次，继续重试
            self.is_finished = False
            self.wait_callback(retry_func, delta_seconds=5, kwargs=kwargs)
            self.action.save(update_fields=["outputs"])
            return

        self.is_finished = True
        # 任务结束的时候，需要发送通知
        self.update_action_status(
            to_status=to_status,
            failure_type=failure_type,
            end_time=end_time or datetime.now(tz=timezone.utc),
            need_poll=need_poll(self.action),
            ex_data={"message": message},
        )
        # 更新任务数据(插入日志)
        level = ActionLogLevel.ERROR if to_status == ActionStatus.FAILURE else ActionLogLevel.INFO
        self.insert_action_log(
            step_name=_("第{}次任务执行结束".format(self.retry_times)),
            action_log=_("执行{}: {}").format(ACTION_STATUS_DICT.get(to_status), message),
            level=level,
        )

        self.action.insert_alert_log(notice_way_display=getattr(self, "notice_way_display", ""))

        if self.plugin_key != ActionPluginType.NOTICE:
            notify_result = self.notify(STATUS_NOTIFY_DICT.get(to_status), need_update_context=True)
            if notify_result:
                execute_notify_result = self.action.outputs.get("execute_notify_result") or {}
                execute_notify_result.update(notify_result)
                self.update_action_outputs(outputs={"execute_notify_result": execute_notify_result})

    def update_action_status(self, to_status, failure_type="", **kwargs):
        """
        更新任务状态
        :param from_status:前置状态
        :param to_status:后置状态
        :param failure_type:失败类型
        :return:
        """
        with transaction.atomic(using=backend_alert_router):
            try:
                locked_action = ActionInstance.objects.select_for_update().get(pk=self.action.id)
            except ActionInstance.DoesNotExist:
                return None
            locked_action.status = to_status
            locked_action.failure_type = failure_type
            for key, value in kwargs.items():
                # 其他需要跟新的参数，直接刷新
                setattr(locked_action, key, value)
            locked_action.save(using=backend_alert_router)
            # 刷新当前的事件记录
            self.action = locked_action

    def update_action_outputs(self, outputs):
        """
        更新用户的输出
        :param outputs:
        :return:
        """
        if not isinstance(outputs, dict):
            # 没有输出参数列表，直接返回
            return

        with transaction.atomic(using=backend_alert_router):
            try:
                locked_action = ActionInstance.objects.select_for_update().get(pk=self.action.id)
            except ActionInstance.DoesNotExist:
                return None
            if locked_action.outputs:
                locked_action.outputs.update(outputs)
            else:
                locked_action.outputs = outputs
            outputs.update(locked_action.outputs)
            locked_action.save(using=backend_alert_router)
            self.action = locked_action

    def notify(self, notify_step, need_update_context=False):
        """
        根据当前的状态发送不同的通知
        """

        if self.no_need_notify(notify_step):
            # 不需要通知测试，直接返回
            return

        notify_info = AlertAssignee(self.context["alert"], self.notify_config["user_groups"]).get_notice_receivers(
            NoticeType.ACTION_NOTICE, notify_step
        )

        notice_result = defaultdict(list)

        # TODO 企业微信机器人通知@用户功能
        wxbot_mention_users = notify_info.pop("wxbot_mention_users", [])
        if wxbot_mention_users:
            wxbot_mention_users = wxbot_mention_users[0]
        for notice_way, notice_receivers in notify_info.items():
            try:
                channel, notice_way = notice_way.split("|")
            except ValueError:
                # 如果解析不出来的，表示是以前的通知方式，可以直接忽略
                channel = ""
                notice_way = notice_way
            title_template_path = f"notice/fta_action/{notice_way}_title.jinja"
            content_template_path = "notice/fta_action/{notice_way}_content.jinja".format(
                notice_way="markdown" if notice_way in settings.MD_SUPPORTED_NOTICE_WAYS else notice_way
            )
            sender_class = self.NOTICE_SENDER.get(channel, Sender)
            notify_sender = sender_class(
                context=self.get_context() if need_update_context else self.context,
                title_template_path=title_template_path,
                content_template_path=content_template_path,
                notice_type=NoticeType.ACTION_NOTICE,
                bk_tenant_id=self.bk_tenant_id,
            )
            # 将通知提醒人员更新为当前获取的账户信息
            notify_sender.mentioned_users = wxbot_mention_users
            if notice_way != NoticeWay.VOICE:
                # 不是电话通知的时候，直接发送
                notice_result[notice_way].append(
                    notify_sender.send(
                        notice_way,
                        notice_receivers=notice_receivers,
                        action_plugin=self.action.action_plugin["plugin_type"],
                    )
                )
                continue
            for notice_receiver in notice_receivers:
                # 当为电话通知的时候，直接打电话
                notice_result[notice_way].append(
                    notify_sender.send(
                        notice_way,
                        notice_receivers=notice_receiver,
                        action_plugin=self.action.action_plugin["plugin_type"],
                    )
                )
        return {notify_step: notice_result}

    def no_need_notify(self, notify_step=NotifyStep.BEGIN):
        # 通知类型的响应事件，作为事件处理
        # 没有处理套餐配置的，不做通知
        # 没有通知套餐的，不做通知

        if self.action_config.get("plugin_type") == ActionPluginType.NOTICE:
            # 当为通知套餐的时候， 不需要发送执行通知
            return True

        if not self.notify_config:
            # 通知配置不存在的时候，不需要发送执行通知
            return True

        notify_step_signal = NOTIFY_STEP_ACTION_SIGNAL_MAPPING.get(int(notify_step))
        if self.notify_config and notify_step_signal not in self.notify_config["signal"]:
            # 当前处理阶段不需要发送通知
            return True

        return False

    def timeout_callback(self):
        """
        超时任务回调
        """
        if self.action.status in ActionStatus.END_STATUS:
            # 已经结束，直接返回
            return

        self.set_finished(
            ActionStatus.FAILURE,
            message=_("处理执行时间超过套餐配置的最大时长{}分钟, 按失败处理").format(self.timeout_setting // 60),
            failure_type=FailureType.TIMEOUT,
        )

    def approve_timeout_callback(self, **kwargs):
        """
        审批超时任务回调
        """
        if self.action.status != ActionStatus.WAITING:
            return
        sn = kwargs.get("sn") or self.action.outputs.get("approve_info", {}).get("sn")
        try:
            TicketRevokeResource().request(
                {
                    "sn": sn,
                    "operator": "fta-system",
                    "action_message": _("异常防御审批执行时间套餐配置30分钟, 按忽略处理"),
                }
            )
            self.set_finished(ActionStatus.SKIPPED, message=_("异常防御审批执行时间套餐配置30分钟, 按忽略处理"))
        except BaseException as error:
            self.set_finished(
                ActionStatus.FAILURE,
                message=_("异常防御审批执行时间套餐配置30分钟, 撤回单据失败，错误信息：{}").format(str(error)),
            )

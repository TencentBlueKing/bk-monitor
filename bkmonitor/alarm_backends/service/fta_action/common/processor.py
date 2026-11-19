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
from copy import deepcopy
from importlib import import_module
from typing import Any

import jmespath
from django.conf import settings
from django.utils.functional import cached_property
from django.utils.translation import gettext as _

from alarm_backends.service.fta_action import (
    ActionAlreadyFinishedError,
    BaseActionProcessor,
)
from bkmonitor.models import ActionPlugin
from bkmonitor.utils.template import Jinja2Renderer, NoticeRowRenderer
from bkmonitor.utils.user import (
    batch_get_user_display_names,
    get_user_display_name,
    resolve_biz_tenant_id,
)
from constants.action import ActionStatus, FailureType
from core.drf_resource.exceptions import CustomException
from core.errors.alarm_backends import EmptyAssigneeError
from core.errors.api import BKAPIError
from core.errors.iam import APIPermissionDeniedError

logger = logging.getLogger("fta_action.run")


class ActionProcessor(BaseActionProcessor):
    """
    通用处理器
    """

    def __init__(self, action_id, alerts=None):
        super().__init__(action_id, alerts=alerts)
        self.execute_config = self.action_config["execute_config"]
        self.backend_config = self.action.action_plugin.get("backend_config", {})
        self.function_config = {item["function"]: item for item in self.backend_config}
        logger.info("load common.ActionProcessor for action(%s) finished", action_id)

    @cached_property
    def inputs(self):
        """
        输入数据
        """
        template_detail = self.execute_config["template_detail"]
        try:
            template_detail = self.jinja_render(template_detail)
        except BaseException as error:
            logger.error("Format execute params error %s", str(error))
            self.set_finished(ActionStatus.FAILURE, message=_("获取任务参数异常，错误信息：{}").format(str(error)))
            # 直接设置为结束，抛出异常，终止整个执行
            raise

        template_detail_list = [{"key": key, "value": value} for key, value in template_detail.items()]
        execute_config = deepcopy(self.execute_config)
        execute_config["template_detail"] = template_detail_list
        execute_config["template_detail_dict"] = template_detail
        params = {
            "operator": self.notice_receivers[0] if self.notice_receivers else self.action.assignee,
            "execute_config": execute_config,
            "bk_biz_id": self.action.bk_biz_id,
            "action_name": _("[故障自愈]-{}").format(self.action_config.get("name")),
            "bk_paas_inner_host": settings.BK_COMPONENT_API_URL.rstrip("/"),
            "bk_paas_host": settings.BK_PAAS_HOST.rstrip("/"),
        }
        params.update(ActionPlugin.PUBLIC_PARAMS)
        return params

    def execute(self, failed_times=0):
        """
        执行
        :return:
        """
        # 只有在可执行状态下的任务才能执行
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))

        # 执行入口，需要发送自愈通知
        self.set_start_to_execute()

        if not self.backend_config:
            self.set_finished(ActionStatus.FAILURE, message="unknown execute function")

        # 执行函数为配置参数的第一个
        execute_func = getattr(self, self.backend_config[0]["function"])
        if not execute_func:
            self.set_finished(ActionStatus.FAILURE, message="unknown execute function")

        return execute_func()

    def jinja_render(self, template_value):
        """
        做jinja渲染
        :param template_value:
        :return:
        """
        user_content = Jinja2Renderer.render(self.context.get("default_content_template", ""), self.context)
        alarm_content = NoticeRowRenderer.render(user_content, self.context)
        self.context["user_content"] = alarm_content

        if isinstance(template_value, str):
            return Jinja2Renderer.render(template_value, self.context)
        if isinstance(template_value, dict):
            render_value = {}
            for key, value in template_value.items():
                render_value[key] = self.jinja_render(value)
            return render_value
        if isinstance(template_value, list):
            return [self.jinja_render(value) for value in template_value]
        return template_value

    def create_task(self, **kwargs):
        """
        创建任务阶段
        """
        task_config = self.function_config.get("create_task")
        return self.run_node_task(task_config, **kwargs)

    def schedule(self, **kwargs):
        """轮询"""
        # 只有在可执行状态下的任务才能执行
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))

        task_config = self.function_config.get("schedule")
        return self.run_node_task(task_config, **kwargs)

    def _get_tenant_id(self) -> str | None:
        """
        解析动作所属租户 ID

        显式透传给查询接口，确保 CacheType.USER 缓存键按租户隔离，
        并在无 run_action 线程本地租户上下文的场景下按 bk_biz_id 解析租户。
        非零业务解析失败时返回 None 直接回退原标识，避免落入默认租户串值。
        """
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return None

        bk_tenant_id = getattr(self, "bk_tenant_id", None)
        if isinstance(bk_tenant_id, str) and bk_tenant_id:
            return bk_tenant_id

        action = getattr(self, "action", None)
        return resolve_biz_tenant_id(
            getattr(action, "bk_biz_id", None),
            context_label=f"action({getattr(action, 'id', None)})",
        )

    def _batch_convert_assignees(self, assignees: list[Any], bk_tenant_id: str | None = None) -> list[str]:
        """批量转展示名，查询失败、租户解析失败或个别查不到时回退原值"""
        if not settings.ENABLE_MULTI_TENANT_MODE:
            return [assignee if isinstance(assignee, str) else str(assignee) for assignee in assignees]

        resolved_tenant_id = bk_tenant_id if bk_tenant_id is not None else self._get_tenant_id()
        display_map = batch_get_user_display_names(assignees, bk_tenant_id=resolved_tenant_id, strict_tenant=True)
        return [
            (display_map.get(assignee) or assignee) if isinstance(assignee, str) else str(assignee)
            for assignee in assignees
        ]

    def get_assignee_display_names(self) -> list[str]:
        """
        获取负责人展示名

        self.action.assignee 存储的是用户唯一标识（多租户下为 bk_username），
        直接拼进提示文案会显示成用户看不懂的标识，故转为展示名。
        转换失败（如接口异常、租户上下文缺失）时回退原值，不能影响失败结果落库。
        """
        assignees = self.action.assignee or []
        if not isinstance(assignees, list):
            assignees = [assignees]
        assignees = [assignee for assignee in assignees if assignee]
        if not assignees:
            return []

        if settings.ENABLE_MULTI_TENANT_MODE:
            bk_tenant_id = self._get_tenant_id()
            if not bk_tenant_id:
                return [assignee if isinstance(assignee, str) else str(assignee) for assignee in assignees]
            if len(assignees) > 1:
                return self._batch_convert_assignees(assignees, bk_tenant_id)
        else:
            bk_tenant_id = None

        display_names: list[str] = []
        for assignee in assignees:
            if not isinstance(assignee, str):
                display_names.append(str(assignee))
                continue
            try:
                display_name = (
                    get_user_display_name(assignee, bk_tenant_id=bk_tenant_id)
                    if bk_tenant_id
                    else get_user_display_name(assignee)
                )
            except Exception as error:
                logger.warning(
                    "convert assignee(%s) to display name failed for action(%s): %s",
                    assignee,
                    self.action.id,
                    error,
                )
                display_name = assignee
            display_names.append(display_name if isinstance(display_name, str) and display_name else assignee)
        return display_names

    def run_node_task(self, config, **kwargs):
        if self.action.status not in ActionStatus.CAN_EXECUTE_STATUS:
            raise ActionAlreadyFinishedError(_("当前任务状态不可执行"))
        node_execute_times_key = "node_execute_times_{}".format(config.get("function", "execute"))
        self.action.outputs[node_execute_times_key] = self.action.outputs.get(node_execute_times_key, 0) + 1
        current_step_name = config.get("name")
        self.insert_action_log(current_step_name, _("执行任务参数： %s") % kwargs)
        try:
            outputs = self.run_request_action(config, **kwargs)
        except (APIPermissionDeniedError, BKAPIError, CustomException) as error:
            self.set_finished(
                to_status=ActionStatus.FAILURE,
                message=_("以当前告警负责人[{}]执行{}时, 接口返回{}").format(
                    ",".join(self.get_assignee_display_names()), current_step_name, str(error)
                ),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return
        except EmptyAssigneeError as error:
            self.set_finished(
                to_status=ActionStatus.FAILURE,
                message=_("执行{}出错，{}").format(current_step_name, str(error)),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return
        except BaseException as exc:
            # 出现异常的时候，当前节点执行三次重新推入队列执行
            logger.exception(str(exc))

            kwargs["node_execute_times"] = self.action.outputs.get(node_execute_times_key, 1)
            self.set_finished(
                ActionStatus.FAILURE,
                failure_type=FailureType.FRAMEWORK_CODE,
                message=_("执行{}: {}").format(current_step_name, str(exc)),
                retry_func=config.get("function", "execute"),
                kwargs=kwargs,
            )
            return

        self.update_action_outputs(outputs)

        if self.is_action_finished(outputs, config.get("finished_rule")):
            # 根据配置任务参数是来判断当前任务是否结束
            if self.is_action_success(outputs, config.get("success_rule")):
                self.set_finished(ActionStatus.SUCCESS)
            else:
                self.set_finished(
                    ActionStatus.FAILURE,
                    message=_("{}阶段出错，第三方任务返回执行失败: {}").format(
                        current_step_name, outputs.get("message")
                    ),
                    retry_func=config.get("function", "execute"),
                    kwargs=kwargs,
                )
            return outputs

        if config.get("need_schedule"):
            # 当前阶段未结束，还需要轮询
            schedule_timedelta = config.get("schedule_timedelta", 5)

            self.wait_callback(
                config.get("function", "schedule"),
                {"pre_node_outputs": outputs},
                delta_seconds=schedule_timedelta,
            )
            return outputs

        if config.get("next_function"):
            # 当前节点已经结束，插入节点日志
            if config.get("need_insert_log"):
                self.action.insert_alert_log(
                    content_template=config.get("log_template", ""), notice_way_display=self.notice_way_display
                )
            self.wait_callback(config.get("next_function"), {"pre_node_outputs": outputs}, delta_seconds=2)
            return outputs

        self.set_finished(ActionStatus.SUCCESS)
        return outputs

    def run_request_action(self, request_schema, **kwargs):
        """执行url请求"""
        try:
            resource_module = import_module(request_schema["resource_module"])
        except ImportError as err:
            logger.exception(err)
            return {}
        source_class = request_schema["resource_class"]
        if not hasattr(resource_module, source_class):
            return {}

        request_class = getattr(resource_module, source_class)
        inputs = self.get_request_inputs(request_schema, **kwargs)
        data = {"response": request_class(**request_schema.get("init_kwargs", {})).request(**inputs)}
        outputs = self.decode_request_outputs(output_templates=request_schema.get("outputs", []), **data)
        return outputs

    def get_request_inputs(self, request_schema, **kwargs):
        """构建完成映射和模板渲染的请求参数。"""
        inputs = self.jmespath_search_data(inputs=request_schema.get("inputs", []), **kwargs)
        inputs.update(
            {
                "assignee": self.action.assignee if self.action.assignee else [],
                "action_plugin_key": self.action.action_plugin["plugin_key"]
                or self.action.action_plugin["plugin_type"],
            }
        )
        inputs.update(request_schema.get("request_data_mapping", {}))
        if request_schema.get("render_inputs", False):
            # 对由 jmespath/静态映射生成的 inputs 可选执行二次 Jinja 渲染。
            inputs = self.jinja_render(inputs)
        return inputs

    def decode_request_outputs(self, output_templates, **kwargs):
        """
        解析请求的输出
        :param output_templates: 输出参数模板
        :param kwargs:
        :return:
        """
        kwargs.update(self.inputs)
        outputs = {}
        for output_template in output_templates:
            kwargs.update(outputs)
            format_type = output_template.get("format", "jmespath")
            key = output_template["key"]
            value = output_template["value"]
            outputs[key] = (
                Jinja2Renderer.render(value, kwargs) if format_type == "jinja2" else jmespath.search(value, kwargs)
            )
        return outputs

    def jmespath_search_data(self, inputs, **kwargs):
        """
        jmespath解析请求输入数据
        """
        kwargs.update(self.inputs)
        return {
            item["key"]: jmespath.search(item["value"], kwargs) if item.get("format") == "jmespath" else item["value"]
            for item in inputs
        }

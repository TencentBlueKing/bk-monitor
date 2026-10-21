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

from alarm_backends.service.fta_action.common.processor import ActionProcessor as CommonActionProcessor
from constants.action import ActionSignal

logger = logging.getLogger("fta_action.run")


class ActionProcessor(CommonActionProcessor):
    """
    标准排障处理器
    """

    def get_request_inputs(self, request_schema, **kwargs):
        inputs = super().get_request_inputs(request_schema, **kwargs)
        if (
            request_schema.get("function") == "create_task"
            and request_schema.get("resource_module") == "api.bk_incident.default"
            and request_schema.get("resource_class") == "CreateTaskResource"
            and not inputs.get("source")
        ):
            # 旧任务保存了缺少 source 映射的插件快照，不能仅靠更新插件表修复。
            inputs["source"] = self.execute_config.get("source") or (
                "bk_monitor_debug" if self.action.signal == ActionSignal.DEMO else "bk_monitor"
            )
        return inputs

    def start_task(self, **kwargs):
        """执行任务"""
        task_config = self.function_config.get("start_task")
        self.run_node_task(task_config, **kwargs)

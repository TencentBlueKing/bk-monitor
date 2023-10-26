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

from alarm_backends.service.fta_action.common.processor import ActionProcessor as CommonActionProcessor

logger = logging.getLogger("fta_action.run")


class ActionProcessor(CommonActionProcessor):
    """
    标准运维处理器
    """

    def start_task(self, **kwargs):
        """执行任务"""
        task_config = self.function_config.get("start_task")
        self.run_node_task(task_config, **kwargs)

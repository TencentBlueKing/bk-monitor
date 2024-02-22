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
"""
graph_exporter进程健康状态
"""


import logging

from django.conf import settings

from alarm_backends.service.scheduler.tasks.image_exporter import render_html_string_to_graph

from .checker import CheckerRegister

register = CheckerRegister.graph_exporter
logger = logging.getLogger("self_monitor")


@register.status()
def graph_exporter_status(manager, result, ttl=60):
    """graph_exporter状态"""
    graph_exporter_task = render_html_string_to_graph.delay("hello world!", handle_exception=True)
    try:
        chart = graph_exporter_task.get(timeout=settings.IMAGE_EXPORTER_TIMEOUT)
        if chart:
            result.ok(value="ok")
        else:
            result.fail(message="No image found!")
    except Exception as e:
        result.fail(message=str(e))
        logger.exception(e)
    finally:
        graph_exporter_task.forget()

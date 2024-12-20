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

from celery import platforms
from celery.signals import worker_process_init, worker_process_shutdown

from alarm_backends.service.scheduler.app import app
from bkmonitor.utils.graph_exporter.exporter import GraphExporter

logger = logging.getLogger("image_exporter")


class CustomGraphExporter(GraphExporter):
    def render_string(self, html_string, base_dir=None, options=None):
        temp_file_path = self._generate_temp_file(html_string, base_dir)
        file_url = self.convert_file_path_to_url(temp_file_path)

        self.browser.set_window_size(900, 600)

        try:
            return self.render_url(file_url, options)
        finally:
            self._clean_temp_file(temp_file_path)

    def perform_render(self, options=None):
        time.sleep(0.5)
        return super(CustomGraphExporter, self).perform_render(options)


graph_exporter = CustomGraphExporter()


def close_driver():
    """
    用于worker退出时，退出 phantomjs 的进程
    :return:
    """
    global graph_exporter
    graph_exporter.quit()


@worker_process_shutdown.connect
def pool_process_shutdown_handler(signal=None, sender=None, **kwargs):
    logger.info("Worker is shutting downing")
    close_driver()


@worker_process_init.connect
def install_pool_process_sighandlers(signal=None, sender=None, **kwargs):
    logger.info("Worker is starting")
    platforms.signals["TERM"] = close_driver
    platforms.signals["INT"] = close_driver


@app.task(queue="celery_image_exporter")
def render_html_string_to_graph(html_string, template_path=None):
    # 记录运行时间
    start_time = time.time()
    pngbase64 = graph_exporter.render_string(html_string, template_path)
    end_time = time.time()
    logger.debug("The process takes %s to finish" % (end_time - start_time))
    return pngbase64

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


import glob
import logging
import os
import signal
import time

from django.conf import settings

from alarm_backends.service.selfmonitor.log.rotate import TimeAndSizeRotateFile

logger = logging.getLogger("self_monitor")

IS_STOPING = False


def onsignal(signum, frame):
    """handle quit signal"""
    global IS_STOPING
    logger.info("shutdown received.")

    IS_STOPING = True


class LogProcessor(object):
    """
    Log Rotate Processor
    """

    def process(self):
        signal.signal(signal.SIGTERM, onsignal)
        signal.signal(signal.SIGINT, onsignal)

        file_rotate_handler = []
        for file_name in glob.glob(os.path.join(settings.LOG_PATH, "kernel*.log")):
            h = TimeAndSizeRotateFile(
                file_name,
                settings.LOG_LOGFILE_MAXSIZE,
                settings.LOG_LOGFILE_BACKUP_COUNT,
                settings.LOG_LOGFILE_BACKUP_GZIP,
            )
            file_rotate_handler.append(h)

        while not IS_STOPING:
            try:
                for h in file_rotate_handler:
                    h.handle()

                time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                break
            except Exception:  # noqa
                time.sleep(3)

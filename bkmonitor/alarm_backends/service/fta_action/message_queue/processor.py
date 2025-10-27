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

from alarm_backends.core.context import ActionContext
from alarm_backends.core.i18n import i18n
from alarm_backends.service.fta_action.common import BaseActionProcessor
from bkmonitor.models import ActionInstance, ActionStatus

from .client import get_client

logger = logging.getLogger("fta_action.run")


class ActionProcessor(BaseActionProcessor):
    """
    消息队列处理器
    """

    def __init__(self, action_id, alerts=None):
        if not settings.ENABLE_MESSAGE_QUEUE or not settings.MESSAGE_QUEUE_DSN:
            return
        self.action = ActionInstance.objects.get(id=action_id)
        self.clients = self._init_clients()
        i18n.set_biz(self.action.bk_biz_id)
        self.alerts = alerts
        self.context = ActionContext(self.action, alerts=self.alerts, use_alert_snap=True).get_dictionary()

    def _init_clients(self):
        """
        初始化消息队列客户端
        """
        dsn_config = settings.MESSAGE_QUEUE_DSN
        clients = []
        confs = []

        # 兼容字符串格式
        if isinstance(dsn_config, str):
            confs.append(dsn_config)
        # 处理字典格式
        elif isinstance(dsn_config, dict):
            # 1. 添加默认队列 (biz_id=0)
            if "0" in dsn_config:
                confs.append(dsn_config["0"])

            # 2. 添加业务特定队列
            biz_id = self.action.bk_biz_id
            if str(biz_id) in dsn_config:
                confs.append(dsn_config[str(biz_id)])
        # 依次构建客户端；支持字符串DSN与结构化字典
        for conf in confs:
            clients.append(get_client(conf))
        return clients

    def execute(self):
        if not settings.ENABLE_MESSAGE_QUEUE or not settings.MESSAGE_QUEUE_DSN:
            return

        if self.context["alert"].is_shielded and not settings.ENABLE_PUSH_SHIELDED_ALERT:
            logger.info(
                "Ignore to execute message queue action(%s) for shielded alert(%s) "
                "because config[ENABLE_PUSH_SHIELDED_ALERT] is %s",
                self.action.id,
                self.context["alert"].id,
                settings.ENABLE_PUSH_SHIELDED_ALERT,
            )
            # 任务结束的时候，需要发送通知
            self.update_action_status(
                to_status=ActionStatus.FAILURE,
                end_time=datetime.now(tz=timezone.utc),
                ex_data={"message": _("当前告警已屏蔽且不允许推送屏蔽告警")},
            )
            return

        send_message = self.context["alarm"].alert_info
        if settings.COMPATIBLE_ALARM_FORMAT:
            # COMPATIBLE_ALARM_FORMAT 表示是否使用老版本告警格式（设置为True的话，推送的字段会少一些）
            send_message = self.context["alarm"].callback_message
        success_count = 0
        total_clients = len(self.clients)
        error_details = []

        for client in self.clients:
            try:
                client.send(send_message)
                success_count += 1
            except BaseException as error:
                error_details.append(str(error))

        # 任务结束的时候，需要发送通知
        end_time = datetime.now(tz=timezone.utc)
        if success_count == total_clients:
            self.update_action_status(
                to_status=ActionStatus.SUCCESS,
                end_time=end_time,
                ex_data={"message": _("推送至消息队列成功")},
            )
        elif success_count > 0:
            self.update_action_status(
                to_status=ActionStatus.SUCCESS,
                end_time=end_time,
                ex_data={
                    "message": _("推送至消息队列部分成功({}/{})，失败原因: {}").format(
                        success_count, total_clients, "; ".join(error_details)
                    )
                },
            )
        else:
            self.update_action_status(
                to_status=ActionStatus.FAILURE,
                end_time=end_time,
                execute_times=self.action.execute_times + 1,
                ex_data={"message": _("推送至消息队列失败，失败原因 {}").format("; ".join(error_details))},
            )

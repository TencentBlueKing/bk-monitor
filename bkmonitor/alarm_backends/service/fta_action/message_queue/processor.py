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
        self.client = get_client(settings.MESSAGE_QUEUE_DSN)
        self.action = ActionInstance.objects.get(id=action_id)
        i18n.set_biz(self.action.bk_biz_id)
        self.alerts = alerts
        self.context = ActionContext(self.action, alerts=self.alerts, use_alert_snap=True).get_dictionary()

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
        try:
            self.client.send(send_message)
        except BaseException as error:
            # 任务结束的时候，需要发送通知
            self.update_action_status(
                to_status=ActionStatus.FAILURE,
                end_time=datetime.now(tz=timezone.utc),
                execute_times=self.action.execute_times + 1,
                ex_data={"message": _("推送至消息队列失败，失败原因 {}").format(str(error))},
            )
            return
        # 任务结束的时候，需要发送通知
        self.update_action_status(
            to_status=ActionStatus.SUCCESS,
            end_time=datetime.now(tz=timezone.utc),
            ex_data={"message": _("推送至消息队列成功")},
        )

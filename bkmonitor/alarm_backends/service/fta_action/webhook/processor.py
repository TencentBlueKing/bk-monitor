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
import copy
import json
import logging

import requests
from django.utils.translation import gettext as _

from alarm_backends.service.fta_action.common import BaseActionProcessor
from bkmonitor.utils.encode import EncodeWebhook
from constants.action import ActionStatus

logger = logging.getLogger("fta_action.run")


class ActionProcessor(BaseActionProcessor):
    """webhook处理器"""

    def __init__(self, action_id, alerts=None):
        super(ActionProcessor, self).__init__(action_id, alerts)
        logger.info("---begin to webhook(%s) ---", self.action.id)
        template_detail = copy.deepcopy(self.execute_config["template_detail"])
        try:
            body = template_detail.get("body")
            body["content"] = json.loads(body.get("content"))
        except BaseException:
            pass

        try:
            webhook_config = self.jinja_render(template_detail)
        except BaseException as error:
            self.set_finished(ActionStatus.FAILURE, message=_("获取上下文参数错误: {} ").format(str(error)))
            raise error
        self.url = webhook_config["url"]
        self.method = webhook_config["method"]
        self.headers = {
            item["key"]: item["value"] for item in webhook_config["headers"] if item.get("is_enabled", False)
        }
        encode_webhook = EncodeWebhook(self.headers)
        self.data = encode_webhook.encode_body(webhook_config["body"])
        self.headers = encode_webhook.headers
        self.query_params = {item["key"]: item["value"] for item in webhook_config["query_params"]}
        self.auth = encode_webhook.encode_authorization(webhook_config["authorize"])
        self.failed_retry = template_detail.get("failed_retry") or self.failed_retry
        self.max_retry_times = self.failed_retry.get("max_retry_times")
        self.retry_interval = self.failed_retry.get("retry_interval")

    def execute_webhook(self):
        result, message = self.webhook_request()
        # 目前默认返回码是200的就设置为成功
        self.set_finished(ActionStatus.SUCCESS if result else ActionStatus.FAILURE, message=message)
        return message

    def webhook_request(self):
        """
        发送回调请求
        """
        result = True
        try:
            r = requests.request(
                self.method,
                self.url,
                data=self.data,
                params=self.query_params,
                headers=self.headers,
                timeout=self.failed_retry["timeout"],
                auth=self.auth,
                verify=False,
            )

            if 200 <= r.status_code < 300:
                # 支持2xx的所有场景 2xx代表操作被成功接收并处理
                try:
                    decode_content = r.content.decode("utf-8", errors="ignore")
                    message = "{}...".format(decode_content[:200]) if len(decode_content) > 200 else decode_content
                except BaseException as error:
                    message = "response status_code is 200, decode content error {}".format(str(error))

            else:
                result = False
                content = "{}...".format(r.text[:200]) if len(r.text) > 200 else r.text
                message = "response not valid, status_code: {}, content: {}".format(r.status_code, content)

        except requests.Timeout:
            result = False
            message = "webhook request timeout({})".format(self.failed_retry["timeout"])
        except Exception as e:
            result = False
            message = "webhook request failed, {}".format(e)

        logger.info("---end webhook(%s), response message %s ", self.action.id, message)

        return result, message

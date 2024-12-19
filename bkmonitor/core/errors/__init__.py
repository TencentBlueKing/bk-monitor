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

from django.utils.translation import gettext_lazy as _lazy

logger = logging.getLogger(__name__)


class ErrorDetails:
    """错误详情信息补充类"""

    def __init__(self, exc_type=None, exc_code=None, overview=None, detail=None, popup_message="warning"):
        self.exc_type = exc_type  # 错误类型
        self.exc_code = exc_code  # 错误码
        self.overview = overview  # 错误概述
        self.detail = detail  # 错误详情
        self.popup_message = popup_message  # 错误弹框类型 warning-黄色 error-红色

    def to_dict(self):
        return {
            "type": self.exc_type,
            "code": self.exc_code,
            "overview": str(self.overview),
            "detail": str(self.detail),
            "popup_message": self.popup_message,
        }


class Error(Exception):
    """错误基类"""

    # HTTP状态码
    status_code = 500
    # 错误码，基类无法直接使用，不定义正确错误码
    code = 0
    # 错误描述
    name = _lazy("基础错误")
    # 错误消息模板
    message_tpl = _lazy("系统异常，请联系管理员")
    # 错误级别
    level = logging.ERROR
    # 错误描述
    description = ""
    # 错误信息详情
    error_details = None
    popup_message = "warning"  # 弹框颜色，默认为黄框

    def __init__(self, context=None, data=None, extra=None, **kwargs):
        if not context:
            context = {}
        if not isinstance(context, dict):
            self.message = context or self.name
        else:
            context.update(kwargs)
            try:
                self.message = self.message_tpl.format(**context)
            except Exception:
                # 1. 防止处理异常信息再次抛出异常
                # 2. 防止 pickle.loads 时产生异常
                self.message = self.message_tpl
        self.data = data

        if not extra:
            extra = {}

        # 返回给前端的额外字段
        self.extra = extra
        self.set_details(
            exc_type=type(self).__name__,
            exc_code=self.code,
            overview=self.message,
            detail=self.data,
            popup_message=self.popup_message,
        )

    def set_details(self, exc_type=None, exc_code=None, overview=None, detail=None, popup_message="warning"):
        """设置错误详情信息"""
        self.error_details = ErrorDetails(exc_type, exc_code, overview, detail, popup_message).to_dict()

    def __str__(self):
        return self.message

    def __repr__(self):
        return self.message

    def log(self):
        log_method = {
            logging.ERROR: logger.error,
            logging.CRITICAL: logger.critical,
            logging.FATAL: logger.critical,
            logging.WARNING: logger.warning,
            logging.DEBUG: logger.debug,
            "EXCEPTION": logger.exception,
            logging.INFO: logger.info,
            logging.NOTSET: logger.info,
        }
        if self.level not in log_method:
            self.level = logging.ERROR
            logger.error("log level {} is not exists".format(self.level))

        log_method[self.level](self)

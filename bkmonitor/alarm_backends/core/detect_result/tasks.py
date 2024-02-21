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


import datetime
import logging

from django.conf import settings

from alarm_backends.core.detect_result.clean import CleanResult
from common.context_processors import Platform

logger = logging.getLogger("celery")


def recover_weixin_robot_limit():
    if datetime.datetime.now().hour != 0:
        return
    # 新的一天：重置企业号业务灰度名单后，恢复通知额度
    if settings.IS_WECOM_ROBOT_ENABLED and Platform.te:
        settings.WECOM_ROBOT_BIZ_WHITE_LIST = []


def clean_expired_detect_result():
    try:
        recover_weixin_robot_limit()
        CleanResult.clean_expired_detect_result()
    except Exception as e:
        logger.exception(e)


def clean_md5_to_dimension_cache():
    try:
        CleanResult.clean_md5_to_dimension_cache()
    except Exception as e:
        logger.exception(e)

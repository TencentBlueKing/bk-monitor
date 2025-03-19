# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""
import logging
import time

import requests
from django.conf import settings
from django.utils.translation import gettext as _

from home_application.handlers.metrics import (
    HealthzMetric,
    NamespaceData,
    register_healthz_metric,
)

logger = logging.getLogger()


class HomeMetric(object):
    @staticmethod
    @register_healthz_metric(namespace="service_module")
    def check():
        namespace_data = NamespaceData(namespace="service_module", status=False, data=[])
        ping_result = HomeMetric().ping()
        namespace_data.status = [i.status for i in ping_result].count(True) == len(ping_result)
        if not namespace_data.status:
            namespace_data.message = _("服务模块检查失败, 请查看细节")

        namespace_data.data.extend(ping_result)
        return namespace_data

    @staticmethod
    def ping():
        data = []
        result = HealthzMetric(status=False, metric_name="home")
        start_time = time.time()
        url = settings.BK_IAM_RESOURCE_API_HOST
        if not url:
            result.status = True
            result.message = _("监听域名未配置, 跳过检查")
            data.append(result)
            return data
        try:
            resp = requests.get(url)
            if resp.status_code == 200:
                result.status = True
            else:
                result.message = f"failed to call {url}, status_code: {resp.status_code}, msg: {resp.text}"
                result.suggestion = _("确认服务是否异常, 若无异常, 则检查配置settings.BK_IAM_RESOURCE_API_HOST是否正确")
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"failed to call {url}, err: {e}")
            return data
        spend_time = time.time() - start_time
        result.metric_value = "{}ms".format(int(spend_time * 1000))
        data.append(result)
        return data

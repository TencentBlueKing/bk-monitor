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

from django.conf import settings

from apps.api.base import DataAPI
from config.domains import BKFARA_APIGATEWAY_ROOT


def bkfara_after_request(response):
    # DataAPI 为非标准响应补入的 result 不属于 BKFara 业务数据。
    return {"result": True, "data": {key: value for key, value in response.items() if key != "result"}}


class _BkFaraDataAPI(DataAPI):
    HTTP_SUCCESS_STATUS_CODES = (200, 201, 202)
    EXCLUDE_URL_KEYS = True


class _BkFaraApi:
    MODULE = "BKFara"

    def __init__(self):
        bkfara_api_url = (settings.BKFARA_API_URL or BKFARA_APIGATEWAY_ROOT).rstrip("/")
        self.create_task = _BkFaraDataAPI(
            method="POST",
            url=bkfara_api_url + "/ct/v1/clustering/tasks",
            module=self.MODULE,
            description="创建聚类任务",
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.get_task = _BkFaraDataAPI(
            method="GET",
            url=bkfara_api_url + "/ct/v1/tasks/{task_id}",
            module=self.MODULE,
            description="查询聚类任务",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.get_task_parameters = _BkFaraDataAPI(
            method="GET",
            url=bkfara_api_url + "/ct/v1/tasks/{task_id}/parameters",
            module=self.MODULE,
            description="查询聚类模型参数及采用状态",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.update_task_parameters = _BkFaraDataAPI(
            method="PATCH",
            url=bkfara_api_url + "/ct/v1/tasks/{task_id}/parameters",
            module=self.MODULE,
            description="更新已有聚类模型参数",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.configure_clustering = _BkFaraDataAPI(
            method="PUT",
            url=bkfara_api_url + "/ct/v1/tasks/{task_id}/clustering",
            module=self.MODULE,
            description="配置聚类绑定",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.get_clustering = _BkFaraDataAPI(
            method="GET",
            url=bkfara_api_url + "/ct/v1/tasks/{task_id}/clustering",
            module=self.MODULE,
            description="查询聚类绑定",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.stop_clustering = _BkFaraDataAPI(
            method="POST",
            url=bkfara_api_url + "/internal/ct/v1/clustering/tasks/{task_id}/stop",
            module=self.MODULE,
            description="关闭聚类业务",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )
        self.restart_clustering = _BkFaraDataAPI(
            method="POST",
            url=bkfara_api_url + "/internal/ct/v1/clustering/tasks/{task_id}/restart",
            module=self.MODULE,
            description="重新开启聚类业务",
            url_keys=["task_id"],
            header_keys=["Idempotency-Key"],
            after_request=bkfara_after_request,
            no_query_params=True,
        )

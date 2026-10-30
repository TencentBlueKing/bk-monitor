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

"""BKFara 管理接口；传输、超时、日志和认证头发送复用 DataAPI。"""

import copy

from django.conf import settings
from requests.exceptions import ConnectionError, SSLError, Timeout

from apps.api.base import DataAPI
from apps.api.exception import DataAPIException
from apps.exceptions import ApiRequestError


def bkfara_before_request(params):
    if not settings.BKFARA_API_URL or not settings.BKFARA_API_TOKEN:
        raise ApiRequestError("BKFara 管理接口未配置，请检查 BKAPP_BKFARA_API_URL 与 BKAPP_BKFARA_API_TOKEN")
    params["Authorization"] = f"Bearer {settings.BKFARA_API_TOKEN}"
    return params


def bkfara_after_request(response):
    # DataAPI 为非标准响应补入的 result 不属于 BKFara 业务数据。
    return {"result": True, "data": {key: value for key, value in response.items() if key != "result"}}


class _BkFaraDataAPI(DataAPI):
    HTTP_SUCCESS_STATUS_CODES = (200, 201, 202)
    EXCLUDE_URL_KEYS = True

    def __call__(self, params=None, **kwargs):
        kwargs["request_cookies"] = False
        return super().__call__(copy.deepcopy(params), **kwargs)

    def _send_request(self, params, timeout, request_id, request_cookies, bk_tenant_id):
        try:
            return super()._send_request(params, timeout, request_id, request_cookies, bk_tenant_id)
        except DataAPIException as error:
            response, cause = error.response, error.__context__
            status = response.status_code if response is not None else None
            body = {}
            if response is not None:
                try:
                    body = response.json()
                except ValueError:
                    pass
            if not isinstance(body, dict):
                body = {}
            # 不自动重试写操作；调用方持久保存并沿用相同幂等键和请求体。
            unknown = self.method.upper() != "GET" and (
                status in (502, 503, 504)
                or status in self.HTTP_SUCCESS_STATUS_CODES
                or isinstance(cause, Timeout | ConnectionError)
                and not isinstance(cause, SSLError)
            )
            raise ApiRequestError(
                error.error_message,
                errors={"status_code": status, "code": body.get("code"), "result_unknown": unknown},
            ) from error


class _BkFaraApi:
    MODULE = "BKFara"

    def __init__(self):
        for name, method, path in (
            ("create_task", "POST", "/ct/v1/clustering/tasks"),
            ("get_task", "GET", "/ct/v1/tasks/{task_id}"),
            ("get_task_parameters", "GET", "/ct/v1/tasks/{task_id}/parameters"),
            ("update_task_parameters", "PATCH", "/ct/v1/tasks/{task_id}/parameters"),
            ("configure_clustering", "PUT", "/ct/v1/tasks/{task_id}/clustering"),
            ("get_clustering", "GET", "/ct/v1/tasks/{task_id}/clustering"),
            ("stop_clustering", "POST", "/internal/ct/v1/clustering/tasks/{task_id}/stop"),
            ("restart_clustering", "POST", "/internal/ct/v1/clustering/tasks/{task_id}/restart"),
        ):
            setattr(
                self,
                name,
                _BkFaraDataAPI(
                    method=method,
                    url=settings.BKFARA_API_URL.rstrip("/") + path,
                    module=self.MODULE,
                    url_keys=["task_id"] if "{task_id}" in path else [],
                    header_keys=["Authorization", "Idempotency-Key"],
                    before_request=bkfara_before_request,
                    after_request=bkfara_after_request,
                    no_query_params=True,
                ),
            )

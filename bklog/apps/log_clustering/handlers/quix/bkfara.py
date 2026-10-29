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

import copy

import requests
from django.conf import settings

from apps.log_clustering.exceptions import (
    BkFaraApiException,
    BkFaraConflictException,
    BkFaraNotConfiguredException,
    BkFaraResultUnknownException,
)
from apps.utils.log import logger

# 网关类错误无法确认后端是否已执行写操作
RESULT_UNKNOWN_STATUS_CODES = (502, 503, 504)


def build_create_task_payload(index_set_id: int, quix_config: dict, model_parameters: dict | None = None) -> dict:
    """模型参数使用算法字段与编码，由调用方完成业务配置适配。Kafka 绑定从服务端回读。"""
    payload = {"profile": quix_config["profile"], "index_id": str(index_set_id)}
    if model_parameters is not None:
        payload["training"] = {"parameters": copy.deepcopy(model_parameters)}
    return payload


class BkFaraClient:
    """
    BKFara 聚类任务管理接口
    写操作超时或网关错误时结果未知，调用方必须沿用同一幂等键和请求体重试，不能换键重建任务
    """

    def __init__(self, base_url: str = None, token: str = None, ca_cert_path: str = None, timeout: int = None):
        base_url = settings.BKFARA_API_URL if base_url is None else base_url
        token = settings.BKFARA_API_TOKEN if token is None else token
        if not base_url or not token:
            raise BkFaraNotConfiguredException()
        ca_cert_path = settings.BKFARA_CA_CERT_PATH if ca_cert_path is None else ca_cert_path

        self.base_url = base_url.rstrip("/")
        self.verify = ca_cert_path or True
        self.timeout = timeout or settings.BKFARA_API_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def create_task(self, payload: dict, idempotency_key: str) -> dict:
        return self._request("POST", "/ct/v1/clustering/tasks", payload, idempotency_key)

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/ct/v1/tasks/{task_id}")

    def get_task_parameters(self, task_id: str) -> dict:
        return self._request("GET", f"/ct/v1/tasks/{task_id}/parameters")

    def update_task_parameters(
        self, task_id: str, expected_control_version: int, model_parameters: dict, idempotency_key: str
    ) -> dict:
        return self._request(
            "PATCH",
            f"/ct/v1/tasks/{task_id}/parameters",
            {
                "expected_control_version": expected_control_version,
                "training": {"parameters": copy.deepcopy(model_parameters)},
            },
            idempotency_key,
        )

    def configure_clustering(self, task_id: str, payload: dict, idempotency_key: str) -> dict:
        return self._request("PUT", f"/ct/v1/tasks/{task_id}/clustering", payload, idempotency_key)

    def get_clustering(self, task_id: str) -> dict:
        return self._request("GET", f"/ct/v1/tasks/{task_id}/clustering")

    def stop_clustering(self, task_id: str, boundary: dict, completion: dict = None) -> dict:
        """
        业务关闭接口：支持边界与可选完成确认；结果入库且实际解绑后可提交完成确认。
        模型更新和 Worker 维护不调用此接口，业务关闭顺序由调用方编排。
        """
        payload = {"boundary": boundary}
        if completion is not None:
            payload["completion"] = completion
        return self._request("POST", f"/internal/ct/v1/clustering/tasks/{task_id}/stop", payload)

    def restart_clustering(self, task_id: str, expected_control_version: int, idempotency_key: str) -> dict:
        return self._request(
            "POST",
            f"/internal/ct/v1/clustering/tasks/{task_id}/restart",
            {"expected_control_version": expected_control_version},
            idempotency_key,
        )

    def _request(self, method: str, path: str, payload: dict = None, idempotency_key: str = None) -> dict:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else {}
        error_params = {"method": method, "path": path}
        try:
            response = self.session.request(
                method,
                f"{self.base_url}{path}",
                json=payload,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify,
            )
        except requests.exceptions.SSLError as e:
            raise BkFaraApiException(BkFaraApiException.MESSAGE.format(status_code=None, detail=e, **error_params))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            raise BkFaraResultUnknownException(BkFaraResultUnknownException.MESSAGE.format(detail=e, **error_params))

        try:
            body = response.json() if response.content else {}
        except ValueError:
            body = {"message": response.text[:500]}
        logger.info("[bkfara] %s %s -> %s", method, path, response.status_code)

        if response.ok:
            return body

        if not isinstance(body, dict):
            body = {"message": body}
        detail = body.get("message") or body.get("detail") or body
        data = {"status_code": response.status_code, "code": body.get("code")}
        if response.status_code in RESULT_UNKNOWN_STATUS_CODES:
            raise BkFaraResultUnknownException(
                BkFaraResultUnknownException.MESSAGE.format(detail=detail, **error_params), data=data
            )
        if response.status_code == 409:
            raise BkFaraConflictException(
                BkFaraConflictException.MESSAGE.format(detail=detail, **error_params), data=data
            )
        raise BkFaraApiException(
            BkFaraApiException.MESSAGE.format(status_code=response.status_code, detail=detail, **error_params),
            data=data,
        )

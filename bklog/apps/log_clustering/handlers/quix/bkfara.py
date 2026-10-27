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

RUNTIME_DOMAIN = "log-clustering"

# 网关类错误无法确认后端是否已执行写操作
RESULT_UNKNOWN_STATUS_CODES = (502, 503, 504)


def build_create_task_payload(index_set_id: int, quix_config: dict) -> dict:
    return {
        "runtime_key": {"domain": RUNTIME_DOMAIN, "business_key": str(index_set_id)},
        **copy.deepcopy(quix_config["task_template"]),
    }


def build_clustering_payload(task_id: str, expected_control_version: int, quix_config: dict) -> dict:
    kafka = copy.deepcopy(quix_config["kafka"])
    for key in ("input_topic", "output_topic", "consumer_group", "result_group"):
        kafka[key] = kafka[key].format(task_id=task_id)
    return {
        "expected_control_version": expected_control_version,
        "kafka": kafka,
        "resource_profile_ref": copy.deepcopy(quix_config["resource_profile_ref"]),
    }


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
        return self._request("POST", "/ct/v1/tasks", payload, idempotency_key)

    def get_task(self, task_id: str) -> dict:
        return self._request("GET", f"/ct/v1/tasks/{task_id}")

    def configure_clustering(self, task_id: str, payload: dict, idempotency_key: str) -> dict:
        return self._request("PUT", f"/ct/v1/tasks/{task_id}/clustering", payload, idempotency_key)

    def get_clustering(self, task_id: str) -> dict:
        return self._request("GET", f"/ct/v1/tasks/{task_id}/clustering")

    def stop_clustering(self, task_id: str, boundary: dict, completion: dict = None) -> dict:
        """
        两阶段停止：第一次只传候选 Topic 边界；结果入库且实际解绑后，第二次传同一边界和完成确认
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

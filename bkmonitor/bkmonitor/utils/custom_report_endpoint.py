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
from typing import Any

logger = logging.getLogger(__name__)


def get_valid_custom_report_endpoints(configured_endpoints: Any) -> list[dict[str, str]]:
    """按配置顺序返回具有有效地址和别名的上报服务。"""
    if not isinstance(configured_endpoints, list):
        logger.warning("CUSTOM_REPORT_ENDPOINTS must be a list")
        return []

    valid_services = []
    for index, service in enumerate(configured_endpoints):
        endpoint = service.get("endpoint") if isinstance(service, dict) else None
        alias = service.get("alias") if isinstance(service, dict) else None
        if not all(isinstance(value, str) and value.strip() for value in (endpoint, alias)):
            logger.warning(f"skip invalid CUSTOM_REPORT_ENDPOINTS item at index {index}")
            continue
        valid_services.append({"endpoint": endpoint.strip(), "alias": alias.strip()})

    return valid_services

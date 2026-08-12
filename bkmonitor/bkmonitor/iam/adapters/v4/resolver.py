"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# ---------------------------------------------------------------------------
# V4ResourceResolver — V4 资源实例补全器（回调版）
#
# 基于 adapters/v4/callbacks.py 的回调 handler，
# 通过 CallbackService 的 fetch_instance_info 补全 name / ancestor_chain。
# ---------------------------------------------------------------------------

from __future__ import annotations

import logging

from ...iam_engine.core.types import ResourceInstance
from ...iam_engine.provider.resolver import ResourceResolver

logger = logging.getLogger(__name__)


class V4ResourceResolver(ResourceResolver):
    """V4 资源实例补全器。

    通过 V4 callback handler 的 fetch_instance_info 补全实例属性。
    配置方式：
        IAM_FRAMEWORK.PROVIDERS[*].options.resolver_class =
            "bkmonitor.iam.adapters.v4.resolver.V4ResourceResolver"
    """

    def __init__(self):
        # 延迟导入 callback handler（避免循环依赖）
        pass

    def resolve(self, resource: ResourceInstance) -> ResourceInstance:
        """V4: 当前 callback_service 已处理 display_name，直接返回。

        如需自定义补全逻辑，可在此扩展。
        """
        return resource

"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from ..iam_engine.schema.definitions import ResourceTypeDef


class ResourceTypes:
    """资源类型定义（v3/v4 共用）。"""

    SPACE = ResourceTypeDef(id="space", name="空间")
    APM_APPLICATION = ResourceTypeDef(id="apm_application", name="APM应用", ancestor="space")
    GRAFANA_DASHBOARD = ResourceTypeDef(id="grafana_dashboard", name="Grafana仪表盘", ancestor="space")
    RUM_APPLICATION = ResourceTypeDef(id="rum_application", name="RUM应用", ancestor="space")

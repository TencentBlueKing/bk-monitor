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
# 资源类型定义（v3/v4 共用）
#
# extensions["v3"] 字段说明：
#   system_id                   : V3 IAM 系统 ID（bk_monitorv3）
#   selection_mode              : instance / attribute
#   related_instance_selections : V3 平台的实例选择器列表
# ---------------------------------------------------------------------------

from ..iam_engine.schema.definitions import ResourceTypeDef


class ResourceTypes:
    """资源类型定义（v3/v4 共用）。"""

    SPACE = ResourceTypeDef(
        id="space",
        name="空间",
        extensions={
            "v3": {
                "system_id": "bk_monitorv3",
                "selection_mode": "instance",
                "name_en": "Space",
                "related_instance_selections": [
                    {"system_id": "bk_monitorv3", "id": "space_list"},
                ],
            }
        },
    )
    APM_APPLICATION = ResourceTypeDef(
        id="apm_application",
        name="APM应用",
        ancestor="space",
        extensions={
            "v3": {
                "system_id": "bk_monitorv3",
                "selection_mode": "instance",
                "name_en": "APM Application",
                "related_instance_selections": [
                    {"system_id": "bk_monitorv3", "id": "apm_application_list_v2"},
                ],
            }
        },
    )
    GRAFANA_DASHBOARD = ResourceTypeDef(
        id="grafana_dashboard",
        name="Grafana仪表盘",
        ancestor="space",
        extensions={
            "v3": {
                "system_id": "bk_monitorv3",
                "selection_mode": "instance",
                "name_en": "Grafana Dashboard",
                "related_instance_selections": [
                    {"system_id": "bk_monitorv3", "id": "grafana_dashboard_list"},
                ],
            }
        },
    )
    RUM_APPLICATION = ResourceTypeDef(
        id="rum_application",
        name="RUM应用",
        ancestor="space",
        extensions={
            "v3": {
                "system_id": "bk_monitorv3",
                "selection_mode": "instance",
                "name_en": "RUM Application",
                "related_instance_selections": [
                    {"system_id": "bk_monitorv3", "id": "rum_application_list_v2"},
                ],
            }
        },
    )

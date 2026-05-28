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

from copy import deepcopy

from django.conf import settings

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.exceptions import ClusteringTenantResourceConfigNotExistException
from apps.log_search.models import Space

TENANT_RESOURCE_CONFIGS_KEY = "tenant_resource_configs"
REQUIRED_TENANT_RESOURCE_FIELDS = ("project_id", "bk_biz_id", "model_id", "tspider_cluster")
TENANT_RESOURCE_FIELDS = REQUIRED_TENANT_RESOURCE_FIELDS + (
    "pattern_storage_cluster",
    "collector_clustering_es_storage",
    "doris_storage",
)


def get_online_clustering_config(bk_biz_id: int):
    """Resolve temporary tenant-specific resources for the online clustering flow."""
    config = deepcopy(FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config)
    bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id)

    if bk_tenant_id == settings.BK_APP_TENANT_ID:
        return config, bk_tenant_id

    tenant_config = (config.get(TENANT_RESOURCE_CONFIGS_KEY) or {}).get(bk_tenant_id) or {}
    missing_fields = [field for field in REQUIRED_TENANT_RESOURCE_FIELDS if not tenant_config.get(field)]
    if missing_fields:
        raise ClusteringTenantResourceConfigNotExistException(
            ClusteringTenantResourceConfigNotExistException.MESSAGE.format(
                bk_tenant_id=bk_tenant_id, fields=",".join(missing_fields)
            )
        )

    for field in TENANT_RESOURCE_FIELDS:
        config.pop(field, None)
    config.update(tenant_config)
    config["pattern_storage_cluster"] = config.get("pattern_storage_cluster") or config.get("tspider_cluster")
    return config, bk_tenant_id

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

import re
from copy import deepcopy

from django.utils.translation import gettext as _

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import BKDATA_CLUSTERING_TOGGLE
from apps.log_clustering.constants import DEFAULT_SIGNATURE_FORMAT_UDF
from apps.log_search.models import Space

TENANT_RESOURCE_CONFIGS_KEY = "tenant_resource_configs"


def get_online_clustering_config(bk_biz_id: int):
    """Resolve tenant-specific resources for the online clustering flow.

    Example:
    {
        "project_id": 100,
        "bk_biz_id": 2,
        "model_id": "default_model",
        "tspider_cluster": "default_tspider",
        "tenant_resource_configs": {
            "tenant_a": {
                "project_id": 1001,
                "model_id": "tenant_a_model",
                "tspider_cluster": "tenant_a_tspider",
                "signature_format_udf": "udf_signature_format_tenant_a",
                "predict_es_storage": {"cluster_name": "tenant_a_es", "cluster_id": 101}
            }
        }
    }

    Tenant values are optional overrides. If a field is absent under the tenant key,
    the top-level value is used. The optional predict_es_storage binds the
    BKBase cluster name to the matching BKMonitor cluster ID. Omit cluster_id
    if the BKBase name points to the source index set's physical ES cluster.
    Only initial index configuration creation reads predict_es_storage.
    Flow creation, retry and update use the persisted index binding.
    """
    config = deepcopy(FeatureToggleObject.toggle(BKDATA_CLUSTERING_TOGGLE).feature_config)
    bk_tenant_id = Space.get_tenant_id(bk_biz_id=bk_biz_id)
    tenant_config = (config.get(TENANT_RESOURCE_CONFIGS_KEY) or {}).get(bk_tenant_id) or {}

    config.update(tenant_config)
    config["pattern_storage_cluster"] = config.get("pattern_storage_cluster") or config.get("tspider_cluster")
    return config


def get_signature_format_udf(config: dict) -> str:
    udf = config.get("signature_format_udf", DEFAULT_SIGNATURE_FORMAT_UDF)
    if not isinstance(udf, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", udf):
        raise ValueError(_("signature_format_udf 必须是有效的 SQL 函数名"))
    return udf


def get_predict_es_storage(config: dict) -> tuple[str, int | None]:
    storage = config.get("predict_es_storage")
    if storage is None:
        return "", None
    if not isinstance(storage, dict):
        raise ValueError(_("predict_es_storage 必须是包含 cluster_name 的对象"))
    cluster_name = storage.get("cluster_name")
    if not isinstance(cluster_name, str) or not cluster_name or len(cluster_name) > 64:
        raise ValueError(_("predict_es_storage.cluster_name 必须是长度不超过 64 的 BKBase 集群名"))
    cluster_id = storage.get("cluster_id")
    if cluster_id is not None and (type(cluster_id) is not int or cluster_id <= 0):
        raise ValueError(_("predict_es_storage.cluster_id 必须是正整数"))
    return cluster_name, cluster_id

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

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.feature_toggle.plugins.constants import MINI_CLUSTERING_CONFIG
from apps.log_clustering.exceptions import QuixClusteringConfigInvalidException

QUIX_FEATURE_CONFIG_KEY = "bkbase_quix"

REQUIRED_RESOURCE_KEYS = ("kind", "namespace", "name")


def get_quix_config() -> dict:
    """
    读取 MINI_CLUSTERING_CONFIG 开关 feature_config 中的 bkbase_quix 配置，结构：
    {
        "profile": "...",               # BKFara 部署方登记的聚类任务 Profile 名称
        "kafka_resource": {"kind": "Kafka", "namespace": "...", "name": "..."},           # BKBase 已登记资源
        "pattern_resource": {"kind": "ElasticSearch", "namespace": "...", "name": "..."},
        "max_message_bytes": 1048576,     # 可选
    }
    任务模板、Worker Profile 和 Kafka 绑定由 BKFara 解析；这里保留 BKBase 所需的资源引用。
    """
    feature = FeatureToggleObject.toggle(MINI_CLUSTERING_CONFIG)
    feature_config = (feature.feature_config if feature else None) or {}
    config = copy.deepcopy(feature_config.get(QUIX_FEATURE_CONFIG_KEY) or {})

    missing = ["profile"] if not config.get("profile") else []

    for resource_key in ("kafka_resource", "pattern_resource"):
        resource = config.get(resource_key) or {}
        missing.extend(f"{resource_key}.{key}" for key in REQUIRED_RESOURCE_KEYS if not resource.get(key))

    if missing:
        raise QuixClusteringConfigInvalidException(
            QuixClusteringConfigInvalidException.MESSAGE.format(detail=f"missing {', '.join(missing)}")
        )

    return config

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

# Topic 与消费组按 task_id 隔离，命名需与 BKFara 部署约定一致
DEFAULT_KAFKA_NAME_TEMPLATES = {
    "input_topic": "lc-{task_id}-in",
    "output_topic": "lc-{task_id}-out",
    "consumer_group": "lc-{task_id}-worker",
    "result_group": "lc-{task_id}-result",
}

REQUIRED_KAFKA_KEYS = (
    "cluster_ref",
    "partitions",
    "retention_ms",
    "recovery_window_ms",
    "source_namespace",
    "mapping_revision",
)

REQUIRED_RESOURCE_KEYS = ("kind", "namespace", "name")


def get_quix_config() -> dict:
    """
    读取 MINI_CLUSTERING_CONFIG 开关 feature_config 中的 bkbase_quix 配置，结构：
    {
        "task_template": {...},           # BKFara 创建任务请求中除 runtime_key 外的完整对象（模型、回流、训练、serving 引用）
        "resource_profile_ref": {...},    # BKFara 已登记的 Worker 资源配置引用
        "kafka": {
            "cluster_ref": "...", "partitions": 2, "retention_ms": 604800000, "recovery_window_ms": 86400000,
            "source_namespace": "...", "mapping_revision": "log-v1",
            "input_topic": "lc-{task_id}-in", ...  # 可选，覆盖默认命名模板
        },
        "kafka_resource": {"kind": "Kafka", "namespace": "...", "name": "..."},           # BKBase 已登记资源
        "pattern_resource": {"kind": "ElasticSearch", "namespace": "...", "name": "..."},
        "max_message_bytes": 1048576,     # 可选
    }
    引用对象由部署方成套提供，这里只做完整性校验，不修改其中的摘要
    """
    feature = FeatureToggleObject.toggle(MINI_CLUSTERING_CONFIG)
    feature_config = (feature.feature_config if feature else None) or {}
    config = copy.deepcopy(feature_config.get(QUIX_FEATURE_CONFIG_KEY) or {})

    missing = [key for key in ("task_template", "resource_profile_ref") if not config.get(key)]

    kafka = {**DEFAULT_KAFKA_NAME_TEMPLATES, **(config.get("kafka") or {})}
    missing.extend(f"kafka.{key}" for key in REQUIRED_KAFKA_KEYS if kafka.get(key) in (None, ""))

    for resource_key in ("kafka_resource", "pattern_resource"):
        resource = config.get(resource_key) or {}
        missing.extend(f"{resource_key}.{key}" for key in REQUIRED_RESOURCE_KEYS if not resource.get(key))

    if missing:
        raise QuixClusteringConfigInvalidException(
            QuixClusteringConfigInvalidException.MESSAGE.format(detail=f"missing {', '.join(missing)}")
        )

    if kafka["recovery_window_ms"] > kafka["retention_ms"]:
        raise QuixClusteringConfigInvalidException(
            QuixClusteringConfigInvalidException.MESSAGE.format(
                detail="kafka.recovery_window_ms must not exceed kafka.retention_ms"
            )
        )

    config["kafka"] = kafka
    return config

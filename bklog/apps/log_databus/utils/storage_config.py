# -*- coding: utf-8 -*-
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

from typing import Any

from apps.log_databus.constants import DORIS_CLUSTER_TYPE

# Metadata 各存储的过期天数字段名：ESStorage.consul_config 用 retention，
# DorisStorage.consul_config 用 expire_days。日志平台对外统一暴露 retention。
RETENTION_FIELD_ALIASES = ("retention", "expire_days")


def get_storage_retention(storage_config: dict[str, Any] | None, default: Any = None) -> Any:
    """从 metadata 存储配置中取过期天数，屏蔽 ES 与 Doris 的字段名差异"""
    if not storage_config:
        return default
    for field in RETENTION_FIELD_ALIASES:
        value = storage_config.get(field)
        # 0 天在本模块语义上等同「未设置」（bulk_cluster_infos 查不到结果表时即兜底为 retention=0），
        # 故 doris 结果表同时带上 retention=0 与 expire_days 时，仍应取 expire_days
        if value is not None and value != 0:
            return value
    return default


def build_storage_retention_config(storage_cluster_type: str, retention: Any) -> dict[str, Any]:
    """
    生成下发给 metadata 的过期天数配置片段，与 get_storage_retention 反向对称。

    metadata 侧两种存储只认各自的字段名：DorisStorage 的 create_table 签名与 UPGRADE_FIELD_CONFIG
    都只有 expire_days，传 retention 会在创建时落进 **kwargs、在更新时被 update_storage 跳过，
    两条路径均静默失效，Doris 表因此固定为模型默认的 30 天。
    doris 分支仍保留 retention：metadata 会忽略它，但结果表配置的其他消费方仍按该键读取。
    """
    if storage_cluster_type == DORIS_CLUSTER_TYPE:
        return {"retention": retention, "expire_days": retention}
    return {"retention": retention}

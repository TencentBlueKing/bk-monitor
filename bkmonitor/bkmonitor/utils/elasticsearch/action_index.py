"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

"""动作索引（bkfta_action_*）的物理索引枚举与字段检查。

供补字段、回填等一次性运维命令共用，避免命令里重复写正则与容错逻辑。
"""

import re

ACTION_INDEX_NAME_PATTERN = re.compile(r"^bkfta_action_\d+_\d+$")


def list_action_indices(es_client) -> list[str]:
    """枚举打开的 bkfta_action 物理索引，过滤掉读写别名。"""
    return sorted(
        name for name in es_client.indices.get(index="bkfta_action_*") if ACTION_INDEX_NAME_PATTERN.match(name)
    )


def index_has_field(es_client, index: str, field: str) -> bool:
    """判断物理索引的 mapping 中是否已存在指定字段。"""
    mapping = es_client.indices.get_mapping(index=index)
    properties = (mapping.get(index) or {}).get("mappings", {}).get("properties") or {}
    return field in properties


def filter_indices_by_date(indices: list[str], start: str = "", end: str = "") -> list[str]:
    """按索引名中的 YYYYMMDD 过滤，start / end 传 8 位日期字符串，空值表示不限。"""
    result = []
    for name in indices:
        parts = name.split("_")
        date_str = parts[2] if len(parts) >= 3 else ""
        if start and date_str < start:
            continue
        if end and date_str > end:
            continue
        result.append(name)
    return result

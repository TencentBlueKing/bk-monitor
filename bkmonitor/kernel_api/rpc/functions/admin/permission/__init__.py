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
# 权限 RPC 包入口
#
# 结构（自 permission.py 拆分收口）：
#   _shared.py —— provider 无关的共享构建逻辑（分类表 / action 元数据 / action_categories）
#   _v3.py     —— v3 语义收口（query_user_permissions）
#   _v4.py     —— v4 新接口（后续 PR C 加入）
#
# 本模块 re-export 各 RPC 函数与测试引用的内部符号，保证旧 import 路径
# （from kernel_api.rpc.functions.admin.permission import ...）不破。
# ---------------------------------------------------------------------------

from ._shared import (
    FUNC_ACTION_CATEGORIES,
    OPERATION_ACTION_CATEGORIES,
    _build_action_groups,
    _build_action_info,
    _build_business_groups,
    _get_action_category,
    _get_v3_type,
    action_categories,
)
from ._v3 import (
    FUNC_QUERY_USER_PERMISSIONS,
    OPERATION_QUERY_USER_PERMISSIONS,
    USE_DIALECT_ACTION_ID,
    _build_action_result_item,
    _enrich_permissions,
    _field_to_resource_type,
    _normalize_username,
    _parse_action_permissions,
    _parse_expression_entries,
    _parse_iam_path,
    _query_policies_with_fallback,
    _to_dialect_action_id,
    query_user_permissions,
)

__all__ = [
    # 公开 API
    "action_categories",
    "query_user_permissions",
    "FUNC_ACTION_CATEGORIES",
    "OPERATION_ACTION_CATEGORIES",
    "FUNC_QUERY_USER_PERMISSIONS",
    "OPERATION_QUERY_USER_PERMISSIONS",
    # 内部 re-export（供 provider / 测试按旧路径引用，不可删除）
    "_build_action_groups",
    "_build_action_info",
    "_build_business_groups",
    "_get_action_category",
    "_get_v3_type",
    "USE_DIALECT_ACTION_ID",
    "_build_action_result_item",
    "_enrich_permissions",
    "_field_to_resource_type",
    "_normalize_username",
    "_parse_action_permissions",
    "_parse_expression_entries",
    "_parse_iam_path",
    "_query_policies_with_fallback",
    "_to_dialect_action_id",
]

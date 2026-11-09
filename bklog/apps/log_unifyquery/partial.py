"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext as _

from apps.log_search.exceptions import BaseSearchException


def is_partial_result(result):
    """Read both raw and aggregate UQ completeness markers."""
    status = result.get("status") or {}
    return bool(result.get("is_partial")) or status.get("code") in {"QUERY_RAW_PARTIAL", "QUERY_TS_PARTIAL"}


def require_complete_result(result):
    """Exports and exact statistics require every queried route to answer."""
    if is_partial_result(result):
        raise BaseSearchException(_("查询结果不完整，请稍后重试"))
    return result

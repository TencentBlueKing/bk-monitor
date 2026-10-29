"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings


def is_issue_ai_analysis_enabled_for_biz(bk_biz_id) -> bool:
    """判断业务是否命中 Issue AI 分析白名单；空名单关闭，-1 表示全量开启。"""

    white_list = getattr(settings, "ISSUE_AI_ANALYSIS_BIZ_WHITE_LIST", None) or []
    try:
        normalized_white_list = {int(item) for item in white_list}
        normalized_bk_biz_id = int(bk_biz_id)
    except (TypeError, ValueError):
        return False

    return bool(normalized_white_list) and (
        -1 in normalized_white_list or normalized_bk_biz_id in normalized_white_list
    )

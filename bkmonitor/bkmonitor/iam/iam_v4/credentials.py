"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


def resolve_credentials(key: str = "default") -> dict:
    """从 Django settings 解析 IAM v4 凭据。"""
    from django.conf import settings

    return {
        "app_code": getattr(settings, "BK_IAM_APP_CODE", ""),
        "app_secret": getattr(settings, "BK_IAM_APP_SECRET", ""),
    }

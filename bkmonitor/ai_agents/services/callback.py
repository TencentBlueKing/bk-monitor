"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from blueapps.utils.request_provider import get_local_request, get_local_request_id, get_request_username
from langfuse.callback import CallbackHandler


# TODO: 将callback集成至AgentSDK
def get_langfuse_callback(metadata: dict | None = None) -> CallbackHandler | None:
    """
    获取langfuse回调
    """
    user_id = get_request_username()
    if not user_id:
        local_request = get_local_request()
        user_id = getattr(local_request.app, "bk_app_code", "anonymous")
    request_id = get_local_request_id()
    return CallbackHandler(user_id=user_id, session_id=request_id, metadata=metadata)

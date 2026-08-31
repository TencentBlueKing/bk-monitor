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

import json
from typing import Any

from apps.constants import INDEX_SET_SCOPED_EXTERNAL_ACTIONS, ExternalPermissionActionEnum, ViewSetActionEnum
from apps.utils.log import logger


def is_default_allowed(view_set: str, view_action: str) -> bool:
    """接口是否默认放行，默认放行的接口不进鉴权来源。"""
    for _d in ViewSetActionEnum.get_keys():
        if _d.view_set != view_set:
            continue
        if not _d.view_action or _d.view_action == view_action:
            if _d.action_id == ExternalPermissionActionEnum.LOG_COMMON.value or _d.default_permission:
                return True
    return False


def resolve_declared_action_id(view_set: str, view_action: str) -> str:
    """接口自身声明的 action_id。

    与外部用户持有哪些授权项无关，因此在「没有旧票但新侧放行」时依然能定位操作类型，
    审计和能力路由都以它为准。
    """
    for _d in ViewSetActionEnum.get_keys():
        if _d.view_set != view_set:
            continue
        if not _d.view_action or _d.view_action == view_action:
            return _d.action_id
    return ExternalPermissionActionEnum.LOG_COMMON.value


def resolve_resource(action_id: str, url_kwargs: dict[str, Any], json_data_str: str) -> int | None:
    """解析请求指向的资源实例。索引集维度的授权项统一从 URL / body 取 index_set_id。"""
    if action_id in INDEX_SET_SCOPED_EXTERNAL_ACTIONS:
        if "index_set_id" in url_kwargs:
            return int(url_kwargs.get("index_set_id", ""))
        try:
            json_data = json.loads(json_data_str)
            if "index_set_id" in json_data:
                return int(json_data.get("index_set_id", ""))
        except json.decoder.JSONDecodeError:
            logger.exception(f"解析请求数据({json_data_str})失败")
    return None

# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import logging
from functools import reduce
from typing import Any, Dict, List, Union

logger = logging.getLogger("metadata")


def getitems(obj: Dict, items: Union[List, str], default: Any = None) -> Any:
    """
    递归获取数据
    注意：使用字符串作为键路径时，须确保 Key 值均为字符串

    :param obj: Dict 类型数据
    :param items: 键列表：['foo', 'bar']，或者用 "." 连接的键路径： ".foo.bar" 或 "foo.bar"
    :param default: 默认值
    :return: 返回对应的value或者默认值
    """
    if not isinstance(obj, dict):
        raise TypeError("Dict object support only!")
    if isinstance(items, str):
        items = items.strip(".").split(".")
    try:
        return reduce(lambda x, i: x[i], items, obj)
    except (IndexError, KeyError, TypeError):
        return default


def get_biz_id_by_space_uid(space_uid):
    """
    根据space_uid查询归属的业务ID
    """
    from metadata.models.space import SpaceResource
    from metadata.models.space.constants import SpaceTypes

    try:
        space_type, space_id = space_uid.split("__")
        if space_type == SpaceTypes.BKCC.value:
            return int(space_id)
        bk_biz_id = (
            SpaceResource.objects.filter(
                space_type_id=space_type, space_id=space_id, resource_type=SpaceTypes.BKCC.value
            )
            .first()
            .resource_id
        )
        return int(bk_biz_id)
    except Exception:  # pylint: disable=broad-except
        return None

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
import hashlib
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
        return 0


def get_space_uid_and_bk_biz_id_by_bk_data_id(bk_data_id: int):
    """
    根据data_id，查询对应的space_uid和bk_biz_id
    @param bk_data_id: 数据ID
    @return: bk_biz_id, space_uid
    """
    from metadata.models.space import Space, SpaceDataSource

    try:
        # 查询DataSource关联的记录
        related_space_info = SpaceDataSource.objects.filter(bk_data_id=bk_data_id).first()
        if not related_space_info:
            logger.warning(
                "get_space_uid_and_bk_biz_id_by_bk_data_id: no related_space_info found for bk_data_id->[%s]",
                bk_data_id,
            )
            return 0, ""
        space_uid = related_space_info.space_type_id + '__' + related_space_info.space_id
        bk_biz_id = get_biz_id_by_space_uid(space_uid=space_uid)

        if bk_biz_id < 0:
            # NOTE：可能存在SpaceDataSource中绑定了错误的元信息的情况，这里ID为负数的话，则去Space中取真实的space_uid
            logger.warning(
                "get_space_uid_and_bk_biz_id_by_bk_data_id: bk_data_id->[%s],search space_resource found a "
                "negative biz_id->[%s]",
                bk_data_id,
                bk_biz_id,
            )
            space = Space.objects.get(id=abs(bk_biz_id))
            space_uid = space.space_uid
            bk_biz_id = get_biz_id_by_space_uid(space_uid=space_uid)

        return bk_biz_id, space_uid
    except Exception as e:  # pylint: disable=broad-except
        logger.warning(
            "get_space_uid_and_bk_biz_id_by_bk_data_id: failed to get info for bk_data_id->[%s],error->[%s]",
            bk_data_id,
            e,
        )
        return 0, ""


def get_hour_off_set_by_table_id(table_id: str, max_hours: int = 16):
    """
    根据table_id，计算对应的时间偏移量，用以在索引轮转周期任务时将其分散到不同的时间段中进行创建
    @param table_id: 结果表ID
    @param max_hours: 最大偏移量
    @return: 时间偏移量
    """
    # 计算标识符的哈希值
    hash_object = hashlib.md5(table_id.encode())
    hash_digest = hash_object.hexdigest()

    # 计算偏移量
    offset = int(hash_digest, 16) % max_hours
    return offset

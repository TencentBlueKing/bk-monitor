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
from typing import Dict, List, Optional, Tuple

from django.db import models
from django.db.models.functions import Concat
from django.db.models.query import QuerySet
from django.utils.translation import gettext as _

from . import constants

logger = logging.getLogger("metadata")


class SpaceTypeManager(models.Manager):
    def list_all_space_types(self) -> List:
        """查询所有的空间类型"""
        space_types = list(self.all().values("type_id", "type_name", "allow_merge", "allow_bind", "dimension_fields"))
        for space_type in space_types:
            space_type["type_name"] = _(space_type["type_name"])
        return space_types


class SpaceManager(models.Manager):
    def compose_space_uid(self, space_type_id: str, space_id: str) -> str:
        """组装空间唯一标识"""
        return f"{space_type_id}{constants.SPACE_UID_HYPHEN}{space_id}"

    def split_space_uid(self, space_uid: str) -> Tuple[str, str]:
        """拆分空间唯一标识"""
        space_info = space_uid.split(constants.SPACE_UID_HYPHEN, 1)
        if len(space_info) < 2:
            logger.error("space_uid: %s is invalid", space_uid)
            raise Exception(f"space_uid{space_uid} is invalid")
        return space_info[0], space_info[1]

    def list_all_spaces(
        self,
        space_type_id: Optional[str] = None,
        space_id: Optional[str] = None,
        space_name: Optional[str] = None,
        id: Optional[int] = None,
        is_exact: Optional[bool] = False,
        page: Optional[int] = constants.DEFAULT_PAGE,
        page_size: Optional[int] = constants.DEFAULT_PAGE_SIZE,
        exclude_platform_space: Optional[bool] = True,
        space_type_id_name: Optional[Dict] = None,
    ) -> Dict:
        """查询所有空间实例

        :param space_type_id: 空间类型 ID
        :param space_id: 空间 ID
        :param space_name: 空间名称
        :param id: 空间自增 ID
        :param is_exact: 是否为精确查询
        :param page: 分页
        :param page_size: 每页的数量
        :param exclude_platform_space: 过滤掉平台级的空间
        """
        spaces = self.all()
        # 如果有过滤条件，则根据条件进行过滤
        spaces = self._filter(spaces, space_name, space_id, space_type_id, id, is_exact, exclude_platform_space)
        # 获取总量
        count = spaces.count()
        # NOTE: 当 page * page_size 大于等于 count，返回的数据为空
        # 分页数据
        if page != 0:
            spaces = spaces[(page - 1) * page_size : page * page_size]
        # 获取空间列表
        space_list = list(
            spaces.annotate(
                space_uid=Concat("space_type_id", models.Value(constants.SPACE_UID_HYPHEN), "space_id")
            ).values(
                "id",
                "space_uid",
                "space_type_id",
                "space_id",
                "space_code",
                "space_name",
                "status",
                "time_zone",
                "language",
                "is_bcs_valid",
            )
        )
        space_type_id_name = space_type_id_name or {}
        # 类型为 bkci, 但是标识 bcs 不可用的记录，space code 设置为空
        for sl in space_list:
            # 添加 `display_name` 字段，格式[类型名称]空间名称
            sl[
                "display_name"
            ] = f"[{space_type_id_name.get(sl['space_type_id'], sl['space_type_id'])}] {sl['space_name']}"
            if sl["space_type_id"] == constants.SpaceTypes.BKCI.value and sl["is_bcs_valid"]:
                sl["space_code"] == ""
        # 返回对应字段
        return {
            "count": count,
            "list": space_list,
        }

    def _filter(
        self,
        spaces: QuerySet,
        space_name: Optional[str] = None,
        space_id: Optional[str] = None,
        space_type_id: Optional[str] = None,
        id: Optional[int] = None,
        is_exact: Optional[bool] = False,
        exclude_platform_space: Optional[bool] = True,
    ) -> QuerySet:
        """根据条件进行过滤"""
        if exclude_platform_space:
            spaces = spaces.exclude(
                space_type_id=constants.EXCLUDED_SPACE_TYPE_ID, space_id=constants.EXCLUDED_SPACE_ID
            )
        if id:
            return spaces.filter(id=id)
        if not (space_name or space_id or space_type_id):
            return spaces
        # 模糊查询
        if not is_exact:
            if space_name:
                spaces = spaces.filter(space_name__icontains=space_name)
            if space_id:
                spaces = spaces.filter(space_id__icontains=space_id)
            if space_type_id:
                spaces = spaces.filter(space_type_id__icontains=space_type_id)
            return spaces
        # 精确查询，如果name、space_id、space_type都存在，则需要都满足
        if space_name:
            spaces = spaces.filter(space_name=space_name)
        if space_id:
            spaces = spaces.filter(space_id=space_id)
        if space_type_id:
            spaces = spaces.filter(space_type_id=space_type_id)
        return spaces

    def get_space_info_by_biz_id(self, bk_biz_id: int) -> Dict:
        if bk_biz_id < 0:
            obj = self.get(id=abs(bk_biz_id))
            return {"space_type": obj.space_type_id, "space_id": obj.space_id}
        elif bk_biz_id > 0:
            return {"space_type": "bkcc", "space_id": str(bk_biz_id)}
        else:
            raise ValueError("biz_id: %s not match space info", bk_biz_id)

    def get_biz_id_by_space(self, space_type: str, space_id: str) -> Optional[int]:
        """通过空间类型和空间ID获取业务ID"""
        try:
            obj = self.get(space_type_id=space_type, space_id=space_id)
        except self.model.DoesNotExist:
            return None
        if space_type == constants.SpaceTypes.BKCC.value:
            return int(obj.space_id)
        # 非bkcc空间类型，返回负值
        return -obj.id


class SpaceResourceManager(models.Manager):
    def get_resource_by_resource_type(self, space_type_id: str, resource_type: str) -> List:
        """通过资源类型，获取对应的资源"""
        return list(
            self.filter(space_type_id=space_type_id, resource_type=resource_type).values(
                "resource_id", "dimension_values"
            )
        )

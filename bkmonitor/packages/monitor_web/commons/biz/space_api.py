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
from typing import List, Union

from django.utils.translation import ugettext as _
from rest_framework.exceptions import ValidationError

from bkm_space import api as space_api
from bkm_space.define import Space as SpaceDefine
from bkmonitor.commons.tools import batch_request
from core.drf_resource import api


class InjectSpaceApi(space_api.AbstractSpaceApi):
    @classmethod
    def _init_space(cls, space_dict: dict) -> SpaceDefine:
        # 补充 space_type 描述
        space_type_list = api.metadata.list_space_types()
        for st in space_type_list:
            if st["type_id"] == space_dict["space_type_id"]:
                space_dict.update(st)
        return SpaceDefine.from_dict(space_dict)

    @classmethod
    def get_space_detail(cls, space_uid: str = "", bk_biz_id: int = 0) -> Union[None, SpaceDefine]:
        """
        查看具体空间实例详情
        :param space_uid: 空间唯一标识
        :param id: 空间自增ID
        """
        params = {}
        if bk_biz_id < 0:
            params.update({"id": abs(bk_biz_id)})
        elif bk_biz_id > 0:
            params.update({"space_uid": f"bkcc__{bk_biz_id}"})
        elif space_uid:
            params.update({"space_uid": space_uid})
        else:
            raise ValidationError(_("参数[space_uid]、和[id]不能同时为空"))
        space_info = api.metadata.get_space_detail(**params)
        return cls._init_space(space_info)

    @classmethod
    def list_spaces(cls, refresh=False) -> List[SpaceDefine]:
        """
        查询空间列表
        """
        func = api.metadata.list_spaces
        if refresh:
            func = api.metadata.list_spaces.request.refresh
        space_list = batch_request(func, params={}, get_data=lambda x: x["list"], app="metadata", limit=1000)

        # 获得支持的空间类型
        space_type_list = api.metadata.list_space_types()
        space_type_map = {st["type_id"]: st for st in space_type_list}

        result = []
        for space_dict in space_list:
            # 添加空间类型属性
            type_id = space_dict["space_type_id"]
            space_type_item = space_type_map.get(type_id, {})
            if space_type_item:
                space_dict.update(space_type_item)
            # 将字典转换为空间对象
            space_obj = SpaceDefine.from_dict(space_dict)
            result.append(space_obj)

        return result

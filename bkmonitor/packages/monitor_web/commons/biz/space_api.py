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

from django.conf import settings
from django.core.cache import caches
from django.db import connections
from django.utils.translation import ugettext as _
from rest_framework.exceptions import ValidationError

from bkm_space import api as space_api
from bkm_space.define import Space as SpaceDefine
from bkm_space.define import SpaceTypeEnum
from core.drf_resource import api

local_mem = caches["locmem"]


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
        ret: List[SpaceDefine] = local_mem.get("metadata:list_spaces", None)
        if ret is None or refresh:
            ret: List[SpaceDefine] = [
                SpaceDefine.from_dict(space_dict, cleaned=True)
                for space_dict in cls.list_spaces_dict(using_cache=False)
            ]
            local_mem.set("metadata:list_spaces", ret, timeout=600)
        return ret

    @classmethod
    def list_spaces_dict(cls, using_cache=True) -> List[dict]:
        """
        告警性能版本获取空间列表
        """
        ret: List[dict] = local_mem.get("metadata:list_spaces_dict", None)
        if ret is not None and using_cache:
            return ret
        with connections["monitor_api"].cursor() as cursor:
            sql = """
                SELECT s.id,
                       s.space_type_id,
                       s.space_id,
                       s.space_name,
                       s.space_code,
                       s.time_zone,
                       s.language,
                       s.is_bcs_valid,
                       CONCAT(s.space_type_id, '__', s.space_id) AS space_uid,
                       t.type_name
                FROM
                    metadata_space s
                JOIN
                    metadata_spacetype t
                ON
                    s.space_type_id = t.type_id
            """
            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            spaces: List[dict] = [dict(zip(columns, row)) for row in cursor.fetchall()]
        # db 无数据， 开发环境给出提示， 生产环境不提示（正常部署不会出现该问题）
        if not spaces and settings.RUN_MODE == "DEVELOP":
            raise Exception(
                "未成功初始化metadata空间数据，请执行"
                "env DJANGO_CONF_MODULE=conf.worker.development.enterprise python manage.py init_space_data"
            )
        for space in spaces:
            # bk_biz_id
            if space["space_type_id"] != SpaceTypeEnum.BKCC.value:
                space["bk_biz_id"] = -space["id"]
            else:
                space["bk_biz_id"] = int(space["space_id"])
            # is_demo
            space["is_demo"] = space["bk_biz_id"] == int(settings.DEMO_BIZ_ID or 0)
            # display_name
            # [cc-auto]配置发现
            display_name = f"[{space['space_id']}]{space['space_name']}"
            if space['space_type_id'] == SpaceTypeEnum.BKCC.value:
                # [2]蓝鲸
                display_name = f"[{space['space_id']}]{space['space_name']}"
            space["display_name"] = display_name + f" ({space['type_name']})"

        # 10min
        local_mem.set("metadata:list_spaces_dict", spaces, 600)
        return spaces

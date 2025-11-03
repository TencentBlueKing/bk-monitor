"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import traceback

from django.conf import settings
from django.core.cache import caches
from django.db import connections
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from bkm_space import api as space_api
from bkm_space.define import Space as SpaceDefine
from bkm_space.define import SpaceTypeEnum
from core.drf_resource import api
from core.prometheus import metrics

local_mem = caches["space"]

logger = logging.getLogger(__name__)


class Empty:
    pass


miss_cache = Empty()
_space_transform = {}


def enrich_space_display_name(space_dict):
    # display_name
    # [cc-auto]配置发现
    display_name = f"[{space_dict['space_id']}]{space_dict['space_name']}"
    if space_dict["space_type_id"] == SpaceTypeEnum.BKCC.value:
        # [2]蓝鲸
        display_name = f"[{space_dict['space_id']}]{space_dict['space_name']}"
    space_dict["display_name"] = display_name + f" ({space_dict['type_name']})"
    return


class InjectSpaceApi(space_api.AbstractSpaceApi):
    @classmethod
    def _init_space(cls, space_dict: dict) -> SpaceDefine:
        if not space_dict.get("type_name"):
            # 补充 space_type 描述
            space_type_list = api.metadata.list_space_types()
            for st in space_type_list:
                if st["type_id"] == space_dict["space_type_id"]:
                    space_dict.update(st)
        enrich_space_display_name(space_dict)
        return SpaceDefine.from_dict(space_dict)

    @classmethod
    def get_space_detail(cls, space_uid: str = "", bk_biz_id: int = 0) -> None | SpaceDefine:
        """
        查看具体空间实例详情
        :param space_uid: 空间唯一标识
        :param id: 空间自增ID
        """
        params = {}
        # 0. 尝试优先使用 space_uid， 使用local_men的数据基于 space_uid 设计
        if bk_biz_id < 0:
            # 1. 非cmdb空间
            if bk_biz_id in _space_transform:
                # 1.1 尝试从映射表中获取space_uid
                params["space_uid"] = _space_transform[bk_biz_id]
            else:
                # 1.2内存中没有业务id信息， 智能尝试用id 查询api
                params["id"] = abs(bk_biz_id)
        elif bk_biz_id > 0:
            # 2. cmdb空间, 直接生成space_uid
            params.update({"space_uid": f"{SpaceTypeEnum.BKCC.value}__{bk_biz_id}"})
        elif space_uid:
            # 3. 指定 space_uid
            params.update({"space_uid": space_uid})
        else:
            logger.error(f"get_space_detail error stack: {traceback.print_stack()}")
            raise ValidationError(_("参数[space_uid]、和[id]不能同时为空"))

        cache_key = params.get("space_uid", "")
        using_cache = cache_key or bk_biz_id > 0
        if using_cache:
            # 尝试从缓存获取, 解决 bkcc 业务层面快速获取空间信息的场景， 非 bkcc 空间，没有预先缓存，通过api获取后再更新
            space = local_mem.get(f"metadata:spaces_map:{cache_key}", miss_cache)
            if space is not miss_cache:
                metrics.SPACE_QUERY_COUNT.labels(using_cache="1", role=settings.ROLE).inc()
                return SpaceDefine.from_dict(space)

        # 通过数据库直查
        filters = {}
        if "id" in params:
            filters["id"] = params["id"]
        elif "space_uid" in params:
            filters["space_type_id"], filters["space_id"] = params["space_uid"].split("__", 1)
        space_info = cls.list_spaces_dict(using_cache=False, filters=filters)
        metrics.SPACE_QUERY_COUNT.labels(using_cache="0", role=settings.ROLE).inc()
        if not space_info:
            return None
        space_info = space_info[0]

        # 如果是非 cmdb 空间，需要通过 metadata 补全信息
        # 由于一开始缺乏 bk_tenant_id 信息，需要先查询数据库才能继续查询 metadata
        if space_info["space_type_id"] != SpaceTypeEnum.BKCC.value:
            space_info = api.metadata.get_space_detail(
                space_uid=f"{space_info['space_type_id']}__{space_info['space_id']}",
                bk_tenant_id=space_info["bk_tenant_id"],
            )

        # 补充miss 的 space_uid 信息（非cmdb 空间）
        local_mem.set(f"metadata:spaces_map:{space_info['space_uid']}", space_info, timeout=3600)
        return cls._init_space(space_info)

    @classmethod
    def list_spaces(cls, refresh=False, bk_tenant_id: str | None = None) -> list[SpaceDefine]:
        """
        查询空间列表
        """
        cache_key = f"metadata:list_spaces:{bk_tenant_id}" if bk_tenant_id else "metadata:list_spaces"

        ret: list[SpaceDefine] = local_mem.get(cache_key, miss_cache)
        if ret is miss_cache or refresh:
            ret: list[SpaceDefine] = [
                SpaceDefine.from_dict(space_dict, cleaned=True)
                for space_dict in cls.list_spaces_dict(using_cache=False, bk_tenant_id=bk_tenant_id)
            ]
            local_mem.set(cache_key, ret, timeout=3600)

        return ret

    @classmethod
    def list_spaces_dict(
        cls, using_cache=True, bk_tenant_id: str | None = None, filters: dict[str, str | int] | None = None
    ) -> list[dict]:
        """
        告警性能版本获取空间列表
        TODO: Space表增加租户字段后，需要修改 SQL，增加租户字段查询，当前使用默认租户
        """
        if bk_tenant_id:
            cache_key = f"metadata:list_spaces_dict:{bk_tenant_id}"
        else:
            cache_key = "metadata:list_spaces_dict"

        ret = miss_cache
        # 如果指定了过滤条件，则不使用缓存
        if using_cache and not filters:
            ret = local_mem.get(cache_key, miss_cache)
        if ret is not miss_cache:
            return ret

        with connections["monitor_api"].cursor() as cursor:
            sql = """
                SELECT s.id,
                       s.bk_tenant_id,
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
            if filters:
                sql += " WHERE "
                where_conditions = []
                for field, value in filters.items():
                    if isinstance(value, str):
                        where_conditions.append(f" s.{field} = '{value}'")
                    elif isinstance(value, int):
                        where_conditions.append(f" s.{field} = {value}")
                sql += " AND ".join(where_conditions)

            cursor.execute(sql)
            columns = [col[0] for col in cursor.description]
            spaces: list[dict] = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # 过滤指定租户
            if bk_tenant_id:
                spaces = [space for space in spaces if space["bk_tenant_id"] == bk_tenant_id]

        # db 无数据， 开发环境给出提示， 生产环境不提示（正常部署不会出现该问题）
        if not spaces and settings.RUN_MODE == "DEVELOP" and not filters and not bk_tenant_id:
            raise Exception(
                "未成功初始化metadata空间数据，请执行"
                "env DJANGO_CONF_MODULE=conf.worker.development.enterprise python manage.py init_space_data"
            )

        _space_transform.clear()
        for space in spaces:
            cc_space = space["space_type_id"] == SpaceTypeEnum.BKCC.value
            # bk_biz_id
            if not cc_space:
                space["bk_biz_id"] = -space["id"]
            else:
                space["bk_biz_id"] = int(space["space_id"])
            # is_demo
            space["is_demo"] = space["bk_biz_id"] == int(settings.DEMO_BIZ_ID or 0)
            enrich_space_display_name(space)
            if cc_space:
                # 仅针对cmdb空间，进行缓存， 非cc空间，需要额外resource信息，走api丰富。
                local_mem.set(f"metadata:spaces_map:{space['space_uid']}", space, timeout=3600)
            else:
                # 非cmdb 空间，内存暂存一份bk_biz_id -> space_uid 的映射
                _space_transform[space["bk_biz_id"]] = space["space_uid"]

        # 如果指定了过滤条件，则不缓存
        if not filters:
            local_mem.set(cache_key, spaces, timeout=3600)

        return spaces

    @classmethod
    def list_sticky_spaces(cls, username):
        sql = """SELECT `metadata_spacestickyinfo`.`space_uid_list`
        FROM `metadata_spacestickyinfo`
        WHERE `metadata_spacestickyinfo`.`username` = %s
        """
        with connections["monitor_api"].cursor() as cursor:
            cursor.execute(sql, (username,))
            sticky_spaces = cursor.fetchone() or []
            if sticky_spaces:
                sticky_spaces = json.loads(sticky_spaces[0])
            return sticky_spaces

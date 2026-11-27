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
from opentelemetry import trace
from rest_framework.exceptions import ValidationError

from bkm_space import api as space_api
from bkm_space.define import Space as SpaceDefine
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import BKMS_SPACE_ID_PREFIX
from bkmonitor.space.pinyin import pinyin_search_patterns
from core.drf_resource import api
from core.prometheus import metrics

local_mem = caches["space"]

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


# 空间缓存时间，单位：秒
SPACE_CACHE_TIMEOUT = 600


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
        local_mem.set(f"metadata:spaces_map:{space_info['space_uid']}", space_info, timeout=SPACE_CACHE_TIMEOUT)
        return cls._init_space(space_info)

    @classmethod
    def list_spaces(cls, refresh=False, bk_tenant_id: str | None = None) -> list[SpaceDefine]:
        """
        查询空间列表
        """
        cache_key = f"metadata:list_spaces:{bk_tenant_id}" if bk_tenant_id else "metadata:list_spaces"

        ret: list[SpaceDefine] = local_mem.get(cache_key, miss_cache)
        if ret is miss_cache or refresh:
            ret = [
                SpaceDefine.from_dict(space_dict, cleaned=True)
                for space_dict in cls.list_spaces_dict(using_cache=False, bk_tenant_id=bk_tenant_id)
            ]
            local_mem.set(cache_key, ret, timeout=SPACE_CACHE_TIMEOUT)

        return ret

    @classmethod
    def _read_space_rows(
        cls, conditions, params, *, first=False, limit=None, type_names=None, seek=False
    ) -> list[dict]:
        """Read the directory projection without touching either space cache."""
        type_projection = "t.type_name" if type_names is None else "s.space_type_id AS type_name"
        type_join = "JOIN metadata_spacetype t ON s.space_type_id = t.type_id" if type_names is None else ""
        index = "FORCE INDEX (PRIMARY)" if seek else ""
        sql = f"""
                SELECT s.id,
                       s.bk_tenant_id,
                       s.space_type_id,
                       s.space_id,
                       s.space_name,
                       s.status,
                       s.space_code,
                       s.time_zone,
                       s.language,
                       s.is_bcs_valid,
                       s.is_global,
                       CONCAT(s.space_type_id, '__', s.space_id) AS space_uid,
                       {type_projection}
                FROM metadata_space s {index} {type_join}
            """
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        if first:
            sql += " ORDER BY s.id LIMIT 1"
        elif limit is not None:
            sql += " ORDER BY s.id LIMIT %s"
            params.append(limit)
        with connections["monitor_api"].cursor() as cursor:
            cursor.execute(sql, params)
            columns = [col[0] for col in cursor.description]
            spaces = [dict(zip(columns, row)) for row in cursor.fetchall()]

        for space in spaces:
            if type_names is not None:
                space["type_name"] = type_names[space["space_type_id"]]
            cc_space = space["space_type_id"] == SpaceTypeEnum.BKCC.value
            # bk_biz_id
            if not cc_space:
                space["bk_biz_id"] = -space["id"]
            else:
                space["bk_biz_id"] = int(space["space_id"])
            # is_demo
            space["is_demo"] = space["bk_biz_id"] == int(settings.DEMO_BIZ_ID or 0)
            enrich_space_display_name(space)
        return spaces

    @staticmethod
    def _restrict_to_biz_ids(conditions, params, biz_ids):
        if biz_ids is not None:
            cc_ids, other_ids = [], []
            for raw_id in biz_ids:
                # Match the same canonical strings as the IAM candidate intersection.
                try:
                    biz_id = int(raw_id)
                except (TypeError, ValueError):
                    continue
                if str(biz_id) != str(raw_id):
                    continue
                if biz_id > 0:
                    cc_ids.append(str(biz_id))
                elif biz_id < 0:
                    other_ids.append(-biz_id)
            predicates = []
            if cc_ids:
                placeholders = ", ".join(["%s"] * len(cc_ids))
                predicates.append(f"(s.space_type_id = %s AND s.space_id IN ({placeholders}))")
                params.extend([SpaceTypeEnum.BKCC.value, *cc_ids])
            if other_ids:
                placeholders = ", ".join(["%s"] * len(other_ids))
                predicates.append(f"(s.space_type_id != %s AND s.id IN ({placeholders}))")
                params.extend([SpaceTypeEnum.BKCC.value, *other_ids])
            if not predicates:
                return False
            conditions.append("(" + " OR ".join(predicates) + ")")
        return True

    @classmethod
    def read_space_records(
        cls, bk_tenant_id: str, biz_ids=None, *, space_uid: str | None = None, first_available=False
    ) -> list[dict]:
        """Read tenant-scoped directory records. None selects the tenant, an empty ID set selects nothing."""
        conditions = ["s.bk_tenant_id = BINARY %s"]
        params = [bk_tenant_id]
        if space_uid is not None:
            space_type, _, space_id = space_uid.partition("__")
            if not space_type or not space_id:
                return []
            # Preserve the case-sensitive UID match of the Python directory lookup.
            conditions.extend(["s.space_type_id = BINARY %s", "s.space_id = BINARY %s"])
            params.extend([space_type, space_id])
        if not cls._restrict_to_biz_ids(conditions, params, biz_ids):
            return []
        if first_available:
            # Apply these predicates before LIMIT, including the reserved -1 / 0 IDs.
            conditions.extend(
                [
                    "NOT (s.space_type_id = %s AND s.space_id = %s)",
                    "NOT (s.space_type_id != %s AND s.id = 1)",
                    "NOT (BINARY s.status = %s AND s.space_type_id = %s AND BINARY s.space_id LIKE %s)",
                ]
            )
            params.extend(
                [
                    SpaceTypeEnum.BKCC.value,
                    "0",
                    SpaceTypeEnum.BKCC.value,
                    "disabled",
                    SpaceTypeEnum.BKCI.value,
                    BKMS_SPACE_ID_PREFIX + "%",
                ]
            )
        with tracer.start_as_current_span("space.read_records", record_exception=False) as span:
            span.set_attribute("space.first_available", first_available)
            span.set_attribute("space.finite_ids", biz_ids is not None or space_uid is not None)
            rows = cls._read_space_rows(conditions, params, first=first_available)
            span.set_attribute("space.row_count", len(rows))
            return rows

    @classmethod
    def _page_conditions(cls, tenant, biz_ids, space_type, after_id, space_uids):
        """Read a stable keyset window with the same tenant and BKMS semantics as the user directory."""
        conditions = [
            "s.bk_tenant_id = BINARY %s",
            "s.id > %s",
            "NOT (BINARY s.status = %s AND s.space_type_id = %s AND BINARY s.space_id LIKE %s)",
        ]
        params = [tenant, after_id, "disabled", SpaceTypeEnum.BKCI.value, BKMS_SPACE_ID_PREFIX + "%"]
        if not cls._restrict_to_biz_ids(conditions, params, biz_ids):
            return ["1=0"], []
        if space_uids:
            placeholders = ", ".join(["(BINARY %s, BINARY %s)"] * len(space_uids))
            conditions.append(f"(s.space_type_id, s.space_id) IN ({placeholders})")
            for uid in space_uids:
                params.extend(uid.split("__", 1))
        if space_type == "bcs":
            conditions.extend(["s.space_type_id = %s", "s.space_code IS NOT NULL", "s.space_code <> ''"])
            params.append(SpaceTypeEnum.BKCI.value)
        elif space_type:
            conditions.append("s.space_type_id = %s")
            params.append(space_type)
        return conditions, params

    @classmethod
    def read_space_page_types(cls):
        with connections["monitor_api"].cursor() as cursor:
            cursor.execute("SELECT type_id, type_name FROM metadata_spacetype", [])
            return dict(cursor.fetchall())

    @classmethod
    def read_space_page_candidates(
        cls, tenant, biz_ids, space_type, after_id, limit, *, type_names, space_uids=None, row_ids=None
    ):
        conditions, params = cls._page_conditions(tenant, biz_ids, space_type, after_id, space_uids)
        if not type_names:
            return []
        conditions.append("s.space_type_id IN (" + ", ".join(["%s"] * len(type_names)) + ")")
        params.extend(type_names)
        if row_ids:
            conditions.append("s.id IN (" + ", ".join(["%s"] * len(row_ids)) + ")")
            params.extend(row_ids)
        seek = not (biz_ids is not None or space_uids or row_ids or space_type)
        return cls._read_space_rows(conditions, params, limit=limit, type_names=type_names, seek=seek)

    @classmethod
    def iter_space_search_keys(
        cls, tenant, biz_ids, space_type, after_id, *, type_names, space_uids=None, text_filter="", search_pinyin=False
    ):
        """Read only the keys used by the selector. Keyset windows bound the DB driver's buffer."""
        conditions, params = cls._page_conditions(tenant, biz_ids, space_type, after_id, space_uids)
        if not type_names:
            return
        pinyin_patterns = ()
        if search_pinyin:
            connection = connections["monitor_api"]
            # MySQL 5.7's regex engine is byte-oriented. Keep phonetic matching in Python there.
            bounded = space_uids or (biz_ids is not None and len(biz_ids) <= 500)
            if (
                bounded
                or getattr(connection, "mysql_version", (8, 0)) < (8, 0)
                or getattr(connection, "mysql_is_mariadb", False)
            ):
                text_filter = ""
            else:
                pinyin_patterns = pinyin_search_patterns(text_filter)
        if text_filter:
            text = """LOCATE(%s, LOWER(CONCAT_WS(CHAR(0), s.space_name, s.space_id, s.id,
                IF(s.space_type_id = 'bkcc', s.space_id, CONCAT('-', s.id)), s.space_code,
                CONCAT(s.space_type_id, '__', s.space_id),
                IF(s.space_type_id = 'bkci' AND s.space_code <> '', '容器项目', '')))) > 0"""
            params.append(text_filter)
            matching_types = [kind for kind, label in type_names.items() if text_filter in label.lower()]
            if matching_types:
                text += " OR s.space_type_id IN (" + ", ".join(["%s"] * len(matching_types)) + ")"
                params.extend(matching_types)
            if pinyin_patterns:
                text += " OR (" + " AND ".join(["s.space_name REGEXP %s"] * len(pinyin_patterns)) + ")"
                params.extend(pinyin_patterns)
            conditions.append("(" + text + ")")
        index = "FORCE INDEX (PRIMARY)" if biz_ids is None and not space_uids and not space_type else ""
        base = f"""SELECT s.id, s.space_type_id, s.space_id, s.space_name, s.space_code
                   FROM metadata_space s {index} WHERE """ + " AND ".join(conditions)
        window = 4096
        while True:
            with connections["monitor_api"].cursor() as cursor:
                cursor.execute(base + " AND s.id > %s ORDER BY s.id LIMIT %s", [*params, after_id, window])
                rows = cursor.fetchall()
            for row in rows:
                if row[1] in type_names:
                    yield (*row, type_names[row[1]])
            if len(rows) < window:
                return
            after_id = rows[-1][0]

    @classmethod
    def list_spaces_dict(
        cls, using_cache=True, bk_tenant_id: str | None = None, filters: dict[str, str | int] | None = None
    ) -> list[dict]:
        """
        告警性能版本获取空间列表
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

        conditions = [f"s.{field} = %s" for field in filters or {}]
        params = list((filters or {}).values())
        if bk_tenant_id:
            conditions.append("s.bk_tenant_id = BINARY %s")
            params.append(bk_tenant_id)
        spaces = cls._read_space_rows(conditions, params)

        # db 无数据， 开发环境给出提示， 生产环境不提示（正常部署不会出现该问题）
        if not spaces and settings.RUN_MODE == "DEVELOP" and not filters and not bk_tenant_id:
            raise Exception(
                "未成功初始化metadata空间数据，请执行"
                "env DJANGO_CONF_MODULE=conf.worker.development.enterprise python manage.py init_space_data"
            )

        _space_transform.clear()
        for space in spaces:
            cc_space = space["space_type_id"] == SpaceTypeEnum.BKCC.value
            if cc_space:
                # 仅针对cmdb空间，进行缓存， 非cc空间，需要额外resource信息，走api丰富。
                local_mem.set(f"metadata:spaces_map:{space['space_uid']}", space, timeout=SPACE_CACHE_TIMEOUT)
            else:
                # 非cmdb 空间，内存暂存一份bk_biz_id -> space_uid 的映射
                _space_transform[space["bk_biz_id"]] = space["space_uid"]

        # 如果指定了过滤条件，则不缓存
        if not filters:
            local_mem.set(cache_key, spaces, timeout=SPACE_CACHE_TIMEOUT)

        return spaces

    @classmethod
    def list_space_dicts_by_biz_ids(cls, bk_biz_ids: list[int], bk_tenant_id: str | None = None) -> list[dict]:
        """按 bk_biz_id 精确查询空间，只返回 bk_biz_id（供权限候选构造使用）。

        与 `list_spaces_dict` 的**一致之处**：同样 `JOIN metadata_spacetype`（类型为空或
        不在类型表里的空间两边都查不出来）、同样的租户过滤口径、同样的 bk_biz_id 推导
        （CMDB 空间取 `space_id`，其余取 `-id`）。因此返回的候选集合是 `list_spaces_dict`
        的子集，不会多出旧路径没有的业务。

        差异只有两点：
        1. 只查请求涉及的空间，不做全表扫描；
        2. 不读写 `caches["space"]`，也不修改模块级 `_space_transform` 映射 —— 后者是
           `get_space_detail` 负数分支依赖的全局状态，污染它会让其他业务取到错误空间。

        负数 bk_biz_id 表示非 CMDB 空间，满足 `bk_biz_id = -metadata_space.id`。
        """
        if not bk_biz_ids:
            return []

        # 归一化为 int：调用方（parse_biz_item）已保证类型，这里再做一次防御，
        # 避免字符串入参在 `biz_id > 0` 比较处抛 TypeError。
        normalized_biz_ids = [int(biz_id) for biz_id in bk_biz_ids]
        cc_space_ids = [str(biz_id) for biz_id in normalized_biz_ids if biz_id > 0]
        non_cc_space_ids = [abs(biz_id) for biz_id in normalized_biz_ids if biz_id < 0]
        if not cc_space_ids and not non_cc_space_ids:
            return []

        cc_placeholders = ", ".join(["%s"] * len(cc_space_ids))
        non_cc_placeholders = ", ".join(["%s"] * len(non_cc_space_ids))
        where_parts = []
        sql_params: list[object] = []
        if cc_space_ids:
            where_parts.append(f"(s.space_type_id = %s AND s.space_id IN ({cc_placeholders}))")
            sql_params.append(SpaceTypeEnum.BKCC.value)
            sql_params.extend(cc_space_ids)
        if non_cc_space_ids:
            where_parts.append(f"(s.space_type_id != %s AND s.id IN ({non_cc_placeholders}))")
            sql_params.append(SpaceTypeEnum.BKCC.value)
            sql_params.extend(non_cc_space_ids)

        # JOIN 必须与 list_spaces_dict 一致（INNER JOIN）：space_type_id 为空、或不在
        # metadata_spacetype 中的空间，旧实现不会返回。漏掉 JOIN 只会让这里多出旧路径
        # 不存在的候选，在 skip_check / 全量授权时被误判为有权限，属于权限放宽。
        sql = f"""
            SELECT s.id, s.bk_tenant_id, s.space_type_id, s.space_id
            FROM metadata_space s
            JOIN metadata_spacetype t ON s.space_type_id = t.type_id
            WHERE {" OR ".join(where_parts)}
        """
        with connections["monitor_api"].cursor() as cursor:
            cursor.execute(sql, sql_params)
            columns = [col[0] for col in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

        space_dicts: list[dict] = []
        for row in rows:
            # 与 list_spaces_dict 的租户口径保持一致
            if bk_tenant_id and row["bk_tenant_id"] != bk_tenant_id:
                continue
            if row["space_type_id"] == SpaceTypeEnum.BKCC.value:
                space_dicts.append({"bk_biz_id": int(row["space_id"])})
            else:
                space_dicts.append({"bk_biz_id": -row["id"]})
        return space_dicts

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

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

from collections import defaultdict
from dataclasses import asdict
from typing import Any

from django.db.transaction import atomic
from django.utils.translation import gettext as _

from apps.log_search.constants import (
    INDEX_SET_NOT_EXISTED,
    FavoriteGroupType,
    FavoriteListOrderType,
    FavoriteSourceType,
    FavoriteType,
    FavoriteVisibleType,
    IndexSetType,
)
from apps.log_search.exceptions import (
    FavoriteAlreadyExistException,
    FavoriteGroupAlreadyExistException,
    FavoriteGroupNotAllowedDeleteException,
    FavoriteGroupNotExistException,
    FavoriteNotAllowedAccessException,
    FavoriteNotExistException,
    FavoriteUnionSearchAlreadyExistException,
    FavoriteUnionSearchNotExistException,
    FavoriteVisibleTypeNotAllowedModifyException,
)
from apps.log_search.models import (
    Favorite,
    FavoriteGroup,
    FavoriteUnionSearch,
    LogIndexSet,
)
from apps.models import model_to_dict
from apps.utils.local import (
    get_request_app_code,
    get_request_external_username,
    get_request_username,
)
from apps.utils.lucene import (
    LuceneChecker,
    LuceneParser,
    LuceneTransformer,
    generate_query_string,
)
from apps.utils.scene_lucene import build_scene_query_string


def _build_query_string_by_source(favorite: Favorite) -> str:
    """收藏详情/列表的 query_string 拼装入口。

    场景化收藏会把 table_id_conditions / scene_filter_values 一并拼上，
    与场景检索历史接口的可读预览保持一致。
    """
    source_type = favorite.source_type or FavoriteSourceType.INDEX_SET.value
    if source_type == FavoriteSourceType.SCENE.value:
        merged = dict(favorite.params or {})
        merged["table_id_conditions"] = favorite.table_id_conditions or []
        merged["scene_filter_values"] = favorite.scene_filter_values or []
        return build_scene_query_string(merged)
    return generate_query_string(favorite.params)


class FavoriteHandler:
    data: Favorite | None = None

    def __init__(self, favorite_id: int = None, space_uid: str = None) -> None:
        self.favorite_id = favorite_id
        self.space_uid = space_uid
        self.username = get_request_external_username() or get_request_username()
        self.source_app_code = get_request_app_code()
        if favorite_id:
            try:
                self.data = Favorite.objects.get(pk=favorite_id)
                # 组归属校验使用收藏自身的 source_type，避免 scene 收藏被 index_set 组覆盖判定
                user_groups: list[dict[str, Any]] = FavoriteGroup.get_user_groups(
                    self.data.space_uid,
                    self.username,
                    source_type=self.data.source_type or FavoriteSourceType.INDEX_SET.value,
                )
                if self.data.group_id not in [i["id"] for i in user_groups]:
                    raise FavoriteNotAllowedAccessException()
            except Favorite.DoesNotExist:
                raise FavoriteNotExistException()

    def retrieve(self) -> dict:
        """收藏详情"""
        result = model_to_dict(self.data)
        source_type = self.data.source_type or FavoriteSourceType.INDEX_SET.value
        if source_type == FavoriteSourceType.SCENE.value:
            # 场景化收藏与索引集解耦：不查 LogIndexSet，直接回显 scene 元信息
            result["query_string"] = _build_query_string_by_source(self.data)
            return result
        if result["index_set_type"] == IndexSetType.UNION.value:
            active_index_set_id_dict = {
                i["index_set_id"]: {"index_set_name": i["index_set_name"], "is_active": i["is_active"]}
                for i in LogIndexSet.objects.filter(index_set_id__in=result["index_set_ids"]).values(
                    "index_set_id", "index_set_name", "is_active"
                )
            }
            is_actives = []
            index_set_names = []
            for index_set_id in result["index_set_ids"]:
                if active_index_set_id_dict.get(index_set_id):
                    is_actives.append(active_index_set_id_dict[index_set_id]["is_active"])
                    index_set_names.append(active_index_set_id_dict[index_set_id]["index_set_name"])
                else:
                    is_actives.append(False)
                    index_set_names.append(INDEX_SET_NOT_EXISTED)
            result["is_actives"] = is_actives
            result["index_set_names"] = index_set_names
        else:
            if LogIndexSet.objects.filter(index_set_id=result["index_set_id"]).exists():
                result["is_active"] = True
                result["index_set_name"] = LogIndexSet.objects.get(index_set_id=result["index_set_id"]).index_set_name
            else:
                result["is_active"] = False
                result["index_set_name"] = INDEX_SET_NOT_EXISTED

        result["query_string"] = _build_query_string_by_source(self.data)
        return result

    def list_group_favorites(
        self,
        order_type: str = FavoriteListOrderType.NAME_ASC.value,
        source_type: str = None,
    ) -> list:
        """收藏栏分组后且排序后的收藏列表（按 source_type 隔离）"""
        # 列表与分组按同一 source_type 桶取，避免 favorites 中出现 group_info 缺失的 group_id
        effective_source_type = source_type or FavoriteSourceType.INDEX_SET.value
        groups = FavoriteGroupHandler(space_uid=self.space_uid).list(source_type=effective_source_type)
        public_group_ids = []
        group_info = {}
        for i in groups:
            group_info[i["id"]] = i
            if i["group_type"] in [FavoriteGroupType.PUBLIC.value, FavoriteGroupType.UNGROUPED.value]:
                # UNGROUPED在favorites表中也是public
                public_group_ids.append(i["id"])
        favorites = Favorite.get_user_favorite(
            space_uid=self.space_uid,
            username=self.username,
            order_type=order_type,
            public_group_ids=public_group_ids,
            source_type=effective_source_type,
        )
        # 渲染兜底：历史孤儿 fav（group_id 不在当前 source_type 桶内）统一归到 ungrouped，避免被静默吞掉
        visible_group_ids = {g["id"] for g in groups}
        ungrouped_id = next(
            (g["id"] for g in groups if g["group_type"] == FavoriteGroupType.UNGROUPED.value),
            None,
        )
        favorites_by_group = defaultdict(list)
        for favorite in favorites:
            gid = favorite["group_id"]
            if gid not in visible_group_ids and ungrouped_id is not None:
                gid = ungrouped_id
            favorites_by_group[gid].append(favorite)
        return [
            {
                "group_id": group["id"],
                "group_name": group_info[group["id"]]["name"],
                "group_type": group_info[group["id"]]["group_type"],
                "favorites": favorites_by_group[group["id"]],
            }
            for group in groups
        ]

    def list_favorites(
        self,
        order_type: str = FavoriteListOrderType.NAME_ASC.value,
        source_type: str = None,
    ) -> list:
        """管理界面列出根据name A-Z排序的所有收藏（按 source_type 隔离）"""
        effective_source_type = source_type or FavoriteSourceType.INDEX_SET.value
        groups = FavoriteGroupHandler(space_uid=self.space_uid).list(source_type=effective_source_type)
        public_group_ids = []
        group_info = {}
        for i in groups:
            group_info[i["id"]] = i
            if i["group_type"] in [FavoriteGroupType.PUBLIC.value, FavoriteGroupType.UNGROUPED.value]:
                # UNGROUPED在favorites表中也是public
                public_group_ids.append(i["id"])
        favorites = Favorite.get_user_favorite(
            space_uid=self.space_uid,
            username=self.username,
            order_type=order_type,
            public_group_ids=public_group_ids,
            source_type=effective_source_type,
        )

        # 渲染兜底：孤儿 fav 的 group_id 不在当前 source_type 桶里时，重定向到 ungrouped，避免 KeyError 500
        ungrouped_id = next(
            (g["id"] for g in groups if g["group_type"] == FavoriteGroupType.UNGROUPED.value),
            None,
        )

        ret = list()
        for fi in favorites:
            fi_source = fi.get("source_type") or FavoriteSourceType.INDEX_SET.value
            display_group_id = fi["group_id"]
            if display_group_id not in group_info and ungrouped_id is not None:
                display_group_id = ungrouped_id
            data = {
                "id": fi["id"],
                "name": fi["name"],
                "group_id": display_group_id,
                "group_name": group_info.get(display_group_id, {}).get("name", _("未分组")),
                "index_set_type": fi["index_set_type"],
                "visible_type": fi["visible_type"],
                "search_mode": fi["search_mode"],
                "params": fi["params"],
                "search_fields": fi["params"].get("search_fields", []) if fi.get("params") else [],
                "keyword": fi["params"].get("keyword", "") if fi.get("params") else "",
                "is_enable_display_fields": fi["is_enable_display_fields"],
                "display_fields": fi["display_fields"],
                "source_type": fi_source,
                "created_by": fi["created_by"],
                "updated_by": fi["updated_by"],
                "updated_at": fi["updated_at"],
            }
            if fi_source == FavoriteSourceType.SCENE.value:
                data["scene_id"] = fi.get("scene_id")
                data["table_id_conditions"] = fi.get("table_id_conditions") or []
                data["scene_filter_values"] = fi.get("scene_filter_values") or []
            elif fi["index_set_type"] == IndexSetType.SINGLE.value:
                data["index_set_id"] = fi["index_set_id"]
                data["index_set_name"] = fi["index_set_name"]
                data["is_active"] = fi["is_active"]
            else:
                data["index_set_ids"] = fi["index_set_ids"]
                data["index_set_names"] = fi["index_set_names"]
                data["is_actives"] = fi["is_actives"]

            ret.append(data)

        return ret

    @atomic
    def create_or_update(
        self,
        name: str,
        ip_chooser: dict,
        addition: list,
        keyword: str,
        visible_type: str,
        search_fields: list,
        is_enable_display_fields: bool,
        display_fields: list,
        chart_params: dict = None,
        search_mode: str = None,
        index_set_id: int = None,
        group_id: int = None,
        index_set_ids: list = None,
        index_set_type: str = IndexSetType.SINGLE.value,
        favorite_type: str = FavoriteType.SEARCH.value,
        source_type: str = None,
        scene_id: str = None,
        table_id_conditions: list = None,
        scene_filter_values: list = None,
    ) -> dict:
        chart_params = chart_params or {}
        # 构建params（场景化收藏沿用同一份结构，便于复用 generate_query / get_search_fields 等）
        params = {
            "ip_chooser": ip_chooser,
            "addition": addition,
            "keyword": keyword,
            "search_fields": search_fields,
            "chart_params": chart_params,
        }
        space_uid = self.space_uid if self.space_uid else self.data.space_uid
        search_mode = search_mode if search_mode else self.data.search_mode

        # 收藏来源类型：更新时若未传则沿用既有值；新建时默认 index_set
        if source_type is None:
            source_type = (self.data.source_type if self.data else FavoriteSourceType.INDEX_SET.value)
        is_scene = source_type == FavoriteSourceType.SCENE.value

        if group_id:
            # 三重属主校验：避免前端跨 space / 跨 source_type / 跨 owner 传入 group_id 写出孤儿数据
            try:
                favorite_group = FavoriteGroup.objects.get(id=group_id, space_uid=space_uid)
            except FavoriteGroup.DoesNotExist:
                raise FavoriteGroupNotExistException()
            fg_source_type = favorite_group.source_type or FavoriteSourceType.INDEX_SET.value
            if fg_source_type != source_type:
                raise FavoriteGroupNotExistException()
            if favorite_group.group_type == FavoriteGroupType.PRIVATE.value:
                if favorite_group.created_by != self.username:
                    raise FavoriteGroupNotExistException()
                visible_type = FavoriteVisibleType.PRIVATE.value
            else:
                visible_type = FavoriteVisibleType.PUBLIC.value
        else:
            # Lazy 创建按 Favorite 自身 source_type 分桶，避免 scene 收藏挂到 index_set 组
            if visible_type == FavoriteVisibleType.PRIVATE.value:
                favorite_group = FavoriteGroup.get_or_create_private_group(
                    space_uid=space_uid, username=self.username, source_type=source_type
                )
            else:
                favorite_group = FavoriteGroup.get_or_create_ungrouped_group(
                    space_uid=space_uid, source_type=source_type
                )
            group_id = favorite_group.id

        if self.data:
            # 公开收藏转个人收藏仅限于自己创建的
            if favorite_group.group_type == FavoriteGroupType.PRIVATE.value:
                if self.data.created_by != self.username:
                    raise FavoriteVisibleTypeNotAllowedModifyException()
            if (self.data.name != name or self.data.group_id != group_id) and Favorite.objects.filter(
                name=name,
                space_uid=space_uid,
                group_id=group_id,
                created_by=self.username,
            ).exists():
                raise FavoriteAlreadyExistException()

            update_model_fields = {
                "name": name,
                "group_id": group_id,
                "params": params,
                "visible_type": visible_type,
                "search_mode": search_mode,
                "is_enable_display_fields": is_enable_display_fields,
                "display_fields": display_fields,
                "source_type": source_type,
            }
            if is_scene:
                if scene_id is not None:
                    update_model_fields["scene_id"] = scene_id
                if table_id_conditions is not None:
                    update_model_fields["table_id_conditions"] = table_id_conditions
                if scene_filter_values is not None:
                    update_model_fields["scene_filter_values"] = scene_filter_values
            else:
                if index_set_id:
                    update_model_fields["index_set_id"] = index_set_id
                    update_model_fields["index_set_type"] = index_set_type
                if index_set_ids:
                    update_model_fields["index_set_ids"] = index_set_ids
                    update_model_fields["index_set_type"] = index_set_type

            for key, value in update_model_fields.items():
                setattr(self.data, key, value)
            self.data.save()

        else:
            if Favorite.objects.filter(
                name=name, space_uid=space_uid, group_id=group_id, created_by=self.username
            ).exists():
                raise FavoriteAlreadyExistException()
            create_kwargs = dict(
                space_uid=space_uid,
                name=name,
                group_id=group_id,
                params=params,
                visible_type=visible_type,
                search_mode=search_mode,
                is_enable_display_fields=is_enable_display_fields,
                display_fields=display_fields,
                favorite_type=favorite_type,
                source_type=source_type,
                created_by=self.username,
            )
            if is_scene:
                create_kwargs.update(
                    {
                        "scene_id": scene_id,
                        "table_id_conditions": table_id_conditions or [],
                        "scene_filter_values": scene_filter_values or [],
                    }
                )
            else:
                create_kwargs.update(
                    {
                        "index_set_id": index_set_id,
                        "index_set_ids": index_set_ids,
                        "index_set_type": index_set_type,
                    }
                )
            self.data = Favorite.objects.create(**create_kwargs)

        return model_to_dict(self.data)

    @staticmethod
    @atomic
    def batch_update(params: list):
        for param in params:
            # source_type / scene_id 视为不可变（避免误操作把场景化收藏改成普通收藏），
            # 但 table_id_conditions / scene_filter_values 允许批量调整
            FavoriteHandler(favorite_id=param["id"]).create_or_update(
                name=param["name"],
                ip_chooser=param["ip_chooser"],
                addition=param["addition"],
                keyword=param["keyword"],
                visible_type=param["visible_type"],
                search_mode=param.get("search_mode"),
                search_fields=param["search_fields"],
                is_enable_display_fields=param["is_enable_display_fields"],
                display_fields=param["display_fields"],
                group_id=param["group_id"],
                table_id_conditions=param.get("table_id_conditions"),
                scene_filter_values=param.get("scene_filter_values"),
            )

    def delete(self):
        self.data.delete()

    @staticmethod
    def batch_delete(id_list: list):
        Favorite.objects.filter(id__in=id_list).delete()

    @staticmethod
    def get_search_fields(keyword: str) -> list:
        """获取检索语句中可以拆分的字段"""
        fields = [asdict(field) for field in LuceneParser(keyword=keyword).parsing()]

        return fields

    @staticmethod
    def generate_query_by_ui(keyword: str, params: list) -> str:
        """根据params里的参数名以及Value进行替换"""
        return LuceneTransformer().transform(keyword=keyword, params=params)

    @staticmethod
    def inspect(keyword: str, fields: list[dict[str, Any]] = None) -> dict:
        return LuceneChecker(query_string=keyword, fields=fields).resolve()


class FavoriteGroupHandler:
    data: FavoriteGroup | None = None

    def __init__(self, group_id: int = None, space_uid: str = None) -> None:
        self.group_id = group_id
        self.space_uid = space_uid
        self.username = get_request_external_username() or get_request_username()
        self.source_app_code = get_request_app_code()
        if group_id:
            try:
                self.data = FavoriteGroup.objects.get(pk=group_id)
            except FavoriteGroup.DoesNotExist:
                raise FavoriteGroupNotExistException()

    @staticmethod
    def _normalize_group_name(group: dict) -> dict:
        """对私有/未分组按 group_type 强制兜底为本地化名称，不依赖 DB 中存的字面值。

        使用 gettext 而非 lazy，确保在 request locale 下即时翻译。
        """
        group_type = group.get("group_type")
        if group_type == FavoriteGroupType.PRIVATE.value:
            group["name"] = _("个人收藏")
        elif group_type == FavoriteGroupType.UNGROUPED.value:
            group["name"] = _("未分组")
        return group

    def retrieve(self) -> dict:
        return self._normalize_group_name(model_to_dict(self.data))

    def list(self, source_type: str = FavoriteSourceType.INDEX_SET.value) -> list:
        """获取所有收藏组（按 source_type 隔离）"""
        groups = FavoriteGroup.get_user_groups(
            space_uid=self.space_uid, username=self.username, source_type=source_type
        )
        return [self._normalize_group_name(g) for g in groups]

    @atomic
    def create_or_update(
        self, name: str, source_type: str = FavoriteSourceType.INDEX_SET.value
    ) -> dict:
        """创建和修改都是针对公开组的"""
        space_uid = self.space_uid if self.space_uid else self.data.space_uid
        group_type = FavoriteGroupType.PUBLIC.value
        # 检查name是否可用：同一 space_uid + source_type 维度内重名校验
        if (self.data and self.data.name != name) or not self.data:
            qs = FavoriteGroup.objects.filter(name=name, space_uid=space_uid)
            if self.data:
                qs = qs.filter(source_type=self.data.source_type)
            else:
                qs = qs.filter(source_type=source_type)
            if qs.exists():
                raise FavoriteGroupAlreadyExistException()

        # 修改
        if self.data:
            self.data.name = name
            self.data.save()
        # 创建
        else:
            self.data = FavoriteGroup.objects.create(
                name=name,
                group_type=group_type,
                space_uid=space_uid,
                source_app_code=self.source_app_code,
                source_type=source_type,
            )

        return self._normalize_group_name(model_to_dict(self.data))

    @atomic
    def delete(self) -> None:
        """删除公开分组，并将组内收藏移到未分组"""
        # 只有公开组可以被删除
        if self.data.group_type != FavoriteGroupType.PUBLIC.value:
            raise FavoriteGroupNotAllowedDeleteException()
        # 将该组的收藏全部归到与本组相同 source_type 的未分组
        unknown_group_id = FavoriteGroup.get_or_create_ungrouped_group(
            space_uid=self.data.space_uid,
            source_type=self.data.source_type or FavoriteSourceType.INDEX_SET.value,
        )
        Favorite.objects.filter(group_id=self.group_id).update(group_id=unknown_group_id.id)
        self.data.delete()


class FavoriteUnionSearchHandler:
    data: FavoriteUnionSearch | None = None

    def __init__(self, favorite_union_id: int = None, space_uid: str = None) -> None:
        self.favorite_union_id = favorite_union_id
        self.space_uid = space_uid
        self.username = get_request_external_username() or get_request_username()
        if favorite_union_id:
            try:
                self.data = FavoriteUnionSearch.objects.get(id=favorite_union_id)
            except FavoriteUnionSearch.DoesNotExist:
                raise FavoriteUnionSearchNotExistException()

    def list(self) -> list[dict]:
        """联合检索获取指定空间下用户搜索组合收藏列表"""
        objs = FavoriteUnionSearch.objects.filter(space_uid=self.space_uid, username=self.username)
        ret = [model_to_dict(obj) for obj in objs]
        return ret

    @atomic
    def create_or_update(self, data: dict) -> dict:
        """联合检索搜索组合收藏创建或者更新"""

        params = {"username": self.username, "name": data["name"]}

        if not self.data:
            params.update({"space_uid": data["space_uid"]})
            check_query_set = FavoriteUnionSearch.objects.filter(**params)
        else:
            params.update({"space_uid": self.data.space_uid})
            check_query_set = FavoriteUnionSearch.objects.filter(**params).exclude(id=self.favorite_union_id)

        if check_query_set.exists():
            raise FavoriteUnionSearchAlreadyExistException(
                FavoriteUnionSearchAlreadyExistException.MESSAGE.format(name=data["name"])
            )

        if not self.data:
            params.update(
                {
                    "defaults": {
                        "index_set_ids": data["index_set_ids"],
                    }
                }
            )
            obj, is_create = FavoriteUnionSearch.objects.update_or_create(**params)
        else:
            self.data.name = data["name"]
            self.data.index_set_ids = data["index_set_ids"]
            self.data.save()
            obj = self.data

        return model_to_dict(obj)

    def retrieve(self) -> dict:
        """联合检索搜索组合收藏详情"""
        return model_to_dict(self.data)

    def destroy(self):
        """联合检索搜索组合收藏删除"""
        self.data.delete()

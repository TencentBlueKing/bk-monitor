"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
from typing import Any

from django.conf import settings
from django.utils.translation import gettext_lazy as _lazy
from iam import Resource

from bk_dataview.api import get_org_by_id
from bk_dataview.models import Dashboard, Org
from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from bkmonitor.utils.cache import lru_cache_with_ttl
from core.errors.iam import ResourceNotExistError


class ResourceMeta(metaclass=abc.ABCMeta):
    """
    资源定义
    """

    # === IAM 资源元数据声明 ===
    system_id: str = ""
    id: str = ""
    name: str = ""
    selection_mode: str = ""
    related_instance_selections: list = ""

    # === 资源拓扑关系 ===
    # 父资源类型；顶级资源为 None。
    parent_resource: type["ResourceMeta"] | None = None

    @classmethod
    def to_json(cls):
        return {
            "system_id": cls.system_id,
            "id": cls.id,
            "selection_mode": cls.selection_mode,
            "related_instance_selections": cls.related_instance_selections,
        }

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return Resource(cls.system_id, cls.id, str(instance_id), attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建资源实例（带实例名称）可由子类重载
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """
        return cls.create_simple_instance(instance_id, attribute)

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {instance_id: parent_instance_id}。

        注意：
          - “是否有父资源”这一模型层信息，请通过 `parent_resource` 类属性判断，
            不要用“本方法是否返回空”来隐式判断。
          - 顶级资源（parent_resource is None）不应重写本方法，保持默认返回 {}。
          - 非顶级资源子类应重写本方法，返回本实例到父实例 id 的批量映射。
        """
        return {}

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {instance_id: display_name}。子类重写。"""
        return {}


class Business(ResourceMeta):
    """
    CMDB业务
    """

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "space"
    name = _lazy("空间")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "space_list"}]

    # 顶级资源：无父资源
    parent_resource = None

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        """
        创建简单资源实例
        :param instance_id: 实例ID
        :param attribute: 属性kv对
        """

        # 注意，此处 instance_id 有可能是 bk_biz_id，或者是space_uid，需要做统一转换
        try:
            bk_biz_id = int(instance_id)
        except Exception:  # pylint: disable=broad-except
            bk_biz_id = None

        try:
            if bk_biz_id is None:
                space = space_api.SpaceApi.get_space_detail(space_uid=instance_id)
            else:
                space = space_api.SpaceApi.get_space_detail(space_uid=bk_biz_id_to_space_uid(bk_biz_id))
            bk_biz_id = str(space_uid_to_bk_biz_id(space_uid=space.space_uid, id=space.id))
            space_name = f"[{space.space_type_id}] {space.space_name}"
        except Exception:  # pylint: disable=broad-except:
            bk_biz_id = str(instance_id)
            space_name = instance_id

        attribute = attribute or {}
        attribute.update({"id": bk_biz_id, "name": space_name})
        return Resource(cls.system_id, cls.id, bk_biz_id, attribute)

    @classmethod
    def create_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = cls.create_simple_instance(instance_id, attribute)
        return resource

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {bk_biz_id: "[空间类型中文] 空间名"}。

        注意 instance_id 是 bk_biz_id 字符串，与 metadata.Space 的映射规则如下
        （见 bkm_space.utils.space_uid_to_bk_biz_id / Space.get_bk_biz_id）：
          - CMDB 业务(bkcc): bk_biz_id = int(Space.space_id)，为正数；
          - 其他类型空间: bk_biz_id = -Space.pk，为负数。
        因此需要按正/负数分别用不同字段回查；并且正数分支必须限定
        space_type_id=bkcc，避免与其他类型下同值 space_id 的记录发生串扰。
        """
        from metadata.models import Space, SpaceType
        from metadata.models.space.constants import SpaceTypes

        if not instance_ids:
            return {}

        positive_ids: set[str] = set()
        negative_pks: set[int] = set()
        for raw in instance_ids:
            try:
                v = int(raw)
            except (TypeError, ValueError):
                continue
            if v > 0:
                positive_ids.add(str(v))
            elif v < 0:
                negative_pks.add(-v)

        if not positive_ids and not negative_pks:
            return {}

        # 空间类型中文名映射（type_id -> type_name），用于拼接展示名前缀。
        type_name_map = dict(SpaceType.objects.values_list("type_id", "type_name"))

        result: dict[str, str] = {}

        if positive_ids:
            # CMDB 业务：以 space_id 反查，必须限定 bkcc 类型避免串扰。
            qs = Space.objects.filter(
                space_type_id=SpaceTypes.BKCC.value,
                space_id__in=positive_ids,
            ).values("space_id", "space_type_id", "space_name")
            for row in qs:
                type_display = type_name_map.get(row["space_type_id"], row["space_type_id"])
                result[str(row["space_id"])] = f"[{type_display}] {row['space_name']}"

        if negative_pks:
            # 非 CMDB 空间：以主键 pk 反查，bk_biz_id = -pk。
            qs = Space.objects.filter(id__in=negative_pks).values("id", "space_type_id", "space_name")
            for row in qs:
                type_display = type_name_map.get(row["space_type_id"], row["space_type_id"])
                result[str(-row["id"])] = f"[{type_display}] {row['space_name']}"

        return result


class ApmApplication(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "apm_application"
    name = _lazy("APM应用")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "apm_application_list_v2"}]

    # 父资源：CMDB 业务/空间
    parent_resource = Business

    @classmethod
    def create_instance_by_info(cls, item: dict) -> Resource:
        instance_id = item["application_id"]
        bk_biz_id = str(item["bk_biz_id"])
        resource = super().create_simple_instance(
            instance_id=instance_id,
            attribute={
                "id": instance_id,
                "name": item["app_name"],
                "bk_biz_id": bk_biz_id,
                "_bk_iam_path_": f"/{Business.id},{bk_biz_id}/",
            },
        )
        return resource

    @classmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 60, decision_to_drop_func=lambda v: v is None)
    def _get_app_simple_info_by_id_or_none(cls, application_id: str) -> dict[str, Any] | None:
        """获取应用概要信息，不存在则返回 None。
        应用概要信息不会修改，此处给 60 min 的内存缓存，以提高整体鉴权性能。
        :param application_id: 应用 ID
        :return:
        """
        from apm_web.models import Application

        return (
            Application.objects.filter(application_id=application_id)
            .values("application_id", "app_name", "bk_biz_id")
            .first()
        )

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = super().create_simple_instance(instance_id, attribute)
        app_simple_info: dict[str, Any] | None = cls._get_app_simple_info_by_id_or_none(instance_id)
        if app_simple_info is None:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": app_simple_info["app_name"],
            "bk_biz_id": str(app_simple_info["bk_biz_id"]),
            "_bk_iam_path_": "/{},{}/".format(Business.id, app_simple_info["bk_biz_id"]),
        }
        return resource

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        from apm_web.models import Application

        if not instance_ids:
            return {}
        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "app_name")
        return {str(row["application_id"]): row["app_name"] for row in qs}

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        from apm_web.models import Application

        if not instance_ids:
            return {}
        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "bk_biz_id")
        return {str(row["application_id"]): str(row["bk_biz_id"]) for row in qs if row["bk_biz_id"] is not None}


class GrafanaDashboard(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "grafana_dashboard"
    name = _lazy("Grafana仪表盘")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "grafana_dashboard_list"}]

    # 父资源：CMDB 业务/空间
    parent_resource = Business

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = super().create_simple_instance(instance_id, attribute)
        dashboard = Dashboard.objects.filter(uid=instance_id).only("uid", "title", "org_id").first()
        if not dashboard:
            return resource

        org = get_org_by_id(dashboard.org_id)
        if not org:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": dashboard.title,
            "bk_biz_id": org["name"],
            "_bk_iam_path_": "/{},{}/".format(Business.id, org["name"]),
        }
        return resource

    # Grafana 前端约定：dashboard.folder_id=0 表示"未挂在任何目录下"，
    # 在 UI 上会显示到一个名为 "General" 的虚拟目录（DB 里并不存在这条 folder 记录）。
    GENERAL_FOLDER_NAME = "General"

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        """返回 {instance_id: display_name}。

        instance_id 只有两种形态：
          - Dashboard: "{org_id}|{uid}"
          - Folder:    "folder:{org_id}|{folder_id}"

        展示名与权限中心侧 GrafanaDashboardProvider 保持一致：
          - Folder:    "[目录] {folder_title}"
          - Dashboard: "[仪表盘] {folder_title}/{dashboard_title}"
                       dashboard.folder_id=0 或对应 folder 查不到时，
                       folder_title 兜底为 "General"（Grafana 虚拟目录）。
        """
        if not instance_ids:
            return {}

        # 在解析阶段就建立 uid/folder_id 到 raw_id 列表的反查映射，
        # 避免后续在数据库结果与 instance_ids 之间做 O(N*M) 的双层循环匹配。
        uid_to_raw_ids: dict[str, list[str]] = {}
        folder_id_to_raw_ids: dict[int, list[str]] = {}
        for raw_id in instance_ids:
            prefix, sep, suffix = raw_id.partition("|")
            if not sep:
                continue
            if prefix.startswith("folder:"):
                try:
                    folder_id_to_raw_ids.setdefault(int(suffix), []).append(raw_id)
                except (ValueError, TypeError):
                    continue
            else:
                if suffix:
                    uid_to_raw_ids.setdefault(suffix, []).append(raw_id)

        result: dict[str, str] = {}

        # Dashboard 分支：额外拼上所在 folder 的名称（folder_id=0 或查不到时兜底为 General）
        if uid_to_raw_ids:
            dashboards = list(
                Dashboard.objects.filter(uid__in=uid_to_raw_ids.keys()).values("uid", "title", "folder_id")
            )
            # folder_id=0 直接兜底为 General，不查库；只查真实的 folder_id
            need_folder_ids = {d["folder_id"] for d in dashboards if d["folder_id"]}
            folder_title_map: dict[int, str] = {}
            if need_folder_ids:
                folder_title_map = dict(
                    Dashboard.objects.filter(id__in=need_folder_ids, is_folder=1).values_list("id", "title")
                )
            for d in dashboards:
                folder_name = folder_title_map.get(d["folder_id"], cls.GENERAL_FOLDER_NAME)
                display_name = f"[仪表盘] {folder_name}/{d['title']}"
                for raw_id in uid_to_raw_ids.get(d["uid"], []):
                    result[raw_id] = display_name

        # Folder 分支：直接加 [目录] 前缀
        if folder_id_to_raw_ids:
            for row in Dashboard.objects.filter(id__in=folder_id_to_raw_ids.keys(), is_folder=1).values("id", "title"):
                for raw_id in folder_id_to_raw_ids.get(row["id"], []):
                    result[raw_id] = f"[目录] {row['title']}"

        return result

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        if not instance_ids:
            return {}

        org_ids: set[int] = set()
        id_to_org: dict[str, int] = {}
        for raw_id in instance_ids:
            try:
                prefix = raw_id.split("|")[0]
                org_id = int(prefix.replace("folder:", ""))
                org_ids.add(org_id)
                id_to_org[raw_id] = org_id
            except (ValueError, IndexError):
                continue

        org_map = dict(Org.objects.filter(id__in=org_ids).values_list("id", "name"))
        return {raw_id: str(org_map[oid]) for raw_id, oid in id_to_org.items() if oid in org_map}


class RumApplication(ResourceMeta):
    system_id = settings.BK_IAM_SYSTEM_ID
    id = "rum_application"
    name = _lazy("RUM应用")
    selection_mode = "instance"
    related_instance_selections = [{"system_id": system_id, "id": "rum_application_list_v2"}]

    # 父资源：CMDB 业务/空间
    parent_resource = Business

    @classmethod
    def create_instance_by_info(cls, item: dict) -> Resource:
        instance_id = item["application_id"]
        bk_biz_id = str(item["bk_biz_id"])
        resource = super().create_simple_instance(
            instance_id=instance_id,
            attribute={
                "id": instance_id,
                "name": item["app_name"],
                "bk_biz_id": bk_biz_id,
                "_bk_iam_path_": f"/{Business.id},{bk_biz_id}/",
            },
        )
        return resource

    @classmethod
    @lru_cache_with_ttl(maxsize=128, ttl=60 * 60, decision_to_drop_func=lambda v: v is None)
    def _get_app_simple_info_by_id_or_none(cls, application_id: str) -> dict[str, Any] | None:
        """获取应用概要信息，不存在则返回 None。
        应用概要信息不会修改，此处给 60 min 的内存缓存，以提高整体鉴权性能。
        :param application_id: 应用 ID
        :return:
        """
        from rum_web.models.application import Application

        return (
            Application.objects.filter(application_id=application_id)
            .values("application_id", "app_name", "bk_biz_id")
            .first()
        )

    @classmethod
    def create_simple_instance(cls, instance_id: str, attribute=None) -> Resource:
        resource = super().create_simple_instance(instance_id, attribute)
        app_simple_info: dict[str, Any] | None = cls._get_app_simple_info_by_id_or_none(instance_id)
        if app_simple_info is None:
            return resource

        resource.attribute = {
            "id": str(instance_id),
            "name": app_simple_info["app_name"],
            "bk_biz_id": str(app_simple_info["bk_biz_id"]),
            "_bk_iam_path_": "/{},{}/".format(Business.id, app_simple_info["bk_biz_id"]),
        }
        return resource

    @classmethod
    def batch_get_display_names(cls, instance_ids: set[str]) -> dict[str, str]:
        from rum_web.models.application import Application

        if not instance_ids:
            return {}
        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "app_name")
        return {str(row["application_id"]): row["app_name"] for row in qs}

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        from rum_web.models.application import Application

        if not instance_ids:
            return {}
        qs = Application.objects.filter(application_id__in=instance_ids).values("application_id", "bk_biz_id")
        return {str(row["application_id"]): str(row["bk_biz_id"]) for row in qs if row["bk_biz_id"] is not None}


class ResourceEnum:
    """
    资源类型枚举
    """

    BUSINESS = Business
    APM_APPLICATION = ApmApplication
    GRAFANA_DASHBOARD = GrafanaDashboard
    RUM_APPLICATION = RumApplication


_all_resources = {resource.id: resource for resource in ResourceEnum.__dict__.values() if hasattr(resource, "id")}


def get_resource_by_id(resource_id: str) -> ResourceMeta:
    """
    根据资源ID获取资源
    """
    if resource_id not in _all_resources:
        raise ResourceNotExistError({"resource_id": resource_id})

    return _all_resources[resource_id]

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
import operator
from functools import reduce

from django.conf import settings
from django.db.models import Q, QuerySet
from typing import Any
from iam import Resource
from bkmonitor.utils.cache import lru_cache_with_ttl
from bkm_space.utils import api as space_api
from bkm_space.utils import bk_biz_id_to_space_uid
from iam import DjangoQuerySetConverter
from iam.resource.provider import ListResult, ResourceProvider
from iam_engine.v4.callback import V3ResourceApiDispatcher

from apm_web.models import Application
from bk_dataview.api import get_org_by_id, get_org_by_name
from bk_dataview.models import Dashboard, Org
from bkm_space.define import SpaceTypeEnum
from bkm_space.utils import space_uid_to_bk_biz_id
from bkmonitor.iam import ResourceEnum
from bkmonitor.iam.resource import Business
from bkmonitor.iam.mode import get_mode_provider
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import resource
from core.drf_resource.viewsets import ResourceRoute, ResourceViewSet
from metadata.models import Space, SpaceType


class IAMViewSet(ResourceViewSet):
    permission_classes = []

    resource_routes = [
        ResourceRoute("GET", resource.iam.get_authority_meta, endpoint="get_authority_meta"),
        ResourceRoute("POST", resource.iam.check_allowed_by_action_ids, endpoint="check_allowed_by_action_ids"),
        ResourceRoute("POST", resource.iam.get_authority_detail, endpoint="get_authority_detail"),
        ResourceRoute("POST", resource.iam.check_allowed, endpoint="check_allowed"),
        ResourceRoute(
            "POST", resource.iam.check_allowed_by_apm_application, endpoint="check_allowed_by_apm_application"
        ),
        ResourceRoute("POST", resource.iam.get_authority_apply_info, endpoint="get_authority_apply_info"),
        ResourceRoute("GET", resource.iam.test, endpoint="test"),
    ]


class ExternalViewSet(ResourceViewSet):
    permission_classes = []

    resource_routes = [
        ResourceRoute("GET", resource.iam.get_external_permission_list, endpoint="get_external_permission_list"),
        ResourceRoute("GET", resource.iam.get_resource_by_action, endpoint="get_resource_by_action"),
        ResourceRoute(
            "POST", resource.iam.create_or_update_external_permission, endpoint="create_or_update_external_permission"
        ),
        ResourceRoute("POST", resource.iam.delete_external_permission, endpoint="delete_external_permission"),
        ResourceRoute("POST", resource.iam.create_or_update_authorizer, endpoint="create_or_update_authorizer"),
        ResourceRoute("GET", resource.iam.get_authorizer_by_biz, endpoint="get_authorizer_by_biz"),
        ResourceRoute("GET", resource.iam.get_authorizer_list, endpoint="get_authorizer_list"),
        ResourceRoute("GET", resource.iam.get_apply_record_list, endpoint="get_apply_record_list"),
    ]


class ResourceApiDispatcher(V3ResourceApiDispatcher):
    def __init__(self, iam, system):
        super().__init__(iam, system, mode_loader=lambda: get_mode_provider().get_mode())

    def _get_options(self, request):
        options = super()._get_options(request)
        if not options.get("bk_tenant_id"):
            options["bk_tenant_id"] = DEFAULT_TENANT_ID
        return options


class BaseResourceProvider(ResourceProvider, metaclass=abc.ABCMeta):
    @classmethod
    def create_simple_instance(cls, instance_id, attribute=None):
        return Resource(cls.system_id, cls.id, str(instance_id), attribute)

    def list_attr(self, **options):
        return ListResult(results=[], count=0)

    def list_attr_value(self, filter, page, **options):
        return ListResult(results=[], count=0)


class ApmApplicationProvider(BaseResourceProvider):
    resource_type = "apm_application"

    @staticmethod
    def get_queryset():
        return Application.objects

    def list_instance(self, filter, page, **options):
        bk_tenant_id = options["bk_tenant_id"]
        tenant_queryset = self.get_queryset().filter(bk_tenant_id=bk_tenant_id)
        queryset = tenant_queryset.none()
        with_path = False
        if not (filter.parent or filter.search or filter.resource_type_chain):
            queryset = tenant_queryset.all()
        elif filter.parent:
            parent_id = filter.parent["id"]
            if parent_id:
                queryset = tenant_queryset.filter(bk_biz_id=parent_id)
        elif filter.search and filter.resource_type_chain:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filter.search.get(self.resource_type, [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(app_alias__icontains=keyword) | Q(app_name__icontains=keyword)

            queryset = tenant_queryset.filter(q_filter)

        if options.get("include_resource_metadata"):
            with_path = True
            if filter.parent and filter.search:
                q_filter = Q()
                for keyword in filter.search.get(self.resource_type, []):
                    q_filter |= Q(app_alias__icontains=keyword) | Q(app_name__icontains=keyword)
                queryset = queryset.filter(q_filter)

        if not with_path:
            results = [
                {"id": str(item.pk), "display_name": item.app_alias}
                for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = []
            for item in queryset[page.slice_from : page.slice_to]:
                results.append(
                    {
                        "id": str(item.pk),
                        "display_name": item.app_alias,
                        "_bk_iam_path_": [
                            [
                                {
                                    "type": ResourceEnum.BUSINESS.id,
                                    "id": str(item.bk_biz_id),
                                    "display_name": str(item.bk_biz_id),
                                }
                            ]
                        ],
                    }
                )

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filter, **options):
        ids = []
        if filter.ids:
            for identity in filter.ids:
                try:
                    ids.append(int(identity))
                except (TypeError, ValueError):
                    if not options.get("include_resource_metadata"):
                        raise

        queryset = self.get_queryset().filter(pk__in=ids, bk_tenant_id=options["bk_tenant_id"])

        results = [{"id": str(item.pk), "display_name": item.app_alias} for item in queryset]
        if options.get("include_resource_metadata"):
            for result, item in zip(results, queryset):
                result["name"] = item.app_name
                result["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filter, page, **options):
        bk_tenant_id = options["bk_tenant_id"]
        if not filter.parent or "id" not in filter.parent:
            queryset = self.get_queryset().filter(bk_tenant_id=bk_tenant_id).all()
        else:
            parent_id = filter.parent.get("id")
            queryset = self.get_queryset().filter(bk_tenant_id=bk_tenant_id, bk_biz_id=parent_id)

        if filter.keyword:
            queryset = queryset.filter(app_alias__icontains=filter.keyword)

        results = [
            {"id": item.application_id, "display_name": item.app_alias}
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filter, page, **options):
        bk_tenant_id = options["bk_tenant_id"]
        if not filter.parent or "id" not in filter.parent:
            queryset = self.get_queryset().filter(bk_tenant_id=bk_tenant_id).all()
        else:
            parent_id = filter.parent.get("id")
            queryset = self.get_queryset().filter(bk_tenant_id=bk_tenant_id, bk_biz_id=parent_id)

        if filter.keyword:
            queryset = queryset.filter(app_alias__icontains=filter.keyword)

        results = [
            {"id": item.application_id, "display_name": item.app_alias}
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "apm_application"

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
        return (
            cls.get_queryset()
            .filter(application_id=application_id)
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
        if not instance_ids:
            return {}
        qs = cls.get_queryset().filter(application_id__in=instance_ids).values("application_id", "app_name")
        return {str(row["application_id"]): row["app_name"] for row in qs}

    @classmethod
    def batch_get_parent(cls, instance_ids: set[str]) -> dict[str, str]:
        if not instance_ids:
            return {}
        qs = cls.get_queryset().filter(application_id__in=instance_ids).values("application_id", "bk_biz_id")
        return {str(row["application_id"]): str(row["bk_biz_id"]) for row in qs if row["bk_biz_id"] is not None}


class RumApplicationProvider(ApmApplicationProvider):
    resource_type = "rum_application"

    @staticmethod
    def get_queryset():
        from rum_web.models.application import Application as RumApplication

        return RumApplication.objects

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "rum_application"


class SpaceQuerySetConverter(DjangoQuerySetConverter):
    def _eq(self, left, right):
        bk_biz_id = int(right)
        if bk_biz_id >= 0:
            return Q(space_type_id=SpaceTypeEnum.BKCC) & Q(space_id=bk_biz_id)
        else:
            return Q(id=-bk_biz_id)

    def _not_eq(self, left, right):
        return ~self._eq(left, right)

    def _in(self, left, right):
        return reduce(operator.or_, [self._eq(left, bk_biz_id) for bk_biz_id in right])

    def _not_in(self, left, right):
        return reduce(operator.and_, [self._not_eq(left, bk_biz_id) for bk_biz_id in right])


class SpaceProvider(BaseResourceProvider):
    @classmethod
    def get_space_queryset(cls):
        return Space.objects.exclude(space_id="0")

    @classmethod
    def generate_resources(cls, queryset):
        space_types = {t.type_id: t.type_name for t in SpaceType.objects.all()}
        resources = [
            {
                # 注意：由于 space_uid 长度会超过权限中心的限制 (32位)，因此资源ID使用业务ID代替
                # 规则：当空间类型为业务ID时，使用业务ID作为资源ID
                # 当空间类型为其他时，取空间自增ID的相反数(负数)作为资源ID
                "id": str(space_uid_to_bk_biz_id(space.space_uid, space.id)),
                "display_name": f"[{space_types.get(space.space_type_id, space.space_type_id)}] {space.space_name}",
            }
            for space in queryset
        ]
        return resources

    def list_instance(self, filter, page, **options):
        queryset = self.get_space_queryset().filter(bk_tenant_id=options["bk_tenant_id"])

        if filter.search:
            keywords = filter.search.get("space", [])

            q_filter = Q()
            for keyword in keywords:
                # 支持按空间类型，空间ID，空间名称(模糊) 搜索
                q_filter |= Q(space_type_id=keyword) | Q(space_id=keyword) | Q(space_name__icontains=keyword)

            queryset = queryset.filter(q_filter)

        results = self.generate_resources(queryset[page.slice_from : page.slice_to])

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filter, **options):
        conditions = []
        for bk_biz_id in filter.ids:
            try:
                bk_biz_id = int(bk_biz_id)
            except (TypeError, ValueError):
                if not options.get("include_resource_metadata"):
                    raise
                continue
            if bk_biz_id >= 0:
                conditions.append(Q(space_type_id=SpaceTypeEnum.BKCC.value) & Q(space_id=bk_biz_id))
            else:
                conditions.append(Q(id=-bk_biz_id))

        if not conditions:
            return ListResult(results=[], count=0)

        queryset = self.get_space_queryset().filter(
            reduce(operator.or_, conditions), bk_tenant_id=options["bk_tenant_id"]
        )
        results = self.generate_resources(queryset)
        if options.get("include_resource_metadata"):
            for item in results:
                item["_bk_iam_path_"] = f"/space,{item['id']}/"
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filter, page, **options):
        expression = filter.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = SpaceQuerySetConverter()
        filters = converter.convert(expression)
        queryset = self.get_space_queryset().filter(filters, bk_tenant_id=options["bk_tenant_id"])
        results = self.generate_resources(queryset[page.slice_from : page.slice_to])
        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filter, page, **options):
        keyword = filter.keyword
        queryset = self.get_space_queryset().filter(
            Q(space_type_id=keyword) | Q(space_id=keyword) | Q(space_name__icontains=keyword),
            bk_tenant_id=options["bk_tenant_id"],
        )
        results = self.generate_resources(queryset[page.slice_from : page.slice_to])
        return ListResult(results=results, count=queryset.count())

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "space"

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


class GrafanaDashboardProvider(BaseResourceProvider):
    """Grafana仪表盘 - 同时展示目录和仪表盘"""

    # General 目录常量
    GENERAL_FOLDER_ID = 0
    GENERAL_FOLDER_NAME = "General"
    # Folder 前缀，用于区分目录和仪表盘
    FOLDER_PREFIX = "folder:"

    def _get_org_ids_by_options(self, options: dict) -> set:
        """根据选项获取有权限的 org_id 集合"""
        bk_tenant_id = options["bk_tenant_id"]
        spaces = Space.objects.filter(bk_tenant_id=bk_tenant_id)
        bk_biz_ids = {
            str(-space.id) if space.space_type_id != SpaceTypeEnum.BKCC.value else space.space_id for space in spaces
        }
        return set(Org.objects.filter(name__in=bk_biz_ids).values_list("id", flat=True))

    def filter_by_options(self, items: QuerySet[Dashboard], options: dict):
        """支持按租户ID过滤"""
        org_ids = self._get_org_ids_by_options(options)
        return items.filter(org_id__in=org_ids)

    def list_instance(self, filter, page, **options):
        """
        列出实例：同时展示目录和仪表盘
        目录: [目录] {folder_name}
        仪表盘: [仪表盘] {folder_name}/{dashboard_name}
        """
        # 确定目标 org
        target_org_id = None
        if filter.parent and filter.parent.get("id"):
            org = get_org_by_name(org_name=filter.parent["id"])
            if not org:
                return ListResult(results=[], count=0)
            target_org_id = org["id"]

        # 获取有权限的 org_ids
        valid_org_ids = self._get_org_ids_by_options(options)
        if target_org_id and target_org_id not in valid_org_ids:
            return ListResult(results=[], count=0)

        # 查询文件夹和仪表盘
        folder_results, dashboard_results = self._query_folders_and_dashboards(target_org_id, options)

        # 关键字搜索过滤
        if filter.search:
            keywords = filter.search.get("grafana_dashboard", [])
            if keywords:
                # 过滤 folder
                folder_results = [
                    f for f in folder_results if any(kw.lower() in f["display_name"].lower() for kw in keywords)
                ]
                # 过滤 dashboard
                dashboard_results = [
                    d for d in dashboard_results if any(kw.lower() in d["display_name"].lower() for kw in keywords)
                ]

        # 合并结果
        all_results = folder_results + dashboard_results
        paged_results = all_results[page.slice_from : page.slice_to]

        # 构造返回结果（添加拓扑路径）
        results = []
        org_map = {}

        # 构造返回结果
        for item in paged_results:
            result = {
                "id": item["id"],
                "display_name": item["display_name"],
            }

            # 添加拓扑路径
            if filter.resource_type_chain or options.get("include_resource_metadata"):
                org_id = item["org_id"]
                if org_id not in org_map:
                    org_map[org_id] = item.get("org") or get_org_by_id(org_id)
                org = org_map[org_id]
                if org:
                    result["_bk_iam_path_"] = [
                        [
                            {
                                "type": ResourceEnum.BUSINESS.id,
                                "id": str(org["name"]),
                                "display_name": str(org["name"]),
                            }
                        ]
                    ]
            results.append(result)

        return ListResult(results=results, count=len(all_results))

    def fetch_instance_info(self, filter, **options):
        """获取实例信息 - 支持目录和仪表盘"""
        results = []
        metadata = options.get("include_resource_metadata", False)
        instances = {}
        dashboard_uids = []
        folder_queries = []  # (instance_id, folder_id)

        for instance_id in filter.ids:
            instance_id = str(instance_id)

            # 判断是目录还是仪表盘
            if instance_id.startswith(self.FOLDER_PREFIX):
                # Folder: "folder:{org_id}|{folder_id}"
                # 处理目录
                folder_part = instance_id[len(self.FOLDER_PREFIX) :]
                if "|" in folder_part:
                    org_id_str, folder_id_str = folder_part.split("|", 1)
                    try:
                        folder_queries.append((instance_id, int(folder_id_str)))
                    except ValueError:
                        continue
            else:
                # Dashboard: "{org_id}|{uid}" 或 "{uid}"
                if "|" in instance_id:
                    _, uid = instance_id.split("|", 1)
                else:
                    uid = instance_id
                dashboard_uids.append((instance_id, uid))

        # 查询真实 folder
        if folder_queries:
            folder_id_list = [fid for _, fid in folder_queries]
            folders = self.filter_by_options(Dashboard.objects.filter(id__in=folder_id_list, is_folder=True), options)
            folder_map = {f.id: f for f in folders}
            for instance_id, folder_id in folder_queries:
                if folder_id in folder_map:
                    if metadata:
                        org_id = instance_id[len(self.FOLDER_PREFIX) :].partition("|")[0]
                        if org_id != str(folder_map[folder_id].org_id):
                            continue
                        instances[instance_id] = folder_map[folder_id]
                    results.append(
                        {
                            "id": instance_id,
                            "display_name": f"[目录] {folder_map[folder_id].title}",
                        }
                    )

        # 查询 dashboard
        if dashboard_uids:
            uid_list = [uid for _, uid in dashboard_uids]
            queryset = Dashboard.objects.filter(uid__in=uid_list, is_folder=False)
            dashboards = self.filter_by_options(queryset, options)

            # 获取 folder 名称映射
            folder_ids = {d.folder_id for d in dashboards if d.folder_id}
            folder_names = {}
            if folder_ids:
                for f in Dashboard.objects.filter(id__in=folder_ids, is_folder=True):
                    folder_names[f.id] = f.title

            dashboard_map = {d.uid: d for d in dashboards}
            for instance_id, uid in dashboard_uids:
                if uid in dashboard_map:
                    d = dashboard_map[uid]
                    if metadata:
                        if "|" in instance_id and instance_id.partition("|")[0] != str(d.org_id):
                            continue
                        instances[instance_id] = d
                    folder_id = d.folder_id if d.folder_id else self.GENERAL_FOLDER_ID
                    folder_name = folder_names.get(folder_id, self.GENERAL_FOLDER_NAME)
                    results.append(
                        {
                            "id": instance_id,
                            "display_name": f"[仪表盘] {folder_name}/{d.title}",
                        }
                    )

        if metadata:
            org_names = {
                org.id: org.name for org in Org.objects.filter(id__in={item.org_id for item in instances.values()})
            }
            for item in results:
                model = instances[item["id"]]
                if model.org_id in org_names:
                    item["_bk_iam_path_"] = f"/space,{org_names[model.org_id]}/"

        return ListResult(results=results, count=len(results))

    def list_instance_by_policy(self, filter, page, **options):
        """根据策略列出实例"""
        target_org_id = None

        if filter.parent and "id" in filter.parent:
            parent_id = filter.parent.get("id")
            org = get_org_by_name(parent_id)
            if not org:
                return ListResult(results=[], count=0)
            target_org_id = org["id"]

        # 获取有权限的 org_ids
        valid_org_ids = self._get_org_ids_by_options(options)
        if target_org_id and target_org_id not in valid_org_ids:
            return ListResult(results=[], count=0)

        # 查询文件夹和仪表盘
        folder_results, dashboard_results = self._query_folders_and_dashboards(target_org_id, options)

        # 关键字过滤
        if filter.keyword:
            keyword_lower = filter.keyword.lower()
            folder_results = [f for f in folder_results if keyword_lower in f["display_name"].lower()]
            dashboard_results = [d for d in dashboard_results if keyword_lower in d["display_name"].lower()]

        # 返回过滤后的数据
        all_results = folder_results + dashboard_results
        paged = all_results[page.slice_from : page.slice_to]
        return ListResult(results=paged, count=len(all_results))

    def search_instance(self, filter, page, **options):
        """搜索实例"""
        return self.list_instance_by_policy(filter, page, **options)

    def _query_folders_and_dashboards(self, target_org_id: int | None, options: dict) -> tuple[list[dict], list[dict]]:
        """
        查询文件夹和仪表盘的公共逻辑

        返回:
            - folder_results: 文件夹结果列表
            - dashboard_results: 仪表盘结果列表
            - folders_map: folder_id -> folder_name 的映射
        """
        folder_results = []
        folders_map = {}

        # 查询真实文件夹
        folder_queryset = Dashboard.objects.filter(is_folder=True)
        if target_org_id:
            folder_queryset = folder_queryset.filter(org_id=target_org_id)

        real_folders = self.filter_by_options(folder_queryset, options)

        # 构建文件夹结果和映射
        for folder in real_folders:
            folders_map[folder.id] = folder.title
            folder_results.append(
                {
                    "id": f"{self.FOLDER_PREFIX}{folder.org_id}|{folder.id}",
                    "display_name": f"[目录] {folder.title}",
                    "org_id": folder.org_id,
                    "is_folder": True,
                    "folder_name": folder.title,
                }
            )

        # 查询仪表盘
        dashboard_queryset = Dashboard.objects.filter(is_folder=False)
        if target_org_id:
            dashboard_queryset = dashboard_queryset.filter(org_id=target_org_id)

        dashboards = self.filter_by_options(dashboard_queryset, options)
        dashboard_results = []

        # 构建仪表盘结果
        for dashboard in dashboards:
            folder_id = dashboard.folder_id if dashboard.folder_id else self.GENERAL_FOLDER_ID
            folder_name = folders_map.get(folder_id, self.GENERAL_FOLDER_NAME)
            dashboard_results.append(
                {
                    "id": f"{dashboard.org_id}|{dashboard.uid}",
                    "display_name": f"[仪表盘] {folder_name}/{dashboard.title}",
                    "org_id": dashboard.org_id,
                    "is_folder": False,
                    "folder_id": folder_id,
                    "folder_name": folder_name,
                }
            )

        return folder_results, dashboard_results

    system_id = settings.BK_IAM_SYSTEM_ID
    id = "grafana_dashboard"

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

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

import abc

from django.db.models import Q, QuerySet

from apps.api import TransferApi
from apps.iam import Permission, ResourceEnum
from apps.log_databus.constants import STORAGE_CLUSTER_TYPE, REGISTERED_SYSTEM_DEFAULT
from apps.log_databus.models import CollectorConfig
from apps.log_search.models import LogIndexSet, Space
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from iam import PathEqDjangoQuerySetConverter, make_expression, ObjectSet, DjangoQuerySetConverter
from iam.eval.constants import KEYWORD_BK_IAM_PATH_FIELD_SUFFIX, OP
from iam.resource.provider import ResourceProvider, ListResult

from iam_engine.v4.callback import V3ResourceApiDispatcher
from apps.iam.mode import get_mode_provider
from django.conf import settings


class ResourceApiDispatcher(V3ResourceApiDispatcher):
    def __init__(self, iam, system):
        super().__init__(iam, system, mode_loader=lambda: get_mode_provider().get_mode())

    def _get_options(self, request):
        options = super()._get_options(request)
        options["bk_tenant_id"] = request.META.get("HTTP_X_BK_TENANT_ID", settings.BK_APP_TENANT_ID)
        return options


class BaseResourceProvider(ResourceProvider, metaclass=abc.ABCMeta):
    def list_attr(self, **options):
        return ListResult(results=[], count=0)

    def list_attr_value(self, filter, page, **options):
        return ListResult(results=[], count=0)


class SpaceResourceProvider(BaseResourceProvider):
    """V4 cross-system space proxy reads only the BKLog local Space snapshot."""

    @staticmethod
    def get_instance_attributes(instance_id):
        from apps.log_search.models import SpaceType

        try:
            int(instance_id)
            lookup = {"bk_biz_id": instance_id}
        except Exception:
            lookup = {"space_uid": instance_id}
        try:
            space = Space.objects.get(**lookup)
            return {
                "id": str(space.bk_biz_id),
                "name": f"[{SpaceType.get_name_by_id(space.space_type_id)}] {space.space_name}",
            }
        except Exception:
            return {"id": str(instance_id), "name": instance_id}

    @staticmethod
    def _require_tenant_id(options):
        tenant = str(options.get("bk_tenant_id") or "").strip()
        if settings.ENABLE_MULTI_TENANT_MODE and not tenant:
            raise ValueError("bk_tenant_id is required for the space provider")
        return tenant or settings.BK_APP_TENANT_ID

    @staticmethod
    def _to_result_item(space):
        return {
            "id": str(space["bk_biz_id"]),
            "display_name": f"[{space['space_type_name']}] {space['space_name']}",
        }

    def list_instance(self, filter, page, **options):
        spaces, count = Space.get_spaces_page(
            self._require_tenant_id(options),
            offset=page.slice_from,
            limit=page.slice_to - page.slice_from,
            keywords=(filter.search.get("space", []) or []) if filter.search else [],
        )
        return ListResult(results=[self._to_result_item(space) for space in spaces], count=count)

    def fetch_instance_info(self, filter, **options):
        tenant = self._require_tenant_id(options)
        if not filter.ids:
            return ListResult(results=[], count=0)
        spaces = Space.get_spaces_by_bk_biz_ids(tenant, filter.ids)
        results = [self._to_result_item(space) for space in spaces]
        for item in results:
            # There is no stable local approver field; do not invent approvers.
            item["_bk_iam_approvers_"] = []
        return ListResult(results=results, count=len(results))

    def search_instance(self, filter, page, **options):
        raise NotImplementedError

    def list_instance_by_policy(self, filter, page, **options):
        raise NotImplementedError


class CollectionResourceProvider(BaseResourceProvider):
    ENABLE_MULTI_TENANT_MODE = settings.ENABLE_MULTI_TENANT_MODE

    @staticmethod
    def get_instance_attributes(instance_id):
        # Original V3 resource construction is an unscoped primary-key lookup,
        # not callback enumeration. Keep its absence/error contract intact.
        try:
            item = CollectorConfig.objects.get(pk=instance_id)
        except CollectorConfig.DoesNotExist:
            return {}
        return {
            "id": str(instance_id), "name": item.collector_config_name,
            "bk_biz_id": str(item.bk_biz_id), "_bk_iam_path_": f"/space,{item.bk_biz_id}/",
        }

    def get_bk_tenant_objects(self, queryset: QuerySet, bk_tenant_id: str):
        if self.ENABLE_MULTI_TENANT_MODE:
            space_uid_list = Space.get_space_uid_list(bk_tenant_id)
            collector_config_id_list = LogIndexSet.objects.filter(space_uid__in=space_uid_list).values_list(
                "collector_config_id",
                flat=True,
            )
            queryset = queryset.filter(collector_config_id__in=collector_config_id_list)
        return queryset

    def list_instance(self, filter, page, **options):
        queryset = []
        with_path = False
        if not (filter.parent or filter.search or filter.resource_type_chain):
            queryset = CollectorConfig.objects.all()
            queryset = self.get_bk_tenant_objects(queryset, options["bk_tenant_id"])
        elif filter.parent:
            parent_id = filter.parent["id"]
            if parent_id:
                queryset = CollectorConfig.objects.filter(bk_biz_id=parent_id)
        elif filter.search and filter.resource_type_chain:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filter.search.get("collection", [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(collector_config_name__icontains=keyword)

            queryset = CollectorConfig.objects.filter(q_filter)
            queryset = self.get_bk_tenant_objects(queryset, options["bk_tenant_id"])

        if options.get("include_resource_metadata"):
            with_path = True
            queryset = self.get_bk_tenant_objects(queryset, options["bk_tenant_id"])
            if filter.parent and filter.search:
                q_filter = Q()
                for keyword in filter.search.get("collection", []):
                    q_filter |= Q(collector_config_name__icontains=keyword)
                queryset = queryset.filter(q_filter)

        if not with_path:
            results = [
                {"id": str(item.pk), "display_name": item.collector_config_name}
                for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = []
            for item in queryset[page.slice_from : page.slice_to]:
                results.append(
                    {
                        "id": str(item.pk),
                        "display_name": item.collector_config_name,
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
            ids = [int(i) for i in filter.ids]

        queryset = CollectorConfig.objects.filter(pk__in=ids)
        queryset = self.get_bk_tenant_objects(queryset, options["bk_tenant_id"])

        results = [
            {"id": str(item.pk), "display_name": item.collector_config_name, "_bk_iam_approver_": item.created_by}
            for item in queryset
        ]
        if options.get("include_resource_metadata"):
            for result, item in zip(results, queryset):
                result["_bk_iam_path_"] = f"/space,{item.bk_biz_id}/"
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filter, page, **options):
        expression = filter.expression
        if not expression:
            return ListResult(results=[], count=0)

        converter = PathEqDjangoQuerySetConverter(
            key_mapping={
                "collection.id": "pk",
                "collection.owner": "created_by",
                "collection._bk_iam_path_": "bk_biz_id",
            },
            value_hooks={"bk_biz_id": lambda value: value[1:-1].split(",")[1]},
        )
        filters = converter.convert(expression)
        queryset = CollectorConfig.objects.filter(filters)
        queryset = self.get_bk_tenant_objects(queryset, options["bk_tenant_id"])
        results = [
            {"id": str(item.pk), "display_name": item.collector_config_name}
            for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filter, page, **options):
        if not filter.parent or "id" not in filter.parent:
            queryset = CollectorConfig.objects.filter(
                collector_config_name__icontains=filter.keyword,
            )
            if self.ENABLE_MULTI_TENANT_MODE:
                space_uid_list = Space.get_space_uid_list(options["bk_tenant_id"])
                collector_config_id_list = LogIndexSet.objects.filter(space_uid__in=space_uid_list).values_list(
                    "collector_config_id",
                    flat=True,
                )
                queryset = queryset.filter(collector_config_id__in=collector_config_id_list)
        else:
            parent_id = filter.parent.get("id")
            queryset = CollectorConfig.objects.filter(
                bk_biz_id=parent_id, collector_config_name__icontains=filter.keyword
            )

        results = [
            {"id": item.collector_config_id, "display_name": item.collector_config_name}
            for item in queryset[page.slice_from : page.slice_to]
        ]
        return ListResult(results=results, count=queryset.count())


class EsSourceResourceProvider(BaseResourceProvider):
    @staticmethod
    def query_clusters(**filters):
        return TransferApi.get_cluster_info(filters)

    @classmethod
    def get_instance_attributes(cls, instance_id):
        try:
            result = cls.query_clusters(cluster_id=instance_id)
            if not result:
                return {}
            config = result[0]["cluster_config"]
            name = config.get("display_name") or config["cluster_name"]
            biz_id = config["custom_option"].get("bk_biz_id", 0)
        except Exception:
            return {}
        return {
            "id": str(instance_id), "name": name,
            "bk_biz_id": str(biz_id), "_bk_iam_path_": f"/space,{biz_id}/",
        }

    @classmethod
    def list_clusters(cls, bk_tenant_id):
        """
        获取非系统内置集群列表
        """
        # return [
        #     {
        #         "id": "1",
        #         "display_name": "蓝鲸",
        #         "bk_biz_id": "2",
        #         "owner": "admin",
        #         "_bk_iam_path_": "/biz,2/"
        #     },
        #     {
        #         "id": "2",
        #         "display_name": "蓝鲸2",
        #         "bk_biz_id": "2",
        #         "owner": "adminxx",
        #         "_bk_iam_path_": "/biz,2/"
        #     },
        #     {
        #         "id": "3",
        #         "display_name": "test",
        #         "bk_biz_id": "3",
        #         "owner": "admin",
        #         "_bk_iam_path_": "/biz,3/"
        #     },
        #     {
        #         "id": "10",
        #         "display_name": "xxxx",
        #         "bk_biz_id": "99",
        #         "owner": "test",
        #         "_bk_iam_path_": "/biz,99/"
        #     }
        # ]

        clusters = cls.query_clusters(cluster_type=STORAGE_CLUSTER_TYPE, no_request=True)
        # 过滤非内置集群，且业务ID不为空的集群
        clusters = [
            {
                "id": str(cluster["cluster_config"]["cluster_id"]),
                "display_name": cluster["cluster_config"]["cluster_name"],
                "bk_biz_id": str(cluster["cluster_config"]["custom_option"]["bk_biz_id"]),
                "owner": cluster["cluster_config"]["creator"],
                "_bk_iam_path_": "/{},{}/".format(
                    ResourceEnum.BUSINESS.id,
                    cluster["cluster_config"]["custom_option"]["bk_biz_id"],
                ),
            }
            for cluster in clusters
            if cluster["cluster_config"].get("registered_system") != REGISTERED_SYSTEM_DEFAULT
            and cluster["cluster_config"]["custom_option"].get("bk_biz_id")
        ]

        # TODO: 根据租户过滤集群列表

        return clusters

    def list_instance(self, filter, page, **options):
        bk_tenant_id = options["bk_tenant_id"]
        # 获取集群信息
        clusters = self.list_clusters(bk_tenant_id=bk_tenant_id)

        with_path = False
        if filter.parent:
            parent_id = filter.parent["id"]
            if parent_id:
                clusters = [cluster for cluster in clusters if str(cluster["bk_biz_id"]) == str(parent_id)]
        elif filter.search and filter.resource_type_chain:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filter.search.get("es_source", [])

            filtered_clusters = []
            for cluster in clusters:
                cluster_name = cluster["display_name"]
                for keyword in keywords:
                    if keyword in cluster_name:
                        filtered_clusters.append(cluster)
            clusters = filtered_clusters

        if options.get("include_resource_metadata"):
            with_path = True
            if filter.parent and filter.search:
                keywords = filter.search.get("es_source", [])
                clusters = [c for c in clusters if any(k.lower() in c["display_name"].lower() for k in keywords)]

        if not with_path:
            results = [
                {"id": item["id"], "display_name": item["display_name"]}
                for item in clusters[page.slice_from : page.slice_to]
            ]
        else:
            results = []
            for item in clusters[page.slice_from : page.slice_to]:
                results.append(
                    {
                        "id": item["id"],
                        "display_name": item["display_name"],
                        "_bk_iam_path_": [
                            [
                                {
                                    "type": ResourceEnum.BUSINESS.id,
                                    "id": str(item["bk_biz_id"]),
                                    "display_name": str(item["bk_biz_id"]),
                                }
                            ]
                        ],
                    }
                )

        return ListResult(results=results, count=len(clusters))

    def fetch_instance_info(self, filter, **options):
        bk_tenant_id = options["bk_tenant_id"]
        clusters = self.list_clusters(bk_tenant_id=bk_tenant_id)

        if filter.ids:
            ids = [str(i) for i in filter.ids]
            clusters = [cluster for cluster in clusters if str(cluster["id"]) in ids]

        results = [
            {"id": item["id"], "display_name": item["display_name"], "_bk_iam_approver_": item["owner"]}
            for item in clusters
        ]
        if options.get("include_resource_metadata"):
            if not filter.ids:
                return ListResult(results=[], count=0)
            for result, item in zip(results, clusters):
                result["_bk_iam_path_"] = item["_bk_iam_path_"]
        return ListResult(results=results, count=len(clusters))

    def list_instance_by_policy(self, filter, page, **options):
        expression = filter.expression
        if not expression:
            return ListResult(results=[], count=0)

        expr = make_expression(expression)

        bk_tenant_id = options["bk_tenant_id"]
        clusters = self.list_clusters(bk_tenant_id=bk_tenant_id)
        iam_client = Permission.get_iam_client(settings.BK_APP_TENANT_ID)

        filtered_clusters = []

        # 这里需要手动匹配策略... Org
        for cluster in clusters:
            obj_set = ObjectSet()
            obj_set.add_object("es_source", cluster)
            is_allowed = iam_client._eval_expr(expr, obj_set)
            if is_allowed:
                filtered_clusters.append(cluster)

        results = [
            {"id": item["id"], "display_name": item["display_name"]}
            for item in filtered_clusters[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=len(filtered_clusters))

    def search_instance(self, filter, page, **options):
        bk_tenant_id = options["bk_tenant_id"]
        clusters = self.list_clusters(bk_tenant_id=bk_tenant_id)
        if filter.parent and "id" in filter.parent:
            parent_id = filter.parent.get("id")
            clusters = [
                cluster
                for cluster in clusters
                if str(cluster["bk_biz_id"]) == str(parent_id)
                and filter.keyword.lower() in cluster["display_name"].lower()
            ]
        else:
            clusters = [cluster for cluster in clusters if filter.keyword.lower() in cluster["display_name"].lower()]

        return ListResult(
            results=[
                {"id": item["id"], "display_name": item["display_name"]}
                for item in clusters[page.slice_from : page.slice_to]
            ],
            count=len(clusters),
        )


class IndicesResourceProvider(BaseResourceProvider):
    ENABLE_MULTI_TENANT_MODE = settings.ENABLE_MULTI_TENANT_MODE

    @staticmethod
    def get_instance_attributes(instance_id):
        try:
            item = LogIndexSet.objects.get(pk=instance_id)
        except LogIndexSet.DoesNotExist:
            return {}
        biz_id = str(space_uid_to_bk_biz_id(item.space_uid))
        return {
            "id": str(instance_id), "name": item.index_set_name,
            "bk_biz_id": biz_id, "_bk_iam_path_": f"/space,{biz_id}/",
        }

    class PathInDjangoQuerySetConverter(DjangoQuerySetConverter):
        def operator_map(self, operator, field, value):
            if field.endswith(KEYWORD_BK_IAM_PATH_FIELD_SUFFIX) and operator == OP.STARTS_WITH:
                return self._in

    def list_instance(self, filter, page, **options):
        queryset = []
        with_path = False
        bk_tenant_id = options["bk_tenant_id"]

        if not (filter.parent or filter.search or filter.resource_type_chain):
            queryset = LogIndexSet.objects.all()
            if self.ENABLE_MULTI_TENANT_MODE:
                space_uid_list = Space.get_space_uid_list(bk_tenant_id)
                queryset = queryset.filter(space_uid__in=space_uid_list)
        elif filter.parent:
            parent_id = filter.parent["id"]
            if parent_id:
                queryset = LogIndexSet.objects.filter(space_uid=bk_biz_id_to_space_uid(parent_id))
        elif filter.search and filter.resource_type_chain:
            # 返回结果需要带上资源拓扑路径信息
            with_path = True

            keywords = filter.search.get("indices", [])

            q_filter = Q()
            for keyword in keywords:
                q_filter |= Q(index_set_name__icontains=keyword)

            queryset = LogIndexSet.objects.filter(q_filter)
            if self.ENABLE_MULTI_TENANT_MODE:
                space_uid_list = Space.get_space_uid_list(bk_tenant_id)
                queryset = queryset.filter(space_uid__in=space_uid_list)

        if options.get("include_resource_metadata"):
            with_path = True
            if self.ENABLE_MULTI_TENANT_MODE:
                queryset = queryset.filter(space_uid__in=Space.get_space_uid_list(bk_tenant_id))
            if filter.parent and filter.search:
                q_filter = Q()
                for keyword in filter.search.get("indices", []):
                    q_filter |= Q(index_set_name__icontains=keyword)
                queryset = queryset.filter(q_filter)

        if not with_path:
            results = [
                {"id": str(item.pk), "display_name": item.index_set_name}
                for item in queryset[page.slice_from : page.slice_to]
            ]
        else:
            results = []
            bk_biz_id_mapping = {}
            for item in queryset[page.slice_from : page.slice_to]:
                if item.space_uid not in bk_biz_id_mapping:
                    bk_biz_id_mapping[item.space_uid] = str(space_uid_to_bk_biz_id(item.space_uid))
                results.append(
                    {
                        "id": str(item.pk),
                        "display_name": item.index_set_name,
                        "_bk_iam_path_": [
                            [
                                {
                                    "type": ResourceEnum.BUSINESS.id,
                                    "id": bk_biz_id_mapping[item.space_uid],
                                    "display_name": bk_biz_id_mapping[item.space_uid],
                                }
                            ]
                        ],
                    }
                )

        return ListResult(results=results, count=queryset.count())

    def fetch_instance_info(self, filter, **options):
        ids = []
        if filter.ids:
            ids = [int(i) for i in filter.ids]

        queryset = LogIndexSet.objects.filter(pk__in=ids)
        if self.ENABLE_MULTI_TENANT_MODE:
            space_uid_list = Space.get_space_uid_list(options["bk_tenant_id"])
            if options.get("include_resource_metadata"):
                queryset = queryset.filter(space_uid__in=space_uid_list)
            else:
                queryset.filter(space_uid__in=space_uid_list)

        results = [
            {"id": str(item.pk), "display_name": item.index_set_name, "_bk_iam_approver_": item.created_by}
            for item in queryset
        ]
        if options.get("include_resource_metadata"):
            for result, item in zip(results, queryset):
                result["_bk_iam_path_"] = f"/space,{space_uid_to_bk_biz_id(item.space_uid)}/"
        return ListResult(results=results, count=queryset.count())

    def list_instance_by_policy(self, filter, page, **options):
        expression = filter.expression
        if not expression:
            return ListResult(results=[], count=0)

        key_mapping = {
            "indices.id": "pk",
            "indices.owner": "created_by",
            "indices._bk_iam_path_": "space_uid",
        }
        converter = self.PathInDjangoQuerySetConverter(
            key_mapping, {"space_uid": lambda value: bk_biz_id_to_space_uid(value[1:-1].split(",")[1])}
        )
        filters = converter.convert(expression)
        queryset = LogIndexSet.objects.filter(filters)
        if self.ENABLE_MULTI_TENANT_MODE:
            space_uid_list = Space.get_space_uid_list(options["bk_tenant_id"])
            queryset = queryset.filter(space_uid__in=space_uid_list)
        results = [
            {"id": str(item.pk), "display_name": item.index_set_name}
            for item in queryset[page.slice_from : page.slice_to]
        ]

        return ListResult(results=results, count=queryset.count())

    def search_instance(self, filter, page, **options):
        if not filter.parent or "id" not in filter.parent:
            queryset = LogIndexSet.objects.filter(index_set_name__icontains=filter.keyword)
        else:
            parent_id = filter.parent.get("id")
            queryset = LogIndexSet.objects.filter(
                space_uid=bk_biz_id_to_space_uid(parent_id), index_set_name__icontains=filter.keyword
            )
        if self.ENABLE_MULTI_TENANT_MODE:
            space_uid_list = Space.get_space_uid_list(options["bk_tenant_id"])
            queryset = queryset.filter(space_uid__in=space_uid_list)
        return ListResult(
            results=[
                {"id": item.index_set_id, "display_name": item.index_set_name}
                for item in queryset[page.slice_from : page.slice_to]
            ],
            count=queryset.count(),
        )

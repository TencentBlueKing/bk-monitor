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


import copy
import hashlib
import json
import logging
import operator
from datetime import datetime
from functools import reduce
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.exceptions import EmptyResultSet
from django.db import models
from django.db.models import Count, Q
from django.db.models.query import QuerySet
from django.utils import timezone
from django.utils.translation import ugettext as _
from humanize import naturaldelta

from bkmonitor.models.bcs_label import BCSLabel
from bkmonitor.utils.common_utils import chunks
from bkmonitor.utils.kubernetes import BcsClusterType, BkmMetricbeatEndpointUpStatus
from core.drf_resource import api

logger = logging.getLogger("kubernetes")

IGNORE_LABEL_KEYS = {
    "pod-template-hash",
    "controller-revision-hash",
    "statefulset.kubernetes.io/pod-name",
    "controller-uid",
    "job-name",
}


class BCSBaseManager(models.Manager):
    def count_service_status_quantity(self, query_set_list):
        """统计每种运行状态的数量 ."""
        if not query_set_list:
            model_items = self.all().values("status").annotate(count=Count("status"))
        else:
            model_items = self.filter(*query_set_list).values("status").annotate(count=Count("status"))
        status_summary = {model["status"]: model["count"] for model in model_items}
        return status_summary

    def count_monitor_status_quantity(self, query_set_list: List) -> Dict:
        """统计每种指标数据状态的数量 ."""
        if not query_set_list:
            model_items = self.all().values("monitor_status").annotate(count=Count("monitor_status"))
        else:
            model_items = self.filter(*query_set_list).values("monitor_status").annotate(count=Count("monitor_status"))
        status_summary = {model["monitor_status"]: model["count"] for model in model_items}
        return status_summary

    def get_cluster_ids(self, bk_biz_id):
        if not isinstance(bk_biz_id, (list, tuple)):
            bk_biz_id = [bk_biz_id]
        cluster_ids = self.filter(bk_biz_id__in=bk_biz_id).values_list("bcs_cluster_id", flat=True)
        return list(cluster_ids)

    def get_bk_biz_ids(self):
        items = self.all().values("bk_biz_id").distinct()
        bk_biz_ids = [item["bk_biz_id"] for item in items]
        return bk_biz_ids

    def filter_by_biz_id(
        self,
        bk_biz_id: int,
    ) -> QuerySet:
        """获得资源查询QuerySet ."""
        query_set = Q(bk_biz_id=bk_biz_id)
        if bk_biz_id < 0:
            clusters = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
            if not clusters:
                # 业务下没有集群
                raise EmptyResultSet

            shared_q_list = []
            for cluster_id, value in clusters.items():
                cluster_type = value.get("cluster_type")
                namespace_list = value["namespace_list"]
                if cluster_type == BcsClusterType.SHARED and namespace_list and self.model.has_namespace_field():
                    shared_q_list.append(Q(bcs_cluster_id=cluster_id, namespace__in=namespace_list))
                else:
                    shared_q_list.append(Q(bcs_cluster_id=cluster_id))
            if shared_q_list:
                query_set = reduce(operator.or_, shared_q_list)
            else:
                raise EmptyResultSet

        return self.filter(query_set)


class BCSBase(models.Model):
    class Meta:
        abstract = True

    # 运行状态
    STATE_SUCCESS = "success"  # 正常（有数据）
    STATE_FAILURE = "failed"  # 异常
    STATE_DISABLED = "disabled"  # 正常（无数据）

    # 指标数据状态
    METRICS_STATE_STATE_SUCCESS = "success"  # 正常（有数据）
    METRICS_STATE_FAILURE = "failed"  # 异常
    METRICS_STATE_DISABLED = "disabled"  # 正常（无数据）

    api_labels = {}

    labels = models.ManyToManyField(BCSLabel)
    bk_biz_id = models.IntegerField(verbose_name="业务ID", default=0, db_index=True)
    bcs_cluster_id = models.CharField(max_length=32, db_index=True)

    created_at = models.DateTimeField()
    deleted_at = models.DateTimeField(null=True)
    status = models.CharField(max_length=32, default="", db_index=True)
    monitor_status = models.CharField(max_length=32, default="")
    last_synced_at = models.DateTimeField(verbose_name="同步时间")

    unique_hash = models.CharField(max_length=32, null=True, unique=True)

    @classmethod
    def get_resource_usage_columns(cls):
        return [
            {
                "id": "resource_usage_cpu",
                "name": _("CPU使用量"),
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "resource_usage_memory",
                "name": _("内存使用量"),
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "resource_usage_disk",
                "name": _("磁盘使用量"),
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
        ]

    @classmethod
    def get_resource_usage_ratio_columns(cls):
        return [
            {
                "id": "request_cpu_usage_ratio",
                "name": _("CPU使用率(request)"),
                "type": "progress",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "limit_cpu_usage_ratio",
                "name": _("CPU使用率(limit)"),
                "type": "progress",
                "disabled": False,
                "checked": True,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "request_memory_usage_ratio",
                "name": _("内存使用率(request)"),
                "type": "progress",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "limit_memory_usage_ratio",
                "name": _("内存使用率(limit) "),
                "type": "progress",
                "disabled": False,
                "checked": True,
                "sortable": True,
                "sortable_type": "progress",
            },
        ]

    @classmethod
    def get_container_resources_columns(cls):
        return [
            {
                "id": "resource_requests_cpu",
                "name": "cpu request",
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "resource_limits_cpu",
                "name": "cpu limit",
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "resource_requests_memory",
                "name": "memory request",
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
            {
                "id": "resource_limits_memory",
                "name": "memory limit",
                "type": "string",
                "disabled": False,
                "checked": False,
                "sortable": True,
                "sortable_type": "progress",
            },
        ]

    @classmethod
    def hash_resource_labels(cls, items: List):
        """获得资源的标签hash_id ."""
        has_ids = []
        for item in items:
            if not item.id:
                continue
            for k, v in item.api_labels.items():
                if k in IGNORE_LABEL_KEYS:
                    continue
                hash_id = cls.md5str(k + ":" + v)
                has_ids.append(hash_id)
        return has_ids

    @classmethod
    def bulk_save_labels(cls, items: List) -> None:
        """批量更新标签 ."""
        bulk_create_label_list = []
        bcs_cluster_id_list = []
        resource_id_map_hash_ids = {}

        # 获得资源的标签hash_id
        has_id_set = set(cls.hash_resource_labels(items))

        # 获取可以新增的标签
        hash_id_existed = []
        for hash_ids in chunks(list(has_id_set), 500):
            hash_id_existed.extend(
                list(BCSLabel.objects.filter(hash_id__in=hash_ids).values_list("hash_id", flat=True))
            )
        hash_id_created = set(has_id_set) - set(hash_id_existed)

        # 批量添加标签
        for item in items:
            if not item.id:
                continue
            for k, v in item.api_labels.items():
                if k in IGNORE_LABEL_KEYS:
                    continue
                bcs_cluster_id_list.append(item.bcs_cluster_id)
                # 获得标签hash值
                hash_id = cls.md5str(k + ":" + v)
                resource_id_map_hash_ids.setdefault((item.id, item.bcs_cluster_id), []).append(hash_id)
                # 需要新增的标签
                if hash_id in hash_id_created:
                    bulk_create_label_list.append(BCSLabel(hash_id=hash_id, key=k, value=v))
        if bulk_create_label_list:
            try:
                BCSLabel.objects.bulk_create(bulk_create_label_list, 200)
            except Exception as exc_info:
                logger.exception(exc_info)

        # 获得中间表远程唯一性数据
        new_resource_label_hash_set = {
            (key[0], key[1], label_hash_id)
            for key, label_hash_ids in resource_id_map_hash_ids.items()
            for label_hash_id in label_hash_ids
        }

        # 获得中间表历史唯一性数据
        old_resource_label_hash_set = {
            (item.resource_id, item.bcs_cluster_id, item.label_id)
            for item in cls.labels.through.objects.filter(bcs_cluster_id__in=bcs_cluster_id_list)
        }

        # 中间表添加数据
        bulk_create_label_relation_list = []
        resource_label_hash_set_inserted = new_resource_label_hash_set - old_resource_label_hash_set
        if resource_label_hash_set_inserted:
            for resource_id, bcs_cluster_id, label_hash_id in resource_label_hash_set_inserted:
                bulk_create_label_relation_list.append(
                    cls.labels.through(
                        bcs_cluster_id=bcs_cluster_id,
                        label_id=label_hash_id,
                        resource_id=resource_id,
                    )
                )
            try:
                cls.labels.through.objects.bulk_create(bulk_create_label_relation_list, 200)
            except Exception as exc_info:
                logger.exception(exc_info)

        # 中间表删除数据
        label_hash_set_inserted_deleted = old_resource_label_hash_set - new_resource_label_hash_set
        if label_hash_set_inserted_deleted:
            for resource_id, bcs_cluster_id, label_hash_id in label_hash_set_inserted_deleted:
                cls.labels.through.objects.filter(
                    bcs_cluster_id=bcs_cluster_id, label_id=label_hash_id, resource_id=resource_id
                ).delete()

    @staticmethod
    def md5str(source: str):
        m = hashlib.md5()
        m.update(source.encode("utf8"))
        return m.hexdigest()

    def get_unique_hash(self):
        raise NotImplementedError

    @staticmethod
    def get_columns(columns_type="list"):
        raise NotImplementedError

    @classmethod
    def count(cls, params):
        if settings.BCS_API_DATA_SOURCE == "db":
            return cls.objects.filter(**params).count()
        return len(cls.load_item_from_api(params))

    @classmethod
    def load_item(cls, params=None):
        params = params or {}
        params = copy.deepcopy(params)
        bk_biz_id = params["bk_biz_id"]
        if bk_biz_id < 0:
            # 如果是研发项目，查询关联的所有集群，包括共享集群
            params.pop("bk_biz_id")
            clusters = api.kubernetes.get_cluster_info_from_bcs_space({"bk_biz_id": bk_biz_id})
            bcs_cluster_id_list = list(clusters.keys())
            params["bcs_cluster_id__in"] = bcs_cluster_id_list
        if settings.BCS_API_DATA_SOURCE == "db":
            return cls.load_item_from_db(params)
        else:
            return cls.load_item_from_api(params)

    @classmethod
    def load_item_from_db(cls, params):
        params = params if params else {}
        try:
            return cls.objects.get(**params)
        except cls.DoesNotExist:
            return

    @classmethod
    def load_item_from_api(cls, params):
        params = params if params else {}
        data = cls.load_list_from_api(params)

        def matched(item, match_params):
            for k, v in match_params.items():
                if v != getattr(item, k):
                    return False
            return True

        for item in data:
            if matched(item, params):
                return item

    @classmethod
    def condition_list_to_conditions(cls, condition_list):
        conditions = {}
        for condition in condition_list:
            for key, value in condition.items():
                if not conditions.get(key):
                    conditions[key] = []
                if not isinstance(value, list):
                    value = [value]
                conditions[key] += value
        return conditions

    @classmethod
    def label_query_set_parser(cls, conditions):
        label_count = 0
        q_list = []
        for key in conditions.keys():
            label_values = conditions.get(key, [])
            if not label_values:
                continue
            q = Q(labels__key=key) & Q(labels__value__in=label_values)
            q_list.append(q)
            label_count += 1

        queryset = reduce(lambda x, y: x | y, q_list)
        data = cls.objects.filter(queryset).annotate(Count("id")).values("id", "id__count")
        id_list = []
        for item in data:
            if item["id__count"] == label_count:
                id_list.append(item["id"])
        if id_list:
            return Q(id__in=id_list)

    @classmethod
    def get_query_set_list_by_params(cls, params):
        q_list = []
        label_conditions = {k.replace("__label_", ""): v for k, v in params.items() if k.find("__label_") == 0}
        else_conditions = {k: v for k, v in params.items() if k.find("__label_") != 0}
        if label_conditions:
            q = cls.label_query_set_parser(label_conditions)
            if not q:
                return []
            else:
                q_list.append(q)
        query_params = {k: v for k, v in params.items()}
        for k, v in else_conditions.items():
            query_params[k] = v

        # 添加bk_biz_id
        bk_biz_id = query_params.get("bk_biz_id")
        if bk_biz_id and hasattr(cls, "bk_biz_id"):
            if isinstance(bk_biz_id, list):
                q_list.append(Q(**{"bk_biz_id__in": bk_biz_id}))
            else:
                q_list.append(Q(**{"bk_biz_id": bk_biz_id}))

        # 添加cluster_id
        bcs_cluster_id = query_params.get("bcs_cluster_id")
        if bcs_cluster_id and hasattr(cls, "bcs_cluster_id"):
            if isinstance(bcs_cluster_id, list):
                q_list.append(Q(**{"bcs_cluster_id__in": bcs_cluster_id}))
            else:
                q_list.append(Q(**{"bcs_cluster_id": bcs_cluster_id}))

        for k, v in query_params.items():
            if hasattr(cls, k) and k not in {"keyword", "bk_biz_id", "bcs_cluster_id", "status"}:
                if isinstance(v, list):
                    q_list.append(Q(**{f"{k}__in": v}))
                else:
                    q_list.append(Q(**{f"{k}": v}))

        # 添加name过滤
        name_value = query_params.get("keyword")
        if name_value and hasattr(cls, "name"):
            for value in name_value:
                q_list.append(Q(name__contains=value))

        return q_list

    @classmethod
    def has_namespace_field(cls):
        return "namespace" in [f.name for f in cls._meta.get_fields()]

    @classmethod
    def has_space_uid_field(cls):
        return "space_uid" in [f.name for f in cls._meta.get_fields()]

    @staticmethod
    def load_list_from_api(params):
        raise NotImplementedError

    def render(self, bk_biz_id, render_type="list"):
        data = {}
        if render_type == "detail":
            data = []
        for column in self.get_columns(render_type):
            render = getattr(self, "render_" + column["id"], "")

            if render and callable(render):
                value = render(bk_biz_id, render_type)
            else:
                value = getattr(self, column["id"], "")
            if render_type == "detail":
                data.append(
                    {
                        "key": column["id"],
                        "name": column["name"],
                        "type": column["type"],
                        "value": value,
                    }
                )
            else:
                data[column["id"]] = value
        return data

    @staticmethod
    def build_link(bk_biz_id, text, dashboard, filter_query):
        filter_query_items = []
        for key, value in filter_query.items():
            if isinstance(value, list):
                for value_item in value:
                    filter_query_items.append(f"filter-{key}={value_item}")
            else:
                filter_query_items.append(f"filter-{key}={value}")
        filter_query_string = "&".join(filter_query_items)
        return {
            "value": text,
            "target": "blank",
            "url": f"?bizId={bk_biz_id}#/k8s?dashboardId={dashboard}&sceneType=detail&{filter_query_string}",
        }

    @staticmethod
    def build_search_link(
        bk_biz_id: int, dashboard_id: str, value: Any, search: Optional[List] = None, scene_type="detail"
    ):
        url = f"?bizId={bk_biz_id}#/k8s?sceneId=kubernetes&dashboardId={dashboard_id}&sceneType={scene_type}"
        if search:
            query_data = json.dumps({"selectorSearch": search})
            url = f"{url}&queryData={query_data}"
        value = {
            "value": value,
            "target": "blank",
            "url": url,
        }
        return value

    def get_label_list(self):
        if settings.BCS_API_DATA_SOURCE == "db":
            return [{"key": label.key, "value": label.value} for label in self.labels.all()]
        if not self.api_labels:
            self.api_labels = {}
        label_list = []
        for k, v in self.api_labels.items():
            label_list.append(
                {
                    "key": k,
                    "value": v,
                }
            )
        return label_list

    def render_age(self, bk_biz_id, render_type="list"):
        if isinstance(self.created_at, timezone.datetime):
            return naturaldelta(datetime.utcnow().replace(tzinfo=timezone.utc) - self.created_at)

    def render_labels(self, bk_biz_id, render_type="list"):
        if self.api_labels:
            return self.api_labels
        elif self.id:
            return {label.key: label.value for label in self.labels.all()}
        else:
            return {}

    def render_label_list(self, bk_biz_id, render_type="list"):
        return self.get_label_list()

    def render_monitor_status(self, bk_biz_id, render_type="list"):
        if self.monitor_status == self.METRICS_STATE_STATE_SUCCESS:
            result = {
                "type": self.METRICS_STATE_STATE_SUCCESS,
                "text": _("正常"),
            }
        elif self.monitor_status == self.METRICS_STATE_FAILURE:
            result = {
                "type": self.METRICS_STATE_FAILURE,
                "text": _("异常"),
            }
        elif self.monitor_status == self.METRICS_STATE_DISABLED:
            result = {
                "type": self.METRICS_STATE_DISABLED,
                "text": _("无数据"),
            }
        else:
            result = {
                "type": self.METRICS_STATE_FAILURE,
                "text": _("异常"),
            }
        return result

    def render_bk_cluster_name(self, bk_biz_id, render_type="list") -> str:
        from bkmonitor.models import BCSCluster

        bcs_cluster = BCSCluster.objects.filter(bcs_cluster_id=self.bcs_cluster_id).first()
        if not bcs_cluster:
            return ""
        bcs_cluster_name = bcs_cluster.name
        return bcs_cluster_name

    @classmethod
    def add_cluster_column(cls, columns: List, columns_type: str) -> List:
        if columns_type == "detail":
            columns.extend(
                [
                    {
                        "id": "bk_cluster_name",
                        "name": _("集群名称"),
                        "type": "string",
                        "disabled": False,
                        "checked": True,
                    },
                ]
            )

        return columns

    @classmethod
    def get_filter_tags(cls, bk_biz_id, field_name, display_name=None, value_map=None, multiable=False):
        value_map = value_map or {}
        try:
            qs = cls.objects.filter_by_biz_id(bk_biz_id)
            items = qs.values_list(field_name, flat=True).distinct()
            display_name = display_name or field_name
            children = sorted(
                [
                    {
                        "name": item,
                        "id": value_map.get(item, item),
                    }
                    for item in items
                    if value_map.get(item, item)
                ],
                key=lambda item: item["id"],
            )
        except EmptyResultSet:
            children = []

        return {
            "name": display_name,
            "id": field_name,
            "multiable": multiable,
            "children": children,
        }

    @classmethod
    def get_filter_cluster(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "bcs_cluster_id", display_name="cluster")

    @classmethod
    def get_filter_service_status(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "status")

    @classmethod
    def get_filter_namespace(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "namespace")

    @classmethod
    def get_filter_workload_name(cls, params):
        return cls.get_filter_tags(params["bk_biz_id"], "workload_name")

    @classmethod
    def get_column_filter_conf(cls, params, field):
        bk_biz_id = params["bk_biz_id"]
        space_related_cluster_ids = params.get("space_related_cluster_ids")
        if bk_biz_id >= 0:
            query = cls.objects.filter(bk_biz_id=bk_biz_id)
        else:
            query = cls.objects.filter(bcs_cluster_id__in=space_related_cluster_ids)
        items = query.values(field).distinct()
        status_list = sorted(list({item[field] for item in items if item[field]}))
        return [
            {
                "text": status,
                "value": status,
            }
            for status in status_list
        ]

    @staticmethod
    def get_cpu_usage_resource(usages: Dict, group_by: List) -> Dict:
        """获得CPU资源使用量 ."""
        data = {}
        for value in usages.values():
            keys = value.get("keys")
            value = value.get("usage", {}).get("resource_usage_cpu")
            key = tuple(keys.get(group_key) for group_key in group_by)
            old_value = data.get(key)
            if old_value is None or value > old_value:
                data[key] = value

        return data

    @staticmethod
    def fetch_container_usage(bk_biz_id: int, bcs_cluster_id: str, group_by: List) -> Dict:
        """获得cpu,memory,disk使用量 ."""
        usage_types = ["cpu", "memory", "disk"]
        bulk_params = [
            {
                "bk_biz_id": bk_biz_id,
                "bcs_cluster_id": bcs_cluster_id,
                "group_by": group_by,
                "usage_type": usage_type,
            }
            for usage_type in usage_types
        ]
        usages = api.kubernetes.fetch_container_usage.bulk_request(bulk_params)
        data = {}
        for usage in usages:
            usage_type = usage["usage_type"]
            usage_data = usage["data"]
            usage_key = "resource_usage_" + usage_type
            for item in usage_data:
                key = ".".join([item[group_key] for group_key in group_by])
                keys = {group_key: item[group_key] for group_key in group_by}
                # 获得旧的值
                data_item = data.get(
                    key,
                    {
                        "keys": keys,
                        "usage": {},
                    },
                )
                data_item_usage = data_item["usage"].get(usage_key)
                # 将新值和旧值进行比较，替换旧值，取最新的资源使用率
                if not data_item_usage or (data_item_usage < item["_result_"]):
                    data_item["usage"][usage_key] = item["_result_"]
                data[key] = data_item

        return data

    @classmethod
    def merge_monitor_status(cls, usage_resource_map: Dict, monitor_operator_status_up_map: Dict) -> Dict:
        """合并两个来源的数据状态 ."""
        # 根据资源使用率设置数据状态
        resource_status_map = {}
        for key, value in usage_resource_map.items():
            if value is not None:
                monitor_status = cls.METRICS_STATE_STATE_SUCCESS
            else:
                monitor_status = cls.METRICS_STATE_DISABLED
            resource_status_map[key] = monitor_status

        # 根据采集器指标设置数据状态
        resource_status_map.update(monitor_operator_status_up_map)

        return resource_status_map

    @staticmethod
    def get_monitor_beat_up_status(
        bk_biz_id: int, bcs_cluster_id: str, monitor_type: Optional[str], group_by: List
    ) -> Dict:
        """获得采集器的采集健康状态 ."""
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
            "group_by": group_by,
        }
        if monitor_type:
            params["monitor_type"] = monitor_type
        metric_value_dict = api.kubernetes.fetch_k8s_bkm_metricbeat_endpoint_up(params)
        return metric_value_dict

    @classmethod
    def update_monitor_status_by_pod(cls, bcs_base_queryset, pod_models) -> None:
        """更新数据状态 ."""
        # 获得已存在的记录
        old_unique_hash_map = {model.unique_hash: (model.monitor_status,) for model in bcs_base_queryset}

        # 获得新的记录
        pod_monitor_status_map = {
            (pod_model.namespace, pod_model.name): pod_model.monitor_status for pod_model in pod_models
        }
        new_unique_hash_map = {}
        for model in bcs_base_queryset:
            monitor_status = cls.METRICS_STATE_FAILURE
            unique_hash = model.unique_hash
            pod_name_str = model.pod_name_list
            if pod_name_str:
                # Get all associated service pods
                pod_name_list = pod_name_str.split(",")
                namespace = model.namespace
                for pod_name in pod_name_list:
                    key = (namespace, pod_name)
                    old_monitor_status = new_unique_hash_map.get(key)
                    new_monitor_status = pod_monitor_status_map.get(key)
                    # pod have no monitor status
                    if new_monitor_status is None:
                        continue
                    if old_monitor_status is None:
                        monitor_status = new_monitor_status
                    else:
                        if old_monitor_status == cls.METRICS_STATE_STATE_SUCCESS:
                            continue
                        elif old_monitor_status == cls.METRICS_STATE_DISABLED:
                            if new_monitor_status == cls.METRICS_STATE_STATE_SUCCESS:
                                monitor_status = new_monitor_status
                        elif old_monitor_status == cls.METRICS_STATE_FAILURE:
                            monitor_status = new_monitor_status
            new_unique_hash_map[unique_hash] = (monitor_status,)

        # 更新资源使用量
        unique_hash_set_for_update = set(old_unique_hash_map.keys()) & set(new_unique_hash_map.keys())
        for unique_hash in unique_hash_set_for_update:
            if new_unique_hash_map[unique_hash] == old_unique_hash_map[unique_hash]:
                continue
            update_kwargs = new_unique_hash_map[unique_hash]
            monitor_status = update_kwargs[0]
            cls.objects.filter(unique_hash=unique_hash).update(
                **{
                    "monitor_status": monitor_status,
                }
            )

    @classmethod
    def convert_up_code_to_monitor_status(cls, code_list: List) -> str:
        Code = BkmMetricbeatEndpointUpStatus
        code_set = set(code_list)
        if code_set.issubset(
            {
                Code.BeatErrCodeOK,
                Code.BeatScriptPromFormatOuterError,
                Code.BeatMetricBeatPromFormatOuterError,
            }
        ):
            # 全部成功
            monitor_status = cls.METRICS_STATE_STATE_SUCCESS
        else:
            # 有失败的状态码
            monitor_status = cls.METRICS_STATE_FAILURE
        return monitor_status

    @classmethod
    def convert_up_to_monitor_status(
        cls, metric_value_dict: Dict, group_num: int, key_indexes: List, code_index: int
    ) -> Dict:
        """将up指标转换为采集器的状态 ."""
        result = {}
        # 获得状态码有多少种
        data = {}
        for group_key in metric_value_dict.keys():
            if len(group_key) != group_num:
                continue
            code_value = int(group_key[code_index])
            key = tuple(
                [key_item for index, key_item in enumerate(group_key) if index != code_index and index in key_indexes]
            )
            data.setdefault(key, []).append(code_value)

        for key, code_value_list in data.items():
            monitor_status = cls.convert_up_code_to_monitor_status(code_value_list)
            result[key] = monitor_status

        return result

    def update_monitor_status(self, params: Dict) -> None:
        """更新采集器状态 ."""
        bk_biz_id = params["bk_biz_id"]
        # 判断up指标是否存在
        if not api.kubernetes.has_bkm_metricbeat_endpoint_up({"bk_biz_id": bk_biz_id}):
            return
        # 添加分组
        group_by = ["bk_endpoint_url", "code"]
        params["group_by"] = group_by
        # 获得up指标
        metric_value_dict = api.kubernetes.fetch_k8s_bkm_metricbeat_endpoint_up(params)
        # 将up指标转换为采集器的状态
        if not metric_value_dict:
            # 没有指标返回
            monitor_status = self.METRICS_STATE_DISABLED
        else:
            code_list = [int(key[1]) for key in metric_value_dict.keys() if len(key) == len(group_by)]
            monitor_status = self.convert_up_code_to_monitor_status(code_list)

        self.monitor_status = monitor_status
        self.save()


class BCSBaseUsageResources(models.Model):
    class Meta:
        abstract = True

    resource_usage_cpu = models.FloatField(null=True)
    resource_usage_memory = models.BigIntegerField(null=True)
    resource_usage_disk = models.BigIntegerField(null=True)

    @classmethod
    def get_cpu_human_readable(cls, size) -> str:
        if size is None:
            return ""
        if not size:
            return "0"

        m_size = int(size * 1000)
        return f"{m_size}m"

    @classmethod
    def get_bytes_unit_human_readable(cls, size, precision=0) -> str:
        if size is None:
            return ""
        if not size:
            return "0"
        suffixes = ["B", "KB", "MB", "GB", "TB"]
        suffix_index = 0
        while size >= 1024 and suffix_index < 4:
            suffix_index += 1  # increment the index of the suffix
            size = size / 1024.0  # apply the division
        return "%.*f%s" % (precision, size, suffixes[suffix_index])

    def render_resource_usage_cpu(self, bk_biz_id, render_type="list"):
        return self.get_cpu_human_readable(self.resource_usage_cpu)

    def render_resource_usage_memory(self, bk_biz_id, render_type="list"):
        return self.get_bytes_unit_human_readable(self.resource_usage_memory)

    def render_resource_usage_disk(self, bk_biz_id, render_type="list"):
        return self.get_bytes_unit_human_readable(self.resource_usage_disk)


class BCSBaseResources(BCSBaseUsageResources):
    class Meta:
        abstract = True

    resource_requests_cpu = models.FloatField(null=False, default=0)
    resource_requests_memory = models.BigIntegerField(null=False, default=0)
    resource_limits_cpu = models.FloatField(null=False, default=0)
    resource_limits_memory = models.BigIntegerField(null=False, default=0)

    def render_resource_requests_cpu(self, bk_biz_id, render_type="list"):
        return self.get_cpu_human_readable(self.resource_requests_cpu)

    def render_resource_requests_memory(self, bk_biz_id, render_type="list"):
        return self.get_bytes_unit_human_readable(self.resource_requests_memory)

    def render_resource_limits_cpu(self, bk_biz_id, render_type="list"):
        return self.get_cpu_human_readable(self.resource_limits_cpu)

    def render_resource_limits_memory(self, bk_biz_id, render_type="list"):
        return self.get_bytes_unit_human_readable(self.resource_limits_memory)

    def render_resources(self, bk_biz_id, render_type="list"):
        resources = []
        if self.resource_requests_cpu:
            resources.append(
                {
                    "key": "requests cpu",
                    "value": self.get_cpu_human_readable(self.resource_requests_cpu),
                }
            )
        if self.resource_requests_memory:
            resources.append(
                {
                    "key": "requests memory",
                    "value": self.get_bytes_unit_human_readable(self.resource_requests_memory),
                }
            )
        if self.resource_limits_cpu:
            resources.append(
                {
                    "key": "limits cpu",
                    "value": self.get_cpu_human_readable(self.resource_limits_cpu),
                }
            )
        if self.resource_limits_memory:
            resources.append(
                {
                    "key": "limits memory",
                    "value": self.get_bytes_unit_human_readable(self.resource_limits_memory),
                }
            )
        return resources

import abc
import collections
import json
import logging
import operator
import os
import time
from datetime import datetime, timedelta
from functools import reduce

from django.conf import settings
from django.core.exceptions import EmptyResultSet
from django.db.models import Count, Q
from kubernetes.client.exceptions import ApiException
from kubernetes.stream import stream
from rest_framework import serializers

from bkm_space.api import SpaceApi, SpaceTypeEnum
from bkm_space.utils import bk_biz_id_to_space_uid, space_uid_to_bk_biz_id
from bkmonitor.data_source import UnifyQuery, load_data_source
from bkmonitor.models import (
    BCSCluster,
    BCSContainer,
    BCSLabel,
    BCSNode,
    BCSPod,
    BCSPodLabels,
    BCSPodMonitor,
    BCSService,
    BCSServiceMonitor,
    BCSWorkload,
    MetricListCache,
)
from bkmonitor.utils.cache import CacheType
from bkmonitor.utils.kubernetes import (
    BKM_METRICBEAT_ENDPOINT_UP,
    BcsClusterType,
    KubernetesContainerJsonParser,
    KubernetesEndpointJsonParser,
    KubernetesIngressJsonParser,
    KubernetesNodeJsonParser,
    KubernetesPodJsonParser,
    KubernetesPodMonitorJsonParser,
    KubernetesServiceJsonParser,
    KubernetesServiceMonitorJsonParser,
    KubernetesWorkloadJsonParser,
)
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkmonitor.utils.thread_backend import ThreadPool
from constants.data_source import DataSourceLabel, DataTypeLabel
from core.drf_resource import CacheResource, Resource, api
from core.errors.bkmonitor.operator import OperatorVersionNotSupport
from metadata import models

logger = logging.getLogger("kubernetes")
logger.setLevel(logging.INFO)


def get_bytes_unit_human_readable(size, precision=0):
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    suffix_index = 0
    while size >= 1024 and suffix_index < 4:
        suffix_index += 1  # increment the index of the suffix
        size = size / 1024.0  # apply the division
    return f"{size:.{precision}f}{suffixes[suffix_index]}"


def get_filter_query_string(filter_query):
    filter_query_items = []
    for key, value in filter_query.items():
        if isinstance(value, list):
            for value_item in value:
                filter_query_items.append(f"filter-{key}={value_item}")
        else:
            filter_query_items.append(f"filter-{key}={value}")
    filter_query_string = "&".join(filter_query_items)
    return filter_query_string


class FetchKubernetesGrafanaMetricRecords(Resource, abc.ABC):
    """根据promql查询指标的基类 ."""

    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)

    def validate_request_data(self, request_data: dict) -> dict:
        bk_biz_id = int(request_data["bk_biz_id"])
        request_data["bk_biz_id"] = bk_biz_id
        start_time = request_data.get("start_time")
        end_time = request_data.get("end_time")
        if not start_time:
            end_time = int(time.time())
            start_time = int(time.time() - 600)
        request_data["start_time"] = int(start_time) * 1000
        request_data["end_time"] = int(end_time) * 1000

        return request_data

    @classmethod
    def request_graph_unify_query(cls, validated_request_data) -> tuple:
        """执行promql查询 ."""
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        data_source_params = validated_request_data["data_source_params"]
        key_name = data_source_params["key_name"]
        promql = data_source_params["promql"]
        if not promql:
            return key_name, []
        data_sources = [
            cls.DATA_SOURCE_CLASS(bk_biz_id=bk_biz_id, promql=promql, interval=60),
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A")
        records = query.query_data(start_time=start_time, end_time=end_time)
        result = (key_name, records)
        return result

    def request_performance_data(self, validated_request_data: dict) -> list:
        """多线程查询多个promql ."""
        pool = ThreadPool()
        args = self.build_graph_unify_query_iterable(validated_request_data)
        if not args:
            return []
        performance_data = pool.map(self.request_graph_unify_query, args)
        pool.close()
        pool.join()
        return performance_data

    def perform_request(self, validated_request_data: dict) -> list | dict:
        # 多线程查询多个promql
        performance_data = self.request_performance_data(validated_request_data)
        if not performance_data:
            return {}
        # 格式化查询结果
        data = self.format_performance_data(performance_data)
        return data

    @abc.abstractmethod
    def format_performance_data(self, performance_data: list) -> list | dict:
        """格式化查询结果 ."""
        ...

    @abc.abstractmethod
    def build_graph_unify_query_iterable(self, validated_request_data: dict) -> list:
        """构造需要查询的promql ."""
        ...


class FetchK8sNodePerformanceResource(FetchKubernetesGrafanaMetricRecords):
    """查询node节点的性能指标。"""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID", allow_null=True, allow_blank=True)
        start_time = serializers.CharField(required=False, label="start_time")
        end_time = serializers.CharField(required=False, label="end_time")
        overview = serializers.BooleanField(required=False, label="是否计算概览", default=False)
        node_ips = serializers.ListField(required=False, default=[])

    @staticmethod
    def format_performance_data(performance_data: list):
        data = {}
        overview_data = {}
        for key_name, overview, records in performance_data:
            for item in records:
                value = item["_result_"]
                if overview:
                    overview_data[key_name] = value
                else:
                    instance = item.get("instance")
                    if not instance:
                        continue
                    bk_target_ip = instance.rsplit(":")[0]
                    data.setdefault(bk_target_ip, {})[key_name] = value

        result = {
            "data": data,
            "overview": overview_data,
        }
        return result

    @classmethod
    def request_graph_unify_query(cls, validated_request_data) -> tuple:
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        data_source_params = validated_request_data["data_source_params"]
        key_name = data_source_params["key_name"]
        overview = data_source_params.get("overview", False)
        promql = data_source_params["promql"]
        data_sources = [
            cls.DATA_SOURCE_CLASS(bk_biz_id=bk_biz_id, promql=promql, interval=60),
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A")
        records = query.query_data(start_time=start_time, end_time=end_time)
        result = (key_name, overview, records)

        return result

    def build_graph_unify_query_iterable(self, validated_request_data: dict) -> list:
        bk_biz_id = validated_request_data["bk_biz_id"]
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        overview = validated_request_data.get("overview", False)
        node_ips = validated_request_data.get("node_ips", [])
        if node_ips:
            ip_list = [f"{ip}:" for ip in node_ips if ip]
            instance = "^({})".format("|".join(ip_list))
        else:
            instance = ""

        # 获得业务下的集群
        if bcs_cluster_id:
            bcs_cluster_ids = [bcs_cluster_id]
        else:
            try:
                bcs_cluster_ids = list(
                    BCSNode.objects.filter_by_biz_id(bk_biz_id).values_list("bcs_cluster_id", flat=True)
                )
            except EmptyResultSet:
                return []
        bcs_cluster_ids = list(set(bcs_cluster_ids))

        args = []
        system_cpu_summary_usage_promql = self.build_system_cpu_summary_usage_promql(bcs_cluster_ids, instance)
        system_load_load15_promql = self.build_system_load_load15_promql(bcs_cluster_ids, instance)
        system_mem_pct_used_promql = self.build_system_mem_pct_used_promql(bcs_cluster_ids, instance)
        system_io_util_promql = self.build_system_io_util_promql(bcs_cluster_ids, instance)
        system_disk_in_use_promql = self.build_system_disk_in_use_promql(bcs_cluster_ids, instance)

        system_cpu_summary_usage_overview_promql = self.build_system_cpu_summary_usage_overview_promql(bcs_cluster_ids)
        system_load_load15_overview_promql = self.build_system_load_load15_overview_promql(bcs_cluster_ids)
        system_mem_pct_used_overview_promql = self.build_system_mem_pct_used_overview_promql(bcs_cluster_ids)
        system_io_util_overview_promql = self.build_system_io_util_overview_promql(bcs_cluster_ids)
        system_disk_in_use_overview_promql = self.build_system_disk_in_use_overview_promql(bcs_cluster_ids)

        data_source_param_map: list[dict[str, str | bool]] = [
            {"key_name": "system_cpu_summary_usage", "promql": system_cpu_summary_usage_promql},
            {"key_name": "system_load_load15", "promql": system_load_load15_promql},
            {"key_name": "system_mem_pct_used", "promql": system_mem_pct_used_promql},
            {"key_name": "system_io_util", "promql": system_io_util_promql},
            {"key_name": "system_disk_in_use", "promql": system_disk_in_use_promql},
        ]

        if overview:
            data_source_param_map.extend(
                [
                    {
                        "key_name": "system_cpu_summary_usage",
                        "overview": True,
                        "promql": system_cpu_summary_usage_overview_promql,
                    },
                    {"key_name": "system_load_load15", "overview": True, "promql": system_load_load15_overview_promql},
                    {
                        "key_name": "system_mem_pct_used",
                        "overview": True,
                        "promql": system_mem_pct_used_overview_promql,
                    },
                    {"key_name": "system_io_util", "overview": True, "promql": system_io_util_overview_promql},
                    {"key_name": "system_disk_in_use", "overview": True, "promql": system_disk_in_use_overview_promql},
                ]
            )

        for data_source_params in data_source_param_map:
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                }
            )

        return args

    @staticmethod
    def build_system_cpu_summary_usage_promql(bcs_cluster_ids: list[str], instance: str) -> str:
        if not instance:
            promql = (
                '(1 - avg by(bcs_cluster_id, instance) (irate(node_cpu_seconds_total{{mode="idle",'
                'bcs_cluster_id=~"^({bcs_cluster_id})$"}}[5m]))) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        else:
            promql = (
                '(1 - avg by(bcs_cluster_id, instance) (irate(node_cpu_seconds_total{{mode="idle",'
                'bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}}[5m]))) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids), instance=instance)

        return promql

    @staticmethod
    def build_system_cpu_summary_usage_overview_promql(bcs_cluster_ids: list[str]) -> str:
        promql = (
            '(1 - avg(irate(node_cpu_seconds_total{{mode="idle",bcs_cluster_id=~"^({bcs_cluster_id})$"}}[5m]))) * 100'
        ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        return promql

    @staticmethod
    def build_system_load_load15_promql(bcs_cluster_ids: list[str], instance: str) -> str:
        if not instance:
            promql = (
                'sum by(bcs_cluster_id, instance) (node_load15{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
            ).format(
                bcs_cluster_id="|".join(bcs_cluster_ids),
            )
        else:
            promql = (
                'sum by(bcs_cluster_id, instance) (node_load15{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
                'instance=~"{instance}"}})'
            ).format(
                bcs_cluster_id="|".join(bcs_cluster_ids),
                instance=instance,
            )

        return promql

    @staticmethod
    def build_system_load_load15_overview_promql(bcs_cluster_ids: list[str]) -> str:
        promql = ('sum (node_load15{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})').format(
            bcs_cluster_id="|".join(bcs_cluster_ids),
        )
        return promql

    @staticmethod
    def build_system_mem_pct_used_promql(bcs_cluster_ids: list[str], instance: str) -> str:
        if not instance:
            promql = (
                "(SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemFree_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Cached_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Buffers_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
                " + on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Shmem_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}}))'
                " / on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}}) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        else:
            promql = (
                "(SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemFree_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Cached_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}})'
                " - on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Buffers_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}})'
                " + on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance) "
                '(node_memory_Shmem_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}"}}))'
                " / on(bcs_cluster_id,instance) group_right() SUM by(bcs_cluster_id,instance)"
                ' (node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",instance=~"{instance}"}}) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids), instance=instance)

        return promql

    @staticmethod
    def build_system_mem_pct_used_overview_promql(bcs_cluster_ids: list[str]) -> str:
        promql = (
            '(SUM(node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
            '-SUM(node_memory_MemFree_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
            '-SUM(node_memory_Cached_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
            '-SUM(node_memory_Buffers_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})'
            '+SUM(node_memory_Shmem_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}}))'
            '/(SUM(node_memory_MemTotal_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$"}})) *100'
        ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        return promql

    @staticmethod
    def build_system_io_util_promql(bcs_cluster_ids: list[str], instance: str) -> str:
        if not instance:
            promql = (
                "max by(bcs_cluster_id, instance)"
                ' (rate(node_disk_io_time_seconds_total{{bcs_cluster_id=~"^({bcs_cluster_id})$"}}[2m])) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        else:
            promql = (
                "max by(bcs_cluster_id, instance)"
                ' (rate(node_disk_io_time_seconds_total{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
                ' instance=~"{instance}"}}[2m])) * 100'
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids), instance=instance)

        return promql

    @staticmethod
    def build_system_io_util_overview_promql(bcs_cluster_ids: list[str]) -> str:
        promql = (
            'avg (rate(node_disk_io_time_seconds_total{{bcs_cluster_id=~"^({bcs_cluster_id})$"}}[2m])) * 100'
        ).format(
            bcs_cluster_id="|".join(bcs_cluster_ids),
        )
        return promql

    @staticmethod
    def build_system_disk_in_use_promql(bcs_cluster_ids: list[str], instance: str) -> str:
        if not instance:
            promql = (
                "(max by(bcs_cluster_id, instance)"
                ' (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
                " - on(bcs_cluster_id, instance) group_right()"
                " max by(bcs_cluster_id, instance)"
                ' (node_filesystem_free_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}}))'
                " / on(bcs_cluster_id, instance) group_right()"
                " max by(bcs_cluster_id, instance)"
                ' (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
                " * 100"
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        else:
            promql = (
                "(max by(bcs_cluster_id, instance)"
                ' (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
                " - on(bcs_cluster_id, instance) group_right()"
                " max by(bcs_cluster_id, instance)"
                ' (node_filesystem_free_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}}))'
                " / on(bcs_cluster_id, instance) group_right()"
                " max by(bcs_cluster_id, instance)"
                ' (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$", instance=~"{instance}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
                " * 100"
            ).format(bcs_cluster_id="|".join(bcs_cluster_ids), instance=instance)

        return promql

    @staticmethod
    def build_system_disk_in_use_overview_promql(bcs_cluster_ids: list[str]) -> str:
        promql = (
            '(sum (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
            'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
            ' - sum (node_filesystem_free_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
            'fstype=~"ext[234]|btrfs|xfs|zfs"}}))'
            ' / sum (node_filesystem_size_bytes{{bcs_cluster_id=~"^({bcs_cluster_id})$",'
            'fstype=~"ext[234]|btrfs|xfs|zfs"}})'
            " * 100"
        ).format(bcs_cluster_id="|".join(bcs_cluster_ids))
        return promql


class FetchK8sPodListByClusterResource(CacheResource):
    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        namespace_list = serializers.ListField(
            required=False, child=serializers.CharField(), default=[], allow_empty=True
        )

    @staticmethod
    def get_node_field():
        field = [
            "data.metadata.name",
            "data.status.addresses",
        ]
        return ",".join(field)

    @staticmethod
    def get_replica_set_field():
        field = [
            "data.metadata.name",
            "data.metadata.ownerReferences",
        ]
        return ",".join(field)

    @staticmethod
    def get_pod_field():
        field = [
            "data.metadata.name",
            "data.metadata.namespace",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.metadata.ownerReferences",
            "data.spec.initContainers",
            "data.spec.containers",
            "data.status.containerStatuses",
            "data.status.podIP",
            "data.status.hostIP",
            "data.status.phase",
            "data.status.reason",
            "data.status.initContainerStatuses",
            "data.status.conditions",
            "data.deletionTimestamp",
        ]
        return ",".join(field)

    @staticmethod
    def get_job_field():
        field = [
            "data.metadata.name",
            "data.metadata.ownerReferences",
        ]
        return ",".join(field)

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        namespace_list = params["namespace_list"]

        node_list, replica_set_list, job_list = api.bcs_storage.fetch.bulk_request(
            [
                {"cluster_id": bcs_cluster_id, "type": "Node", "field": self.get_node_field()},
                {"cluster_id": bcs_cluster_id, "type": "ReplicaSet", "field": self.get_replica_set_field()},
                {"cluster_id": bcs_cluster_id, "type": "Job", "field": self.get_job_field()},
            ]
        )
        pod_data = api.bcs_storage.fetch_iterator(bcs_cluster_id, "Pod", self.get_pod_field())

        # node的ip与name的映射
        node_ip_name_map = {}
        for node in node_list:
            node_parser = KubernetesNodeJsonParser(node)
            node_ip_name_map[node_parser.node_ip] = node_parser.name

        # workload的ownerReferences映射
        workload_map = {"ReplicaSet": replica_set_list, "Job": job_list}
        workload_parent_map = collections.defaultdict(lambda: collections.defaultdict(list))
        for workload_type, workload_list in workload_map.items():
            for workload in workload_list:
                workload_metadata = workload.get("metadata", {})
                workload_owner_references = workload_metadata.get("ownerReferences", [])
                if not workload_owner_references:
                    continue
                workload_parent_map[workload_type][workload_metadata["name"]] = workload_owner_references

        # 内存释放
        del replica_set_list, job_list, node_list

        namespace_set = set(namespace_list)
        for pod in pod_data:
            pod_parser = KubernetesPodJsonParser(pod)

            images_list = pod_parser.image_list
            restart_count = pod_parser.restart_count
            creation_timestamp = pod_parser.creation_timestamp
            pod_ip = pod_parser.pod_ip
            node_ip = pod_parser.node_ip
            age = pod_parser.age
            ready_total = pod_parser.ready_total
            ready_count = pod_parser.ready_count
            labels = pod_parser.labels
            label_list = pod_parser.label_list
            namespace = pod_parser.namespace
            if namespace_set and namespace not in namespace_set:
                # 共享集群需要验证ns
                continue
            pod_name = pod_parser.name
            status = pod_parser.service_status

            # 获取pod关联的workload
            workload_type, workload_name = "", ""
            pod_workloads = []
            owner_references = pod_parser.metadata.get("ownerReferences", [])
            for index, owner_reference in enumerate(owner_references):
                kind, name = owner_reference["kind"], owner_reference["name"]
                pod_workloads.append({"key": kind, "value": name})
                p_owner_references = workload_parent_map.get(kind, {}).get(name, [])

                # 记录关联的workload
                if not workload_type:
                    workload_type, workload_name = kind, name

                # 记录关联的workload的父级
                for p_owner_reference in p_owner_references:
                    kind, name = p_owner_reference["kind"], p_owner_reference["name"]
                    pod_workloads.append({"key": kind, "value": name})

                    # 只尝试获取第一个OwnerReference关联的workload的父级
                    if index == 0:
                        workload_type, workload_name = kind, name

            resources = pod_parser.resources
            requests_cpu = resources["requests_cpu"]
            limits_cpu = resources["limits_cpu"]
            requests_memory = resources["requests_memory"]
            limits_memory = resources["limits_memory"]

            yield {
                "bcs_cluster_id": bcs_cluster_id,
                "pod": pod,
                "name": pod_name,
                "requests_cpu": requests_cpu,
                "limits_cpu": limits_cpu,
                "requests_memory": requests_memory,
                "limits_memory": limits_memory,
                "resources": [
                    {
                        "key": "requests.cpu",
                        "value": requests_cpu,
                    },
                    {
                        "key": "limits.cpu",
                        "value": limits_cpu,
                    },
                    {
                        "key": "requests.memory",
                        "value": get_bytes_unit_human_readable(requests_memory),
                    },
                    {
                        "key": "limits.memory",
                        "value": get_bytes_unit_human_readable(limits_memory),
                    },
                ],
                "node_name": node_ip_name_map.get(node_ip, ""),
                "node_ip": node_ip,
                "workloads": pod_workloads,
                "workload_type": workload_type,
                "workload_name": workload_name,
                "namespace": namespace,
                "status": status,
                "total_container_count": ready_total,
                "ready_container_count": ready_count,
                "ready": f"{ready_count}/{ready_total}",
                "container_number": ready_total,
                "label_list": label_list,
                "labels": labels,
                "pod_ip": pod_ip,
                "image_id_list": images_list,
                "restarts": restart_count,
                "created_at": creation_timestamp,
                "age": age,
            }


class FetchK8sClusterListResource(CacheResource):
    """获得BCS集群列表 ."""

    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=False, allow_null=True, label="业务ID")
        data_type = serializers.ChoiceField(choices=("simple", "full"), default="simple")

        def validate(self, attrs):
            attrs["project_id"] = None
            bk_biz_id = attrs.get("bk_biz_id")
            if bk_biz_id and bk_biz_id < 0:
                # 获得容器项目ID
                space_uid = bk_biz_id_to_space_uid(bk_biz_id)
                space = SpaceApi.get_related_space(space_uid, SpaceTypeEnum.BKCI.value)
                if space:
                    # 不包含共享集群
                    project_id = space.space_code
                    attrs["project_id"] = project_id
            return attrs

    @staticmethod
    def get_full_clusters(clusters):
        for index, cluster in enumerate(clusters):
            nodes = api.kubernetes.fetch_k8s_node_list_by_cluster({"bcs_cluster_id": cluster["cluster_id"]})
            cluster["master_count"] = len(
                [
                    node
                    for node in nodes
                    if "master" in node["node_roles"] and node["bcs_cluster_id"] == cluster["bcs_cluster_id"]
                ]
            )
            cluster["node_count"] = len(
                [
                    node
                    for node in nodes
                    if "master" not in node["node_roles"] and node["bcs_cluster_id"] == cluster["bcs_cluster_id"]
                ]
            )
        return clusters

    @classmethod
    def cluster_id_in_gray(cls, cluster_id):
        if not settings.ENABLE_BCS_GRAY_CLUSTER:
            return True

        gray_cluster_id_list = []
        if isinstance(settings.BCS_GRAY_CLUSTER_ID_LIST, str):
            gray_cluster_id_list = settings.BCS_GRAY_CLUSTER_ID_LIST.split(",")
        elif isinstance(settings.BCS_GRAY_CLUSTER_ID_LIST, list):
            gray_cluster_id_list = settings.BCS_GRAY_CLUSTER_ID_LIST
        return cluster_id in gray_cluster_id_list

    def get_clusters_from_bcs_cluster_manager(self, params):
        """从cluster manager获取集群列表 ."""
        # 获取集群列表
        bk_biz_id = params.get("bk_biz_id")
        project_id = params.get("project_id")
        bcs_clusters = api.bcs_cluster_manager.fetch_clusters()
        cluster_id_set = set()
        clusters = []
        for bcs_cluster in bcs_clusters:
            cluster_id = bcs_cluster["clusterID"]
            business_id = bcs_cluster["businessID"]
            # 如果是项目空间，优先项目空间过滤
            if project_id and project_id != bcs_cluster["projectID"]:
                continue
            # 业务空间，按业务ID过滤
            if bk_biz_id and bk_biz_id > 0 and f"{bk_biz_id}" != business_id:
                continue
            # 根据灰度配置只同步指定集群ID的集群
            if not self.cluster_id_in_gray(cluster_id):
                continue
            # 忽略重复的集群ID，共享集群有重复的集群ID
            if cluster_id in cluster_id_set:
                continue
            cluster_id_set.add(cluster_id)
            cluster = {
                "bk_biz_id": business_id,
                "cluster_id": cluster_id,
                "bcs_cluster_id": cluster_id,
                "id": cluster_id,
                "name": bcs_cluster["clusterName"],
                "project_id": bcs_cluster["projectID"],
                "project_name": "",
                "created_at": bcs_cluster["createTime"],
                "updated_at": bcs_cluster["updateTime"],
                "status": bcs_cluster["status"],
                "environment": bcs_cluster["environment"],
            }
            clusters.append(cluster)
        if params.get("data_type") == "full":
            clusters = self.get_full_clusters(clusters)

        return clusters

    def get_clusters_from_bcs_cc(self, params):
        bk_biz_id = params.get("bk_biz_id")
        project_id = params.get("project_id")
        projects = [p for p in api.bcs_cc.get_project_list()["results"]]
        project_id_map = {p["project_id"]: {"bk_biz_id": p["cc_app_id"], "name": p["name"]} for p in projects}
        areas = api.bcs_cc.get_area_list()["results"]
        areas_names = {area["id"]: area["chinese_name"] for area in areas}
        bcs_clusters = api.bcs_cc.get_cluster_list()
        cluster_id_set = set()
        clusters = []
        for cluster in bcs_clusters:
            cluster_id = cluster["cluster_id"]
            if not self.cluster_id_in_gray(cluster_id):
                continue
            project = project_id_map.get(cluster["project_id"])
            if not project:
                continue
            cluster_bk_biz_id = project.get("bk_biz_id")
            project_name = project.get("name")
            if not cluster_bk_biz_id:
                continue
            if not project_name:
                continue
            # 如果是bcs项目，直接基于project_id过滤
            if project_id and project_id != cluster["project_id"]:
                continue
            # 业务空间，按业务ID过滤
            if bk_biz_id and bk_biz_id > 0 and bk_biz_id != cluster_bk_biz_id:
                continue
            # 忽略重复的集群ID，共享集群有重复的集群ID
            if cluster_id in cluster_id_set:
                continue
            cluster_id_set.add(cluster_id)
            area_id = cluster.get("area_id")
            cluster["area_name"] = areas_names.get(area_id, area_id)
            cluster["bk_biz_id"] = cluster_bk_biz_id
            cluster["project_name"] = project_name
            cluster["bcs_cluster_id"] = cluster_id
            cluster["id"] = cluster_id
            cluster["name"] = cluster_id
            cluster["created_at"] = cluster["created_at"]
            cluster["updated_at"] = cluster["updated_at"]
            clusters.append(cluster)
        if params.get("data_type") == "full":
            clusters = self.get_full_clusters(params, clusters)
        return clusters

    def perform_request(self, params):
        if settings.BCS_CLUSTER_SOURCE == "bcs-cc":
            return self.get_clusters_from_bcs_cc(params)
        return self.get_clusters_from_bcs_cluster_manager(params)


class FetchK8sIngressListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    @staticmethod
    def get_ingress_field():
        field = [
            "data.metadata.name",
            "data.metadata.namespace",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.spec.rules",
            "data.spec.tls",
            "data.spec.ingressClassName",
            "data.status",
        ]
        return ",".join(field)

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        data = []
        ingress_field = self.get_ingress_field()
        ingress_list = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Ingress", "field": ingress_field})
        for ingress in ingress_list:
            ingress_parser = KubernetesIngressJsonParser(ingress)
            ingress_name = ingress_parser.name
            ingress_labels = ingress_parser.labels
            namespace = ingress_parser.namespace
            creation_timestamp = ingress_parser.creation_timestamp
            service_list = ingress_parser.service_list
            age = ingress_parser.age
            class_name = ingress_parser.class_name
            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "name": ingress_name,
                    "labels": ingress_labels,
                    "cluster": bcs_cluster_id,
                    "namespace": namespace,
                    "service_list": service_list,
                    "class_name": class_name,
                    "created_at": creation_timestamp,
                    "age": age,
                }
            )
        return data


class FetchK8sServiceListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    @staticmethod
    def get_service_field():
        field = [
            "data.metadata.name",
            "data.metadata.namespace",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.spec.type",
            "data.spec.clusterIP",
            "data.spec.clusterIPs",
            "data.spec.externalIPs",
            "data.spec.externalName",
            "data.spec.ports",
            "data.status",
        ]
        return ",".join(field)

    @staticmethod
    def get_endpoint_field():
        field = [
            "data.metadata.name",
            "data.subsets",
        ]
        return ",".join(field)

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        data = []
        endpoint_field = self.get_endpoint_field()
        service_field = self.get_service_field()
        [endpoints, services] = api.bcs_storage.fetch.bulk_request(
            [
                {"cluster_id": bcs_cluster_id, "type": "Endpoints", "field": endpoint_field},
                {"cluster_id": bcs_cluster_id, "type": "Service", "field": service_field},
            ]
        )
        for service in services:
            service_parser = KubernetesServiceJsonParser(service)
            service_name = service_parser.name
            service_labels = service_parser.labels
            namespace = service_parser.namespace
            external_ip = service_parser.external_ip
            ports = service_parser.svc_ports.split(",")
            creation_timestamp = service_parser.creation_timestamp
            age = service_parser.age
            cluster_ip = service_parser.cluster_ip
            service_type = service_parser.service_type

            endpoint_count = service_parser.get_endpoints_count(endpoints)
            pod_count = service_parser.get_pod_count(endpoints)
            pod_name_list = service_parser.get_pod_name_list(endpoints)

            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "name": service_name,
                    "labels": service_labels,
                    "cluster": bcs_cluster_id,
                    "namespace": namespace,
                    "type": service_type,
                    "cluster_ip": cluster_ip,
                    "external_ip": external_ip,
                    "ports": ports,
                    "endpoint_count": endpoint_count,
                    "pod_count": pod_count,
                    "pod_name": pod_name_list,  # 从ep反推
                    "created_at": creation_timestamp,
                    "age": age,
                }
            )
        return data


class FetchK8sServiceMonitorListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    GROUP: str = "monitoring.coreos.com"
    # 版本信息
    VERSION: str = "v1"
    # 资源复数名
    PLURAL = "ServiceMonitor"
    PLURALS = "servicemonitors"

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    def perform_request(self, params) -> list:
        bcs_cluster_id = params["bcs_cluster_id"]
        data = []

        try:
            cluster = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            return data

        resource_list = cluster.custom_objects_api.list_cluster_custom_object(
            group=self.GROUP, version=self.VERSION, plural=self.PLURALS
        )
        for conf in resource_list["items"]:
            service_monitor = KubernetesServiceMonitorJsonParser(conf)
            metric_path = []
            metric_port = []
            metric_interval = []
            name = service_monitor.name
            namespace = service_monitor.namespace
            creation_timestamp = service_monitor.creation_timestamp
            age = service_monitor.age
            labels = service_monitor.labels
            label_list = service_monitor.label_list
            endpoint_count = service_monitor.endpoint_count

            endpoint_list = service_monitor.endpoints
            for endpoint in endpoint_list:
                metric_path.append(endpoint.get("path"))
                metric_port.append(endpoint.get("port"))
                metric_interval.append(endpoint.get("interval"))

            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "name": name,
                    "namespace": namespace,
                    "created_at": creation_timestamp,
                    "metric_path": metric_path,
                    "metric_port": metric_port,
                    "metric_interval": metric_interval,
                    "label_list": label_list,
                    "endpoint_count": endpoint_count,
                    "labels": labels,
                    "age": age,
                }
            )

        return data


class FetchK8sMonitorEndpointListResource(CacheResource):
    """获得servicemointor/podmonitor监听的endpoints列表 ."""

    cache_type = CacheType.BCS

    LABEL_KEY = "app.kubernetes.io/bk-component"
    LABEL_VALUE = "bkmonitor-operator"

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.CharField(required=True)
        bcs_cluster_id = serializers.CharField(required=True)

    @staticmethod
    def exec_commands(api_instance, namespace, pod_name):
        """通过exec命令获得endpoints列表 ."""
        exec_command = [
            "sh",
            "-c",
            "curl -s http://localhost:8080/check/monitor_resource",
        ]
        resp = stream(
            api_instance.connect_get_namespaced_pod_exec,
            pod_name,
            namespace,
            command=exec_command,
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
        )
        resp = resp.strip()
        if not resp:
            return []
        try:
            # 可能返回404错误：404 page not found
            result = json.loads(resp.replace("'", '"'))
        except json.decoder.JSONDecodeError:
            raise OperatorVersionNotSupport()
        return result

    def get_pods(self, bcs_cluster_id: str) -> list[BCSPod]:
        """根据标签检索指定的pods ."""
        try:
            label_model = BCSLabel.objects.get(key=self.LABEL_KEY, value=self.LABEL_VALUE)
        except BCSLabel.DoesNotExist:
            return []
        label_id = label_model.hash_id
        pod_label_models = BCSPodLabels.objects.filter(label_id=label_id, bcs_cluster_id=bcs_cluster_id)
        if not pod_label_models:
            return []
        pod_ids = [model.resource_id for model in pod_label_models]
        pod_models = BCSPod.objects.filter(id__in=pod_ids)

        return pod_models

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        result = []
        try:
            cluster_model = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            return result
        pod_models = self.get_pods(bcs_cluster_id)
        if not pod_models:
            return result

        err = None
        api_instance = cluster_model.core_v1_api
        for pod_model in pod_models:
            namespace = pod_model.namespace
            pod_name = pod_model.name
            try:
                result = self.exec_commands(api_instance, namespace, pod_name)
                err = None
                break
            except OperatorVersionNotSupport as exec_info:
                err = exec_info
            except ApiException:
                # 因为同步延迟原因，pod可能不存在
                pass
        if err and isinstance(err, OperatorVersionNotSupport):
            # bk-operator版本不支持，需要升级版本
            raise OperatorVersionNotSupport
        return result


class FetchK8sPodMonitorListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    GROUP: str = "monitoring.coreos.com"
    # 版本信息
    VERSION: str = "v1"
    # 资源复数名
    PLURAL = "PodMonitor"
    PLURALS = "podmonitors"

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    def perform_request(self, params) -> list:
        bcs_cluster_id = params["bcs_cluster_id"]
        data = []

        try:
            cluster = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            return data

        resource_list = cluster.custom_objects_api.list_cluster_custom_object(
            group=self.GROUP, version=self.VERSION, plural=self.PLURALS
        )
        for conf in resource_list["items"]:
            pod_monitor = KubernetesPodMonitorJsonParser(conf)
            metric_path = []
            metric_port = []
            metric_interval = []
            name = pod_monitor.name
            namespace = pod_monitor.namespace
            creation_timestamp = pod_monitor.creation_timestamp
            age = pod_monitor.age
            labels = pod_monitor.labels
            label_list = pod_monitor.label_list
            endpoint_count = pod_monitor.endpoint_count

            endpoint_list = pod_monitor.endpoints
            for endpoint in endpoint_list:
                metric_path.append(endpoint.get("path"))
                metric_port.append(endpoint.get("port"))
                metric_interval.append(endpoint.get("interval"))

            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "name": name,
                    "namespace": namespace,
                    "created_at": creation_timestamp,
                    "metric_path": metric_path,
                    "metric_port": metric_port,
                    "metric_interval": metric_interval,
                    "label_list": label_list,
                    "endpoint_count": endpoint_count,
                    "labels": labels,
                    "age": age,
                }
            )

        return data


class FetchK8sEndpointListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        endpoints = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Endpoints"})
        data = []
        for endpoint in endpoints:
            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "endpoint": endpoint,
                }
            )
        return data


class FetchK8sContainerListByClusterResource(CacheResource):
    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        pods = api.kubernetes.fetch_k8s_pod_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})

        for pod in pods:
            pod_parser = KubernetesPodJsonParser(pod.get("pod", {}))
            containers = pod_parser.containers
            for container in containers:
                bcs_cluster_id = pod["bcs_cluster_id"]
                labels = pod_parser.labels

                container_parser = KubernetesContainerJsonParser(pod.get("pod", {}), container)
                container_name = container_parser.name
                age = container_parser.age
                status = container_parser.service_status
                created_at = container_parser.created_at
                image = container_parser.image

                container_status = container_parser.container_status
                container_status_ready = container_status.get("ready")

                resources = container_parser.resources
                requests_cpu = resources["requests_cpu"]
                limits_cpu = resources["limits_cpu"]
                requests_memory = resources["requests_memory"]
                limits_memory = resources["limits_memory"]

                yield {
                    "bcs_cluster_id": bcs_cluster_id,
                    "container": container,
                    "container_status": container_status,
                    "requests_cpu": requests_cpu,
                    "limits_cpu": limits_cpu,
                    "requests_memory": requests_memory,
                    "limits_memory": limits_memory,
                    "name": container_name,
                    "labels": labels,
                    "container_name": container_name,
                    "pod_name": pod_parser.name,
                    "node_name": pod["node_name"],
                    "node_ip": pod["node_ip"],
                    "workloads": pod["workloads"],
                    "workload_type": pod["workload_type"],
                    "workload_name": pod["workload_name"],
                    "namespace": pod_parser.namespace,
                    "image": image,
                    "container_status_ready": container_status_ready,
                    "status": status,
                    "created_at": created_at,
                    "age": age,
                }


class FetchK8sNodeListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")

    @staticmethod
    def get_node_field():
        field = [
            "data.metadata.name",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.spec.unschedulable",
            "data.spec.taints",
            "data.status.addresses",
            "data.status.conditions",
        ]
        return ",".join(field)

    @staticmethod
    def get_endpoint_field():
        field = [
            "data.metadata.name",
            "data.subsets",
        ]
        return ",".join(field)

    @staticmethod
    def get_pod_count_statistics(bcs_cluster_id):
        items = (
            BCSPod.objects.filter(bcs_cluster_id=bcs_cluster_id).values("node_ip").annotate(node_count=Count("node_ip"))
        )
        results = {item["node_ip"]: item["node_count"] for item in items}
        return results

    def perform_request(self, params):
        bcs_cluster_id = params["bcs_cluster_id"]
        node_field = self.get_node_field()
        endpoint_field = self.get_endpoint_field()
        [endpoints, nodes] = api.bcs_storage.fetch.bulk_request(
            [
                {"cluster_id": bcs_cluster_id, "type": "Endpoints", "field": endpoint_field},
                {"cluster_id": bcs_cluster_id, "type": "Node", "field": node_field},
            ]
        )
        data = []

        pod_count_statistics = self.get_pod_count_statistics(bcs_cluster_id)

        for node in nodes:
            node_parser = KubernetesNodeJsonParser(node)

            node_ip = node_parser.node_ip
            node_name = node_parser.name
            labels = node_parser.labels
            label_list = node_parser.label_list
            roles = node_parser.role_list
            status = node_parser.service_status

            pod_count = pod_count_statistics.get(node_ip, 0)
            endpoint_count = node_parser.get_endpoints_count(endpoints)
            creation_timestamp = node_parser.creation_timestamp
            taints = node_parser.taint_labels
            age = node_parser.age

            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "node": node,
                    "name": node_name,
                    "taints": taints,
                    "node_roles": roles,
                    "node_ip": node_ip,
                    "status": status,
                    "node_name": node_name,
                    "label_list": label_list,
                    "labels": labels,
                    "endpoint_count": endpoint_count,
                    "pod_count": pod_count,
                    "created_at": creation_timestamp,
                    "age": age,
                }
            )
        return data


class FetchK8sNamespaceListResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True)

    def perform_request(self, params):
        bk_biz_id = params.get("bk_biz_id")
        bcs_cluster_id = params.get("bcs_cluster_id")
        clusters = api.kubernetes.fetch_k8s_cluster_list({"bk_biz_id": bk_biz_id})
        data = []
        for cluster in clusters:
            cluster_id = cluster["bcs_cluster_id"]
            if bcs_cluster_id and bcs_cluster_id != cluster_id:
                continue
            try:
                items = self.get_cluster_data(cluster_id)
                data.extend(items)
            except Exception as e:
                logger.error("get cluster data error", e)
                logger.exception(e)
        return data

    @staticmethod
    def get_cluster_data(bcs_cluster_id):
        data = []
        namespaces = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Namespace"})
        for namespace in namespaces:
            data.append(
                {
                    "bcs_cluster_id": bcs_cluster_id,
                    "namespace": namespace,
                }
            )
        return data


class FetchK8sWorkloadTypeListResource(Resource):
    def perform_request(self, params):
        bk_biz_id = params.get("bk_biz_id")
        bcs_cluster_id = params.get("bcs_cluster_id")
        params = {
            "bk_biz_id": bk_biz_id,
            "bcs_cluster_id": bcs_cluster_id,
        }
        # 获取所有workload类型，包括自定义类型
        workload_type_list = BCSPod.objects.get_workload_type_list(params)

        return workload_type_list


class FetchK8sWorkloadListByClusterResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        workload_type_list = serializers.ListField(required=False, allow_empty=True, allow_null=True)

    @staticmethod
    def get_workload_field():
        field = [
            "data.metadata.name",
            "data.metadata.namespace",
            "data.metadata.resourceVersion",
            "data.metadata.creationTimestamp",
            "data.metadata.labels",
            "data.metadata.ownerReferences",
            "data.spec.jobTemplate.spec.template.spec.containers",
            "data.spec.template.spec.containers",
            "data.spec.schedule",
            "data.spec.suspend",
            "data.spec.completions",
            "data.spec.parallelism",
            "data.status",
        ]
        return ",".join(field)

    def perform_request(self, params):
        data = []
        bcs_cluster_id = params["bcs_cluster_id"]
        workload_type_list = params.get("workload_type_list")
        if not workload_type_list:
            workload_type_list = api.kubernetes.fetch_k8s_workload_type_list({"bcs_cluster_id": bcs_cluster_id})

        # 计算关联pod的资源情况
        pod_list = api.kubernetes.fetch_k8s_pod_list_by_cluster({"bcs_cluster_id": bcs_cluster_id})
        workload_resources_map = collections.defaultdict(
            lambda: {"requests_cpu": 0, "limits_cpu": 0, "requests_memory": 0, "limits_memory": 0, "pod_names": []}
        )
        for pod in pod_list:
            if not pod.get("workload_type"):
                continue
            pod_resource = workload_resources_map[
                (pod["workload_type"], pod["workload_name"], pod["namespace"], pod["bcs_cluster_id"])
            ]
            pod_resource["requests_cpu"] += pod.get("requests_cpu", 0)
            pod_resource["limits_cpu"] += pod.get("limits_cpu", 0)
            pod_resource["requests_memory"] += pod.get("requests_memory", 0)
            pod_resource["limits_memory"] += pod.get("limits_memory", 0)
            pod_resource["pod_names"].append(pod["name"])

        workload_field = self.get_workload_field()
        for workload_type in workload_type_list:
            items = api.bcs_storage.fetch(
                {"cluster_id": bcs_cluster_id, "type": workload_type, "field": workload_field}
            )
            for workload in items:
                workload_specification = KubernetesWorkloadJsonParser(workload)
                workload_specification.kind = workload_type
                # 获得容器配置
                workload_name = workload_specification.name
                workload_namespace = workload_specification.namespace
                # 容器的数量
                container_number = workload_specification.container_count
                # 标签
                workload_labels = workload_specification.labels
                label_list = workload_specification.label_list

                image_list = workload_specification.image_list
                creation_timestamp = workload_specification.creation_timestamp
                age = workload_specification.age

                workload_status = workload_specification.workload_status
                top_workload_type = workload_specification.top_workload_type

                workload_resource = workload_resources_map[
                    (workload_type, workload_name, workload_namespace, bcs_cluster_id)
                ]
                # 忽略中间的workload
                item = {
                    "bcs_cluster_id": bcs_cluster_id,
                    "workload_type": workload_type,
                    "top_workload_type": top_workload_type,
                    "workload_name": workload_name,
                    "workload_labels": workload_labels,
                    "name": workload_name,
                    "requests_cpu": workload_resource["requests_cpu"],
                    "limits_cpu": workload_resource["limits_cpu"],
                    "requests_memory": workload_resource["requests_memory"],
                    "limits_memory": workload_resource["limits_memory"],
                    "resources": [
                        {
                            "key": "requests.cpu",
                            "value": workload_resource["requests_cpu"],
                        },
                        {
                            "key": "limits.cpu",
                            "value": workload_resource["limits_cpu"],
                        },
                        {
                            "key": "requests.memory",
                            "value": get_bytes_unit_human_readable(workload_resource["requests_memory"]),
                        },
                        {
                            "key": "limits.memory",
                            "value": get_bytes_unit_human_readable(workload_resource["limits_memory"]),
                        },
                    ],
                    "namespace": workload_namespace,
                    "images": "\n".join(image_list),
                    "label_list": label_list,
                    "labels": workload_labels,
                    "pod_count": len(workload_resource["pod_names"]),
                    "container_number": container_number,
                    "pod_name": workload_resource["pod_names"],
                    "created_at": creation_timestamp,
                    "age": age,
                }
                item.update(workload_status)
                data.append(item)

        return data


class FetchK8sEventListResource(CacheResource):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.space_associated_clusters = {}

    class RequestSerializer(serializers.Serializer):
        start_time = serializers.CharField(required=True, label="start_time")
        end_time = serializers.CharField(required=True, label="end_time")
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="集群ID")
        namespace = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="namespace")
        kind = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="kind")
        name = serializers.CharField(required=False, allow_null=True, allow_blank=True, label="name")
        data_type = serializers.ChoiceField(default="list", choices=("list", "chart"))
        limit = serializers.IntegerField(default=10)
        offset = serializers.IntegerField(default=0)

        class ViewOptionsSerializer(serializers.Serializer):
            filters = serializers.DictField(required=False, allow_null=True)

        view_options = ViewOptionsSerializer(required=False, allow_null=True)

    def get_cluster_info_list(self, params: dict) -> list:
        """获得集群接入注册信息 ."""
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")

        filter_q = Q(bk_biz_id=bk_biz_id)
        if bk_biz_id < 0 and self.space_associated_clusters:
            # 获得容器空间关联的集群
            shared_q_list = []
            for cluster_id, value in self.space_associated_clusters.items():
                cluster_type = value["cluster_type"]
                namespace_list = value["namespace_list"]
                if cluster_type == BcsClusterType.SHARED and namespace_list:
                    shared_q_list.append(Q(bcs_cluster_id=cluster_id))
            if shared_q_list:
                filter_q = reduce(operator.or_, shared_q_list)

        if bcs_cluster_id:
            filter_q &= Q(bcs_cluster_id=bcs_cluster_id)
        cluster_instances = BCSCluster.objects.filter(filter_q)
        cluster_id_list = [instance.bcs_cluster_id for instance in cluster_instances]
        if cluster_id_list:
            cluster_info_list = models.BCSClusterInfo.objects.filter(
                cluster_id__in=cluster_id_list, status=models.BCSClusterInfo.CLUSTER_STATUS_RUNNING
            )
        else:
            cluster_info_list = []
        return cluster_info_list

    def get_data_source_result_list(self, params: dict) -> tuple:
        """获得集群的事件数据源Id ."""
        cluster_info_list = self.get_cluster_info_list(params)
        data_id_to_cluster_id = {
            cluster_info.K8sEventDataID: cluster_info.cluster_id for cluster_info in cluster_info_list
        }
        data_id_list = list(data_id_to_cluster_id.keys())
        if data_id_list:
            data_source_result_list = models.DataSourceResultTable.objects.filter(bk_data_id__in=data_id_list)
        else:
            data_source_result_list = []
        return data_source_result_list, data_id_to_cluster_id

    def get_match_list(self, params: dict, bcs_cluster_id: str, start_time: int, end_time: int) -> list:
        match_list = [{"range": {"time": {"gte": start_time, "lte": end_time}}}]
        keys = ["kind", "name", "namespace"]
        for key in keys:
            value = params.get(key)
            if value:
                if value.startswith("$"):
                    value = params.get("view_options", {}).get("filters", {}).get(value[1:])
                match_list.append({"match": {f"dimensions.{key}": value}})

        # 共享集群需要根据namespace过滤
        namespace_list = self.space_associated_clusters.get(bcs_cluster_id, {}).get("namespace_list")
        if namespace_list:
            match_list.append({"terms": {"dimensions.namespace": namespace_list}})
        if params.get("data_type") == "chart":
            match_list.append(
                {"range": {"time": {"gte": int(params["start_time"]) * 1000, "lt": int(params["end_time"]) * 1000}}}
            )
        return match_list

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        if bk_biz_id < 0:
            self.space_associated_clusters = GetClusterInfoFromBcsSpaceResource()({"bk_biz_id": bk_biz_id})

        # 获得es集群的存储地址
        es_storage_list, table_id_to_cluster_id = self.get_es_storage_list(params)

        data = []
        start_time = int(params["start_time"]) * 1000
        end_time = int(params["end_time"]) * 1000
        duration = end_time - start_time
        calendar_interval = "minute"
        offset = params.get("offset")
        limit = params.get("limit")
        if duration > 2 * 60 * 60 * 1000:
            calendar_interval = "hour"
        if duration > 2 * 24 * 60 * 60 * 1000:
            calendar_interval = "day"

        data_type = params.get("data_type")

        for es_storage in es_storage_list:
            table_id = es_storage.table_id
            bcs_cluster_id = table_id_to_cluster_id.get(table_id)
            if not bcs_cluster_id:
                continue
            # 构造es查询条件
            match_list = self.get_match_list(params, bcs_cluster_id, start_time, end_time)
            client = es_storage.get_client()
            indices = client.indices.get(index="*" + es_storage.index_name + "*").keys()
            body = {
                "size": offset + limit,
                "sort": [{"time": {"order": "desc"}}],
                "query": {"bool": {"must": match_list}},
            }
            if data_type == "chart":
                body["size"] = 0
                body["aggs"] = {
                    "kind": {
                        "terms": {"field": "dimensions.kind", "size": 10},
                        "aggs": {
                            "date_histogram": {
                                "date_histogram": {
                                    "field": "time",
                                    "calendar_interval": calendar_interval,
                                    "min_doc_count": 0,
                                    "time_zone": "+08:00",
                                    "extended_bounds": {"min": start_time, "max": end_time},
                                    "format": "yyyy-MM-dd HH:mm:ss",
                                },
                                "aggs": {"sum_number": {"sum": {"field": "event.count"}}},
                            }
                        },
                    }
                }
            es_data = client.search(index=",".join(indices), body=body, timeout="30s")

            if data_type == "chart":
                if "aggregations" not in es_data:
                    continue
                for kind_bucket in es_data["aggregations"]["kind"]["buckets"]:
                    kind = kind_bucket["key"] if kind_bucket["key"] else "未归类"
                    series_item = {
                        "alias": "_result_",
                        "metric_field": "_result_",
                        "dimensions": {
                            "kind": kind,
                        },
                        "target": "SUM(event){kind=" + kind + "}",
                        "datapoints": [],
                        "stack": "all",
                        "type": "bar",
                    }
                    for date_histogram_bucket in kind_bucket["date_histogram"]["buckets"]:
                        series_item["datapoints"].append(
                            [
                                date_histogram_bucket["sum_number"]["value"],
                                date_histogram_bucket["key"],
                            ],
                        )
                    data.append(series_item)
            else:
                data = {"total": es_data["hits"]["total"]["value"], "list": es_data["hits"]["hits"][offset:]}
        return data

    def get_es_storage_list(self, params: dict) -> tuple:
        data_source_result_list, data_id_to_cluster_id = self.get_data_source_result_list(params)
        table_id_map = {
            data_source_result.table_id: data_source_result.bk_data_id for data_source_result in data_source_result_list
        }
        table_id_list = list(table_id_map.keys())
        # 获得table_id和集群Id的关系
        table_id_to_cluster_id = {
            table_id: data_id_to_cluster_id.get(bk_data_id) for table_id, bk_data_id in table_id_map.items()
        }
        if table_id_list:
            es_storage_list = models.ESStorage.objects.filter(table_id__in=table_id_list)
        else:
            es_storage_list = []
        return es_storage_list, table_id_to_cluster_id


class FetchContainerUsage(Resource):
    """获得容器资源使用量 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        usage_type = serializers.ChoiceField(choices=("cpu", "memory", "disk"))
        bcs_cluster_id = serializers.CharField()
        namespace = serializers.CharField(required=False, allow_null=True)
        pod_name = serializers.ListField(required=False, allow_empty=True, allow_null=True)
        container_name = serializers.ListField(required=False, allow_empty=True, allow_null=True)
        group_by = serializers.ListField(required=False, allow_empty=True, allow_null=True)

    @classmethod
    def get_data(cls, params):
        usage_type = params.get("usage_type")
        bcs_cluster_id = params.get("bcs_cluster_id")
        namespace = params.get("namespace")
        pod_name = params.get("pod_name")
        container_name = params.get("container_name")
        group_by = params.get("group_by", [])
        bk_biz_id = params["bk_biz_id"]

        data_sources = []
        response = {
            "usage_type": f"{usage_type}",
        }
        # 时间区间：[-2分钟，-1分钟]
        end_time = int(params.get("end_time", (time.time() - 60)) * 1000)
        start_time = int(params.get("start_time", (time.time() - 120)) * 1000)
        where = [
            {"key": "bcs_cluster_id", "method": "eq", "value": bcs_cluster_id},
        ]
        if pod_name:
            where.append({"key": "pod_name", "method": "eq", "value": pod_name})
        if namespace:
            where.append({"key": "namespace", "method": "eq", "value": namespace})
        if container_name:
            where.append({"key": "container_name", "method": "eq", "value": container_name})

        if usage_type == "cpu":
            if not container_name:
                where.append({"key": "container_name", "method": "neq", "value": "POD"})
            data_sources.append(
                load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
                    bk_biz_id=bk_biz_id,
                    table="",
                    metrics=[{"field": "container_cpu_usage_seconds_total", "method": "SUM", "alias": "A"}],
                    interval=60,
                    group_by=group_by,
                    functions=[{"id": "rate", "params": [{"id": "window", "value": "4m"}]}],
                    where=where,
                )
            )
        elif usage_type == "memory":
            if not container_name:
                where.append({"key": "container_name", "method": "neq", "value": "POD"})
            data_sources.append(
                load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
                    bk_biz_id=bk_biz_id,
                    table="",
                    metrics=[{"field": "container_memory_working_set_bytes", "method": "SUM", "alias": "A"}],
                    interval=60,
                    group_by=group_by,
                    where=where,
                )
            )
        elif usage_type == "disk":
            data_sources.append(
                load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)(
                    bk_biz_id=bk_biz_id,
                    table="",
                    metrics=[{"field": "container_fs_usage_bytes", "method": "SUM", "alias": "A"}],
                    interval=60,
                    group_by=group_by,
                    where=where,
                )
            )
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A")
        records = query.query_data(start_time=start_time, end_time=end_time)
        response["data"] = records
        return response

    def perform_request(self, params):
        return self.get_data(params)


class FetchNodeCpuUsage(Resource):
    """获得指定集群节点的CPU使用率 ."""

    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.PROMETHEUS, DataTypeLabel.TIME_SERIES)

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True, label="集群ID")
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")

    def validate_request_data(self, request_data: dict) -> dict:
        bk_biz_id = int(request_data["bk_biz_id"])
        request_data["bk_biz_id"] = bk_biz_id
        start_time = request_data.get("start_time")
        end_time = request_data.get("end_time")
        if not start_time:
            end_time = int(time.time())
            start_time = int(time.time() - 3600)
        request_data["start_time"] = int(start_time) * 1000
        request_data["end_time"] = int(end_time) * 1000

        return request_data

    @staticmethod
    def build_promql(validated_request_data: dict) -> str:
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")
        promql = (
            "(1 - avg by(instance) "
            '(irate(node_cpu_seconds_total{mode="idle", '
            f'bcs_cluster_id="{bcs_cluster_id}"}}[5m])))'
        )

        return promql

    def request_graph_unify_query(self, validated_request_data) -> list:
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data["start_time"]
        end_time = validated_request_data["end_time"]
        promql = self.build_promql(validated_request_data)
        data_sources = [
            self.DATA_SOURCE_CLASS(bk_biz_id=bk_biz_id, promql=promql, interval=60),
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A")
        records = query.query_data(start_time=start_time, end_time=end_time)
        return records

    @staticmethod
    def format_performance_data(records: list) -> dict:
        """格式化数据 ."""
        data = {}
        if not records:
            return {}
        for item in records:
            instance = item.get("instance")
            if not instance:
                continue
            bk_target_ip = instance.rsplit(":")[0]
            value = item.get("_result_")
            data[bk_target_ip] = value

        return data

    def perform_request(self, validated_request_data: dict) -> dict:
        performance_data = self.request_graph_unify_query(validated_request_data)
        if not performance_data:
            return {}
        data = self.format_performance_data(performance_data)
        return data


class FetchUsageRatio(FetchKubernetesGrafanaMetricRecords):
    """集群或节点的资源使用率 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField()
        usage_type = serializers.ListField(child=serializers.ChoiceField(choices=("cpu", "memory", "disk")))
        bcs_cluster_id = serializers.CharField()
        start_time = serializers.IntegerField(required=False, label="start_time")
        end_time = serializers.IntegerField(required=False, label="end_time")

    @staticmethod
    def format_performance_data(performance_data):
        data = {}
        for key_name, records in performance_data:
            if not records:
                continue
            value = records[-1]["_result_"]
            data[key_name] = value
        return data

    def build_graph_unify_query_iterable(self, validated_request_data: dict) -> list:
        usage_type = validated_request_data["usage_type"]
        bk_biz_id = validated_request_data["bk_biz_id"]
        start_time = validated_request_data.get("start_time")
        end_time = validated_request_data.get("end_time")
        bcs_cluster_id = validated_request_data.get("bcs_cluster_id")

        args = []
        data_source_param_map = []

        if "cpu" in usage_type:
            promql = (
                f'(1 - avg (irate(node_cpu_seconds_total{{mode="idle", bcs_cluster_id="{bcs_cluster_id}"}}[5m]))) * 100'
            )
            data_source_param_map.append({"key_name": "cpu", "promql": promql})

        if "memory" in usage_type:
            promql = (
                "(SUM by(bcs_cluster_id)"
                f' (node_memory_MemTotal_bytes{{bcs_cluster_id="{bcs_cluster_id}"}})'
                " - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id)"
                f' (node_memory_MemFree_bytes{{bcs_cluster_id="{bcs_cluster_id}"}})'
                " - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) "
                f'(node_memory_Cached_bytes{{bcs_cluster_id="{bcs_cluster_id}"}})'
                " - on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) "
                f'(node_memory_Buffers_bytes{{bcs_cluster_id="{bcs_cluster_id}"}})'
                " + on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id) "
                f'(node_memory_Shmem_bytes{{bcs_cluster_id="{bcs_cluster_id}"}}))'
                " / on(bcs_cluster_id) group_right() SUM by(bcs_cluster_id)"
                f' (node_memory_MemTotal_bytes{{bcs_cluster_id="{bcs_cluster_id}"}}) * 100'
            )
            data_source_param_map.append({"key_name": "memory", "promql": promql})

        if "disk" in usage_type:
            promql = (
                "(sum by(bcs_cluster_id)"
                f' (node_filesystem_size_bytes{{bcs_cluster_id="{bcs_cluster_id}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"})'
                " - on(bcs_cluster_id) group_right()"
                " sum by(bcs_cluster_id)"
                f' (node_filesystem_free_bytes{{bcs_cluster_id="{bcs_cluster_id}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"}))'
                " / on(bcs_cluster_id) group_right()"
                " sum by(bcs_cluster_id)"
                f' (node_filesystem_size_bytes{{bcs_cluster_id="{bcs_cluster_id}",'
                'fstype=~"ext[234]|btrfs|xfs|zfs"})'
                " * 100"
            )
            data_source_param_map.append({"key_name": "disk", "promql": promql})

        for data_source_params in data_source_param_map:
            args.append(
                {
                    "bk_biz_id": bk_biz_id,
                    "bcs_cluster_id": bcs_cluster_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "data_source_params": data_source_params,
                }
            )

        return args


class FetchK8sBkmMetricbeatEndpointUpResource(CacheResource):
    """获得endpoints采集状态 ."""

    DATA_SOURCE_CLASS = load_data_source(DataSourceLabel.BK_MONITOR_COLLECTOR, DataTypeLabel.TIME_SERIES)

    class ResourceSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True)
        bcs_cluster_id = serializers.CharField(required=False)
        node_ip = serializers.CharField(required=False)
        monitor_type = serializers.CharField(required=False)
        namespace = serializers.CharField(required=False)
        service = serializers.CharField(required=False)
        bk_monitor_name = serializers.CharField(required=False)
        group_by = serializers.ListField(required=False, default=[])

    def validate_request_data(self, request_data: dict) -> dict:
        end_time = int(time.time())
        start_time = int(time.time() - 300)
        request_data["start_time"] = start_time * 1000
        request_data["end_time"] = end_time * 1000

        return request_data

    def request_unify_query(self, params):
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        start_time = params["start_time"]
        end_time = params["end_time"]

        node_ip = params.get("node_ip")
        monitor_type = params.get("monitor_type")
        namespace = params.get("namespace")
        service = params.get("service")
        bk_monitor_name = params.get("bk_monitor_name")

        where = []
        if bcs_cluster_id:
            where.append(
                {
                    "key": "bcs_cluster_id",
                    "method": "eq",
                    "value": bcs_cluster_id,
                }
            )
        if node_ip:
            where.append(
                {
                    "key": "instance",
                    "method": "reg",
                    "value": [f"^{node_ip}:"],
                }
            )
        if monitor_type:
            where.append({"key": "monitor_type", "method": "eq", "value": monitor_type})
        if namespace:
            where.append({"key": "namespace", "method": "eq", "value": namespace})
        if service:
            where.append({"key": "service", "method": "eq", "value": service})
        if bk_monitor_name:
            where.append({"key": "bk_monitor_name", "method": "eq", "value": bk_monitor_name})

        group_by = params.get("group_by", [])

        data_sources = [
            self.DATA_SOURCE_CLASS(
                bk_biz_id=bk_biz_id,
                table="",
                metrics=[{"field": BKM_METRICBEAT_ENDPOINT_UP, "method": "COUNT", "alias": "A"}],
                interval=60,
                group_by=group_by,
                functions=[],
                where=where,
            )
        ]
        query = UnifyQuery(bk_biz_id=bk_biz_id, data_sources=data_sources, expression="A")
        records = query.query_data(start_time=start_time, end_time=end_time)

        return records

    @staticmethod
    def format_data(validated_request_data: dict, unify_query_result: list) -> dict:
        group_by = validated_request_data.get("group_by", [])
        data = {}
        for record in unify_query_result:
            key = [record.get(group) for group in group_by if record.get(group)]
            value = record["_result_"]
            data[tuple(key)] = value

        return data

    def perform_request(self, validated_request_data: dict) -> list:
        unify_query_result = self.request_unify_query(validated_request_data)
        result = self.format_data(validated_request_data, unify_query_result)

        return result


class FetchMetricsDefine(Resource):
    data_file_path = os.path.dirname(os.path.abspath(__file__))

    @classmethod
    def load(cls):
        """
        读取内置视图配置文件
        """
        file_path = os.path.join(cls.data_file_path, "kubernetes_metrics_define.json")
        with open(file_path, encoding="utf8") as f:
            return json.loads(f.read())

    def perform_request(self, params):
        return self.load()


class FetchResourceCount(Resource):
    class RequestSerializer(serializers.Serializer):
        resource_type = serializers.CharField(required=True, label="resource_type")
        bk_biz_id = serializers.IntegerField(required=True)
        bcs_cluster_id = serializers.CharField(required=False, allow_null=True)

    @staticmethod
    def is_shared_cluster(bcs_cluster_id: str, cluster_info: dict) -> bool:
        return bool(cluster_info.get(bcs_cluster_id))

    def perform_request(self, params):
        bk_biz_id = params["bk_biz_id"]
        resource_type = params["resource_type"]
        bcs_cluster_id = params.get("bcs_cluster_id")
        resources = {
            "cluster": BCSCluster,
            "pod": BCSPod,
            "work_node": BCSNode,
            "node": BCSNode,
            "master_node": BCSNode,
            "service": BCSService,
            "workload": BCSWorkload,
            "container": BCSContainer,
            "service_monitor": BCSServiceMonitor,
            "pod_monitor": BCSPodMonitor,
        }

        resource_cls = resources.get(resource_type)
        if resource_cls:
            try:
                qs = resource_cls.objects.filter_by_biz_id(bk_biz_id)
            except EmptyResultSet:
                return 0
            if bcs_cluster_id:
                qs = qs.filter(bcs_cluster_id=bcs_cluster_id)
            if resource_type == "master_node":
                # master节点过滤
                qs = qs.filter(Q(roles__contains="control-plane") | Q(roles__contains="master"))
            elif resource_type == "work_node":
                # 非master节点过滤
                qs = qs.exclude(Q(roles__contains="control-plane") | Q(roles__contains="master"))
            count = qs.count()
            return count
        else:
            caller = getattr(api.kubernetes, f"fetch_k8s_{resource_type}_list", None)
        if not caller:
            return 0
        return len(caller(params))


class FetchBCSClusterAlertEnabledIDList(Resource):
    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")

    def perform_request(self, params):
        # 获取空间关联的集群id列表，基于集群id列表，再过滤alert_status
        bk_biz_id = params["bk_biz_id"]
        cluster_ids = list(GetClusterInfoFromBcsSpaceResource()(bk_biz_id=bk_biz_id).keys())
        data = BCSCluster.objects.filter(bcs_cluster_id__in=cluster_ids, alert_status="enabled").values(
            "bcs_cluster_id"
        )
        return [item["bcs_cluster_id"] for item in data]


class FetchKubernetesConsistencyCheckResource(Resource, abc.ABC):
    IGNORE_NAMESPACE_SET = {
        "kube-system",
    }

    IGNORE_NAME_SET = {"kubernetes"}

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(required=True, label="业务ID")
        bcs_cluster_id = serializers.CharField(required=True)
        data_type = serializers.ChoiceField(choices=("simple", "full"), default="simple")
        name = serializers.CharField(required=False, allow_null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.shared_namespace_set = {}

    def get_cluster(self, params):
        # 获得业务关联的集群
        bk_biz_id = params["bk_biz_id"]
        bcs_cluster_id = params["bcs_cluster_id"]
        if bk_biz_id < 0:
            clusters = GetClusterInfoFromBcsSpaceResource()({"bk_biz_id": bk_biz_id})
            if bcs_cluster_id not in clusters:
                return None
            # 如果是共享集群，获得有权限的NameSpace
            cluster_info = clusters.get(bcs_cluster_id, {})
            if cluster_info.get("cluster_type") == BcsClusterType.SHARED:
                self.shared_namespace_set = set(cluster_info.get("namespace_list"))
        # 判断集群是否存在
        try:
            cluster_model = BCSCluster.objects.get(bcs_cluster_id=bcs_cluster_id)
        except BCSCluster.DoesNotExist:
            return None
        return cluster_model

    @abc.abstractmethod
    def fetch_from_bk_storages(self, params, *args, **kwargs): ...

    @abc.abstractmethod
    def fetch_from_api_server(self, params, *args, **kwargs): ...

    @abc.abstractmethod
    def fetch_from_db(self, params, *args, **kwargs): ...

    @classmethod
    @abc.abstractmethod
    def compare_third_part(cls, params, bcs_storage, api_server, local_db): ...

    @classmethod
    def get_fetch_kwargs(cls, params, cluster_model):
        fetch_kwargs = {
            "cluster_model": cluster_model,
        }
        return fetch_kwargs

    def can_ignore_namespace(self, namespace):
        """如果是共享集群，忽略不属于这个集群的namespace ."""
        if namespace in self.IGNORE_NAMESPACE_SET:
            return True
        if self.shared_namespace_set and namespace not in self.shared_namespace_set:
            return True
        return False

    def perform_request(self, params):
        cluster_model = self.get_cluster(params)
        if not cluster_model:
            return {}

        fetch_kwargs = self.get_fetch_kwargs(params, cluster_model)

        # 从bkstorages获取
        bcs_storage = self.fetch_from_bk_storages(params, **fetch_kwargs)
        # 从api server获取
        api_server = self.fetch_from_api_server(params, **fetch_kwargs)
        # 从数据库获取
        local_db = self.fetch_from_db(params, **fetch_kwargs)
        # 比较三方数据
        data = self.compare_third_part(params, bcs_storage, api_server, local_db)

        return data


class FetchKubernetesWorkloadConsistencyCheckResource(FetchKubernetesConsistencyCheckResource):
    """BCS workload资源同步校验 ."""

    def fetch_from_bk_storages(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        workload_type_list = kwargs["workload_type_list"]

        bcs_storage_workload = {}
        for workload_type in workload_type_list:
            items = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": workload_type})
            for workload in items:
                parser = KubernetesWorkloadJsonParser(workload)
                parser.kind = workload_type
                workload_name = parser.name
                if name and name != workload_name:
                    continue
                if self.can_ignore_namespace(parser.namespace):
                    continue
                bcs_storage_workload.setdefault(workload_type, []).append(
                    {
                        "name": workload_name,
                        "namespace": parser.namespace,
                        "resource_version": parser.resource_version,
                        "status": parser.service_status,
                    }
                )
        return bcs_storage_workload

    def fetch_from_api_server(self, params, *args, **kwargs):
        name = params.get("name")
        workload_type_list = kwargs["workload_type_list"]
        cluster_model = kwargs["cluster_model"]

        api_server_workload = {}
        apps_v1_api = cluster_model.apps_v1_api
        batch_v1_api = cluster_model.batch_v1_api
        batch_v1_beta1_api = cluster_model.batch_v1_beta1_api
        for workload_type in workload_type_list:
            workload_object = None
            if workload_type == "Deployment":
                workload_object = apps_v1_api.list_deployment_for_all_namespaces()
            elif workload_type == "DaemonSet":
                workload_object = apps_v1_api.list_daemon_set_for_all_namespaces()
            elif workload_type == "StatefulSet":
                workload_object = apps_v1_api.list_stateful_set_for_all_namespaces()
            elif workload_type == "Job":
                workload_object = batch_v1_api.list_job_for_all_namespaces()
            elif workload_type == "CronJob":
                workload_object = batch_v1_beta1_api.list_cron_job_for_all_namespaces()
            if workload_object:
                workload_object_items = workload_object.items
                for workload_item in workload_object_items:
                    workload_item_dict = workload_item.to_dict()
                    parser = KubernetesWorkloadJsonParser(workload_item_dict)
                    parser.kind = workload_type
                    workload_name = parser.name
                    if name and name != workload_name:
                        continue
                    if self.can_ignore_namespace(parser.namespace):
                        continue
                    api_server_workload.setdefault(workload_type, []).append(
                        {
                            "name": workload_name,
                            "namespace": parser.namespace,
                            "resource_version": parser.resource_version,
                            "status": parser.service_status,
                        }
                    )
        return api_server_workload

    def fetch_from_db(self, params, *args, **kwargs):
        bcs_cluster_id = params.get("bcs_cluster_id")
        name = params.get("name")
        workload_models = BCSWorkload.objects.filter(bcs_cluster_id=bcs_cluster_id)
        local_db_workload = {}
        for workload_model in workload_models:
            workload_type = workload_model.type
            workload_name = workload_model.name
            if name and name != workload_name:
                continue
            if self.can_ignore_namespace(workload_model.namespace):
                continue
            local_db_workload.setdefault(workload_type, []).append(
                {
                    "name": workload_name,
                    "namespace": workload_model.namespace,
                    "status": workload_model.status,
                }
            )
        return local_db_workload

    @classmethod
    def compare_third_part(cls, params, bcs_storage_workload, api_server_workload, local_db_workload):
        data_type = params["data_type"]
        compare_data = {}

        bcs_storage_workload_total = 0
        bcs_storage_workload_data = {}
        for workload_type, value in bcs_storage_workload.items():
            count = len(value)
            bcs_storage_workload_total += count
            bcs_storage_workload_data[workload_type] = {
                "count": count,
                "data": value,
            }
            for item in value:
                name = item["name"]
                compare_data.setdefault(workload_type, {}).setdefault(name, {})["bcs_storage"] = item

        api_server_workload_total = 0
        api_server_workload_data = {}
        for workload_type, value in api_server_workload.items():
            count = len(value)
            api_server_workload_total += count
            api_server_workload_data[workload_type] = {
                "count": count,
                "data": value,
            }
            for item in value:
                name = item["name"]
                compare_data.setdefault(workload_type, {}).setdefault(name, {})["api_server"] = item

        local_db_workload_total = 0
        local_db_workload_data = {}
        for workload_type, value in local_db_workload.items():
            count = len(value)
            local_db_workload_total += count
            local_db_workload_data[workload_type] = {
                "count": count,
                "data": value,
            }
            for item in value:
                name = item["name"]
                compare_data.setdefault(workload_type, {}).setdefault(name, {})["local_db"] = item

        # 如果name在3个数据源中至少有一个不存在，则放到diff中
        diff_data = {}
        for workload_type, value in compare_data.items():
            for name, value2 in value.items():
                if len(value2) != 3:
                    diff_data.setdefault(workload_type, {})[name] = value2

        if data_type == "simple":
            data = {
                "diff": diff_data,
            }
        else:
            data = {
                "bcs_storage": {
                    "total": bcs_storage_workload_total,
                    "data": bcs_storage_workload_data,
                },
                "api_server": {
                    "total": api_server_workload_total,
                    "data": api_server_workload_data,
                },
                "local_db": {
                    "total": local_db_workload_total,
                    "data": local_db_workload_data,
                },
                "diff": diff_data,
            }
        return data

    @classmethod
    def get_fetch_kwargs(cls, params, cluster_model):
        bcs_cluster_id = params["bcs_cluster_id"]
        workload_type_list = api.kubernetes.fetch_k8s_workload_type_list({"bcs_cluster_id": bcs_cluster_id})
        fetch_kwargs = {
            "cluster_model": cluster_model,
            "workload_type_list": workload_type_list,
        }
        return fetch_kwargs


class FetchKubernetesPodConsistencyCheckResource(FetchKubernetesConsistencyCheckResource):
    """BCS Pod资源同步校验 ."""

    def fetch_from_bk_storages(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        bcs_storage_pod_list = []
        pod_items = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Pod"})
        for pod in pod_items:
            parser = KubernetesPodJsonParser(pod)
            pod_name = parser.name
            if name and name != pod_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            bcs_storage_pod_list.append(
                {
                    "name": pod_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "status": parser.service_status,
                }
            )
        return bcs_storage_pod_list

    def fetch_from_api_server(self, params, *args, **kwargs):
        name = params.get("name")
        cluster_model = kwargs["cluster_model"]
        api_server_pod_list = []
        api_client = cluster_model.core_v1_api
        pod_object = api_client.list_pod_for_all_namespaces()
        pod_object_items = pod_object.items
        for pod_item in pod_object_items:
            pod_item_dict = pod_item.to_dict()
            parser = KubernetesPodJsonParser(pod_item_dict)
            pod_name = parser.name
            if name and name != pod_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            api_server_pod_list.append(
                {
                    "name": pod_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "status": parser.service_status,
                }
            )
        return api_server_pod_list

    def fetch_from_db(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        pod_models = BCSPod.objects.filter(bcs_cluster_id=bcs_cluster_id)
        local_db_pod_list = []
        for pod_model in pod_models:
            pod_name = pod_model.name
            if name and name != pod_name:
                continue
            if self.can_ignore_namespace(pod_model.namespace):
                continue
            local_db_pod_list.append(
                {
                    "name": pod_name,
                    "namespace": pod_model.namespace,
                    "status": pod_model.status,
                }
            )
        return local_db_pod_list

    @classmethod
    def compare_third_part(cls, params, bcs_storage_pod_list, api_server_pod_list, local_db_pod_list):
        data_type = params["data_type"]
        compare_data = {}

        bcs_storage_pod_total = len(bcs_storage_pod_list)
        for pod_item in bcs_storage_pod_list:
            name = pod_item["name"]
            compare_data.setdefault(name, {})["bcs_storage"] = pod_item

        api_server_pod_total = len(api_server_pod_list)
        for pod_item in api_server_pod_list:
            name = pod_item["name"]
            compare_data.setdefault(name, {})["api_server"] = pod_item

        local_db_pod_total = len(local_db_pod_list)
        for pod_item in local_db_pod_list:
            name = pod_item["name"]
            compare_data.setdefault(name, {})["local_db"] = pod_item

        # 如果name在3个数据源中至少有一个不存在，则放到diff中
        diff_data = {}
        for name, value in compare_data.items():
            if len(value) != 3:
                diff_data[name] = value

        if data_type == "simple":
            data = {
                "diff": diff_data,
            }
        else:
            data = {
                "bcs_storage": {
                    "total": bcs_storage_pod_total,
                    "data": bcs_storage_pod_list,
                },
                "api_server": {
                    "total": api_server_pod_total,
                    "data": api_server_pod_list,
                },
                "local_db": {
                    "total": local_db_pod_total,
                    "data": local_db_pod_list,
                },
                "diff": diff_data,
            }
        return data


class FetchKubernetesNodeConsistencyCheckResource(FetchKubernetesConsistencyCheckResource):
    """BCS Node资源同步校验 ."""

    def fetch_from_bk_storages(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        bcs_storage_node_list = []
        node_items = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Node"})
        for node in node_items:
            node_parser = KubernetesNodeJsonParser(node)
            node_name = node_parser.name
            if name and name != node_name:
                continue
            bcs_storage_node_list.append(
                {
                    "name": node_name,
                    "ip": node_parser.node_ip,
                    "status": node_parser.service_status,
                }
            )
        return bcs_storage_node_list

    def fetch_from_api_server(self, params, *args, **kwargs):
        name = params.get("name")
        cluster_model = kwargs["cluster_model"]

        api_server_node_list = []
        api_client = cluster_model.core_v1_api
        node_object = api_client.list_node()
        node_object_items = node_object.items
        for node_item in node_object_items:
            node_item_dict = node_item.to_dict()
            node_parser = KubernetesNodeJsonParser(node_item_dict)
            node_name = node_parser.name
            if name and name != node_name:
                continue
            api_server_node_list.append(
                {
                    "name": node_name,
                    "ip": node_parser.node_ip,
                    "status": node_parser.service_status,
                }
            )
        return api_server_node_list

    def fetch_from_db(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")

        node_models = BCSNode.objects.filter(bcs_cluster_id=bcs_cluster_id)
        local_db_node_list = []
        for node_model in node_models:
            node_name = node_model.name
            if name and name != node_name:
                continue
            local_db_node_list.append(
                {
                    "name": node_name,
                    "ip": node_model.ip,
                    "status": node_model.status,
                }
            )
        return local_db_node_list

    @classmethod
    def compare_third_part(cls, params, bcs_storage_node_list, api_server_node_list, local_db_node_list):
        data_type = params["data_type"]
        compare_data = {}

        bcs_storage_node_total = len(bcs_storage_node_list)
        for node_item in bcs_storage_node_list:
            name = node_item["name"]
            compare_data.setdefault(name, {})["bcs_storage"] = node_item

        api_server_node_total = len(api_server_node_list)
        for node_item in api_server_node_list:
            name = node_item["name"]
            compare_data.setdefault(name, {})["api_server"] = node_item

        local_db_workload_total = len(local_db_node_list)
        for node_item in local_db_node_list:
            name = node_item["name"]
            compare_data.setdefault(name, {})["local_db"] = node_item

        # 如果name在3个数据源中至少有一个不存在，则放到diff中
        diff_data = {}
        for name, value in compare_data.items():
            if len(value) != 3:
                diff_data[name] = value

        if data_type == "simple":
            data = {
                "diff": diff_data,
            }
        else:
            data = {
                "bcs_storage": {
                    "total": bcs_storage_node_total,
                    "data": bcs_storage_node_list,
                },
                "api_server": {
                    "total": api_server_node_total,
                    "data": api_server_node_list,
                },
                "local_db": {
                    "total": local_db_workload_total,
                    "data": local_db_node_list,
                },
                "diff": diff_data,
            }
        return data


class FetchKubernetesServiceConsistencyCheckResource(FetchKubernetesConsistencyCheckResource):
    """BCS Service资源同步校验 ."""

    def fetch_from_bk_storages(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        bcs_storage_service_list = []
        service_items = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Service"})
        for service in service_items:
            parser = KubernetesServiceJsonParser(service)
            service_name = parser.name
            if name and name != service_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            bcs_storage_service_list.append(
                {
                    "name": service_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "type": parser.service_type,
                    "cluster_ip": parser.cluster_ip,
                    "external_ip": parser.external_ip,
                }
            )
        return bcs_storage_service_list

    def fetch_from_api_server(self, params, *args, **kwargs):
        name = params.get("name")
        cluster_model = kwargs["cluster_model"]

        api_server_service_list = []
        api_client = cluster_model.core_v1_api
        service_object = api_client.list_service_for_all_namespaces()
        service_object_items = service_object.items
        for service_object in service_object_items:
            service_item_dict = service_object.to_dict()
            parser = KubernetesServiceJsonParser(service_item_dict)
            service_name = parser.name
            if service_name in self.IGNORE_NAME_SET:
                continue
            if name and name != service_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            api_server_service_list.append(
                {
                    "name": service_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "type": parser.service_type,
                    "cluster_ip": parser.cluster_ip,
                    "external_ip": parser.external_ip,
                }
            )
        return api_server_service_list

    def fetch_from_db(self, params, *args, **kwargs):
        name = params.get("name")
        bcs_cluster_id = params["bcs_cluster_id"]
        service_models = BCSService.objects.filter(bcs_cluster_id=bcs_cluster_id)
        local_db_service_list = []
        for service_model in service_models:
            service_name = service_model.name
            if name and name != service_name:
                continue
            if self.can_ignore_namespace(service_model.namespace):
                continue
            local_db_service_list.append(
                {
                    "name": service_name,
                    "namespace": service_model.namespace,
                    "type": service_model.type,
                    "cluster_ip": service_model.cluster_ip,
                    "external_ip": service_model.external_ip,
                }
            )
        return local_db_service_list

    @classmethod
    def compare_third_part(cls, params, bcs_storage_service_list, api_server_service_list, local_db_service_list):
        data_type = params["data_type"]
        compare_data = {}

        bcs_storage_service_total = len(bcs_storage_service_list)
        for service_item in bcs_storage_service_list:
            name = service_item["name"]
            compare_data.setdefault(name, {})["bcs_storage"] = service_item

        api_server_service_total = len(api_server_service_list)
        for service_item in api_server_service_list:
            name = service_item["name"]
            compare_data.setdefault(name, {})["api_server"] = service_item

        local_db_service_total = len(local_db_service_list)
        for service_item in local_db_service_list:
            name = service_item["name"]
            compare_data.setdefault(name, {})["local_db"] = service_item

        # 如果name在3个数据源中至少有一个不存在，则放到diff中
        diff_data = {}
        for name, value in compare_data.items():
            if len(value) != 3:
                diff_data[name] = value

        if data_type == "simple":
            data = {
                "diff": diff_data,
            }
        else:
            data = {
                "bcs_storage": {
                    "total": bcs_storage_service_total,
                    "data": bcs_storage_service_list,
                },
                "api_server": {
                    "total": api_server_service_total,
                    "data": api_server_service_list,
                },
                "local_db": {
                    "total": local_db_service_total,
                    "data": local_db_service_list,
                },
                "diff": diff_data,
            }
        return data


class FetchKubernetesEndpointConsistencyCheckResource(FetchKubernetesConsistencyCheckResource):
    """BCS Endpoints资源同步校验 ."""

    def fetch_from_bk_storages(self, params, *args, **kwargs):
        bcs_cluster_id = params["bcs_cluster_id"]
        name = params.get("name")
        bcs_storage_endpoint_list = []
        endpoints_items = api.bcs_storage.fetch({"cluster_id": bcs_cluster_id, "type": "Endpoints"})
        for endpoint in endpoints_items:
            parser = KubernetesEndpointJsonParser(endpoint)
            if parser.namespace in self.IGNORE_NAMESPACE_SET:
                continue
            endpoint_name = parser.name
            if name and name != endpoint_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            bcs_storage_endpoint_list.append(
                {
                    "name": endpoint_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "subsets": parser.subsets,
                }
            )
        return bcs_storage_endpoint_list

    def fetch_from_api_server(self, params, *args, **kwargs):
        name = params.get("name")
        cluster_model = kwargs["cluster_model"]
        api_server_endpoint_list = []
        api_client = cluster_model.core_v1_api
        endpoint_object = api_client.list_endpoints_for_all_namespaces()
        endpoint_object_items = endpoint_object.items
        for endpoint_object in endpoint_object_items:
            endpoint_item_dict = endpoint_object.to_dict()
            parser = KubernetesEndpointJsonParser(endpoint_item_dict)
            if parser.namespace in self.IGNORE_NAMESPACE_SET:
                continue
            endpoint_name = parser.name
            if endpoint_name in self.IGNORE_NAME_SET:
                continue
            if name and name != endpoint_name:
                continue
            if self.can_ignore_namespace(parser.namespace):
                continue
            api_server_endpoint_list.append(
                {
                    "name": endpoint_name,
                    "namespace": parser.namespace,
                    "resource_version": parser.resource_version,
                    "subsets": parser.subsets,
                }
            )
        return api_server_endpoint_list

    @classmethod
    def fetch_from_db(cls, params, *args, **kwargs):
        return []

    @classmethod
    def compare_third_part(cls, params, bcs_storage_endpoint_list, api_server_endpoint_list, local_db):
        data_type = params["data_type"]
        compare_data = {}

        bcs_storage_service_total = len(bcs_storage_endpoint_list)
        for service_item in bcs_storage_endpoint_list:
            name = service_item["name"]
            compare_data.setdefault(name, {})["bcs_storage"] = service_item

        api_server_service_total = len(api_server_endpoint_list)
        for service_item in api_server_endpoint_list:
            name = service_item["name"]
            compare_data.setdefault(name, {})["api_server"] = service_item

        # 如果name在3个数据源中至少有一个不存在，则放到diff中
        diff_data = {}
        for name, value in compare_data.items():
            if len(value) != 2:
                diff_data[name] = value

        if data_type == "simple":
            data = {
                "diff": diff_data,
            }
        else:
            data = {
                "bcs_storage": {
                    "total": bcs_storage_service_total,
                    "data": bcs_storage_endpoint_list,
                },
                "api_server": {
                    "total": api_server_service_total,
                    "data": api_server_endpoint_list,
                },
                "diff": diff_data,
            }
        return data


class FetchK8sCloudIdByClusterResource(CacheResource):
    """获得集群的云区域ID ."""

    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_ids = serializers.ListField(label="集群ID", child=serializers.CharField(), required=False)

    def perform_request(self, params):
        filter_kwargs = {}
        bcs_cluster_ids = params.get("bcs_cluster_ids")
        if bcs_cluster_ids:
            filter_kwargs["cluster_id__in"] = bcs_cluster_ids
        filter_kwargs.update({"status": models.BCSClusterInfo.CLUSTER_STATUS_RUNNING})
        cluster_models = models.BCSClusterInfo.objects.filter(**filter_kwargs)
        data = []
        for cluster_model in cluster_models:
            cluster_id = cluster_model.cluster_id
            bk_cloud_id = cluster_model.bk_cloud_id
            bk_cloud_id = 0 if bk_cloud_id is None else bk_cloud_id
            data.append(
                {
                    "bcs_cluster_id": cluster_id,
                    "bk_cloud_id": bk_cloud_id,
                }
            )
        return data


class FetchK8sEventLogResource(CacheResource):
    """查询事件日志 ."""

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")
        bcs_cluster_id = serializers.CharField(required=False, label="集群ID")
        data_format = serializers.CharField(label="数据格式", default="strategy")
        result_table_id = serializers.CharField(required=False, label="结果表ID", default="", allow_blank=True)
        select = serializers.ListField(required=False, default=[])
        group_by = serializers.ListField(required=False, default=[])
        where = serializers.ListField(label="过滤条件", default=lambda: [])
        start_time = serializers.IntegerField(required=True, label="开始时间（秒）")
        end_time = serializers.IntegerField(required=True, label="结束时间（秒）")
        limit = serializers.IntegerField(label="查询条数", default=10)
        offset = serializers.IntegerField(label="查询偏移", default=0)

    @classmethod
    def get_cluster_info_list(cls, params):
        """获得集群接入注册信息 ."""
        bcs_cluster_id = params.get("bcs_cluster_id")
        cluster_info = models.BCSClusterInfo.objects.get(
            cluster_id=bcs_cluster_id, status=models.BCSClusterInfo.CLUSTER_STATUS_RUNNING
        )
        return cluster_info

    @classmethod
    def get_event_table_id(cls, params):
        """事件结果表 ."""
        result_table_id = params.get("result_table_id")
        if not result_table_id:
            # 获得集群接入注册信息
            cluster_info = cls.get_cluster_info_list(params)
            event_data_id = cluster_info.K8sEventDataID
            # 获得事件结果表
            data_source_result = models.DataSourceResultTable.objects.get(bk_data_id=event_data_id)
            result_table_id = data_source_result.table_id
        return result_table_id

    def validate_request_data(self, params):
        if "start_time" not in params or "end_time" not in params:
            # 默认获取一小时数据
            params["end_time"] = int(datetime.now().timestamp())
            params["start_time"] = int((datetime.now() - timedelta(hours=1)).timestamp())
        # 转换为毫秒
        params["start_time"] *= 1000
        params["end_time"] *= 1000
        return super().validate_request_data(params)

    @classmethod
    def load_data_source(cls, params, result_table_id):
        """加载事件源对象 ."""
        bk_biz_id = params["bk_biz_id"]
        where = params["where"]
        select = params["select"]
        group_by = params.get("group_by")
        data_source_label = DataSourceLabel.CUSTOM
        data_type_label = DataTypeLabel.EVENT
        data_source_class = load_data_source(data_source_label, data_type_label)
        kwargs = dict(
            table=result_table_id,
            select=select,
            where=where,
            group_by=group_by,
            time_field=None,
            bk_biz_id=bk_biz_id,
        )
        data_source = data_source_class(**kwargs)
        return data_source

    @classmethod
    def search_event_log(cls, params, data_source):
        limit = params["limit"]
        # TODO(crayon) 这个接口没有 limit > 0 的引用，理论上原始日志 / 聚合数据需要分别通过 query_log / query_dimensions 获取
        limit = None if limit <= 0 else limit
        start_time = params["start_time"]
        end_time = params["end_time"]
        offset = params["offset"]
        select = params["select"]
        group_by = params.get("group_by")
        q = data_source._get_queryset(
            select=select,
            table=data_source.table,
            agg_condition=data_source._get_where(),
            where=data_source._get_filter_dict(),
            limit=limit,
            offset=offset,
            time_field=None,
            group_by=group_by,
            start_time=start_time,
            end_time=end_time,
        )
        if limit is None:
            # limit=None 不需要返回原始日志，通过 dsl_group_hits=-1 禁用
            q = q.dsl_group_hits(-1)

        data = q.original_data
        return data

    def perform_request(self, params):
        # 获得事件结果表
        try:
            result_table_id = self.get_event_table_id(params)
        except (models.BCSClusterInfo.DoesNotExist, models.DataSourceResultTable.DoesNotExist):
            # 集群未注册
            return {}
        if not result_table_id:
            # data_id未注册
            return {}
        # 创建数据源对象
        data_source = self.load_data_source(params, result_table_id)
        # 查询事件日志
        data = self.search_event_log(params, data_source)
        return data


class GetClusterInfoFromBcsSpaceResource(CacheResource):
    """根据业务id在bcs空间下获取集群信息 ."""

    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        space_uid = serializers.CharField(required=False, label="空间英文名称", allow_null=True, default="")
        shard_only = serializers.BooleanField(required=False, default=False)
        bk_biz_id = serializers.IntegerField(required=False, allow_null=True, default=None)

    def perform_request(self, params: dict) -> dict:
        space_uid: str | None = params.get("space_uid")
        shard_only = params.get("shard_only")
        bk_biz_id = params.get("bk_biz_id")

        if space_uid:
            bk_biz_id = space_uid_to_bk_biz_id(space_uid)
        elif bk_biz_id == 0:
            return {}
        elif bk_biz_id:
            if bk_biz_id > 0:
                # 业务空间下无共享集群
                return {}
            space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        else:
            raise ValueError("space_uid or bk_biz_id is required")

        # 仅有bkci和bcs空间支持获取集群信息
        space_type_id, space_id = space_uid.split("__", 1)
        if space_type_id not in [SpaceTypeEnum.BKCI.value, SpaceTypeEnum.BCS.value]:
            return {}

        cluster_list = api.metadata.get_clusters_by_space_uid(space_uid=space_uid)

        data = {}
        for cluster in cluster_list:
            cluster_id = cluster["cluster_id"]
            namespace_list = cluster.get("namespace_list", [])
            cluster_type = cluster.get("cluster_type")
            if shard_only and cluster_type != BcsClusterType.SHARED:
                # 值获取共享集群
                continue
            # 忽略没有使用的共享集群
            if cluster_type == BcsClusterType.SHARED and not namespace_list:
                continue
            data[cluster_id] = {
                "namespace_list": namespace_list if namespace_list else [],
                "cluster_type": cluster_type,
            }

        return data


def is_shared_cluster(bcs_cluster_id: str, bk_biz_id: int = None, space_uid: str = None) -> bool:
    """判断集群是否是共享集群 ."""
    shard_info = GetClusterInfoFromBcsSpaceResource()(
        {"bk_biz_id": bk_biz_id, "space_uid": space_uid, "shard_only": True}
    )
    return bcs_cluster_id in shard_info


class FetchK8sEventTableId(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bcs_cluster_id = serializers.CharField(label="集群ID")

    @classmethod
    def get_event_table_id(cls, params):
        """获得事件结果表ID ."""
        # 获得集群接入注册信息
        bcs_cluster_id = params.get("bcs_cluster_id")
        cluster_info = models.BCSClusterInfo.objects.get(
            cluster_id=bcs_cluster_id, status=models.BCSClusterInfo.CLUSTER_STATUS_RUNNING
        )
        event_data_id = cluster_info.K8sEventDataID
        # 获得事件结果表
        data_source_result = models.DataSourceResultTable.objects.get(bk_data_id=event_data_id)
        result_table_id = data_source_result.table_id
        return result_table_id

    def perform_request(self, params):
        try:
            result_table_id = self.get_event_table_id(params)
        except (models.BCSClusterInfo.DoesNotExist, models.DataSourceResultTable.DoesNotExist):
            # 集群未注册
            return None
        if not result_table_id:
            # data_id未注册
            return None
        return result_table_id


class HasBkmMetricbeatEndpointUpResource(CacheResource):
    cache_type = CacheType.BCS

    class RequestSerializer(serializers.Serializer):
        bk_biz_id = serializers.IntegerField(label="业务ID")

    def perform_request(self, params: dict):
        bk_tenant_id = bk_biz_id_to_bk_tenant_id(params["bk_biz_id"])
        return MetricListCache.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=params["bk_biz_id"], metric_field=BKM_METRICBEAT_ENDPOINT_UP
        ).exists()

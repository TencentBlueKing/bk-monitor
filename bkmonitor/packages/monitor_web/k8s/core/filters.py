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
from typing import Dict

from monitor_web.k8s.core.errors import K8sResourceNotFound, MultiWorkloadError

filter_options = {}


def register_filter(filter_cls):
    global filter_options
    filter_options[filter_cls.resource_type] = filter_cls
    return filter_cls


class ResourceFilter(object):
    resource_type = ""
    filter_field = ""

    def __init__(self, value, fuzzy=False):
        if not isinstance(value, (list, tuple)):
            value = [value]
        value = list(map(str, value))
        self.value = sorted(value)
        self.fuzzy = fuzzy

    @property
    def filter_uid(self):
        return f"{self.resource_type}{self.filter_field}{self.value}"

    @property
    def filter_dict(self) -> Dict:
        """
        用于ORM的查询
        """
        if len(self.value) == 1:
            if self.fuzzy:
                return {f"{self.filter_field}__icontains": self.value[0]}
            return {self.filter_field: self.value[0]}
        return {f"{self.filter_field}__in": self.value}

    def filter_string(self) -> str:
        if self.fuzzy:
            return self.fuzzy_filter_string()
        if len(self.value) == 1:
            return f'{self.filter_field}="{self.value[0]}"'
        value_regex = "|".join(self.value)
        return f'{self.filter_field}=~"^({value_regex})$"'

    def fuzzy_filter_string(self) -> str:
        return f'''{self.filter_field}=~"({'|'.join(self.value)})"'''


@register_filter
class NamespaceFilter(ResourceFilter):
    resource_type = "namespace"
    filter_field = "namespace"


@register_filter
class PodFilter(ResourceFilter):
    resource_type = "pod"
    filter_field = "pod_name"


@register_filter
class WorkloadFilter(ResourceFilter):
    resource_type = "workload"
    filter_field = "workload"

    @property
    def filter_dict(self) -> Dict[str, str]:
        filter = {}
        if len(self.value) > 1:
            raise MultiWorkloadError()

        parsed = self.value[0].split(":", 1)
        if len(parsed) == 2:
            workload_kind, workload_name = self.value[0].split(":")

            if workload_kind:
                filter["workload_kind"] = workload_kind.strip()
            if workload_name:
                filter["workload_name"] = workload_name.strip()

        else:
            if self.fuzzy:
                filter["workload_name__icontains"] = self.value[0].strip()
            else:
                filter["workload_name"] = self.value[0].strip()

        return filter

    def filter_string(self):
        if self.fuzzy:
            return f'''workload_name=~"{self.value[0].strip()}"'''
        where = ""
        for field, value in self.filter_dict.items():
            where += "," if where else ""
            where += f'{field}="{value}"'
        return where


@register_filter
class ContainerFilter(ResourceFilter):
    resource_type = "container"
    filter_field = "container_name"


@register_filter
class DefaultContainerFilter(ResourceFilter):
    resource_type = "container_exclude"
    filter_field = "container_name"

    def filter_string(self):
        return 'container_name!="POD"'

    @property
    def filter_dict(self):
        return {}


@register_filter
class NodeFilter(ResourceFilter):
    resource_type = "node"
    filter_field = "node"


@register_filter
class ClusterFilter(ResourceFilter):
    resource_type = "bcs_cluster_id"
    filter_field = "bcs_cluster_id"


@register_filter
class SpaceFilter(ResourceFilter):
    resource_type = "bk_biz_id"
    filter_field = "bk_biz_id"


@register_filter
class IngressFilter(ResourceFilter):
    resource_type = "ingress"
    filter_field = "ingress"


@register_filter
class ServiceFilter(ResourceFilter):
    resource_type = "service"
    filter_field = "service"


def load_resource_filter(resource_type, filter_value, fuzzy=False) -> ResourceFilter:
    if resource_type not in filter_options:
        # 兼容xxx_name字段
        if resource_type.endswith("_name"):
            return load_resource_filter(resource_type.split("_name")[0], filter_value, fuzzy)
        raise K8sResourceNotFound(resource_type=resource_type)
    filter_obj = filter_options[resource_type](filter_value, fuzzy)
    return filter_obj

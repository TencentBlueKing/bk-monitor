"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from opentelemetry.semconv.resource import ResourceAttributes
from opentelemetry.semconv.trace import SpanAttributes

from apm.constants import DiscoverRuleType
from apm.core.discover.base import (
    DiscoverBase,
    exists_field,
    extract_field_value,
    get_topo_instance_key,
    combine_list,
)
from apm.models import ApmTopoDiscoverRule, TopoNode
from apm.utils.base import divide_biscuit
from bkm_space.errors import NoRelatedResourceError
from bkm_space.validate import validate_bk_biz_id
from bkmonitor.models import BCSPod
from bkmonitor.utils.cache import lru_cache_with_ttl
from bkmonitor.utils.thread_backend import ThreadPool
from constants.apm import OtlpKey, TelemetryDataType, Vendor


logger = logging.getLogger(__name__)


class NodeDiscover(DiscoverBase):
    DISCOVERY_ALL_SPANS = True
    MAX_COUNT = 100000
    model = TopoNode
    # 批量处理 span 时 每批次的数量
    HANDLE_SPANS_BATCH_SIZE = 10000

    @property
    def extra_data_factory(self):
        return defaultdict(
            lambda: {
                "extra_data": {"category": "", "kind": "", "predicate_value": "", "service_language": ""},
                "platform": {},
                # system: multiple
                "system": {},
                # sdk: multiple
                "sdk": {},
            }
        )

    @classmethod
    @lru_cache_with_ttl(ttl=timedelta(minutes=10).total_seconds())
    def _validate_bk_biz_id(cls, bk_biz_id: int) -> int:
        """将负数项目空间 ID，转为关联业务 ID"""
        try:
            return validate_bk_biz_id(bk_biz_id)
        except NoRelatedResourceError:
            return bk_biz_id

    def get_pod_workload_mapping(self, pod_tuples: tuple[str, ...]) -> dict[tuple[str, ...], dict[str, str]]:
        """获取 pod 和 workload 的映射关系
        Q：为什么不直接使用 Pod 关联信息？
        - k8s 的设计理念是「控制器」，Pod 是当前存活的实例，而工作负载是 Pod 的模板。
        - Pod 可能会随时被销毁，而工作负载则会长期存在。
        - 将观测建立在工作负载上，可以更稳定地获取到服务的关联信息，并直观反映、对比发布前后 Pod 的变化（副本数、CPU、内存）。
        - btw：目前 APM 关联容器页面将 Pod 平铺的方式，缺少基于 Workload 聚合查看的能力，后续可以考虑结合新版容器监控优化。
        """
        if not pod_tuples:
            return {}

        pod_names: set[str] = set()
        namespaces: set[str] = set()
        bcs_cluster_ids: set[str] = set()
        for pod_tuple in pod_tuples:
            bcs_cluster_id, namespace, pod_name = pod_tuple
            pod_names.add(pod_name)
            namespaces.add(namespace)
            bcs_cluster_ids.add(bcs_cluster_id)

        pods: list[dict[str, str]] = BCSPod.objects.filter(
            bk_biz_id=self._validate_bk_biz_id(self.bk_biz_id),
            bcs_cluster_id__in=bcs_cluster_ids,
            namespace__in=namespaces,
            name__in=pod_names,
        ).values("bcs_cluster_id", "namespace", "workload_type", "workload_name", "name")

        pod_workload_mapping: dict[tuple[str, ...], dict[str, str]] = {}
        for pod in pods:
            pod_workload_mapping[(pod["bcs_cluster_id"], pod["namespace"], pod["name"])] = {
                "bcs_cluster_id": pod["bcs_cluster_id"],
                "namespace": pod["namespace"],
                "kind": pod["workload_type"],
                "name": pod["workload_name"],
            }

        return pod_workload_mapping

    def discover(self, origin_data):
        rules_map = defaultdict(list)

        all_rules, other_rule = self.get_rules(_type="all")
        for rule in all_rules:
            rules_map[rule.type].append(rule)
        category_rules = (rules_map.pop(DiscoverRuleType.CATEGORY.value), other_rule)
        rules = [(k, v) for k, v in rules_map.items()]

        pool = ThreadPool()
        results = pool.map_ignore_exception(
            self.batch_execute,
            [(spans, category_rules, rules) for spans in divide_biscuit(origin_data, self.HANDLE_SPANS_BATCH_SIZE)],
        )

        # 结合发现的数据和已有数据判断 创建/更新
        exists_instances = self.list_exists()

        pod_tuples = set()
        create_instances = {}
        update_instances = {}
        for instances_mapping in results:
            if not instances_mapping:
                continue

            for k, v in instances_mapping.items():
                if not k:
                    # topo_key 为空，可能是 Span 未上报 service.name，记录异常日志并跳过。
                    logger.warning(
                        "[NodeDiscover] topo_key empty: bk_biz_id=%s, app_name=%s, skipped",
                        self.bk_biz_id,
                        self.app_name,
                    )
                    continue

                v["system"] = list(v["system"].values())
                v["sdk"] = list(v["sdk"].values())
                if v["extra_data"]["category"] == ApmTopoDiscoverRule.APM_TOPO_CATEGORY_OTHER:
                    if all(k not in i for i in [update_instances, create_instances, exists_instances]):
                        # 如果目前没有发现这个符合 other 规则的服务 才把他添加进列表中 (不然如果更新的话会导致数据被覆盖为空)
                        create_instances.update({k: {**v, "source": [TelemetryDataType.TRACE.value]}})
                else:
                    if k not in exists_instances:
                        create_instances.update({k: {**v, "source": [TelemetryDataType.TRACE.value]}})
                    else:
                        source = exists_instances[k]["source"]
                        if not source:
                            source = [TelemetryDataType.TRACE.value]
                        elif TelemetryDataType.TRACE.value not in source:
                            source.append(TelemetryDataType.TRACE.value)
                        update_instances.update({k: {**v, "source": source}})

                pod_tuples = pod_tuples | v["platform"].get("pod_tuples", set())

        # update
        update_combine_instances = []
        pod_workload_mapping: dict[tuple[str, ...], dict[str, str]] = self.get_pod_workload_mapping(pod_tuples)
        for topo_key, topo_value in update_instances.items():
            # 合并数组字段: platform | system
            exist_instance = exists_instances.get(topo_key)
            if not exist_instance:
                continue

            update_combine_instances.append(
                TopoNode(
                    id=exist_instance["id"],
                    topo_key=topo_key,
                    extra_data=topo_value["extra_data"],
                    platform=self.combine_workloads(
                        pod_workload_mapping, exist_instance["platform"], topo_value["platform"]
                    ),
                    system=combine_list(exist_instance["system"], topo_value["system"]),
                    sdk=combine_list(exist_instance["sdk"], topo_value["sdk"]),
                    source=topo_value["source"],
                    updated_at=datetime.now(),
                )
            )

        TopoNode.objects.bulk_update(
            update_combine_instances, fields=["extra_data", "platform", "system", "sdk", "source", "updated_at"]
        )

        # create
        to_be_created_instances = []
        for topo_key, topo_value in create_instances.items():
            # 匹配 Pod 对应的 Workload。
            topo_value["platform"] = self.combine_workloads(
                pod_workload_mapping, None, topo_value.get("platform") or {}
            )
            to_be_created_instances.append(
                TopoNode(bk_biz_id=self.bk_biz_id, app_name=self.app_name, topo_key=topo_key, **topo_value)
            )
        TopoNode.objects.bulk_create(to_be_created_instances)

        self.clear_if_overflow()
        self.clear_expired()

    @classmethod
    def combine_workloads(
        cls,
        pod_workload_mapping: dict[tuple[str, ...], dict[str, str]],
        target: dict[str, Any] | None,
        source: dict[str, Any],
    ) -> dict[str, Any]:
        if source.get("name") != ApmTopoDiscoverRule.APM_TOPO_PLATFORM_K8S:
            return source

        # 当指标（apm/core/discover/metric/service.py）发现早于节点发现时，可能会出现 target 为 None 的情况。
        # 将空值的 target 设置为一个空字典，继续对 workloads 进行格式处理。
        target = target or {}
        merged_workload_mapping: dict[frozenset, dict[str, int | str]] = {}
        for workload in target.get("workloads", []):
            updated_at: int = workload.pop("updated_at", 0)
            merged_workload_mapping[frozenset(workload.items())] = {**workload, "updated_at": updated_at}

        now: int = int(datetime.now().timestamp())
        for pod_tuple in source.pop("pod_tuples", set()):
            workload: dict[str, int | str] | None = pod_workload_mapping.get(pod_tuple)
            if not workload:
                continue
            # 更新存活时间，便于判断 Workload 时效性
            merged_workload_mapping[frozenset(workload.items())] = {**workload, "updated_at": now}

        source["workloads"] = list(merged_workload_mapping.values())
        return source

    def batch_execute(self, origin_data, category_rules, rules):
        instance_mapping = self.extra_data_factory
        for span in origin_data:
            topo_key = None

            # 先进行 category 类型的规则发现
            # 类型为: category | 作用: 推断出 span 的服务、组件、自定义服务
            match_rule = self.get_match_rule(span, category_rules[0], category_rules[1])
            if match_rule:
                topo_key = self.find_category(instance_mapping, match_rule, category_rules[1], span)

            if not topo_key:
                # topo_key 为空表明发现的是组件类型的节点，服务、组件等类别不一定互斥，比如一个 RPC 服务的 DB 请求 Span。
                # 此处排除已匹配的规则，进行再一次发现，避免节点类别直接设置 other 后不再更新 SDK、框架等信息。
                match_rule = self.get_match_rule(
                    span,
                    category_rules[0],
                    category_rules[1],
                    extra_cond=lambda _rule: _rule.category_id != match_rule.category_id,
                )
                topo_key = get_topo_instance_key(
                    match_rule.instance_keys,
                    match_rule.topo_kind,
                    match_rule.category_id,
                    span,
                )
                instance_mapping[topo_key]["extra_data"]["category"] = match_rule.category_id
                instance_mapping[topo_key]["extra_data"]["kind"] = match_rule.topo_kind

            if not topo_key:
                continue

            # 后续的规则基于上一步发现的 topo_key 来补充数据
            for item in rules:
                item_rule_type = item[0]
                item_rules = item[1]

                if item_rule_type == DiscoverRuleType.SYSTEM.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_system(instance_mapping, match_rule, span, topo_key)

                elif item_rule_type == DiscoverRuleType.PLATFORM.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_platform(instance_mapping, match_rule, span, topo_key)

                elif item_rule_type == DiscoverRuleType.SDK.value:
                    match_rule = self.get_match_rule(span, item_rules)
                    if match_rule:
                        self.find_sdk(instance_mapping, match_rule, span, topo_key)

        return instance_mapping

    def find_category(self, instance_mapping, match_rule, other_rule, span):
        self.find_remote_service(span, match_rule, instance_mapping)

        topo_key = get_topo_instance_key(
            match_rule.instance_keys,
            match_rule.topo_kind,
            match_rule.category_id,
            span,
            component_predicate_key=match_rule.predicate_key,
        )
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            # 组件类型的节点名称需要添加上服务名称的前缀 (不考虑拼接后与用户定义的服务重名情况需要引导用户进行更改)
            topo_key = f"{self.get_service_name(span)}-{topo_key}"

        instance_mapping[topo_key]["extra_data"]["category"] = match_rule.category_id
        instance_mapping[topo_key]["extra_data"]["kind"] = match_rule.topo_kind
        instance_mapping[topo_key]["extra_data"]["predicate_value"] = extract_field_value(
            match_rule.predicate_key, span
        )
        instance_mapping[topo_key]["extra_data"]["service_language"] = extract_field_value(
            (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
        )
        if match_rule.topo_kind == ApmTopoDiscoverRule.TOPO_COMPONENT:
            other_rule_topo_key = get_topo_instance_key(
                other_rule.instance_keys,
                other_rule.topo_kind,
                other_rule.category_id,
                span,
            )
            instance_mapping[other_rule_topo_key]["extra_data"] = {
                "category": other_rule.category_id,
                "kind": other_rule.topo_kind,
                "predicate_value": extract_field_value(other_rule.predicate_key, span),
                "service_language": extract_field_value(
                    (OtlpKey.RESOURCE, ResourceAttributes.TELEMETRY_SDK_LANGUAGE), span
                ),
            }
        # 返回匹配规则的节点名称(非组件类)
        if match_rule.topo_kind != ApmTopoDiscoverRule.TOPO_COMPONENT:
            return topo_key

        return None

    def find_system(self, instance_mapping, match_rule, span, topo_key):
        extra_data = {}
        for i in match_rule.instance_keys:
            extra_data[self.join_keys(i)] = extract_field_value(i, span)
        instance_mapping[topo_key]["system"][match_rule.category_id] = {
            "name": match_rule.category_id,
            "extra_data": extra_data,
        }

    def find_platform(self, instance_mapping, match_rule, span, topo_key):
        extra_data = {}
        for i in match_rule.instance_keys:
            extra_data[self.join_keys(i)] = extract_field_value(i, span)

        platform_metadata: dict[str, Any] = {"name": match_rule.category_id, "extra_data": extra_data}
        if match_rule.category_id != ApmTopoDiscoverRule.APM_TOPO_PLATFORM_K8S:
            instance_mapping[topo_key]["platform"] = platform_metadata
            return

        # 获取 pod 相关信息
        pod_name: str | None = extra_data.get(ApmTopoDiscoverRule.PLATFORM_K8S_POD_NAME_KEY)
        namespace: str | None = extra_data.get(ApmTopoDiscoverRule.PLATFORM_K8S_NAMESPACE_KEY)
        bcs_cluster_id: str | None = extra_data.get(ApmTopoDiscoverRule.PLATFORM_K8S_CLUSTER_ID_KEY)
        pod_tuples: set[tuple[str, ...]] = instance_mapping[topo_key].get("platform", {}).get("pod_tuples", set())
        if pod_name and namespace and bcs_cluster_id:
            pod_tuples.add((bcs_cluster_id, namespace, pod_name))

        platform_metadata["pod_tuples"] = pod_tuples
        instance_mapping[topo_key]["platform"] = platform_metadata

    def find_sdk(self, instance_mapping, match_rule, span, topo_key):
        # SDK 规则中无分类 id 直接将 predicate_value 作为名称
        predicate_value = extract_field_value(match_rule.predicate_key, span)
        extra_data = {self.join_keys(match_rule.predicate_key): predicate_value}
        if Vendor.equal(Vendor.G, predicate_value):
            for i in match_rule.instance_keys:
                extra_data[self.join_keys(i)] = extract_field_value(i, span)
        instance_mapping[topo_key]["sdk"][predicate_value] = {
            "name": predicate_value,
            "extra_data": extra_data,
        }

    def list_exists(self):
        return {
            i["topo_key"]: i
            for i in TopoNode.objects.filter(bk_biz_id=self.bk_biz_id, app_name=self.app_name).values(
                "topo_key", "extra_data", "system", "platform", "sdk", "id", "source"
            )
        }

    def find_remote_service(self, span, rule, instance_map):
        predicate_key = (OtlpKey.ATTRIBUTES, SpanAttributes.PEER_SERVICE)

        if exists_field(predicate_key, span):
            instance_key = get_topo_instance_key(
                [predicate_key],
                ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE,
                rule.category_id,
                span,
            )
            instance_map[instance_key]["extra_data"]["category"] = rule.category_id
            # remote service found by span additionally
            instance_map[instance_key]["extra_data"]["kind"] = ApmTopoDiscoverRule.TOPO_REMOTE_SERVICE
            instance_map[instance_key]["extra_data"]["predicate_value"] = extract_field_value(predicate_key, span)

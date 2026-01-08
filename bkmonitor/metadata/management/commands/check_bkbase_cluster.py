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
from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.models.storage import ClusterInfo
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS

logger = logging.getLogger("metadata")


class Command(BaseCommand):
    """检查bkbase集群信息"""

    help = "检查 bkbase 集群配置与数据库配置的一致性"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.format_type = "text"
        self.result_data = {
            "namespaces": [],
            "summary": {
                "total_clusters": 0,
                "unregistered_clusters": [],
                "duplicate_domain_clusters": [],
                "inconsistent_configs": [],
            },
        }

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="租户ID", default=DEFAULT_TENANT_ID)
        parser.add_argument(
            "--cluster_type", type=str, help="集群类型", choices=[ClusterInfo.TYPE_KAFKA, ClusterInfo.TYPE_ES]
        )
        parser.add_argument("--format", choices=["text", "json"], default="text", help="输出格式，支持text和json")

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        cluster_type = options["cluster_type"]
        self.format_type = options["format"]

        if not cluster_type:
            error_msg = "cluster_type 参数是必需的"
            if self.format_type == "json":
                self.stdout.write(json.dumps({"error": error_msg}, ensure_ascii=False))
            else:
                self.stdout.write(self.style.ERROR(error_msg))
            return

        logger.info(f"开始检查集群配置，cluster_type: {cluster_type}, bk_tenant_id: {bk_tenant_id}")

        try:
            clusters = {
                cluster.cluster_name: cluster for cluster in ClusterInfo.objects.filter(cluster_type=cluster_type)
            }
            self.result_data["summary"]["total_clusters"] = len(clusters)

            if cluster_type not in ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP:
                error_msg = f"不支持的集群类型: {cluster_type}"
                logger.error(error_msg)
                if self.format_type == "json":
                    self.stdout.write(json.dumps({"error": error_msg}, ensure_ascii=False))
                else:
                    self.stdout.write(self.style.ERROR(error_msg))
                return

            kind = ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP[cluster_type]

            # 获取字段映射
            field_mappings: dict[str, str] = {}
            for config in BKBASE_V4_KIND_STORAGE_CONFIGS:
                if config["cluster_type"] != cluster_type:
                    continue
                field_mappings = config["field_mappings"]
                break

            if not field_mappings:
                error_msg = f"cluster_type: {cluster_type}, 未配置字段映射"
                logger.warning(error_msg)
                if self.format_type == "json":
                    self.stdout.write(json.dumps({"error": error_msg}, ensure_ascii=False))
                else:
                    self.stdout.write(self.style.WARNING(error_msg))
                return

            for namespace in ClusterConfig.KIND_TO_NAMESPACES_MAP[kind]:
                logger.info(f"开始检查 namespace: {namespace}")
                namespace_result = self._check_namespace(namespace, bk_tenant_id, kind, clusters, field_mappings)
                self.result_data["namespaces"].append(namespace_result)

            # 输出结果
            if self.format_type == "json":
                self.stdout.write(json.dumps(self.result_data, indent=2, ensure_ascii=False, default=str))
            else:
                self._output_text_summary()

        except Exception as e:
            error_msg = f"检查集群配置失败: {str(e)}"
            logger.exception(error_msg)
            if self.format_type == "json":
                self.stdout.write(json.dumps({"error": error_msg}, ensure_ascii=False))
            else:
                self.stdout.write(self.style.ERROR(error_msg))

    def _check_namespace(
        self,
        namespace: str,
        bk_tenant_id: str,
        kind: str,
        clusters: dict[str, ClusterInfo],
        field_mappings: dict[str, str],
    ) -> dict[str, Any]:
        """检查指定命名空间的集群配置"""
        namespace_result = {
            "namespace": namespace,
            "unregistered_clusters": [],
            "duplicate_domain_clusters": [],
            "inconsistent_configs": [],
        }

        try:
            if self.format_type == "text":
                self.stdout.write(f"\n\nnamespace: {namespace}, 开始检查: ")

            # 获取命名空间下的集群配置
            cluster_configs: dict[str, dict[str, Any]] = {
                cluster_config["metadata"]["name"]: cluster_config
                for cluster_config in api.bkdata.list_data_link(
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    kind=DataLinkKind.get_choice_value(kind),
                )
            }

            # 检查未注册的集群
            unregistered = list(set(clusters.keys()) - set(cluster_configs.keys()))
            namespace_result["unregistered_clusters"] = unregistered
            if unregistered:
                self.result_data["summary"]["unregistered_clusters"].extend(unregistered)
                if self.format_type == "text":
                    self.stdout.write(self.style.WARNING(f"未注册的集群: {unregistered}"))

            # 检查同域名集群
            domain_to_cluster_names: dict[str, set[str]] = defaultdict(set)
            exists_domain_to_cluster_names: dict[str, set[str]] = defaultdict(set)

            for cluster_name, cluster in clusters.items():
                domain_to_cluster_names[f"{cluster.domain_name}:{cluster.port}"].add(cluster_name)

            for cluster_name, cluster_config in cluster_configs.items():
                spec = cluster_config.get("spec", {})
                if not spec:
                    continue
                domain = spec.get(field_mappings["domain_name"])
                port = spec.get(field_mappings["port"])
                if domain and port:
                    exists_domain_to_cluster_names[f"{domain}:{port}"].add(cluster_name)

            # 检查同域名集群
            for domain, cluster_names in domain_to_cluster_names.items():
                exists_cluster_names = exists_domain_to_cluster_names.get(domain, set())

                # 如果已注册的集群和未注册的集群数量之和不超过1，则跳过
                if len(exists_cluster_names | cluster_names) <= 1:
                    continue

                # 存在重复的集群
                duplicate_info = {
                    "domain": domain,
                    "registered": list(exists_cluster_names),
                    "unregistered": list(cluster_names - exists_cluster_names),
                }
                namespace_result["duplicate_domain_clusters"].append(duplicate_info)
                self.result_data["summary"]["duplicate_domain_clusters"].append(duplicate_info)
                if self.format_type == "text":
                    self.stdout.write(
                        self.style.WARNING(
                            f"同域名集群: {domain}, 已注册: {exists_cluster_names}, "
                            f"未注册: {cluster_names - exists_cluster_names}"
                        )
                    )

            # 比对集群配置(同名集群比对配置)
            for cluster_name, cluster in clusters.items():
                # 未注册的集群跳过
                if cluster_name not in cluster_configs:
                    continue
                cluster_config = cluster_configs[cluster_name]

                # 生成集群配置对象
                cluster_config_obj = ClusterConfig(
                    bk_tenant_id=bk_tenant_id,
                    namespace=namespace,
                    name=cluster_name,
                    kind=kind,
                )
                generate_cluster_config = cluster_config_obj.compose_config()

                # 比对 label/annotations/spec 是否一致
                inconsistent_items = []
                if generate_cluster_config["metadata"].get("labels") != cluster_config["metadata"].get("labels"):
                    inconsistent_items.append("labels")
                if generate_cluster_config["metadata"].get("annotations") != cluster_config["metadata"].get(
                    "annotations"
                ):
                    inconsistent_items.append("annotations")
                if generate_cluster_config["spec"] != cluster_config.get("spec"):
                    inconsistent_items.append("spec")

                if inconsistent_items:
                    inconsistent_info = {
                        "cluster_name": cluster_name,
                        "inconsistent_items": inconsistent_items,
                    }
                    namespace_result["inconsistent_configs"].append(inconsistent_info)
                    self.result_data["summary"]["inconsistent_configs"].append(inconsistent_info)
                    if self.format_type == "text":
                        self.stdout.write(
                            self.style.ERROR(
                                f"cluster_name: {cluster_name}, 不一致的配置项: {', '.join(inconsistent_items)}"
                            )
                        )

        except Exception as e:
            error_msg = f"检查命名空间 {namespace} 失败: {str(e)}"
            logger.exception(error_msg)
            namespace_result["error"] = error_msg
            if self.format_type == "text":
                self.stdout.write(self.style.ERROR(error_msg))

        return namespace_result

    def _output_text_summary(self):
        """输出文本格式的汇总信息"""
        summary = self.result_data["summary"]
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("检查汇总"))
        self.stdout.write("=" * 60)
        self.stdout.write(f"总集群数: {summary['total_clusters']}")
        self.stdout.write(f"未注册集群数: {len(summary['unregistered_clusters'])}")
        self.stdout.write(f"同域名集群数: {len(summary['duplicate_domain_clusters'])}")
        self.stdout.write(f"配置不一致集群数: {len(summary['inconsistent_configs'])}")
        self.stdout.write("=" * 60)

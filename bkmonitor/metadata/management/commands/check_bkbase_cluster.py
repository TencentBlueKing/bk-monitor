from collections import defaultdict
from typing import Any

from django.core.management.base import BaseCommand

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models.data_link.constants import DataLinkKind
from metadata.models.data_link.data_link_configs import ClusterConfig
from metadata.models.storage import ClusterInfo
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS


class Command(BaseCommand):
    """检查bkbase集群信息"""

    def add_arguments(self, parser):
        parser.add_argument("--bk_tenant_id", type=str, help="租户ID", default=DEFAULT_TENANT_ID)
        parser.add_argument(
            "--cluster_type", type=str, help="集群类型", choices=[ClusterInfo.TYPE_KAFKA, ClusterInfo.TYPE_ES]
        )

    def handle(self, *args, **options):
        bk_tenant_id = options["bk_tenant_id"]
        cluster_type = options["cluster_type"]

        clusters = {cluster.cluster_name: cluster for cluster in ClusterInfo.objects.filter(cluster_type=cluster_type)}
        kind = ClusterConfig.CLUSTER_TYPE_TO_KIND_MAP[cluster_type]

        # 获取字段映射
        field_mappings: dict[str, str] = {}
        for config in BKBASE_V4_KIND_STORAGE_CONFIGS:
            if config["cluster_type"] != cluster_type:
                continue
            field_mappings = config["field_mappings"]
        if not field_mappings:
            print(f"cluster_type: {cluster_type}, 未配置字段映射")
            return

        for namespace in ClusterConfig.KIND_TO_NAMESPACES_MAP[kind]:
            print(f"\n\n\nnamespace: {namespace}, 开始检查: ")
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
            print(f"未注册的集群: {set(clusters.keys()) - set(cluster_configs.keys())}")

            # 检查同域名集群
            domain_to_cluster_names: dict[str, set[str]] = defaultdict(set)
            exists_domain_to_cluster_names: dict[str, set[str]] = defaultdict(set)

            for cluster_name, cluster in clusters.items():
                domain_to_cluster_names[f"{cluster.domain_name}:{cluster.port}"].add(cluster_name)
            for cluster_name, cluster_config in cluster_configs.items():
                domain = cluster_config["spec"][field_mappings["domain_name"]]
                port = cluster_config["spec"][field_mappings["port"]]
                exists_domain_to_cluster_names[f"{domain}:{port}"].add(cluster_name)

            # 检查同域名集群
            for domain, cluster_names in domain_to_cluster_names.items():
                exists_cluster_names = exists_domain_to_cluster_names.get(domain, set())

                # 如果已注册的集群和未注册的集群数量之和不超过1，则跳过
                if len(exists_cluster_names | cluster_names) <= 1:
                    continue

                # 存在重复的集群
                if len(exists_cluster_names | cluster_names) > 1:
                    print(
                        f"同域名集群: {domain}, 已注册: {exists_cluster_names}, 未注册: {cluster_names - exists_cluster_names}"
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
                cluster_config = cluster_configs.get(cluster_name, {})

                # 比对 label/annotations/spec 是否一致
                if generate_cluster_config["metadata"]["labels"] != cluster_config["metadata"]["labels"]:
                    print(f"cluster_name: {cluster_name}, 标签不一致")
                if generate_cluster_config["metadata"]["annotations"] != cluster_config["metadata"]["annotations"]:
                    print(f"cluster_name: {cluster_name}, 注解不一致")
                if generate_cluster_config["spec"] != cluster_config["spec"]:
                    print(f"cluster_name: {cluster_name}, 配置不一致")

"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import os
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q
from django.db.transaction import atomic

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata import config, models
from metadata.models.storage import ClusterInfo
from metadata.task.bkbase import sync_bkbase_cluster_info
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS
from metadata.utils import env


@atomic(config.DATABASE_CONNECTION_NAME)
def refresh_influxdb_info():
    """刷新influxdb proxy及实例相关的信息"""

    # 1. 判断是否已经存在了默认集群
    if models.InfluxDBClusterInfo.is_default_cluster_exists():
        # 如果已经由默认集群，则退出不做处理
        message = (
            f"cluster->[{models.InfluxDBClusterInfo.DEFAULT_CLUSTER_NAME}] is already exists, nothing will be inited."
        )
        print(message)
        return True

    # 2. 读取所有的influxdb相关环境变量
    try:
        influxdb_ip_list = env.get_env_list("BK_INFLUXDB_BKMONITORV3_IP") or env.get_env_list("INFLUXDB_BKMONITORV3_IP")
        influxdb_port = os.getenv("BK_MONITOR_INFLUXDB_PORT") or os.environ["INFLUXDB_BKMONITORV3_PORT"]
        influxdb_username = os.getenv("BK_MONITOR_INFLUXDB_USER") or os.getenv("INFLUXDB_BKMONITORV3_USER", "")
        influxdb_password = os.getenv("BK_MONITOR_INFLUXDB_PASSWORD") or os.getenv("INFLUXDB_BKMONITORV3_PASS", "")
    except KeyError as error:
        message = f"failed to get environ->[{error}] maybe something go wrong on init?"

        print(message)
        return False

    # 3. 写入到数据库，完成配置
    for index, host_ip in enumerate(influxdb_ip_list):
        host_name = f"INFLUXDB_IP{index}"

        # 单个机器的配置写入
        models.InfluxDBHostInfo.objects.create(
            host_name=host_name,
            domain_name=host_ip,
            port=influxdb_port,
            # 默认配置中不存在认证信息
            username=influxdb_username,
            password=influxdb_password,
            description="system auto add.",
        )

        # 集群信息写入
        models.InfluxDBClusterInfo.objects.create(host_name=host_name, cluster_name="default")

        message = f"host->[{host_name}] for cluster->[default] is add."
        print(message)

    # 4. influxdb proxy的信息写入
    influxdb_host = os.environ.get("BK_INFLUXDB_PROXY_HOST", None)
    influxdb_port = os.environ.get("BK_INFLUXDB_PROXY_PORT", None)
    if influxdb_host is not None and influxdb_port is not None:
        try:
            influx_cluster = models.ClusterInfo.objects.get(
                cluster_type=models.ClusterInfo.TYPE_INFLUXDB, is_default_cluster=True
            )

        except models.ClusterInfo.DoesNotExist:
            influx_cluster = models.ClusterInfo.objects.create(
                cluster_name="influxdb_cluster",
                cluster_type=models.ClusterInfo.TYPE_INFLUXDB,
                is_default_cluster=True,
                port=influxdb_port,
            )

        influx_cluster.domain_name = influxdb_host
        influx_cluster.port = influxdb_port
        influx_cluster.save()
        print("update influx domain & port success.")

    message = "all influxdb host is added to database."
    print(message)

    return True


@atomic(config.DATABASE_CONNECTION_NAME)
def refresh_es7_config(bk_tenant_id: str):
    """刷新ES7的配置信息"""

    # 0. 判断是否存在ES7的信息，如果不存在，则直接退出，不做刷新
    if os.environ.get("BK_MONITOR_ES7_HOST", None) is None:
        message = "cannot found ES7 info nothing will insert."
        print(message)
        return True

    try:
        es_host = os.environ["BK_MONITOR_ES7_HOST"]
        es_port = os.environ["BK_MONITOR_ES7_REST_PORT"]
        es_username = os.environ.get("BK_MONITOR_ES7_USER", "")
        es_password = os.environ.get("BK_MONITOR_ES7_PASSWORD", "")
    except KeyError as error:
        message = f"failed to get environ->[{error}] for ES7 cluster maybe something go wrong on init?"
        print(message)
        return False

    # 0. 判断是否已经存在了默认集群ES7，并确认是否初始化
    default_es = models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        version__startswith="7.",
        cluster_type=models.ClusterInfo.TYPE_ES,
        is_default_cluster=True,
    ).first()
    if default_es:
        # 有默认集群，但未初始化, 刷新该集群
        if default_es.domain_name:
            message = "ES version 7 cluster is exists, nothing will do."
            print(message)
            return True

        default_es.domain_name = es_host
        default_es.port = es_port
        default_es.username = es_username
        default_es.password = es_password
        default_es.save()
        message = f"ES version 7 default cluster is init with {es_host}:{es_port}"
        print(message)
        return True

    # 1. 判断默认的ES集群是ES7的，则直接返回
    if models.ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id, version__startswith="7.", cluster_type=models.ClusterInfo.TYPE_ES
    ).exists():
        message = "ES version 7 cluster is exists, nothing will do."
        print(message)

        return True

    # 2. 将之前的其他的配置改为非默认集群
    models.ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_ES).update(
        is_default_cluster=False
    )
    message = "ALL ES CLUSTER NOT version 7 is unset is_default cluster"
    print(message)

    # 3. 需要创建一个新的ES7配置，写入ES7的域名密码等
    models.ClusterInfo.objects.create(
        bk_tenant_id=bk_tenant_id,
        cluster_name="es7_cluster",
        cluster_type=models.ClusterInfo.TYPE_ES,
        domain_name=es_host,
        port=es_port,
        description="default cluster for ES7",
        is_default_cluster=True,
        username=es_username,
        password=es_password,
        version="7.2",
    )
    message = "cluster for es7 is add to default cluster."
    print(message)


def refresh_kafka_config(bk_tenant_id: str):
    """更新kafka的配置信息"""

    # 判断是否已经存在kafka默认信息
    if models.ClusterInfo.objects.filter(
        ~Q(domain_name=""),
        cluster_type=models.ClusterInfo.TYPE_KAFKA,
        bk_tenant_id=bk_tenant_id,
        is_default_cluster=True,
    ):
        message = "kafka cluster is already exists, nothing will add."
        print(message)
        return True

    kafka_host = os.environ.get("BK_MONITOR_KAFKA_HOST", None)
    kafka_port = os.environ.get("BK_MONITOR_KAFKA_PORT", None)
    if kafka_host is not None and kafka_port is not None:
        try:
            kafka_cluster = models.ClusterInfo.objects.get(
                bk_tenant_id=bk_tenant_id, cluster_type=models.ClusterInfo.TYPE_KAFKA, is_default_cluster=True
            )
        except models.ClusterInfo.DoesNotExist:
            kafka_cluster = models.ClusterInfo.objects.create(
                bk_tenant_id=bk_tenant_id,
                cluster_name="kafka_cluster1",
                cluster_type=models.ClusterInfo.TYPE_KAFKA,
                is_default_cluster=True,
                port=kafka_port,
            )
        kafka_cluster.domain_name = kafka_host
        kafka_cluster.port = kafka_port
        kafka_cluster.save()
        print("update kafka domain & port success.")
    return True


def refresh_bkbase_cluster_info(bk_tenant_id: str):
    """
    同步bkbase集群信息
    """
    for storage_config in BKBASE_V4_KIND_STORAGE_CONFIGS:
        clusters: list[dict[str, Any]] = api.bkdata.list_data_link(
            bk_tenant_id=bk_tenant_id, namespace=storage_config["namespace"], kind=storage_config["kind"]
        )

        sync_bkbase_cluster_info(
            bk_tenant_id=bk_tenant_id,
            cluster_list=clusters,
            field_mappings=storage_config["field_mappings"],
            cluster_type=storage_config["cluster_type"],
        )

    # 检查并设置vm默认集群
    vm_clusters = ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_type=ClusterInfo.TYPE_VM)

    # 检查是否存在vm集群
    if not vm_clusters:
        raise ValueError(f"lack of vm cluster in tenant({bk_tenant_id}), contact bkbase support.")

    # 检查是否存在默认的vm集群
    has_default_vm: bool = False
    vm_cluster_map: dict[str, ClusterInfo] = {}
    for vm_cluster in vm_clusters:
        vm_cluster_map[vm_cluster.cluster_name] = vm_cluster
        if vm_cluster.is_default_cluster:
            has_default_vm = True
            break

    # 如果没有默认的vm集群，就设置一个
    if not has_default_vm:
        # 优先设置名字为vm_default的集群为默认集群，如果没有就随便选一个
        default_vm_cluster = vm_cluster_map.get("vm_default")
        if default_vm_cluster:
            default_vm_cluster.is_default_cluster = True
            default_vm_cluster.save()
        else:
            # 随便选一个
            random_vm_cluster = next(iter(vm_cluster_map.values()))
            random_vm_cluster.is_default_cluster = True
            random_vm_cluster.save()


class Command(BaseCommand):
    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--bk_tenant_id", type=str, default=DEFAULT_TENANT_ID, help="租户ID")
        return super().add_arguments(parser)

    def handle(self, *args, **options):
        """
        将influxdb/ES7/kafka的配置写入到数据库中，作为默认配置
        但如果发现已经由influxdb的默认集群，则该次的执行不生效，原因是
        该命令只是确保默认集群的存在，如果有变化则应该是运维在admin进行手动配置调整
        :param args:
        :param options:
        :return:
        """
        bk_tenant_id = options["bk_tenant_id"]

        # 1. 刷新influxdb实例的配置信息，新版本不再初始化
        # refresh_influxdb_info()

        # 2. 刷新ES7的配置
        refresh_es7_config(bk_tenant_id=bk_tenant_id)

        # 3. 刷新kafka配置
        refresh_kafka_config(bk_tenant_id=bk_tenant_id)

        # 4. 同步bkbase集群信息
        refresh_bkbase_cluster_info(bk_tenant_id=bk_tenant_id)

        print("all cluster init done.")

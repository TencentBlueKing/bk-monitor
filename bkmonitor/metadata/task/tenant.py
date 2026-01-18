import logging
import os
from typing import Any

from django.conf import settings

from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api
from metadata.models import ClusterInfo
from metadata.task.bkbase import sync_bkbase_cluster_info
from metadata.task.constants import BKBASE_V4_KIND_STORAGE_CONFIGS
from metadata.task.sync_space import sync_bkcc_space
from metadata.task.tasks import create_single_tenant_system_datalink, create_single_tenant_system_proc_datalink
from metadata.utils.gse import KafkaGseSyncer

logger = logging.getLogger(__name__)


def _init_kafka_cluster(bk_tenant_id: str):
    """
    初始化Kafka集群
    """
    kafka_cluster_query = ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_type=ClusterInfo.TYPE_KAFKA)

    # 如果有默认的kafka集群，则不再初始化
    if kafka_cluster_query.filter(bk_tenant_id=bk_tenant_id, is_default_cluster=True).exists():
        cluster = kafka_cluster_query.get(bk_tenant_id=bk_tenant_id, is_default_cluster=True)
        logger.info("Kafka cluster already exists for tenant %s, skipping initialization.", bk_tenant_id)
    else:
        # 创建默认的kafka集群
        kafka_host = os.environ.get("BK_MONITOR_KAFKA_HOST", None)
        kafka_port = os.environ.get("BK_MONITOR_KAFKA_PORT", None)
        if not kafka_host or not kafka_port:
            logger.error("BK_MONITOR_KAFKA_HOST and BK_MONITOR_KAFKA_PORT must be set in environment variables")
            raise ValueError("BK_MONITOR_KAFKA_HOST and BK_MONITOR_KAFKA_PORT must be set in environment variables")

        cluster = ClusterInfo.objects.create(
            bk_tenant_id=bk_tenant_id,
            cluster_type=ClusterInfo.TYPE_KAFKA,
            cluster_name="kafka_cluster1",
            domain_name=kafka_host,
            port=kafka_port,
            is_default_cluster=True,
        )

        logger.info("Kafka cluster created for tenant %s", bk_tenant_id)

    # 注册到GSE
    KafkaGseSyncer.register_to_gse(mq_cluster=cluster)

    logger.info("Kafka cluster registered to GSE for tenant %s", bk_tenant_id)


def _init_es_cluster(bk_tenant_id: str):
    """
    初始化ES集群
    """
    # 0. 判断是否存在ES7的信息，如果不存在，则直接退出，不做刷新
    if os.environ.get("BK_MONITOR_ES7_HOST") is None:
        logger.info("BK_MONITOR_ES7_HOST is not set, skipping ES7 cluster initialization.")
        return True

    try:
        es_host = os.environ["BK_MONITOR_ES7_HOST"]
        es_port = os.environ["BK_MONITOR_ES7_REST_PORT"]
        es_username = os.environ.get("BK_MONITOR_ES7_USER", "")
        es_password = os.environ.get("BK_MONITOR_ES7_PASSWORD", "")
    except KeyError as error:
        logger.error(f"get es7 env or tenant({bk_tenant_id}) failed: {error}")
        raise ValueError(f"failed to get environ->[{error}] for es7 cluster maybe something go wrong on init?")

    # 0. 判断是否已经存在了默认集群ES7，并确认是否初始化
    default_es = ClusterInfo.objects.filter(
        bk_tenant_id=bk_tenant_id,
        version__startswith="7.",
        cluster_type=ClusterInfo.TYPE_ES,
        is_default_cluster=True,
    ).first()
    if default_es:
        # 有默认集群，但未初始化, 刷新该集群
        if default_es.domain_name:
            logger.info(f"es7 cluster for tenant({bk_tenant_id}) is exists, nothing will do.")
            return True

        default_es.domain_name = es_host
        default_es.port = es_port
        default_es.username = es_username
        default_es.password = es_password
        default_es.save()
        logger.info(f"es7 default cluster tenant({bk_tenant_id}) is init with {es_host}:{es_port}")
        return True

    # 1. 将之前的其他的配置改为非默认集群
    ClusterInfo.objects.filter(bk_tenant_id=bk_tenant_id, cluster_type=ClusterInfo.TYPE_ES).update(
        is_default_cluster=False
    )

    # 2. 需要创建一个新的ES7配置，写入ES7的域名密码等
    ClusterInfo.objects.create(
        bk_tenant_id=bk_tenant_id,
        cluster_name="es7_cluster",
        cluster_type=ClusterInfo.TYPE_ES,
        domain_name=es_host,
        port=es_port,
        description="default cluster for ES7",
        is_default_cluster=True,
        username=es_username,
        password=es_password,
        version="7.2",
    )
    logger.info(f"es7 cluster for tenant({bk_tenant_id}) is added to default cluster.")


def _init_bkbase_cluster(bk_tenant_id: str):
    """
    初始化BKBase集群
    """
    # 遍历所有存储配置
    for storage_config in BKBASE_V4_KIND_STORAGE_CONFIGS:
        clusters: list[dict[str, Any]] = api.bkdata.list_data_link(
            bk_tenant_id=bk_tenant_id, namespace=storage_config["namespace"], kind=storage_config["kind"]
        )
        if clusters:
            logger.info(
                f"sync bkbase cluster info for tenant({bk_tenant_id}) with {storage_config['kind']}, found {len(clusters)} clusters."
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
        logger.error(f"no vm cluster found for tenant({bk_tenant_id}), contact bkbase support.")
        raise ValueError(f"no  vm cluster found for tenant({bk_tenant_id}), contact bkbase support.")

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
        logger.info(f"no default vm cluster found for tenant({bk_tenant_id}), set one as default.")
        # 优先设置名字为vm_default的集群为默认集群，如果没有就随便选一个
        default_vm_cluster = vm_cluster_map.get("vm_default")
        if default_vm_cluster:
            default_vm_cluster.is_default_cluster = True
            default_vm_cluster.save()
            logger.info(f"set vm default cluster for tenant({bk_tenant_id}) to {default_vm_cluster.cluster_name}")
        else:
            # 随便选一个
            random_vm_cluster = next(iter(vm_cluster_map.values()))
            random_vm_cluster.is_default_cluster = True
            random_vm_cluster.save()
            logger.info(f"set vm default cluster for tenant({bk_tenant_id}) to {random_vm_cluster.cluster_name}")


def init_tenant(bk_tenant_id: str):
    """初始化租户"""

    # 如果未开启多租户模式，则使用默认租户ID
    if not settings.ENABLE_MULTI_TENANT_MODE:
        bk_tenant_id = DEFAULT_TENANT_ID

    # 初始化存储集群
    logger.info(f"start init tenant({bk_tenant_id})")

    logger.info(f"init cluster for tenant({bk_tenant_id})")

    logger.info(f"start init kafka cluster for tenant({bk_tenant_id})")
    _init_kafka_cluster(bk_tenant_id)

    logger.info(f"start init es cluster for tenant({bk_tenant_id})")
    _init_es_cluster(bk_tenant_id)

    logger.info(f"start init bkbase cluster for tenant({bk_tenant_id})")
    _init_bkbase_cluster(bk_tenant_id)

    logger.info(f"start sync bkcc space for tenant({bk_tenant_id})")
    sync_bkcc_space(bk_tenant_id=bk_tenant_id, create_builtin_data_link_delay=False)
    logger.info(f"init cluster for tenant({bk_tenant_id}) done.")

    # 标记已初始化的租户
    if bk_tenant_id not in settings.INITIALIZED_TENANT_LIST:
        logger.info(f"tenant({bk_tenant_id}) is initialized.")
        settings.INITIALIZED_TENANT_LIST = settings.INITIALIZED_TENANT_LIST + [bk_tenant_id]
    else:
        logger.info(f"tenant({bk_tenant_id}) is already initialized")

    # 如果未开启多租户模式，则创建系统数据链路
    if not settings.ENABLE_MULTI_TENANT_MODE:
        create_single_tenant_system_datalink()
        create_single_tenant_system_proc_datalink()

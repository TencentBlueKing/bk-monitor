import base64
import gzip
import logging
from typing import Any, final

from kubernetes import client

from bk_monitor_base.domains.space.define import SpaceTypeEnum
from bk_monitor_base.infras import third_party_api as api
from bk_monitor_base.infras.constant import DEFAULT_TENANT_ID
from bk_monitor_base.infras.third_party_api.cmdb.api import HostIPParams, HostPropertyFilter, format_ip_filter_rule
from bk_monitor_base.infras.third_party_api.cmdb.entity import Host
from bk_monitor_base.metadata.config import settings
from bk_monitor_base.metadata.constants.bk_collector import BkCollectorComp
from bk_monitor_base.metadata.utils.bcs import BcsKubeClient
from bk_monitor_base.metadata.utils.redis_client import RedisClient
from bk_monitor_base.metadata.utils.space import bk_biz_id_to_space_uid
from bk_monitor_base.metadata.utils.tools import count_md5

logger = logging.getLogger(__name__)


class BkCollectorConfig:
    # bk-collector 插件名称
    PLUGIN_NAME: str = "bk-collector"

    @classmethod
    def get_target_host_in_default_cloud_area(cls) -> list[int]:
        """
        获取全局配置中的主机 ID，这些主机需在默认租户的直连区域下
        """
        bk_host_ids: list[int] = []
        proxy_ips = settings.metadata.custom_report_default_proxy_ip
        if not proxy_ips:
            logger.info("no proxy host in direct area, skip it")
            return bk_host_ids

        ip_filters = format_ip_filter_rule(proxy_ips)
        _, hosts = api.cmdb.list_hosts_without_biz(
            bk_tenant_id=DEFAULT_TENANT_ID, host_property_filter=HostPropertyFilter(condition="AND", rules=ip_filters)
        )
        hosts = [host for host in hosts if host.bk_cloud_id == 0]
        bk_host_ids.extend([host.bk_host_id for host in hosts])
        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_bk_tenant_id(cls, bk_tenant_id: str) -> list[int]:
        """
        获取指定租户下所有的 Proxy 机器列表 (不包含直连区域)
        """
        bk_host_ids = []
        cloud_infos = api.cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        for cloud_info in cloud_infos:
            bk_cloud_id = cloud_info.get("bk_cloud_id", -1)
            # 跳过两个特殊管控区域，0 直连区域，-1 未分配
            if int(bk_cloud_id) in [0, -1]:
                continue

            proxy_list = api.node_man.get_proxies(bk_tenant_id=bk_tenant_id, bk_cloud_id=bk_cloud_id)
            for p in proxy_list:
                if p["status"] != "RUNNING":
                    logger.warning(
                        "proxy({}) can not be use with bk-collector, it's not running".format(p["bk_host_id"])
                    )
                else:
                    bk_host_ids.append(p["bk_host_id"])

        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_biz_id(cls, bk_tenant_id: str, bk_biz_id: int) -> list[int]:
        """
        获取指定租户指定业务下所有 Proxy 机器列表
        """
        space_uid = bk_biz_id_to_space_uid(bk_biz_id)
        space_type = space_uid.split("__")[0]
        if space_type == SpaceTypeEnum.BKSAAS.value:
            return []

        try:
            proxies = api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        except Exception as e:  # pylint: disable=broad-except
            proxies = []
            logger.info(f"get_proxies_by_biz({bk_biz_id}) error ({e})")

        proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
        proxy_hosts: list[Host] = []
        for proxy_biz_id in proxy_biz_ids:
            current_proxy_hosts = api.cmdb.get_host_by_ip(
                bk_tenant_id=bk_tenant_id,
                ips=[
                    HostIPParams(
                        **{
                            "ip": proxy.get("inner_ip", "") or proxy.get("inner_ipv6", ""),
                            "bk_cloud_id": proxy["bk_cloud_id"],
                        }
                    )
                    for proxy in proxies
                    if proxy["bk_biz_id"] == proxy_biz_id
                ],
                bk_biz_id=proxy_biz_id,
            )
            proxy_hosts.extend(current_proxy_hosts)
        return [proxy.bk_host_id for proxy in proxy_hosts]


@final
class BkCollectorClusterConfig:
    GLOBAL_CONFIG_BK_BIZ_ID = 0

    @classmethod
    def get_cluster_mapping(cls):
        """获取由 apm_ebpf 模块发现的集群 id"""

        def decode_redis_value(value):
            """
            解码后的字符串或默认值
            """
            if value is None:
                return None

            if isinstance(value, bytes):
                return value.decode("utf-8")
            else:
                return str(value)

        client = RedisClient.from_envs(prefix="BK_MONITOR_TRANSFER")
        cluster_to_bk_biz_ids = client.smembers(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)

        res = {}
        for i in cluster_to_bk_biz_ids:
            value = decode_redis_value(i)
            if value is not None:
                cluster_id, related_bk_biz_ids = cls._split_value(value)
                if cluster_id and related_bk_biz_ids:
                    old_biz_ids = res.get(cluster_id, {})
                    res[cluster_id] = set(old_biz_ids) | set(related_bk_biz_ids)
        return res

    @classmethod
    def _split_value(cls, value: str) -> tuple[str | None, list[str] | None]:
        c = value.split(":")
        if len(c) != 2:
            return None, None
        return c[0], c[1].split(",")

    @classmethod
    def deploy_to_k8s_with_hash(
        cls, cluster_id: str, config_map: dict[str, Any], protocol: str, namespace: str | None = None
    ):
        """
        Args:
            cluster_id: 集群ID
            config_map: 配置映射，格式为 {config_id: config_content}
            protocol: 协议, json or prometheus
            namespace: 命名空间
        """
        if not config_map:
            logger.info(f"deploy to cluster_id({cluster_id}), but config is empty, skip deployment")
            return

        secret_config = BkCollectorComp.get_secrets_config_map_by_protocol(cluster_id, protocol)
        if not secret_config:
            logger.info(f"protocol({protocol}) has no secret config, please check if your config has been initialized")
            return

        # 按secret分组配置
        secret_groups = {}
        for config_id, sub_config in config_map.items():
            # 先计算MD5哈希值，转换为整数再取模，确保分布更均匀
            secret_index = int(count_md5(config_id), 16) % secret_config["secret_hash_ring_bucket_count"]

            # 根据secret_hash_ring_bucket_count的位数计算需要补零的位数
            max_count = secret_config["secret_hash_ring_bucket_count"]
            zero_padding_width = len(str(max_count))

            # 生成secret名称
            secret_subconfig_name = secret_config["secret_hash_ring_bucket_name_tpl"].format(
                str(secret_index).zfill(zero_padding_width), max_count
            )

            # 计算 secret 中 key 的名字
            subconfig_filename = secret_config["secret_data_key_tpl"].format(config_id)

            # 编码配置内容
            gzip_content = gzip.compress(sub_config.encode())
            b64_content = base64.b64encode(gzip_content).decode()

            secret_groups.setdefault(
                secret_subconfig_name,
                {
                    "secret_config": secret_config,
                    "configs": {},
                },
            )["configs"][subconfig_filename] = {
                "config_id": config_id,
                "content": b64_content,
                "raw_content": sub_config,
            }

        # 批量处理每个secret
        bcs_client = BcsKubeClient(cluster_id)
        if namespace is None:
            namespace = BkCollectorClusterConfig.bk_collector_namespace(cluster_id)
        secret_label_selector = f"{BkCollectorComp.SECRET_COMMON_LABELS},{secret_config.get('secret_extra_label')}"

        # 一次性查询所有相关的secret
        existing_secrets = {}
        try:
            secrets_list = bcs_client.client_request(
                bcs_client.core_api.list_namespaced_secret,
                namespace=namespace,
                label_selector=secret_label_selector,
            )
            if secrets_list and secrets_list.items:
                for secret in secrets_list.items:
                    existing_secrets[secret.metadata.name] = secret
        except Exception as e:
            logger.warning(f"Failed to list secrets in namespace {namespace}: {e}")
            existing_secrets = {}

        for secret_name, group_info in secret_groups.items():
            configs = group_info["configs"]

            # 从已查询的secret中获取
            sec = existing_secrets.get(secret_name)

            if sec is None:
                # 不存在，则创建
                logger.info(
                    f"{cluster_id} {protocol} secret({secret_name}) not exists, create it with {len(configs)} configs."
                )

                secret_data = {}
                for filename, config_info in configs.items():
                    secret_data[filename] = config_info["content"]

                sec = client.V1Secret(
                    type="Opaque",
                    metadata=client.V1ObjectMeta(
                        name=secret_name,
                        namespace=namespace,
                        labels=BkCollectorComp.label_selector_to_dict(secret_label_selector),
                    ),
                    data=secret_data,
                )

                bcs_client.client_request(
                    bcs_client.core_api.create_namespaced_secret,
                    namespace=namespace,
                    body=sec,
                )
                logger.info(
                    f"{cluster_id} {protocol} secret({secret_name}) create successful with {len(configs)} configs."
                )
            else:
                # 存在，检查是否需要更新
                logger.info(f"{cluster_id} {protocol} secret({secret_name}) already exists, checking for updates.")
                need_update = False

                if not isinstance(sec.data, dict):
                    sec.data = {}
                    need_update = True

                # 检查每个配置是否需要更新
                for filename, config_info in configs.items():
                    config_id = config_info["config_id"]
                    new_content = config_info["content"]
                    raw_content = config_info["raw_content"]

                    if filename not in sec.data:
                        logger.info(f"{cluster_id} {protocol} config({config_id}) not exists in secret, adding it.")
                        sec.data[filename] = new_content
                        need_update = True
                    else:
                        # 比较内容是否有变化
                        try:
                            old_content = sec.data.get(filename, "")
                            old_raw_content = gzip.decompress(base64.b64decode(old_content)).decode()
                            if old_raw_content != raw_content:
                                logger.info(f"{cluster_id} {protocol} config({config_id}) has changed, updating it.")
                                sec.data[filename] = new_content
                                need_update = True
                        except Exception as e:
                            logger.warning(f"failed to decode old content for config({config_id}): {e}, updating it.")
                            sec.data[filename] = new_content
                            need_update = True

                if need_update:
                    bcs_client.client_request(
                        bcs_client.core_api.patch_namespaced_secret,
                        name=sec.metadata.name,
                        namespace=namespace,
                        body=sec,
                    )
                    logger.info(f"{cluster_id} {protocol} secret({secret_name}) update successful.")
                else:
                    logger.info(f"{cluster_id} {protocol} secret({secret_name}) has not been modified.")

        logger.info(
            f"cluster({cluster_id}) batch deployment completed, processed {len(secret_groups)} secrets with total {len(config_map)} configs."
        )

        # 该逻辑会需要保留一段时间后清理  2025-09-24，半年后可删除该逻辑
        cls.clean_dup_secrets(cluster_id, protocol)

    @classmethod
    def clean_dup_secrets(cls, cluster_id: str, protocol: str):
        """
        - 根据 protocol 查到集群内所有的 secrets
            - 转换为 子配置文件  -> secrets 的对应关系
            - 如果同一个子配置同时存在多个 secrets 中，则执行清理动作
                - 只保留最新的 secrets 记录，清理掉其他 secrets 中的单个子配置记录
            - 如果一个 secrets 中所有的子记录都被清理了。则该 secrets 可以被整体删除
        """

        secret_config = BkCollectorComp.get_secrets_config_map_by_protocol(cluster_id, protocol)
        if not secret_config:
            logger.info(f"protocol({protocol}) has no secret config, please check if your config has been initialized")
            return

        # 查询集群内所有 secrets
        bcs_client = BcsKubeClient(cluster_id)
        namespace = BkCollectorClusterConfig.bk_collector_namespace(cluster_id)
        secret_label_selector = f"{BkCollectorComp.SECRET_COMMON_LABELS},{secret_config.get('secret_extra_label')}"

        try:
            exists_secrets_obj = bcs_client.client_request(
                bcs_client.core_api.list_namespaced_secret,
                namespace=namespace,
                label_selector=secret_label_selector,
            )
        except Exception as e:
            logger.warning(f"[clean dup secrets] failed to list secrets in namespace {namespace}: {e}")
            return

        if not exists_secrets_obj or not exists_secrets_obj.items:
            logger.info(f"[clean dup secrets] cluster_id {cluster_id} has no secrets")
            return

        # 构造 配置文件 -> secrets 的对应关系
        secret_file_to_secret = {}
        sub_config_file_to_secrets = {}
        for secret in exists_secrets_obj.items:
            secret_name = secret.metadata.name
            secret_create_timestamp = secret.metadata.creation_timestamp
            secret_file_to_secret[secret_name] = secret

            if not secret.data or not isinstance(secret.data, dict):
                continue

            for config_file in secret.data:
                sub_config_file_to_secrets.setdefault(config_file, []).append((secret_name, secret_create_timestamp))

        # do clean
        need_update_secrets = {}
        for sub_config_file, secrets in sub_config_file_to_secrets.items():
            if len(secrets) <= 1:
                continue

            sort_secrets = sorted(secrets, key=lambda x: x[1])
            for secret_name, _ in sort_secrets[:-1]:
                need_update_secrets[secret_name] = True
                del secret_file_to_secret[secret_name].data[sub_config_file]

        logger.info(
            f"[clean dup secrets] cluster_id({cluster_id}) protocol({protocol}) delete {len(need_update_secrets)} secrets"
        )
        if len(need_update_secrets) > 10:
            logger.error(
                f"[clean dup secrets] cluster_id {cluster_id} delete {len(need_update_secrets)} secrets more than 10. do nothing"
            )
            return

        for need_update_sec_file in need_update_secrets.keys():
            secret = secret_file_to_secret[need_update_sec_file]
            if not secret.data:
                # delete secret
                logger.info(f"[clean dup secrets] cluster_id {cluster_id} delete secret {need_update_sec_file} start")
                bcs_client.client_request(
                    bcs_client.core_api.delete_namespaced_secret,
                    name=secret.metadata.name,
                    namespace=namespace,
                    body=secret,
                )
                logger.info(f"[clean dup secrets] cluster_id {cluster_id} delete secret {need_update_sec_file} ok")
            else:
                # update secret
                bcs_client.client_request(
                    bcs_client.core_api.replace_namespaced_secret,
                    name=secret.metadata.name,
                    namespace=namespace,
                    body=secret,
                )
                logger.info(f"[clean dup secrets] cluster_id {cluster_id} update secret {need_update_sec_file}")

    @classmethod
    def bk_collector_namespace(cls, cluster_id):
        cluster_namespace = settings.metadata.k8s_operator_deploy_namespace or {}
        return cluster_namespace.get(cluster_id, BkCollectorComp.NAMESPACE)

    @classmethod
    def sub_config_tpl(cls, cluster_id: str, sub_config_tpl_name: str):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=cls.bk_collector_namespace(cluster_id),
            label_selector="component=bk-collector,template=true,type=subconfig",
        )
        if config_maps is None or len(config_maps.items) == 0:
            return None

        content = b""
        for item in config_maps.items:
            if not item.data:
                continue

            content = item.data.get(sub_config_tpl_name)
            if content:
                break

        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"[BkCollectorClusterConfig] parse {sub_config_tpl_name} failed: cluster({cluster_id}), error({e})"
            )

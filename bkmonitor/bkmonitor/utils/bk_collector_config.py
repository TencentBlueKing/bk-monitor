"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import logging

from django.conf import settings
from kubernetes import client

from bkmonitor.utils.bcs import BcsKubeClient
from bkmonitor.utils.common_utils import safe_int
from constants.bk_collector import BkCollectorComp
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger(__name__)


class BkCollectorConfig:
    # bk-collector 插件名称
    PLUGIN_NAME = "bk-collector"

    @classmethod
    def get_target_host_in_default_cloud_area(cls) -> list[int]:
        """
        获取全局配置中的主机 ID，这些主机需在默认租户的直连区域下
        """
        bk_host_ids = []
        proxy_ips = settings.CUSTOM_REPORT_DEFAULT_PROXY_IP
        if not proxy_ips:
            logger.info("no proxy host in direct area, skip it")
            return bk_host_ids

        hosts = api.cmdb.get_host_without_biz(bk_tenant_id=DEFAULT_TENANT_ID, ips=proxy_ips)["hosts"]
        hosts = [host for host in hosts if host["bk_cloud_id"] == 0]
        bk_host_ids.extend([host["bk_host_id"] for host in hosts])
        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_bk_tenant_id(cls, bk_tenant_id) -> list[int]:
        """
        获取指定租户下所有的 Proxy 机器列表 (不包含直连区域)
        """
        bk_host_ids = []
        cloud_infos = api.cmdb.search_cloud_area(bk_tenant_id=bk_tenant_id)
        for cloud_info in cloud_infos:
            bk_cloud_id = cloud_info.get("bk_cloud_id", -1)
            if int(bk_cloud_id) == 0:
                continue

            proxy_list = api.node_man.get_proxies(bk_cloud_id=bk_cloud_id)
            for p in proxy_list:
                if p["status"] != "RUNNING":
                    logger.warning(
                        "proxy({}) can not be use with bk-collector, it's not running".format(p["bk_host_id"])
                    )
                else:
                    bk_host_ids.append(p["bk_host_id"])

        return bk_host_ids

    @classmethod
    def get_target_host_ids_by_biz_id(cls, bk_tenant_id, bk_biz_id) -> list[int]:
        """
        获取指定租户指定业务下所有 Proxy 机器列表
        """
        proxies = api.node_man.get_proxies_by_biz(bk_tenant_id=bk_tenant_id, bk_biz_id=bk_biz_id)
        proxy_biz_ids = {proxy["bk_biz_id"] for proxy in proxies}
        proxy_hosts = []
        for proxy_biz_id in proxy_biz_ids:
            current_proxy_hosts = api.cmdb.get_host_by_ip(
                ips=[
                    {
                        "ip": proxy.get("inner_ip", "") or proxy.get("inner_ipv6", ""),
                        "bk_cloud_id": proxy["bk_cloud_id"],
                    }
                    for proxy in proxies
                    if proxy["bk_biz_id"] == proxy_biz_id
                ],
                bk_biz_id=proxy_biz_id,
            )
            proxy_hosts.extend(current_proxy_hosts)
        return [proxy.bk_host_id for proxy in proxy_hosts]


class BkCollectorClusterConfig:
    GLOBAL_CONFIG_BK_BIZ_ID = 0

    @classmethod
    def get_cluster_mapping(cls):
        """获取由 apm_ebpf 模块发现的集群 id"""
        from alarm_backends.core.storage.redis import Cache

        cache = Cache("cache")
        cluster_to_bk_biz_ids = cache.smembers(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)

        res = {}
        for i in cluster_to_bk_biz_ids:
            cluster_id, related_bk_biz_ids = cls._split_value(i)
            if cluster_id and related_bk_biz_ids:
                res[cluster_id] = related_bk_biz_ids

        return res

    @classmethod
    def bk_collector_namespace(cls, cluster_id):
        cluster_namespace = settings.K8S_OPERATOR_DEPLOY_NAMESPACE or {}
        return cluster_namespace.get(cluster_id, BkCollectorComp.NAMESPACE)

    @classmethod
    def platform_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=cls.bk_collector_namespace(cluster_id),
            label_selector="component=bk-collector,template=true,type=platform",
        )
        if config_maps is None or len(config_maps.items) == 0:
            return None

        content = config_maps.items[0].data.get(BkCollectorComp.CONFIG_MAP_PLATFORM_TPL_NAME)
        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(
                f"[BkCollectorClusterConfig] parse platform_config_tpl failed: cluster({cluster_id}), error({e})"
            )

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

        content = ""
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

    @classmethod
    def _split_value(cls, value):
        c = value.split(":")
        if len(c) != 2:
            return None, None
        return c[0], c[1].split(",")

    @classmethod
    def _find_secrets_in_boundary(cls, _secrets: client.V1SecretList, config_id: int):
        """
        判断 config_id 是否在某个 secrets 的大小边界内，但并不代表该配置一定存在
        如果存在，则返回 sec 对象
        如果不存在，则返回 None
        """
        for _sec in _secrets.items:
            if not isinstance(_sec.data, dict):
                continue

            splits = _sec.metadata.name.rsplit("-", 2)
            if len(splits) != 3:
                continue

            _, min_bound, max_bound = splits
            if safe_int(min_bound) <= int(config_id) <= safe_int(max_bound):
                return _sec

    @classmethod
    def deploy_to_k8s(cls, cluster_id: str, config_id: int, protocol: str, sub_config: str):
        secret_config = BkCollectorComp.SECRET_SUBCONFIG_MAP.get(protocol)
        if secret_config is None:
            logger.info(f"protocol{protocol} has no secret config, do nothing")
            return

        # 计算配置所在的 secret 名字
        # 1-20, 21-40, 41-60, ......
        secret_config_max_count = secret_config["secret_data_max_count"]
        count_boundary = (config_id - 1) // secret_config_max_count
        min_boundary = count_boundary * secret_config_max_count + 1
        max_boundary = (count_boundary + 1) * secret_config_max_count
        secret_subconfig_name = secret_config["secret_name_tpl"].format(min_boundary, max_boundary)

        # 计算 secret 中 key 的名字
        subconfig_filename = secret_config["secret_data_key_tpl"].format(config_id)

        # 编码配置内容
        gzip_content = gzip.compress(sub_config.encode())
        b64_content = base64.b64encode(gzip_content).decode()

        # 下发
        bcs_client = BcsKubeClient(cluster_id)
        namespace = BkCollectorClusterConfig.bk_collector_namespace(cluster_id)
        label_source = BkCollectorComp.LABEL_SOURCE_MAP.get(protocol, BkCollectorComp.LABEL_SOURCE_DEFAULT)
        secrets = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_secret,
            namespace=namespace,
            label_selector=f"component={BkCollectorComp.LABEL_COMPONENT_VALUE},template=false,type={BkCollectorComp.LABEL_TYPE_SUB_CONFIG},source={label_source}",
        )
        sec = cls._find_secrets_in_boundary(secrets, config_id)
        if sec is None:
            # 不存在，则创建
            logger.info(f"{cluster_id} {protocol} config({config_id}) not exists, create it.")
            sec = client.V1Secret(
                type="Opaque",
                metadata=client.V1ObjectMeta(
                    name=secret_subconfig_name,
                    namespace=namespace,
                    labels={
                        "component": BkCollectorComp.LABEL_COMPONENT_VALUE,
                        "type": BkCollectorComp.LABEL_TYPE_SUB_CONFIG,
                        "template": "false",
                        "source": label_source,
                    },
                ),
                data={subconfig_filename: b64_content},
            )

            bcs_client.client_request(
                bcs_client.core_api.create_namespaced_secret,
                namespace=namespace,
                body=sec,
            )
            logger.info(f"{cluster_id} {protocol} config ({config_id}) create successful.")
        else:
            # 存在，且与已有的数据不一致，则更新
            logger.info(f"{cluster_id} {protocol} config ({config_id}) secrets already exists.")
            need_update = False
            if isinstance(sec.data, dict):
                if subconfig_filename not in sec.data:
                    logger.info(f"{cluster_id} {protocol} config ({config_id})  not exists, but secret exists.")
                    sec.data[subconfig_filename] = b64_content
                    need_update = True

                old_content = sec.data.get(subconfig_filename, "")
                old_application_config = gzip.decompress(base64.b64decode(old_content)).decode()
                if old_application_config != sub_config:
                    logger.info(f"{cluster_id} {protocol} config ({config_id}) has changed, update it.")
                    sec.data[subconfig_filename] = b64_content
                    need_update = True
            else:
                logger.info(f"{cluster_id} {protocol} config ({config_id}) not exists, secret exists but not valid.")
                sec.data = {subconfig_filename: b64_content}
                need_update = True

            if need_update:
                bcs_client.client_request(
                    bcs_client.core_api.patch_namespaced_secret,
                    name=sec.metadata.name,
                    namespace=namespace,
                    body=sec,
                )
                logger.info(f"{cluster_id} {protocol} config ({config_id}) update successful.")

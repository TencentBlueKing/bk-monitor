# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2022 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import base64
import gzip
import logging

from kubernetes import client

from alarm_backends.core.storage.redis import Cache
from bkmonitor.utils.bcs import BcsKubeClient
from constants.apm import BkCollectorComp

logger = logging.getLogger("apm")


class ClusterConfig:
    @classmethod
    def get_cluster_mapping(cls):
        """获取由 apm_ebpf 模块发现的集群 id"""
        cache = Cache("cache")
        with cache.pipeline() as p:
            p.smembers(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)
            p.delete(BkCollectorComp.CACHE_KEY_CLUSTER_IDS)
            values = p.execute()
        cluster_to_bk_biz_ids = values[0]

        res = {}
        for i in cluster_to_bk_biz_ids:
            cluster_id, related_bk_biz_ids = cls._split_value(i)
            if cluster_id and related_bk_biz_ids:
                res[cluster_id] = related_bk_biz_ids

        return res

    @classmethod
    def deploy_platform_config(cls, cluster_id, platform_config):
        gzip_content = gzip.compress(platform_config.encode())
        b64_content = base64.b64encode(gzip_content)

        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_secret,
            namespace=BkCollectorComp.NAMESPACE,
            label_selector="component={},template=false,type={}".format(
                BkCollectorComp.LABEL_COMPONENT_VALUE,
                BkCollectorComp.LABEL_TYPE_PLATFORM_CONFIG,
            ),
        )
        if len(config_maps.items) > 0:
            # 存在，且与已有的数据不一致，则更新
            need_update = False
            sec = config_maps.items[0]
            if isinstance(sec.data, dict):
                old_content = sec.data.get(BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME, "")
                if old_content != b64_content:
                    need_update = True
            else:
                need_update = True

            if need_update:
                sec.data = {BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME: b64_content}
                bcs_client.client_request(
                    bcs_client.core_api.patch_namespaced_secret,
                    name=BkCollectorComp.SECRET_PLATFORM_NAME,
                    namespace=BkCollectorComp.NAMESPACE,
                    body=sec,
                )
        else:
            # 不存在，则创建
            sec = client.V1Secret(
                type="Opaque",
                metadata=client.V1ObjectMeta(
                    name=BkCollectorComp.SECRET_PLATFORM_NAME,
                    labels={
                        "component": BkCollectorComp.LABEL_COMPONENT_VALUE,
                        "type": BkCollectorComp.LABEL_TYPE_PLATFORM_CONFIG,
                        "template": "false",
                    },
                ),
                data={BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME: b64_content},
            )

            bcs_client.client_request(
                bcs_client.core_api.create_namespaced_secret,
                namespace=BkCollectorComp.NAMESPACE,
                body=sec,
            )

    @classmethod
    def platform_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=BkCollectorComp.NAMESPACE,
            label_selector="component=bk-collector,template=true,type=platform",
        )
        if len(config_maps.items) == 0:
            return None

        content = config_maps.items[0].data.get(BkCollectorComp.CONFIG_MAP_PLATFORM_TPL_NAME)
        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[ClusterConfig] parse platform_config_tpl failed: cluster({cluster_id}), error({e})")

    @classmethod
    def application_config_tpl(cls, cluster_id):
        bcs_client = BcsKubeClient(cluster_id)
        config_maps = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_config_map,
            namespace=BkCollectorComp.NAMESPACE,
            label_selector="component=bk-collector,template=true,type=subconfig",
        )
        if len(config_maps.items) == 0:
            return None

        content = config_maps.items[0].data.get(BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME)
        try:
            return base64.b64decode(content).decode()
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"[ClusterConfig] parse application_config_tpl failed: cluster({cluster_id}), error({e})")

    @classmethod
    def _split_value(cls, value):
        c = value.split(":")
        if len(c) != 2:
            return None, None
        return c[0], c[1].split(",")

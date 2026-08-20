"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

from django.core.cache import cache

from apps.api import BkDataMetaApi, TransferApi
from apps.api.modules.utils import result_table_id_to_bk_biz_id
from apps.log_databus.constants import DORIS_CLUSTER_TYPE
from apps.log_search.models import Space
from apps.utils.log import logger

DORIS_CLUSTER_NAME_ID_MAP_CACHE_KEY = "bklog_doris_cluster_name_id_map_{bk_tenant_id}"
DORIS_CLUSTER_NAME_ID_MAP_CACHE_TIME = 300


class DorisClusterHandler:
    """解析 BkBase 结果表实际所在的 Doris 存储集群。

    注册 Doris 路由时如果不带 cluster_id，metadata 会把存储建到默认 Doris 集群上，
    查询侧再按这个集群下发路由，数据就查不出来。
    """

    @classmethod
    def get_cluster_id(cls, bkbase_table_id: str, fallback_cluster_name: str = "") -> int | None:
        """
        获取 BkBase 结果表对应的 Doris 存储集群 ID
        :param bkbase_table_id: BkBase 结果表 ID
        :param fallback_cluster_name: BkBase 侧查不到存储时使用的集群名，通常来自本地配置
        :return: 存储集群 ID，无法确定时返回 None
        """
        cluster_name = cls.get_bkbase_cluster_name(bkbase_table_id) or fallback_cluster_name
        if not cluster_name:
            logger.warning("[doris_cluster] doris storage not found in bkbase, bkbase_table_id=%s", bkbase_table_id)
            return None

        # 结果表 ID 前缀即业务，租户跟着结果表走，与 BkDataMetaApi 解析租户的口径保持一致
        bk_tenant_id = Space.get_tenant_id(bk_biz_id=result_table_id_to_bk_biz_id(bkbase_table_id))
        cluster_id = cls.get_cluster_name_id_map(bk_tenant_id).get(cluster_name)
        if not cluster_id:
            logger.warning(
                "[doris_cluster] doris cluster(%s) is not registered in metadata, bkbase_table_id=%s, bk_tenant_id=%s",
                cluster_name,
                bkbase_table_id,
                bk_tenant_id,
            )
            return None
        return cluster_id

    @classmethod
    def get_bkbase_cluster_name(cls, bkbase_table_id: str) -> str:
        """查询 BkBase 结果表实际写入的 Doris 集群名"""
        if not bkbase_table_id:
            return ""

        try:
            storages = BkDataMetaApi.result_tables.storages({"result_table_id": bkbase_table_id})
        except Exception:  # pylint: disable=broad-except
            logger.exception("[doris_cluster] get bkbase storages failed, bkbase_table_id=%s", bkbase_table_id)
            return ""

        doris_storage = (storages or {}).get(DORIS_CLUSTER_TYPE) or {}
        return (doris_storage.get("storage_cluster") or {}).get("cluster_name") or ""

    @classmethod
    def get_cluster_name_id_map(cls, bk_tenant_id: str = "") -> dict:
        """获取集群名到存储集群 ID 的映射"""
        # 租户为空时接口会按请求用户态解析，缓存键必须跟着解析结果走，否则多租户会共用同一份集群列表
        bk_tenant_id = bk_tenant_id or Space.get_tenant_id()
        cache_key = DORIS_CLUSTER_NAME_ID_MAP_CACHE_KEY.format(bk_tenant_id=bk_tenant_id)
        name_id_map = cache.get(cache_key)
        if name_id_map:
            return name_id_map

        try:
            cluster_infos = TransferApi.get_cluster_info(
                {"cluster_type": DORIS_CLUSTER_TYPE}, bk_tenant_id=bk_tenant_id
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception("[doris_cluster] get doris cluster info failed, bk_tenant_id=%s", bk_tenant_id)
            return {}

        name_id_map = {}
        for cluster_info in cluster_infos or []:
            cluster_config = cluster_info.get("cluster_config") or {}
            cluster_id = cluster_config.get("cluster_id")
            if not cluster_id:
                continue
            # 集群名不符合 metadata 命名规范时 cluster_name 会被改写成 auto_cluster_name_{id}，
            # 原始名只保留在 display_name 上，两个名字都登记才能匹配上 BkBase 侧返回的集群名
            for cluster_name in (cluster_config.get("cluster_name"), cluster_config.get("display_name")):
                if cluster_name:
                    name_id_map[cluster_name] = cluster_id

        if name_id_map:
            cache.set(cache_key, name_id_map, DORIS_CLUSTER_NAME_ID_MAP_CACHE_TIME)
        return name_id_map

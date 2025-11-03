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

from bkmonitor.utils.tenant import get_tenant_datalink_biz_id
from core.drf_resource import api
from metadata.models.vm.config import BkDataClean, BkDataStorage
from metadata.models.vm.constants import VM_RETENTION_TIME

logger = logging.getLogger("metadata")


class BkDataAccessor:
    """接入计算平台"""

    def __init__(
        self,
        bk_tenant_id: str,
        bk_table_id: str,
        data_hub_name: str,
        timestamp_len: int,
        bk_biz_id: int | None = None,
        vm_cluster: str | None = "",
        vm_retention_time: str | None = VM_RETENTION_TIME,
        desc: str | None = "",
    ):
        """
        :param bk_table_id: 计算平台的结果表 ID
        :param data_hub_name: 接入名称
        :param bk_biz_id: 蓝鲸业务 ID
        :param vm_cluster: vm 集群
        :param vm_retention_time: vm 集群数据保留时间
        :param desc: 接入数据源描述
        :param timestamp_len: 时间长度， 10 秒 13 毫秒 19纳秒
        """
        # 如果没有指定 bk_biz_id，则使用租户下的默认业务
        if not bk_biz_id:
            bk_biz_id = get_tenant_datalink_biz_id(bk_tenant_id).data_biz_id

        self.bk_table_id = bk_table_id
        self.bk_biz_id = bk_biz_id
        self.data_hub_name = data_hub_name
        self.vm_cluster = vm_cluster
        self.vm_retention_time = vm_retention_time
        self.desc = desc
        self.timestamp_len = timestamp_len

    @property
    def raw_data_name(self) -> str:
        return self.bk_table_id

    @property
    def table_name(self) -> str:
        return self.bk_table_id

    @property
    def clean(self):
        """清洗配置"""
        return BkDataClean(
            raw_data_name=self.raw_data_name,
            result_table_name=self.bk_table_id,
            bk_biz_id=self.bk_biz_id,
            timestamp_len=self.timestamp_len,
        ).value

    @property
    def _vm_cluster_name(self):
        """获取 vm 集群"""
        # 如果存在，则直接返回
        if self.vm_cluster:
            return self.vm_cluster
        # 不存在，则查询默认 vm 集群
        from metadata.models import ClusterInfo

        try:
            cluster = ClusterInfo.objects.get(cluster_type=ClusterInfo.TYPE_VM, is_default_cluster=True)
        except ClusterInfo.DoesNotExist:
            logger.error("not found vm default cluster")
            raise ValueError("not found vm default cluster")
        return cluster.cluster_name

    @property
    def storage(self):
        """存储配置"""
        return BkDataStorage(
            bk_table_id=self.bk_table_id,
            vm_cluster=self._vm_cluster_name,
            expires=self.vm_retention_time,
        ).value

    def create(self):
        """接入计算平台"""
        """
        return: 0bkmonitorv3_storage_ieod_bcs_prom_c_40941
        """
        params = {
            "common": {
                "bk_biz_id": self.bk_biz_id,
                "data_scenario": "custom",
            },
            "raw_data": {
                "raw_data_name": self.data_hub_name,
                "raw_data_alias": self.data_hub_name,
                "data_source_tags": ["server"],
                "description": self.desc,
                "data_scenario": {},
            },
            "clean": [self.clean],
            "storage": self.storage,
        }
        try:
            return api.bkdata.create_data_hub(params)
        except Exception as e:
            logger.error("access bkdata error: %s, param: %s", e, json.dumps(params))
            raise


def _access(
    bk_tenant_id: str,
    bk_table_id: str,
    data_hub_name: str,
    desc: str,
    timestamp_len: int,
    vm_cluster: str | None = "",
    vm_retention_time: str | None = VM_RETENTION_TIME,
) -> dict:
    """接入计算平台"""
    accessor = BkDataAccessor(
        bk_tenant_id=bk_tenant_id,
        bk_table_id=bk_table_id,
        data_hub_name=data_hub_name,
        desc=desc,
        timestamp_len=timestamp_len,
        vm_cluster=vm_cluster,
        vm_retention_time=vm_retention_time,
    )
    data = accessor.create()
    # 解析返回，获取计算平台 data id 和
    try:
        bk_data_id = data.get("raw_data_id")
        clean_rt_id = data.get("clean_rt_id")[0]
    except Exception as e:
        logger.error("parse data of accessing bkdata error: %s, data: %s", e, json.dumps(data))
        raise

    return {"bk_data_id": bk_data_id, "clean_rt_id": clean_rt_id}


def access_vm(
    bk_tenant_id: str,
    raw_data_name: str,
    timestamp_len: int,
    vm_cluster: str | None = "",
    vm_retention_time: str | None = VM_RETENTION_TIME,
) -> dict:
    """接入 vm 流程"""
    return _access(
        bk_tenant_id=bk_tenant_id,
        bk_table_id=raw_data_name,
        data_hub_name=raw_data_name,
        desc="接入计算平台 vm",
        timestamp_len=timestamp_len,
        vm_cluster=vm_cluster,
        vm_retention_time=vm_retention_time,
    )

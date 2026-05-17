"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any

from django.db import models

from metadata.models.common import BaseModel
from metadata.models.space.constants import SpaceTypes


class VMShortLinkRecord(BaseModel):
    """VM 短链路接入记录"""

    FILTER_VALUE_SPACE_ID = "space_id"
    FILTER_VALUE_BK_BIZ_ID = "bk_biz_id"
    FILTER_VALUE_CHOICES = {FILTER_VALUE_SPACE_ID, FILTER_VALUE_BK_BIZ_ID}
    DEFAULT_FILTER_KEY = "bk_biz_id"
    DEFAULT_FILTER_VALUE = FILTER_VALUE_BK_BIZ_ID
    QUERY_ROUTER_SPACE_TYPE = "space_type"
    QUERY_ROUTER_FILTER_KEY = "filter_key"
    QUERY_ROUTER_FILTER_VALUE = "filter_value"

    bk_tenant_id = models.CharField("租户ID", max_length=256, null=True, default="system", db_index=True)
    space_type = models.CharField("空间类型", max_length=64, db_index=True)
    space_id = models.CharField("空间ID", max_length=128, db_index=True)
    table_id = models.CharField("虚拟结果表ID", max_length=128, db_index=True)
    vm_result_table_id = models.CharField("VM 结果表ID", max_length=128, db_index=True)
    vm_result_table_name = models.CharField("VM 结果表名称", max_length=255)
    vm_cluster_id = models.IntegerField("VM 集群ID")
    data_labels = models.JSONField("数据标签列表", default=list)
    query_router_config = models.JSONField("查询路由配置", default=dict)
    is_global = models.BooleanField("是否为同类型空间全局表", default=False)
    is_enabled = models.BooleanField("是否启用", default=True)
    is_deleted = models.BooleanField("是否删除", default=False, db_index=True)

    class Meta:
        verbose_name = "VM 短链路接入记录"
        verbose_name_plural = "VM 短链路接入记录"
        unique_together = (("bk_tenant_id", "table_id"), ("bk_tenant_id", "vm_result_table_id"))

    @classmethod
    def normalize_query_router_config(cls, config: dict[str, Any] | None, default_space_type: str) -> dict[str, Any]:
        """标准化查询路由配置，确保只落库当前支持的 filter_value。"""
        config = config or {}
        space_type = config.get(cls.QUERY_ROUTER_SPACE_TYPE) or default_space_type
        valid_space_types = {item.value for item in SpaceTypes}
        if space_type not in valid_space_types:
            raise ValueError(f"query_router_config.space_type: {space_type} is invalid")

        filter_value = config.get(cls.QUERY_ROUTER_FILTER_VALUE) or cls.DEFAULT_FILTER_VALUE
        if filter_value not in cls.FILTER_VALUE_CHOICES:
            raise ValueError(f"query_router_config.filter_value: {filter_value} is invalid")

        return {
            cls.QUERY_ROUTER_SPACE_TYPE: space_type,
            cls.QUERY_ROUTER_FILTER_KEY: config.get(cls.QUERY_ROUTER_FILTER_KEY) or cls.DEFAULT_FILTER_KEY,
            cls.QUERY_ROUTER_FILTER_VALUE: filter_value,
        }

    @property
    def normalized_query_router_config(self) -> dict[str, Any]:
        return self.normalize_query_router_config(self.query_router_config, self.space_type)

    def match_query_router_space_type(self, space_type: str) -> bool:
        router_space_type = self.normalized_query_router_config[self.QUERY_ROUTER_SPACE_TYPE]
        return router_space_type in [SpaceTypes.ALL.value, space_type]

    def get_query_router_filter(self, space_type: str, space_id: str) -> dict[str, Any] | None:
        """按配置生成非归属空间访问全局短链路时的过滤条件。"""
        config = self.normalized_query_router_config
        filter_value_type = config[self.QUERY_ROUTER_FILTER_VALUE]
        if filter_value_type == self.FILTER_VALUE_SPACE_ID:
            filter_value = space_id
        else:
            from metadata.models.space import Space

            filter_value = Space.objects.get_biz_id_by_space(space_type, space_id)
            if filter_value is None:
                return None

        return {config[self.QUERY_ROUTER_FILTER_KEY]: filter_value}

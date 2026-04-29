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
from django.db.models import F
from django.db.models.functions import Greatest

from constants.apm import TelemetryDataType


class BaseSharedDataSource(models.Model):
    """共享数据源池基类。

    管理共享数据源的容量、用量及元数据，按 data_type 扩展子类。
    """

    DEFAULT_QUOTA = 100

    quota = models.IntegerField("容量上限", default=DEFAULT_QUOTA)
    usage_count = models.IntegerField("当前用量", default=0)
    is_enabled = models.BooleanField("是否启用", default=False, db_index=True)
    bk_data_id = models.IntegerField("数据 ID", default=-1)
    result_table_id = models.CharField("结果表 ID", max_length=128, default="")

    class Meta:
        abstract = True

    @property
    def data_name(self) -> str:
        raise NotImplementedError

    @property
    def table_id(self) -> str:
        raise NotImplementedError

    def to_shared_info(self) -> dict[str, Any]:
        """导出共享链路元数据字典。

        子类覆写以追加扩展字段。
        """
        return {
            "bk_data_id": self.bk_data_id,
            "result_table_id": self.result_table_id,
        }

    @classmethod
    def allocate(cls) -> dict[str, Any] | None:
        """从池中选取可用共享源并占用一个槽位。

        使用乐观锁的方式保证并发安全

        :return: 共享链路信息字典，无可用时返回 None。
        """
        candidate = cls.objects.filter(is_enabled=True, usage_count__lt=F("quota")).order_by("usage_count").first()
        if not candidate:
            return None

        # 乐观锁：仅当 usage_count 未变时才占用槽位，计数 +1
        updated = cls.objects.filter(
            pk=candidate.pk,
            usage_count=candidate.usage_count,
        ).update(usage_count=F("usage_count") + 1)

        if not updated:
            # 若被并发抢占，则重试一次
            return cls.allocate()

        return {**candidate.to_shared_info(), "shared_datasource_id": candidate.pk}

    @classmethod
    def reserve(cls) -> "BaseSharedDataSource":
        """创建草稿实例（is_enabled=False）。

        主键即序列号，用于 data_name 和 table_id 的命名构建。
        """
        return cls.objects.create()

    def activate(self, link_info: dict[str, Any]) -> None:
        """填充链路元数据并启用。

        :param link_info: 来自 ApmDataSourceConfigBase.to_link_info() 的字典。
        子类可覆写以处理扩展字段，需先调用 super().activate()。
        """
        self.bk_data_id = link_info["bk_data_id"]
        self.result_table_id = link_info["result_table_id"]
        self.usage_count = 1
        self.is_enabled = True
        self.save()

    def release(self) -> None:
        """释放占用，usage_count 减 1。"""
        self._change_usage_count(-1)

    def acquire(self) -> None:
        """占用槽位，usage_count 加 1。"""
        self._change_usage_count(1)

    def _change_usage_count(self, delta: int) -> None:
        """原子变更 usage_count。

        使用 Greatest 防止 usage_count 变为负数。
        """
        type(self).objects.filter(pk=self.pk).update(
            usage_count=Greatest(F("usage_count") + delta, 0),
        )


class SharedTraceDataSource(BaseSharedDataSource):
    """Trace 共享数据源。

    扩展 BaseSharedDataSource，增加 Trace 数据类型的索引集字段。
    """

    DATA_NAME_PREFIX = "bkapm"
    DATASOURCE_TYPE = TelemetryDataType.TRACE.value

    index_set_id = models.IntegerField("索引集 ID", null=True)
    index_set_name = models.CharField("索引集名称", max_length=512, null=True)

    class Meta:
        verbose_name = "Trace 共享数据源"

    @property
    def data_name(self) -> str:
        return f"{self.DATA_NAME_PREFIX}_shared_{self.DATASOURCE_TYPE}_{self.pk:04d}"

    @property
    def table_id(self) -> str:
        return f"apm_global.shared_{self.DATASOURCE_TYPE}_{self.pk:04d}"

    def to_shared_info(self) -> dict[str, Any]:
        info = super().to_shared_info()
        info["index_set_id"] = self.index_set_id
        info["index_set_name"] = self.index_set_name
        return info

    def activate(self, link_info: dict[str, Any]) -> None:
        """填充链路元数据并启用（含 Trace 特有字段）。"""
        self.index_set_id = link_info.get("index_set_id")
        self.index_set_name = link_info.get("index_set_name")
        super().activate(link_info)


# data_type -> SharedDataSource 子类映射表，后续扩展其他共享数据源类型
SHARED_DS_REGISTRY: dict[str, type[BaseSharedDataSource]] = {
    TelemetryDataType.TRACE.value: SharedTraceDataSource,
}

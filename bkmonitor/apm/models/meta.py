"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.db import models

from bkmonitor.utils.model_manager import AbstractRecordModel
from constants.common import DEFAULT_TENANT_ID


class TraceScopeIndexSet(AbstractRecordModel):
    """Trace 数据源域与 BKLog 索引集的映射。"""

    bk_biz_id = models.IntegerField("业务 ID")
    index_set_id = models.IntegerField("索引集 ID", db_index=True)
    bk_tenant_id = models.CharField("租户 ID", max_length=64, default=DEFAULT_TENANT_ID)

    class Meta:
        unique_together = ("bk_tenant_id", "bk_biz_id")

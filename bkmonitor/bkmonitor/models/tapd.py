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

from constants.common import DEFAULT_TENANT_ID
from bkmonitor.utils.model_manager import AbstractRecordModel

__all__ = ["TapdWorkspaceBinding", "TapdWorkspaceManualUnbind"]


class TapdWorkspaceBinding(AbstractRecordModel):
    """TAPD 项目关联表

    存储 space 与 TAPD 项目的关联关系。
    唯一约束 (bk_tenant_id, space_uid, tapd_workspace_id) 保证幂等。
    一次关联全空间共享，无需重复关联。

    审计注意：
    - `AbstractRecordModel.save()` 会自动将 `request.user` 填入 `create_user`。
    - 在应用态授权回调（B-03）中，`request.user` 是完成授权的管理员，
      真实发起人需从 `signed_state.initiator` 显式覆盖 `create_user`。
    """

    bk_tenant_id = models.CharField("蓝鲸租户ID", max_length=64, default=DEFAULT_TENANT_ID)
    space_uid = models.CharField("蓝鲸空间唯一标识", max_length=128)
    bk_biz_id = models.IntegerField("蓝鲸CMDB业务ID", db_index=True)
    tapd_workspace_id = models.CharField("TAPD项目ID", max_length=64)
    tapd_workspace_name = models.CharField("TAPD项目名称", max_length=255)

    class Meta:
        db_table = "tapd_workspace_binding"
        unique_together = [("bk_tenant_id", "space_uid", "tapd_workspace_id")]
        verbose_name = "TAPD项目关联"
        verbose_name_plural = "TAPD项目关联"


class TapdWorkspaceManualUnbind(AbstractRecordModel):
    """TAPD 项目手动解绑 tombstone 表

    当用户主动点击"取消关联"时写入本表，用于标记"已手动解绑"状态，
    阻止 `try_bind_importable()` 自动重绑，并与"从未关联"区分。

    重新关联时删除本表记录，恢复为正常可自动重绑状态。

    关键约束：
    - 唯一键 `(bk_tenant_id, space_uid, tapd_workspace_id)` 保证幂等。
    - 不存储项目名称等冗余字段，保持轻量。
    """

    bk_tenant_id = models.CharField("蓝鲸租户ID", max_length=64, default=DEFAULT_TENANT_ID)
    space_uid = models.CharField("蓝鲸空间唯一标识", max_length=128)
    bk_biz_id = models.IntegerField("蓝鲸CMDB业务ID", db_index=True)
    tapd_workspace_id = models.CharField("TAPD项目ID", max_length=64)

    class Meta:
        db_table = "tapd_workspace_manual_unbind"
        unique_together = [("bk_tenant_id", "space_uid", "tapd_workspace_id")]
        verbose_name = "TAPD项目手动解绑记录"
        verbose_name_plural = "TAPD项目手动解绑记录"
        ordering = ["-create_time"]

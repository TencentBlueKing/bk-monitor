"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import logging

from django.conf import settings
from django.db import models
from django.db.transaction import atomic

from bkmonitor.utils.cipher import transform_data_id_to_token
from metadata import config
from metadata.models.custom_report.base import CustomGroupBase

logger = logging.getLogger("metadata")


class LogGroup(CustomGroupBase):
    """
    日志分组记录
    """

    log_group_id = models.BigAutoField(verbose_name="分组ID", primary_key=True)
    log_group_name = models.CharField(verbose_name="日志分组名", max_length=255, db_index=True)
    bk_data_token = models.CharField(verbose_name="上报Token", max_length=255, null=True, blank=True)

    GROUP_ID_FIELD = "log_group_id"
    GROUP_NAME_FIELD = "log_group_name"

    @staticmethod
    def make_table_id(bk_biz_id: int, bk_data_id: int, bk_tenant_id: str, table_name: str | None = None) -> str:
        """
        获取表名
        """
        if settings.ENABLE_MULTI_TENANT_MODE:  # 若启用多租户模式,则在结果表前拼接租户ID
            logger.info("make_table_id: enable multi-tenant mode")
            return f"{bk_tenant_id}_{bk_biz_id}_bklog_{table_name}"

        return f"{bk_biz_id}_bklog_{table_name}"

    def to_json(self, with_token=False) -> dict:
        """
        转为JSON格式
        """

        return {
            "log_group_id": self.log_group_id,
            "bk_tenant_id": self.bk_tenant_id,
            "bk_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "table_id": self.table_id,
            "log_group_name": self.log_group_name,
            "label": self.label,
            "is_enable": self.is_enable,
            "bk_data_token": self.bk_data_token if with_token else "",
            "creator": self.creator,
            "create_time": self.create_time.strftime("%Y-%m-%d %H:%M:%S"),
            "last_modify_user": self.last_modify_user,
            "last_modify_time": self.last_modify_time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    @classmethod
    @atomic(config.DATABASE_CONNECTION_NAME)
    def create_log_group(
        cls,
        bk_data_id,
        bk_biz_id,
        log_group_name,
        label,
        operator,
        bk_tenant_id,
        table_id=None,
        max_rate=-1,
    ) -> "LogGroup":
        """
        创建一个新的自定义分组记录
        """

        # 校验参数
        filter_kwargs = cls.pre_check(
            label=label,
            bk_data_id=bk_data_id,
            custom_group_name=log_group_name,
            bk_biz_id=bk_biz_id,
            bk_tenant_id=bk_tenant_id,
        )

        # 创建自定义日志
        table_id, group = cls._create(
            table_id=table_id,
            bk_biz_id=bk_biz_id,
            bk_data_id=bk_data_id,
            custom_group_name=log_group_name,
            label=label,
            is_split_measurement=False,
            operator=operator,
            max_rate=max_rate,
            bk_tenant_id=bk_tenant_id,
            **filter_kwargs,
        )

        # 需要刷新一次外部依赖的consul，触发transfer更新
        from metadata.models import DataSource

        DataSource.objects.get(bk_data_id=bk_data_id, bk_tenant_id=bk_tenant_id).refresh_consul_config()

        # 更新 BkDataToken
        group.bk_data_token = group.get_bk_data_token()
        group.save()

        # 下发配置到 BkCollector
        from metadata.task.tasks import refresh_custom_log_report_config

        refresh_custom_log_report_config.delay(log_group_id=group.log_group_id)

        return group

    @atomic(config.DATABASE_CONNECTION_NAME)
    def modify_log_group(self, operator, label=None, is_enable=None, max_rate=None) -> bool:
        """
        修改一个日志组
        """

        # 不允许修改 log_group_name，避免 bk_data_token 变化
        resp = self.modify_custom_group(
            operator=operator, custom_group_name=None, label=label, is_enable=is_enable, max_rate=max_rate
        )

        # 下发配置到 BkCollector
        from metadata.task.tasks import refresh_custom_log_report_config

        refresh_custom_log_report_config.delay(log_group_id=self.log_group_id)

        return resp

    @atomic(config.DATABASE_CONNECTION_NAME)
    def delete_log_group(self, operator) -> bool:
        """
        删除一个指定的日志组
        """
        return self.delete_custom_group(operator=operator)

    def get_bk_data_token(self) -> str:
        params = {
            "log_data_id": self.bk_data_id,
            "bk_biz_id": self.bk_biz_id,
            "app_name": self.log_group_name,
        }
        return transform_data_id_to_token(**params)

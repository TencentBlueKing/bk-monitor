# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import json
import logging
from typing import Dict, Optional

from django.conf import settings
from django.db import models

from bkmonitor.utils.db import JsonField
from metadata import config
from metadata.models.data_link import constants, utils

logger = logging.getLogger("__name__")


class DataLinkResourceConfig(models.Model):
    """数据链路资源配置"""

    kind = models.CharField("资源类型", max_length=32)
    name = models.CharField("资源名称", max_length=48)
    namespace = models.CharField("命名空间", max_length=64, default=constants.DEFAULT_BKDATA_NAMESPACE)
    value = JsonField("记录对应的资源信息", null=True, blank=True, help_text="比如针对dataid资源记录申请到的数据源ID")
    status = models.CharField("状态", max_length=32, default="ok")
    content = JsonField("资源配置", null=True, blank=True)
    updater = models.CharField("更新者", max_length=32, default=config.DEFAULT_USERNAME)
    creator = models.CharField("创建者", max_length=32, default=config.DEFAULT_USERNAME)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("update time", auto_now=True)

    class Meta:
        verbose_name = "数据源资源配置"
        verbose_name_plural = "数据源资源配置表"

    @classmethod
    def compose_data_id_config(cls, name: str) -> Dict:
        """数据源下发计算平台的资源配置"""
        tpl = """
        {
            "kind": "DataId",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{bk_biz_id}},
                "description": "{{name}}",
                "maintainers": {{maintainers}}
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": constants.DEFAULT_BKDATA_NAMESPACE,
                "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose data_id config",
        )

    @classmethod
    def compose_bkdata_table_id_config(cls, name: str, data_type: Optional[str] = "metric") -> Dict:
        """组装数据源结果表配置"""
        tpl = """
        {
            "kind": "ResultTable",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "alias": "{{name}}",
                "bizId": {{bk_biz_id}},
                "dataType": "{{data_type}}",
                "description": "{{name}}",
                "maintainers": {{maintainers}}
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": constants.DEFAULT_BKDATA_NAMESPACE,
                "bk_biz_id": settings.DEFAULT_BKDATA_BIZ_ID,
                "data_type": data_type,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose bkdata table_id config",
        )

    @classmethod
    def compose_vm_storage_binding(
        cls,
        name: str,
        rt_name: str,
        vm_name: Optional[str] = None,
        space_type: Optional[str] = None,
        space_id: Optional[str] = None,
    ) -> Dict:
        """组装数据源原始数据配置"""
        tpl = """
        {
            "kind": "VmStorageBinding",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "data": {
                    "kind": "ResultTable",
                    "name": "{{rt_name}}",
                    "namespace": "{{namespace}}"
                },
                "maintainers": {{maintainers}},
                "storage": {
                    "kind": "VmStorage",
                    "name": "{{vm_name}}",
                    "namespace": "{{namespace}}"
                }
            }
        }
        """
        from metadata.models.vm.utils import get_vm_cluster_id_name

        vm_cluster = get_vm_cluster_id_name(space_type=space_type, space_id=space_id)
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": constants.DEFAULT_BKDATA_NAMESPACE,
                "rt_name": rt_name,
                "vm_name": vm_name or vm_cluster.get("cluster_name"),
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose vm storage binding config",
        )

    @classmethod
    def compose_vm_databus_config(
        cls,
        name: str,
        vm_binding_name: str,
        data_id_name: str,
        transform_name: Optional[str] = constants.DEFAULT_METRIC_TRANSFORMER,
        transform_format: Optional[str] = constants.DEFAULT_METRIC_TRANSFORM_FORMAT,
    ) -> Dict:
        """通过data_id获取资源配置"""
        tpl = """
        {
            "kind": "Databus",
            "metadata": {
                "name": "{{name}}",
                "namespace": "{{namespace}}"
            },
            "spec": {
                "maintainers": {{maintainers}},
                "sinks": [
                    {
                        "kind": "VmStorageBinding",
                        "name": "{{vm_binding_name}}",
                        "namespace": "{{namespace}}"
                    }
                ],
                "sources": [
                    {
                        "kind": "DataId",
                        "name": "{{data_id_name}}",
                        "namespace": "{{namespace}}"
                    }
                ],
                "transforms": [
                    {
                        "kind": "PreDefinedLogic",
                        "name": "{{transform_name}}",
                        "format": "{{transform_format}}"
                    }
                ]
            }
        }
        """
        maintainer = settings.BK_DATA_PROJECT_MAINTAINER.split(",")
        return utils.compose_config(
            tpl=tpl,
            render_params={
                "name": name,
                "namespace": constants.DEFAULT_BKDATA_NAMESPACE,
                "vm_binding_name": vm_binding_name,
                "data_id_name": data_id_name,
                "transform_name": transform_name,
                "transform_format": transform_format,
                "maintainers": json.dumps(maintainer),
            },
            err_msg_prefix="compose vm databus config",
        )

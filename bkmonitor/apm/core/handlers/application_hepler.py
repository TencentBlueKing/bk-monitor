"""
TencentBlueKing is pleased to support the open source community by making
蓝鲸智云 - Resource SDK (BlueKing - Resource SDK) available.
Copyright (C) 2017-2025 Tencent,
a Tencent company. All rights reserved.
Licensed under the MIT License (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing,
software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
either express or implied. See the License for the
specific language governing permissions and limitations under the License.
We undertake not to change the open source license (MIT license) applicable
to the current version of the project delivered to anyone in the future.
"""

import re
from typing import Any

from django.conf import settings

from apm.models import DataLink
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from bkm_space.utils import bk_biz_id_to_space_uid, is_bk_saas_space
from bkm_space.define import SpaceTypeEnum
from core.drf_resource import resource
from apm.core.handlers.serializers import ApplicationStorageRouteSerializer


class ApplicationHelper:
    DEFAULT_CLUSTER_TYPE = "elasticsearch"
    DEFAULT_CLUSTER_NAME = "_default"
    # 业务下默认应用的应用名称
    DEFAULT_APPLICATION_NAME = "default_app"

    @classmethod
    def get_default_cluster_id(cls, bk_biz_id: int, app_name: str | None = None):
        """
        从DataLink/集群列表中获取默认集群
        """
        if app_name:
            for _route_dict in settings.APM_APP_STORAGE_ROUTES:
                s = ApplicationStorageRouteSerializer(data=_route_dict)
                if not s.is_valid():
                    continue
                route_dict = s.validated_data
                rule_dict: dict[str, Any] = route_dict["rule"]
                if (
                    rule_dict["space_type"] == SpaceTypeEnum.BKSAAS.value
                    and is_bk_saas_space(bk_biz_id_to_space_uid(bk_biz_id))
                    and re.match(rule_dict["name__reg"], app_name)
                ):
                    return route_dict["storage"]["es_storage_cluster_id"]
        datalink = DataLink.get_data_link(bk_biz_id)
        if datalink and datalink.elasticsearch_cluster_id:
            return datalink.elasticsearch_cluster_id

        clusters = resource.metadata.query_cluster_info(
            bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
            cluster_type=cls.DEFAULT_CLUSTER_TYPE,
            # 兼容metadata逻辑
            registered_system=settings.APP_CODE,
        )
        return next(
            (
                i.get("cluster_config").get("cluster_id")
                for i in clusters
                if i.get("cluster_config", {}).get("registered_system") == cls.DEFAULT_CLUSTER_NAME
            ),
            None,
        )

    @classmethod
    def get_default_storage_config(cls, bk_biz_id: int, app_name: str | None = None):
        """获取默认的集群配置"""
        es_storage_cluster = settings.APM_APP_DEFAULT_ES_STORAGE_CLUSTER
        if not es_storage_cluster or es_storage_cluster == -1:
            # 默认集群从集群列表中选择
            default_cluster_id = ApplicationHelper.get_default_cluster_id(bk_biz_id, app_name)
            if default_cluster_id:
                es_storage_cluster = default_cluster_id

        # 填充默认存储集群
        return {
            "es_storage_cluster": es_storage_cluster,
            "es_retention": settings.APM_APP_DEFAULT_ES_RETENTION,
            "es_number_of_replicas": settings.APM_APP_DEFAULT_ES_REPLICAS,
            "es_shards": settings.APM_APP_DEFAULT_ES_SHARDS,
            "es_slice_size": settings.APM_APP_DEFAULT_ES_SLICE_LIMIT,
        }

    @classmethod
    def create_default_application(cls, bk_biz_id):
        """创建默认应用"""

        from apm_web.models import Application

        application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()
        if application:
            # 存在默认应用 直接返回
            return application

        from apm.resources import CreateApplicationSimpleResource

        CreateApplicationSimpleResource()(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME)
        return Application.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()

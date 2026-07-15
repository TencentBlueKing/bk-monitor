"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings

from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from common.log import logger
from core.drf_resource import resource
from rum.constants import RUM_ELASTICSEARCH_CLUSTER_ID


class RumApplicationHelper:
    """
    RUM 应用辅助类，提供默认集群/存储配置的获取逻辑。
    """

    DEFAULT_CLUSTER_TYPE = "elasticsearch"
    DEFAULT_CLUSTER_NAME = "_default"
    DEFAULT_APPLICATION_NAME = "default_rum_app"

    @classmethod
    def get_default_cluster_id(cls, bk_biz_id, app_name=None):
        """
        获取默认 ES 集群 ID。
        """
        # 1. 全局 settings 配置
        rum_es_cluster_id = RUM_ELASTICSEARCH_CLUSTER_ID
        if rum_es_cluster_id:
            return rum_es_cluster_id

        # 2. 回退到 metadata 集群列表
        try:
            clusters = resource.metadata.query_cluster_info(
                bk_tenant_id=bk_biz_id_to_bk_tenant_id(bk_biz_id),
                cluster_type=cls.DEFAULT_CLUSTER_TYPE,
                registered_system=settings.APP_CODE,
            )
            return next(
                (
                    i.get("cluster_config", {}).get("cluster_id")
                    for i in clusters
                    if i.get("cluster_config", {}).get("registered_system") == cls.DEFAULT_CLUSTER_NAME
                ),
                None,
            )
        except Exception as e:
            logger.exception(f"[RumApplicationHelper] get_default_cluster_id failed: {e}")
            return None

    @classmethod
    def get_default_storage_config(cls, bk_biz_id, app_name=None):
        """获取默认的 ES 存储配置, 同apm从全局配置获取"""
        es_storage_cluster = settings.RUM_APP_DEFAULT_ES_STORAGE_CLUSTER

        if not es_storage_cluster or es_storage_cluster == -1:
            default_cluster_id = cls.get_default_cluster_id(bk_biz_id, app_name)
            if default_cluster_id:
                es_storage_cluster = default_cluster_id

        return {
            "es_storage_cluster": es_storage_cluster,
            "es_retention": settings.RUM_APP_DEFAULT_ES_RETENTION,
            "es_number_of_replicas": settings.RUM_APP_DEFAULT_ES_REPLICAS,
            "es_shards": settings.RUM_APP_DEFAULT_ES_SHARDS,
            "es_slice_size": settings.RUM_APP_DEFAULT_ES_SLICE_LIMIT,
        }

    @classmethod
    def create_default_application(cls, bk_biz_id):
        """创建默认应用"""
        from rum.models import RumApplication

        application = RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()
        if application:
            return application

        from rum.resources import CreateApplicationResource

        CreateApplicationResource()(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME)
        return RumApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=cls.DEFAULT_APPLICATION_NAME).first()

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

import logging

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from apm.models import ApmApplication, EbpfApplicationConfig
from bkmonitor.utils.tenant import bk_biz_id_to_bk_tenant_id
from core.drf_resource import resource

logger = logging.getLogger(__name__)


class EbpfHandler:
    DEFAULT_ES_STORAGE_CLUSTER = settings.APM_APP_DEFAULT_ES_STORAGE_CLUSTER
    DEFAULT_ES_RETENTION = settings.APM_APP_DEFAULT_ES_RETENTION
    DEFAULT_ES_NUMBER_OF_REPLICAS = settings.APM_APP_DEFAULT_ES_REPLICAS
    DEFAULT_ES_SHARDS = settings.APM_APP_DEFAULT_ES_SHARDS
    DEFAULT_ES_SLICE_SIZE = settings.APM_APP_DEFAULT_ES_SLICE_LIMIT
    DEFAULT_CLUSTER = "_default"
    CLUSTER_TYPE = "elasticsearch"

    @classmethod
    def _generate_app_name(cls, bk_biz_id):
        return f"__{bk_biz_id}_ebpf_app"

    @classmethod
    def get_default_cluster(cls, bk_tenant_id: str):
        # 从集群列表获取默认集群
        clusters = resource.metadata.query_cluster_info(bk_tenant_id=bk_tenant_id, cluster_type=cls.CLUSTER_TYPE)
        return next(
            (
                i.get("cluster_config").get("cluster_id")
                for i in clusters
                if i.get("cluster_config", {}).get("registered_system") == cls.DEFAULT_CLUSTER
            ),
            None,
        )

    @classmethod
    def create_ebpf_application(cls, bk_biz_id):
        """创建此业务下的ebpf应用"""

        if EbpfApplicationConfig.objects.filter(bk_biz_id=bk_biz_id).exists():
            raise ValueError(_("%s业务下已经有EBPF应用").format(bk_biz_id))

        es_storage_cluster = cls.DEFAULT_ES_STORAGE_CLUSTER
        if not es_storage_cluster or es_storage_cluster == -1:
            # 默认集群从集群列表中选择
            default_cluster = cls.get_default_cluster(bk_biz_id_to_bk_tenant_id(bk_biz_id))
            if default_cluster:
                es_storage_cluster = default_cluster

        params = {
            "bk_biz_id": bk_biz_id,
            "app_name": cls._generate_app_name(bk_biz_id),
            "app_alias": f"业务{bk_biz_id}-ebpf应用",
            "description": "系统自动创建应用",
            "datasource_option": {
                "es_storage_cluster": es_storage_cluster,
                "es_retention": cls.DEFAULT_ES_RETENTION,
                "es_number_of_replicas": cls.DEFAULT_ES_NUMBER_OF_REPLICAS,
                "es_shards": cls.DEFAULT_ES_SHARDS,
                "es_slice_size": cls.DEFAULT_ES_SLICE_SIZE,
            },
        }

        from apm_web.meta.resources import CreateApplicationResource

        instance = CreateApplicationResource()(**params)

        config = EbpfApplicationConfig.objects.create(bk_biz_id=bk_biz_id, application_id=instance.application_id)

        logger.info(f"创建成功 配置id: {config.id} 应用: {instance.app_name}({instance.application_id})")

    @classmethod
    def use_exists_as_ebpf(cls, bk_biz_id, app_name):
        """将一个已存在的应用作为EBPF应用"""

        if EbpfApplicationConfig.objects.filter(bk_biz_id=bk_biz_id).exists():
            raise ValueError(_("%s业务下已经有EBPF应用").format(bk_biz_id))

        instance = ApmApplication.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
        if not instance:
            raise ValueError(_("应用不存在"))

        config = EbpfApplicationConfig.objects.create(bk_biz_id=bk_biz_id, application_id=instance.id)

        logger.info(f"创建成功 配置id: {config.id} 应用: {instance.app_name}({instance.id})")

    @classmethod
    def delete_ebpf_related(cls, bk_biz_id, delete_application=False):
        """将业务下的ebpf应用取消"""

        config = EbpfApplicationConfig.objects.filter(bk_biz_id=bk_biz_id).first()
        if not config:
            raise ValueError(_("业务下无ebpf应用"))

        application_id = config.application_id
        app = ApmApplication.objects.filter(id=application_id).first()
        EbpfApplicationConfig.objects.filter(bk_biz_id=bk_biz_id).delete()

        if app and delete_application:
            from apm_web.meta.resources import DeleteApplicationResource

            DeleteApplicationResource()(bk_biz_id=bk_biz_id, app_name=app.app_name)
            logger.info(f"删除应用 {app.app_name}({app.id}) 成功")

        logger.info(f"删除成功 bk_biz_id: {bk_biz_id} delete_application: {delete_application}")

    @classmethod
    def get_ebpf_application(cls, bk_biz_id):
        config = EbpfApplicationConfig.objects.filter(bk_biz_id=bk_biz_id).first()
        if not config:
            return None

        return ApmApplication.objects.filter(id=config.application_id).first()

    @classmethod
    def is_ebpf_application(cls, application):
        return EbpfApplicationConfig.objects.filter(
            bk_biz_id=application.bk_biz_id, application_id=application.id
        ).exists()

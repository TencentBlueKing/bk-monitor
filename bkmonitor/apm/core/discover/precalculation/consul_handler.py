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
import traceback
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any
from urllib.parse import urlunparse

from django.conf import settings

from apm.core.discover.precalculation.task_spec import PreCalculateTaskSpec, PreCalculateTaskSpecProvider
from core.drf_resource import resource
from metadata.models import ClusterInfo
from metadata.utils import consul_tools

logger = logging.getLogger("apm")

# APM CONSUL配置路径
CONSUL_PATH = "{}_{}_{}/{}/data_id/{{data_id}}".format(
    settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, "apm"
)

if TYPE_CHECKING:
    from apm.models import ApmApplication


@dataclass
class ConsulKafkaInfo:
    host: str
    username: str
    password: str
    topic: str


@dataclass
class ConsulEsInfo:
    index_name: str
    host: str
    username: str
    password: str


@dataclass
class ConsulAppInfo:
    token: str
    bk_tenant_id: str
    bk_biz_id: int
    bk_biz_name: Any
    app_id: int
    app_name: str


@dataclass
class ConsulData:
    """
    需要刷新到consul的APM数据结构
    """

    data_id: str
    token: str
    is_shared: bool
    bk_tenant_id: str
    bk_biz_id: int
    bk_biz_name: Any
    app_id: int
    app_name: str
    apps: list[ConsulAppInfo]

    # kafka链接信息
    kafka_info: ConsulKafkaInfo
    # ES查询端信息
    trace_es_info: ConsulEsInfo
    # ES保存端信息
    save_es_info: ConsulEsInfo


class ConsulHandler:
    @classmethod
    def check_update(cls):
        """刷新当前所有应用的dataId至consul中"""
        space_mapping = {i["space_id"]: i for i in resource.metadata.list_spaces().get("list", [])}

        for task_spec in PreCalculateTaskSpecProvider.list_task_specs(
            enabled_only=True,
            require_trace_enabled=False,
            require_metric_enabled=False,
        ):
            cls._check_update_task_spec(task_spec, space_mapping)

        logger.info("check all consul update finished")

    @classmethod
    def _get_space_name(cls, space_mapping, app: "ApmApplication") -> Any:
        return space_mapping[str(app.bk_biz_id)]["space_name"] if str(app.bk_biz_id) in space_mapping else app.bk_biz_id

    @classmethod
    def _build_app_info(cls, space_mapping, application: "ApmApplication") -> ConsulAppInfo:
        return ConsulAppInfo(
            token=application.get_bk_data_token(),
            bk_tenant_id=application.bk_tenant_id,
            bk_biz_id=application.bk_biz_id,
            bk_biz_name=cls._get_space_name(space_mapping, application),
            app_id=application.pk,
            app_name=application.app_name,
        )

    @classmethod
    def _get_info(cls, space_mapping, task_spec: PreCalculateTaskSpec):
        from apm.core.discover.precalculation.storage import PrecalculateStorage

        datasource_info = resource.metadata.query_data_source(bk_data_id=task_spec.data_id)
        if not datasource_info.get("result_table_list"):
            return None

        application = task_spec.primary_app
        result_table_config = datasource_info["result_table_list"][0]["shipper_list"][0]
        result_table_cluster_config = result_table_config["cluster_config"]
        save_storage = PrecalculateStorage(application.bk_biz_id, application.app_name)
        save_storage_info = ClusterInfo.objects.get(
            bk_tenant_id=application.bk_tenant_id, cluster_id=save_storage.storage_cluster_id
        )
        apps = [cls._build_app_info(space_mapping, app) for app in task_spec.apps] if task_spec.is_shared else []

        return ConsulData(
            data_id=task_spec.data_id,
            token=application.get_bk_data_token(),
            is_shared=task_spec.is_shared,
            bk_tenant_id=application.bk_tenant_id,
            bk_biz_id=application.bk_biz_id,
            bk_biz_name=cls._get_space_name(space_mapping, application),
            app_id=application.pk,
            app_name=application.app_name,
            apps=apps,
            kafka_info=ConsulKafkaInfo(
                host=f"{datasource_info['mq_config']['cluster_config']['domain_name']}"
                f":"
                f"{datasource_info['mq_config']['cluster_config']['port']}",
                username=datasource_info["mq_config"]["auth_info"]["username"],
                password=datasource_info["mq_config"]["auth_info"]["password"],
                topic=datasource_info["mq_config"]["storage_config"]["topic"],
            ),
            trace_es_info=ConsulEsInfo(
                index_name=task_spec.trace_result_table_id.replace(".", "_"),
                host=urlunparse(
                    (
                        result_table_cluster_config["schema"] if result_table_cluster_config["schema"] else "http",
                        f"{result_table_cluster_config['domain_name']}:{result_table_cluster_config['port']}",
                        "",
                        "",
                        "",
                        "",
                    )
                ),
                username=result_table_config["auth_info"]["username"],
                password=result_table_config["auth_info"]["password"],
            ),
            save_es_info=ConsulEsInfo(
                index_name=save_storage.origin_index_name,
                host=urlunparse(
                    (
                        save_storage_info.schema if save_storage_info.schema else "http",
                        f"{save_storage_info.domain_name}:{save_storage_info.port}",
                        "",
                        "",
                        "",
                        "",
                    )
                ),
                username=save_storage_info.username,
                password=save_storage_info.password,
            ),
        )

    @classmethod
    def _check_update_task_spec(cls, task_spec: PreCalculateTaskSpec, space_mapping):
        """
        检查任务的 consul 配置是否有更新，若有则刷新配置。
        """
        key = CONSUL_PATH.format(data_id=task_spec.data_id)

        try:
            cur_data = cls._get_info(space_mapping, task_spec)
            if cur_data is None:
                return None
        except Exception as e:  # noqa
            logger.error(
                f"failed to get current consul config! data_id: {task_spec.data_id}. "
                f"error: {e}. stack: {traceback.format_exc()}"
            )
            return None

        consul_tools.HashConsul().put(key, asdict(cur_data))
        logger.info(f"put consul config -> {key}")
        return task_spec.data_id

    @classmethod
    def check_update_by_task_spec(cls, task_spec: PreCalculateTaskSpec):
        space_mapping = {i["space_id"]: i for i in resource.metadata.list_spaces().get("list", [])}
        return cls._check_update_task_spec(task_spec, space_mapping)

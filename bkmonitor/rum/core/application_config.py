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
from opentelemetry import trace

from jinja2.sandbox import SandboxedEnvironment as Environment

from bkmonitor.utils.bk_collector_config import BkCollectorConfig, BkCollectorClusterConfig
from rum.models import RumApplication, RumAppConfig
from rum.constants import ApdexConfigKey
from constants.bk_collector import BkCollectorComp

logger = logging.getLogger("rum")

tracer = trace.get_tracer(__name__)
jinja_env = Environment()


class RumApplicationConfig(BkCollectorConfig):
    def __init__(self, application: RumApplication):
        self._application: RumApplication = application

    @classmethod
    def refresh_k8s(cls, applications: list[RumApplication]) -> None:
        """批量刷新多个应用的 k8s 配置"""
        if not applications:
            return

        # 按业务ID分组，因为不同业务可能需要部署到不同的集群
        biz_applications = {}
        for application in applications:
            bk_biz_id = application.bk_biz_id
            biz_applications.setdefault(bk_biz_id, []).append(application)
        need_deploy_all_biz_ids = [int(i) for i in biz_applications.keys()]
        need_deploy_all_biz_ids += [str(i) for i in biz_applications.keys()]

        cluster_mapping = BkCollectorClusterConfig.get_cluster_mapping()
        cluster_mapping = {k: v for k, v in cluster_mapping.items() if set(need_deploy_all_biz_ids) & set(v)}

        # 补充默认部署集群
        if settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            for cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
                cluster_mapping[cluster_id] = [BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID]

        # 按集群分组配置，实现批量下发
        for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
            with tracer.start_as_current_span(f"cluster-id: {cluster_id}") as s:
                try:
                    application_tpl = BkCollectorClusterConfig.sub_config_tpl(
                        cluster_id, BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME
                    )
                    if not application_tpl:
                        continue

                    # 收集该集群需要部署的所有配置
                    cluster_config_map = {}
                    compiled_template = jinja_env.from_string(application_tpl)
                    for bk_biz_id, biz_application_list in biz_applications.items():
                        need_deploy_bk_biz_ids = {
                            str(bk_biz_id),
                            int(bk_biz_id),
                            BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID,
                        }
                        if not set(need_deploy_bk_biz_ids) & set(cc_bk_biz_ids):
                            continue

                        # 为该业务下的所有应用生成配置
                        for application in biz_application_list:
                            try:
                                application_config_context = cls(application).get_application_config()
                                application_config = compiled_template.render(application_config_context)
                                cluster_config_map[application.id] = application_config
                            except Exception as e:  # pylint: disable=broad-except
                                # 单个失败，继续渲染模板
                                s.record_exception(exception=e)
                                logger.exception(f"generate config for application({application.app_name})")

                    # 批量下发该集群的所有配置
                    if cluster_config_map:
                        BkCollectorClusterConfig.deploy_to_k8s_with_hash(cluster_id, cluster_config_map, "rum")
                        logger.info(f"batch deploy {len(cluster_config_map)} rum configs to k8s cluster({cluster_id})")

                except Exception as e:  # pylint: disable=broad-except
                    s.record_exception(exception=e)
                    logger.exception(f"batch refresh rum application config to k8s({cluster_id})")

    def get_application_config(self):
        """获取应用配置上下文"""
        config = {
            "bk_biz_id": self._application.bk_biz_id,
            "bk_app_name": self._application.app_name,
        }
        config.update(self.get_bk_data_id_config())
        config["bk_data_token"] = self._application.get_bk_data_token()
        config["resource_filter_config_metrics"] = self.get_resource_filter_config_metrics()

        apdex_config = self.get_apdex_config()
        qps_config = self.get_qps_config()

        if apdex_config:
            config["apdex_config"] = apdex_config
        if qps_config:
            config["qps_config"] = qps_config

        return config

    def get_bk_data_id_config(self) -> dict[str, int]:
        data_ids: dict[str, int] = {}
        if not self._application.is_enabled:
            return data_ids
        metric_data_source = self._application.metric_datasource
        if metric_data_source:
            data_ids["metric_data_id"] = metric_data_source.bk_data_id

        rum_data_source = self._application.rum_datasource
        if rum_data_source:
            data_ids["trace_data_id"] = rum_data_source.bk_data_id

        return data_ids

    @staticmethod
    def get_resource_filter_config_metrics():
        """
        维度补充配置
        """
        return {
            "name": "resource_filter/metrics",
            "drop": {"keys": ["resource.bk.data.token", "resource.process.pid", "resource.tps.tenant.id"]},
            "from_token": {"keys": ["app_name"]},
        }

    def get_apdex_config(self, scope_type=RumAppConfig.APPLICATION_LEVEL):
        config_qs = RumAppConfig.configs(
            self._application.bk_biz_id,
            self._application.app_name,
            scope_type,
        ).filter(config_type__startswith="apdex:")
        apdex_config = {"name": "apdex_calculator/rum_apdex_common", "type": "standard", "rules": []}
        for config_obj in config_qs:
            if config_obj.config_type == f"apdex:{ApdexConfigKey.APDEX_VIEW_LOAD}":
                apdex_config["rules"].append(
                    {
                        "kind": "SPAN_KIND_INTERNAL",
                        "predicate_key": "span_name",
                        "predicate_value": "documentLoad",
                        "destination": "rum_view_load_apdex_type",
                        "metric_name": "rum_view_load_apdex",
                        "apdex_t": config_obj.config_value,
                    }
                )
            elif config_obj.config_type == f"apdex:{ApdexConfigKey.APDEX_API_REQUEST}":
                apdex_config["rules"].append(
                    {
                        "kind": "SPAN_KIND_CLIENT",
                        "predicate_key": "attributes.http.method",
                        "destination": "rum_api_request_apdex_type",
                        "metric_name": "rum_api_request_apdex",
                        "apdex_t": config_obj.config_value,
                        "duration": {"start_event": "fetchStart", "end_event": "responseEnd"},
                    }
                )
        return apdex_config

    def get_qps_config(self, scope_type=RumAppConfig.APPLICATION_LEVEL):
        qps_obj = (
            RumAppConfig.configs(
                self._application.bk_biz_id,
                self._application.app_name,
                scope_type,
            )
            .filter(config_type__startswith="qps:")
            .first()
        )

        if not qps_obj:
            return None

        return {"name": "rate_limiter/token_bucket", "type": "token_bucket", "qps": qps_obj.config_value}

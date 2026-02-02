"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import copy
import json
import logging
from collections import defaultdict

from jinja2.sandbox import SandboxedEnvironment as Environment
from django.conf import settings
from opentelemetry import trace

from apm.constants import (
    DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG,
    DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG,
    GLOBAL_CONFIG_BK_BIZ_ID,
    ConfigTypes,
    DEFAULT_APM_APPLICATION_LOGS_ATTRIBUTE_CONFIG,
)
from apm.models import (
    ApdexConfig,
    ApmApplication,
    ApmInstanceDiscover,
    ApmMetricDimension,
    CustomServiceConfig,
    LicenseConfig,
    NormalTypeValueConfig,
    ProbeConfig,
    QpsConfig,
    SamplerConfig,
    SubscriptionConfig,
)
from bkmonitor.utils.bk_collector_config import BkCollectorConfig, BkCollectorClusterConfig
from bkmonitor.utils.common_utils import count_md5
from constants.bk_collector import BkCollectorComp
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger("apm")

tracer = trace.get_tracer(__name__)
jinja_env = Environment()


class ApplicationConfig(BkCollectorConfig):
    PLUGIN_APPLICATION_CONFIG_TEMPLATE_NAME = "bk-collector-application.conf"

    def __init__(self, application):
        self._application: ApmApplication = application

    def refresh(self):
        """[旧] 下发应用配置（通过节点管理）"""
        bk_tenant_id = self._application.bk_tenant_id
        bk_biz_id = self._application.bk_biz_id

        # 1. 获取应用配置上下文
        application_config = self.get_application_config()

        # 2.1 获取指定租户指定业务下的主机
        proxy_target_hosts = self.get_target_host_ids_by_biz_id(bk_tenant_id, bk_biz_id)

        # 2.2 获取默认租户下全局配置中主机配置列表
        default_target_hosts = self.get_target_host_in_default_cloud_area()
        if not default_target_hosts and not proxy_target_hosts:
            logger.info("no bk-collector node, otlp is disabled")
            return

        try:
            # 3. 下发给指定租户下
            if bk_tenant_id == DEFAULT_TENANT_ID:
                self.deploy(bk_tenant_id, application_config, default_target_hosts + proxy_target_hosts)
            else:
                self.deploy(DEFAULT_TENANT_ID, application_config, default_target_hosts)
                self.deploy(bk_tenant_id, application_config, proxy_target_hosts)
        except Exception:  # noqa
            logger.exception("auto deploy bk-collector application config error")

    @classmethod
    def refresh_k8s(cls, applications: list[ApmApplication]) -> None:
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

        cluster_mapping: dict = BkCollectorClusterConfig.get_cluster_mapping()
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
                                application_config_context = cls(application).get_application_config(cluster_id)
                                application_config = compiled_template.render(application_config_context)
                                cluster_config_map[application.id] = application_config
                            except Exception as e:  # pylint: disable=broad-except
                                # 单个失败，继续渲染模板
                                s.record_exception(exception=e)
                                logger.exception(f"generate config for application({application.app_name})")

                    # 批量下发该集群的所有配置
                    if cluster_config_map:
                        BkCollectorClusterConfig.deploy_to_k8s_with_hash(cluster_id, cluster_config_map, "apm")
                        logger.info(f"batch deploy {len(cluster_config_map)} apm configs to k8s cluster({cluster_id})")

                except Exception as e:  # pylint: disable=broad-except
                    s.record_exception(exception=e)
                    logger.exception(f"batch refresh apm application config to k8s({cluster_id})")

    def get_application_config(self, bcs_cluster_id: str | None = None):
        """获取应用配置上下文"""
        config = {
            "bk_biz_id": self._application.bk_biz_id,
            "bk_app_name": self._application.app_name,
        }
        config.update(self.get_bk_data_id_config())
        config["bk_data_token"] = self._application.get_bk_data_token()
        config["resource_filter_config"] = self.get_resource_filter_config()
        config["resource_filter_config_logs"] = self.get_resource_filter_config_logs()
        config["resource_filter_config_metrics"] = self.get_resource_filter_config_metrics(bcs_cluster_id)

        apdex_config = self.get_apdex_config(ApdexConfig.APP_LEVEL)
        sampler_config = self.get_random_sampler_config(ApdexConfig.APP_LEVEL)
        # dimensions_config = self.get_dimensions_config()

        custom_service_config = self.get_custom_service_config()
        qps_config = self.get_qps_config()
        license_config = self.get_license_config()
        queue_config = self.get_queue_config()
        attribute_config = self.get_config(ConfigTypes.DB_CONFIG, DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG)
        attribute_config_logs = self.get_config(
            ConfigTypes.ATTRIBUTES_CONFIG_LOGS, DEFAULT_APM_APPLICATION_LOGS_ATTRIBUTE_CONFIG
        )
        sdk_config, sdk_config_scope = self.get_probe_config()
        db_slow_command_config = self.get_config(
            ConfigTypes.DB_SLOW_COMMAND_CONFIG, DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG
        )

        profiles_drop_sampler_config = self.get_profiles_drop_sampler_config()
        traces_drop_sampler_config = self.get_traces_drop_sampler_config()
        metrics_filter_config = self.get_metrics_filter_config()

        if apdex_config:
            config["apdex_config"] = apdex_config.get(self._application.app_name)
        if sampler_config:
            config["sampler_config"] = sampler_config.get(self._application.app_name)
        # if dimensions_config:
        #     config["dimensions_config"] = dimensions_config
        if custom_service_config:
            config["custom_service_config"] = custom_service_config
        if qps_config:
            config["qps_config"] = qps_config
        if license_config:
            config["license_config"] = license_config
        if profiles_drop_sampler_config:
            config["profiles_drop_sampler_config"] = profiles_drop_sampler_config
        if traces_drop_sampler_config:
            config["traces_drop_sampler_config"] = traces_drop_sampler_config
        if queue_config:
            config["queue_config"] = queue_config

        if attribute_config:
            config["attribute_config"] = attribute_config

        if attribute_config_logs:
            config["attribute_config_logs"] = attribute_config_logs

        if sdk_config and sdk_config_scope:
            config["sdk_config"] = sdk_config
            config["sdk_config_scope"] = sdk_config_scope

        if db_slow_command_config:
            config["db_slow_command_config"] = db_slow_command_config

        if metrics_filter_config:
            config["metrics_filter_config"] = metrics_filter_config

        # 增加all_app_config的配置将覆盖对应的原有配置
        all_app_config = self.get_config(ConfigTypes.ALL_APP_CONFIG, {})
        if all_app_config:
            config.update(all_app_config)

        service_configs = self.get_sub_configs("service_name", ApdexConfig.SERVICE_LEVEL)
        if service_configs:
            config["service_configs"] = service_configs
        instance_configs = self.get_sub_configs("id", ApdexConfig.INSTANCE_LEVEL)
        if instance_configs:
            config["instance_configs"] = instance_configs

        # 增加all_service_configs的配置将覆盖对应的原有的service_configs配置
        all_service_configs = self.get_all_service_configs()
        all_service_configs = self.validate_all_service_configs(all_service_configs)
        if all_service_configs:
            old_service_configs = config.get("service_configs", [])
            config["service_configs"] = self.update_all_configs(old_service_configs, all_service_configs, "unique_key")

        # 增加all_instance_configs的配置将覆盖对应的原有的service_configs配置
        all_instance_configs = self.get_all_instance_configs()
        all_instance_configs = self.validate_all_instance_configs(all_instance_configs)
        if all_instance_configs:
            old_instance_configs = config.get("instance_configs", [])
            config["instance_configs"] = self.update_all_configs(old_instance_configs, all_instance_configs, "id")

        return config

    def get_metrics_filter_config(self) -> dict:
        params = {"bk_biz_id": self._application.bk_biz_id, "app_name": self._application.app_name}
        json_value = NormalTypeValueConfig.get_app_value(**params, config_type=ConfigTypes.CODE_RELABEL_CONFIG)

        if not json_value:
            return {}

        code_relabel_rules = json.loads(json_value)

        if not isinstance(code_relabel_rules, list):
            return {}

        if not code_relabel_rules:
            return {}

        return {"name": "metrics_filter/relabel", "code_relabel": code_relabel_rules}

    def get_bk_data_id_config(self):
        data_ids = {}
        metric_data_source = self._application.metric_datasource
        if self._application.is_enabled_metric and metric_data_source:
            data_ids["metric_data_id"] = metric_data_source.bk_data_id

        log_data_source = self._application.log_datasource
        if self._application.is_enabled_log and log_data_source:
            data_ids["log_data_id"] = log_data_source.bk_data_id

        trace_data_source = self._application.trace_datasource
        if self._application.is_enabled_trace and trace_data_source:
            data_ids["trace_data_id"] = trace_data_source.bk_data_id

        profile_data_source = self._application.profile_datasource
        if self._application.is_enabled_profiling and profile_data_source:
            data_ids["profile_data_id"] = profile_data_source.bk_data_id

        return data_ids

    def get_qps_config(self):
        qps = QpsConfig.get_application_qps(self._application.bk_biz_id, app_name=self._application.app_name)
        if not qps:
            return None

        return {"name": "rate_limiter/token_bucket", "type": "token_bucket", "qps": qps}

    def get_queue_config(self):
        params = {"bk_biz_id": self._application.bk_biz_id, "app_name": self._application.app_name}

        log_size = NormalTypeValueConfig.get_app_value(**params, config_type=ConfigTypes.QUEUE_LOGS_BATCH_SIZE)
        metric_size = NormalTypeValueConfig.get_app_value(**params, config_type=ConfigTypes.QUEUE_METRIC_BATCH_SIZE)
        trace_size = NormalTypeValueConfig.get_app_value(**params, config_type=ConfigTypes.QUEUE_TRACES_BATCH_SIZE)
        profile_size = NormalTypeValueConfig.get_app_value(**params, config_type=ConfigTypes.QUEUE_PROFILES_BATCH_SIZE)

        res = {}
        if log_size:
            res["logs_batch_size"] = log_size
        if metric_size:
            res["metrics_batch_size"] = metric_size
        if trace_size:
            res["traces_batch_size"] = trace_size
        if profile_size:
            res["profiles_batch_size"] = profile_size

        return res

    def get_custom_service_config(self):
        res = []
        query = CustomServiceConfig.objects.filter(
            bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
        )
        for item in query:
            config = CustomServiceConfig.DISCOVER_KEYS[item.type]

            res.append(
                {
                    **config,
                    "type": item.type,
                    "service": item.name,
                    "rule": item.rule,
                    "match_type": item.match_type,
                    **self._get_match_groups(item),
                }
            )

        if not res:
            return {}

        return {"name": "service_discover/common", "rules": res}

    def _get_match_groups(self, item):
        """获取自定义远程服务match_groups"""
        if item.match_type == "auto":
            res = []
            for source, config in CustomServiceConfig.MATCH_GROUPS["auto"].get(item.type, {}).items():
                if source in item.rule["regex"]:
                    res.append({"source": source, "destination": config["destination"]})
            return {"match_groups": res}

        if item.match_type == "manual":
            res = []
            for source, config in CustomServiceConfig.MATCH_GROUPS["manual"].get(item.type, {}).items():
                if source == "service":
                    res.append({"source": source, "destination": config["destination"]})
                else:
                    if source in item.rule:
                        res.append({"source": source, "destination": config["destination"]})
            return {"match_groups": res}

        return {}

    def get_instance_name_config(self):
        """获取应用实例名配置"""
        return list(
            ApmInstanceDiscover.objects.filter(
                bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
            )
            .order_by("rank")
            .values("discover_key", "rank")
        )

    def get_dimensions_config(self):
        """获取应用汇聚维度配置"""
        mapping = {}
        qs = ApmMetricDimension.objects.filter(
            bk_biz_id=self._application.bk_biz_id,
            app_name=self._application.app_name,
        )

        for item in qs:
            # 同一个span_kind和predicate_key进行归类
            mapping.setdefault((item.span_kind, item.predicate_key), []).append(item.dimension_key)

        res = []
        for key, dimensions in mapping.items():
            res.append({"span_kind": key[0], "predicate_key": key[1], "dimensions": dimensions})

        return res

    def get_resource_filter_config(self):
        """获取bk.instance.id是由哪几个字段组成"""
        from apm.models.config import ApmInstanceDiscover

        instance_id_assemble_keys = [
            q.discover_key
            for q in ApmInstanceDiscover.objects.filter(
                bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
            )
        ]
        if not instance_id_assemble_keys:
            instance_id_assemble_keys = [
                q.discover_key for q in ApmInstanceDiscover.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)
            ]
        return {
            "name": "resource_filter/instance_id",
            "assemble": [{"destination": "bk.instance.id", "separator": ":", "keys": instance_id_assemble_keys}],
            "drop": {"keys": ["resource.bk.data.token", "resource.tps.tenant.id"]},
        }

    @staticmethod
    def get_resource_filter_config_logs():
        """
        针对日志数据源 resource 字段处理逻辑
        """
        return {
            "name": "resource_filter/logs",
            "drop": {"keys": ["resource.bk.data.token", "resource.tps.tenant.id"]},
        }

    def get_resource_filter_config_metrics(self, bcs_cluster_id=None):
        """
        维度补充配置
        """
        default_metrics_config = {
            "name": "resource_filter/metrics",
            "drop": {"keys": ["resource.bk.data.token", "resource.process.pid", "resource.tps.tenant.id"]},
            "from_token": {"keys": ["app_name"]},
        }

        if not bcs_cluster_id or bcs_cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            # 中心化集群，可以接收到所有的数据，不对中心化集群做维度补充逻辑
            return default_metrics_config

        enabled_apps = settings.APM_RESOURCE_FILTER_METRICS_ENABLED_APPS

        # 只有在白名单中的应用才启用该功能
        if enabled_apps and self._application.app_name in enabled_apps.get(str(self._application.bk_biz_id), []):
            extra_config = {
                "from_record": [
                    {
                        "source": "request.client.ip",
                        "destination": "resource.net.host.ip",
                    }
                ],
                "from_cache": {"key": "resource.net.host.ip", "cache_name": "k8s_cache"},
            }
            extra_config.update(default_metrics_config)
            return extra_config
        return default_metrics_config

    def get_sub_configs(self, unique_key: str, config_level):
        apdex_configs = self.get_apdex_config(config_level)
        sampler_configs = self.get_random_sampler_config(config_level)
        keys = set(sampler_configs.keys()) | set(apdex_configs.keys())
        configs = []
        for key in sorted(keys):
            config = {}
            apdex_config = apdex_configs.get(key)
            sampler_config = sampler_configs.get(key)
            if apdex_config:
                config["apdex_config"] = apdex_config
            if sampler_config:
                config["sampler_config"] = sampler_config
            config["unique_key"] = key
            configs.append(config)
        return configs

    def get_apdex_config(self, config_level):
        rules = ApdexConfig.configs(self._application.bk_biz_id, self._application.app_name, config_level)
        apdex_config = defaultdict(lambda: {"name": "apdex_calculator/standard", "type": "standard", "rules": []})
        for config in rules:
            apdex_config[config.config_key]["rules"].append(config.to_config_json())
        return apdex_config

    def get_random_sampler_config(self, config_level):
        configs = SamplerConfig.configs(self._application.bk_biz_id, self._application.app_name, config_level)
        sampler_config = {}
        for config in configs:
            sampler_config[config.config_key] = config.to_config_json()
        return sampler_config

    def get_profiles_drop_sampler_config(self):
        return {
            "name": "sampler/drop_profiles",
            "type": "drop",
            "enabled": not self._application.is_enabled_profiling,
        }

    def get_traces_drop_sampler_config(self):
        return {
            "name": "sampler/drop_traces",
            "type": "drop",
            "enabled": not self._application.is_enabled,
        }

    def get_license_config(self):
        license_config = LicenseConfig.get_application_license_config(
            bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
        )
        if not license_config:
            return {}

        return license_config

    def get_config(self, config_type: str, default_config: dict):
        """
        获取配置
        :param config_type: type 类型
        :param default_config: 默认配置
        :return:
        """

        params = {"bk_biz_id": self._application.bk_biz_id, "app_name": self._application.app_name}
        json_value = NormalTypeValueConfig.get_app_value(**params, config_type=config_type)

        if not json_value:
            return {}

        value = json.loads(json_value)

        config = copy.deepcopy(default_config)
        config.update(value)

        return config

    def get_probe_config(self):
        """
        获取探针配置
        :return:
        """

        config = ProbeConfig.get_config(bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name)
        if not config:
            return {}, {}

        sdk_config = self.get_sdk_config(config)
        sdk_config_scope = self.get_sdk_config_scope(config)
        return sdk_config, sdk_config_scope

    @staticmethod
    def get_sdk_config(sdk_config):
        """
        探针配置
        :return:
        """
        res = []
        for rule in sdk_config.rules:
            tem_item = {
                "type": rule.get("type", "Http"),
                "enabled": rule.get("enable", False),
                "target": rule.get("target", ""),
                "field": rule.get("field", ""),
            }
            res.append(tem_item)
        return {"sn": sdk_config.sn, "rules": res}

    @staticmethod
    def get_sdk_config_scope(sdk_config_scope):
        """
        探针配置作用范围
        :return:
        """
        res = []
        for rule in sdk_config_scope.rules:
            tem_item = {
                "type": rule.get("type", "Http"),
                "enabled": rule.get("enable", False),
                "target": rule.get("target", ""),
                "field": rule.get("field", ""),
                "prefix": rule.get("prefix", "custom_tag"),
                "filters": rule.get("filters", []),
            }
            res.append(tem_item)
        return {"name": "probe_filter/common", "rules": res}

    def deploy(self, bk_tenant_id: str, application_config, bk_host_ids: list[int]):
        """
        下发bk-collector的应用配置
        """
        scope = {
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
        }
        subscription_params = {
            "scope": scope,
            "steps": [
                {
                    "id": self.PLUGIN_NAME,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": self.PLUGIN_NAME,
                        "plugin_version": "latest",
                        "config_templates": [
                            {"name": self.PLUGIN_APPLICATION_CONFIG_TEMPLATE_NAME, "version": "latest"}
                        ],
                    },
                    "params": {"context": application_config},
                }
            ],
        }

        application_subscription = SubscriptionConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
        )
        if application_subscription.exists():
            try:
                logger.info("apm application config subscription task already exists.")
                sub_config_obj = application_subscription.first()
                subscription_params["subscription_id"] = sub_config_obj.subscription_id
                subscription_params["run_immediately"] = True

                old_subscription_params_md5 = count_md5(sub_config_obj.config)
                new_subscription_params_md5 = count_md5(subscription_params)
                if old_subscription_params_md5 != new_subscription_params_md5:
                    logger.info("apm application config subscription task config has changed, update it.")
                    result = api.node_man.update_subscription(subscription_params)
                    logger.info(f"update apm application config subscription successful, result:{result}")
                    application_subscription.update(config=subscription_params)
                return sub_config_obj.subscription_id
            except Exception as e:  # noqa
                logger.exception(f"update apm application config subscription error:{e}, params:{subscription_params}")
        else:
            try:
                logger.info("apm application config subscription task not exists, create it.")
                result = api.node_man.create_subscription(subscription_params)
                logger.info(f"create apm application config subscription successful, result:{result}")

                # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                subscription_id = result["subscription_id"]
                SubscriptionConfig.objects.create(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=self._application.bk_biz_id,
                    app_name=self._application.app_name,
                    config=subscription_params,
                    subscription_id=subscription_id,
                )

                result = api.node_man.run_subscription(
                    bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, actions={self.PLUGIN_NAME: "INSTALL"}
                )
                logger.info(f"run apm application config subscription result:{result}")
            except Exception as e:  # noqa
                logger.exception(f"create apm application config subscription error{e}, params:{subscription_params}")

    def get_all_service_configs(self):
        all_service_configs = (
            NormalTypeValueConfig.service_configs(self._application.bk_biz_id, self._application.app_name)
            .filter(config_key=ConfigTypes.ALL_SERVICE_CONFIG, type=ConfigTypes.ALL_SERVICE_CONFIG)
            .first()
        )
        if all_service_configs:
            return json.loads(all_service_configs.value)
        return {}

    def get_all_instance_configs(self):
        all_instance_configs = (
            NormalTypeValueConfig.instance_configs(self._application.bk_biz_id, self._application.app_name)
            .filter(config_key=ConfigTypes.ALL_INSTANCE_CONFIG, type=ConfigTypes.ALL_INSTANCE_CONFIG)
            .first()
        )
        if all_instance_configs:
            return json.loads(all_instance_configs.value)
        return {}

    @classmethod
    def update_all_configs(cls, configs, all_configs, key):
        """使用all_*_configs的配置替换configs中同 key 的配置"""
        help_merge_dict = {configs[key]: configs for configs in configs}
        for all_config in all_configs:
            help_merge_dict[all_config[key]] = all_config
        return list(help_merge_dict.values())

    @classmethod
    def validate_all_service_configs(cls, all_service_configs):
        """检查all_service_configs是否合法并更新键名为‘unique_key’，非法返回空list"""
        if not isinstance(all_service_configs, list):
            return []
        elif not all(x.get("service_name") for x in all_service_configs):
            logger.error("非法的all_service_configs， 有配置缺乏主键：'service_name'")
            return []

        for all_service_config in all_service_configs:
            all_service_config["unique_key"] = all_service_config.pop("service_name")

        return all_service_configs

    @classmethod
    def validate_all_instance_configs(cls, all_service_configs):
        """检查all_instance_configs是否合法，非法返回空list"""
        if not isinstance(all_service_configs, list):
            return []
        elif not all(x.get("id") for x in all_service_configs):
            logger.error("非法的all_service_configs， 有配置缺乏主键：'id'")
            return []
        return all_service_configs

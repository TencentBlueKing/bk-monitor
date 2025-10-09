"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

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


class ApplicationConfig(BkCollectorConfig):
    PLUGIN_APPLICATION_CONFIG_TEMPLATE_NAME = "bk-collector-application.conf"

    # 类级别的模板缓存
    _template_cache = {}
    _jinja_env = Environment()

    def __init__(self, application):
        self._application: ApmApplication = application

    def refresh(self):
        """[旧] 下发应用配置（通过节点管理）"""
        bk_tenant_id = self._application.bk_tenant_id
        bk_biz_id = self._application.bk_biz_id

        # 1. 获取应用配置上下文
        config_cache = self._batch_preload_configs([self._application])
        application_config = self.get_application_config_with_cache(config_cache)

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

        cluster_mapping: dict = BkCollectorClusterConfig.get_cluster_mapping()

        # 补充默认部署集群
        if settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            for cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
                cluster_mapping[cluster_id] = [BkCollectorClusterConfig.GLOBAL_CONFIG_BK_BIZ_ID]

        # 批量预加载所有应用的配置数据
        config_cache = cls._batch_preload_configs(applications)

        # 按集群分组配置，实现批量下发
        for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
            with tracer.start_as_current_span(f"cluster-id: {cluster_id}") as s:
                try:
                    application_tpl = BkCollectorClusterConfig.sub_config_tpl(
                        cluster_id, BkCollectorComp.CONFIG_MAP_APPLICATION_TPL_NAME
                    )
                    if not application_tpl:
                        continue

                    # 使用缓存的编译模板
                    cache_key = f"{cluster_id}:{hash(application_tpl)}"
                    if cache_key not in cls._template_cache:
                        cls._template_cache[cache_key] = cls._jinja_env.from_string(application_tpl)
                    compiled_template = cls._template_cache[cache_key]

                    # 收集该集群需要部署的所有配置
                    cluster_config_map = {}

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
                                # 使用预加载的配置缓存
                                application_config_context = cls(application).get_application_config_with_cache(
                                    config_cache
                                )
                                # 使用预编译的模板
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

    @classmethod
    def _batch_preload_configs(cls, applications: list[ApmApplication]) -> dict:
        """批量预加载所有应用的配置数据，避免N+1查询问题"""
        if not applications:
            return {}

        # 收集所有需要查询的业务ID
        bk_biz_ids = list(set(app.bk_biz_id for app in applications))

        config_cache = {
            "custom_service_configs": {},
            "apdex_configs": {},
            "sampler_configs": {},
            "qps_configs": {},
            "license_configs": {},
            "normal_type_configs": {},
            "probe_configs": {},
            "instance_discover_configs": {},
            "metric_dimension_configs": {},
            "global_instance_discover": None,
        }

        try:
            # 批量查询自定义服务配置
            custom_service_qs = CustomServiceConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in custom_service_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["custom_service_configs"].setdefault(key, []).append(config)

            # 批量查询 Apdex 配置
            apdex_qs = ApdexConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in apdex_qs:
                key = (config.bk_biz_id, config.app_name, config.config_level)
                config_cache["apdex_configs"].setdefault(key, []).append(config)

            # 批量查询采样配置
            sampler_qs = SamplerConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in sampler_qs:
                key = (config.bk_biz_id, config.app_name, config.config_level)
                config_cache["sampler_configs"].setdefault(key, []).append(config)

            # 批量查询 QPS 配置
            qps_qs = QpsConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in qps_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["qps_configs"][key] = config

            # 批量查询许可证配置
            license_qs = LicenseConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in license_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["license_configs"][key] = config

            # 批量查询普通类型值配置
            normal_type_qs = NormalTypeValueConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in normal_type_qs:
                key = (config.bk_biz_id, config.app_name, config.type)
                config_cache["normal_type_configs"][key] = config

            # 批量查询探针配置
            probe_qs = ProbeConfig.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in probe_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["probe_configs"][key] = config

            # 批量查询实例发现配置
            instance_discover_qs = ApmInstanceDiscover.objects.filter(bk_biz_id__in=bk_biz_ids).order_by("rank")
            for config in instance_discover_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["instance_discover_configs"].setdefault(key, []).append(config)

            # 批量查询指标维度配置
            metric_dimension_qs = ApmMetricDimension.objects.filter(bk_biz_id__in=bk_biz_ids)
            for config in metric_dimension_qs:
                key = (config.bk_biz_id, config.app_name)
                config_cache["metric_dimension_configs"].setdefault(key, []).append(config)

            # 查询全局实例发现配置（只需要查询一次）
            global_instance_discover = list(
                ApmInstanceDiscover.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID).values("discover_key")
            )
            config_cache["global_instance_discover"] = [item["discover_key"] for item in global_instance_discover]

        except Exception as e:
            logger.exception(f"batch preload configs error: {e}")

        return config_cache

    def get_application_config_with_cache(self, config_cache: dict):
        """使用预加载的配置缓存获取应用配置上下文"""
        config = {
            "bk_biz_id": self._application.bk_biz_id,
            "bk_app_name": self._application.app_name,
        }
        config.update(self.get_bk_data_id_config())
        config["bk_data_token"] = self._application.get_bk_data_token()
        config["resource_filter_config"] = self.get_resource_filter_config_with_cache(config_cache)
        config["resource_filter_config_logs"] = self.get_resource_filter_config_logs()

        apdex_config = self.get_apdex_config_with_cache(config_cache, ApdexConfig.APP_LEVEL)
        sampler_config = self.get_random_sampler_config_with_cache(config_cache, ApdexConfig.APP_LEVEL)

        custom_service_config = self.get_custom_service_config_with_cache(config_cache)
        qps_config = self.get_qps_config_with_cache(config_cache)
        license_config = self.get_license_config_with_cache(config_cache)
        queue_config = self.get_queue_config_with_cache(config_cache)
        attribute_config = self.get_config_with_cache(
            config_cache, ConfigTypes.DB_CONFIG, DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG
        )
        attribute_config_logs = self.get_config_with_cache(
            config_cache, ConfigTypes.ATTRIBUTES_CONFIG_LOGS, DEFAULT_APM_APPLICATION_LOGS_ATTRIBUTE_CONFIG
        )
        sdk_config, sdk_config_scope = self.get_probe_config_with_cache(config_cache)
        db_slow_command_config = self.get_config_with_cache(
            config_cache, ConfigTypes.DB_SLOW_COMMAND_CONFIG, DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG
        )
        profiles_drop_sampler_config = self.get_profiles_drop_sampler_config()
        traces_drop_sampler_config = self.get_traces_drop_sampler_config()
        metrics_filter_config = self.get_metrics_filter_config_with_cache(config_cache)

        if apdex_config:
            config["apdex_config"] = apdex_config.get(self._application.app_name)
        if sampler_config:
            config["sampler_config"] = sampler_config.get(self._application.app_name)
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

        service_configs = self.get_sub_configs_with_cache(config_cache, "service_name", ApdexConfig.SERVICE_LEVEL)
        if service_configs:
            config["service_configs"] = service_configs
        instance_configs = self.get_sub_configs_with_cache(config_cache, "id", ApdexConfig.INSTANCE_LEVEL)
        if instance_configs:
            config["instance_configs"] = instance_configs

        return config

    def get_metrics_filter_config_with_cache(self, config_cache: dict) -> dict:
        """使用缓存获取指标过滤配置"""
        key = (self._application.bk_biz_id, self._application.app_name, ConfigTypes.CODE_RELABEL_CONFIG)
        config = config_cache["normal_type_configs"].get(key)

        if not config:
            return {}

        try:
            code_relabel_rules = json.loads(config.value)
            if not isinstance(code_relabel_rules, list) or not code_relabel_rules:
                return {}
            return {"name": "metrics_filter/relabel", "code_relabel": code_relabel_rules}
        except (json.JSONDecodeError, TypeError):
            return {}

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

    def get_qps_config_with_cache(self, config_cache: dict):
        """使用缓存获取 QPS 配置"""
        key = (self._application.bk_biz_id, self._application.app_name)
        config = config_cache["qps_configs"].get(key)

        if not config:
            return None

        return {"name": "rate_limiter/token_bucket", "type": "token_bucket", "qps": config.qps}

    def get_queue_config_with_cache(self, config_cache: dict):
        """使用缓存获取队列配置"""
        log_size_key = (self._application.bk_biz_id, self._application.app_name, ConfigTypes.QUEUE_LOGS_BATCH_SIZE)
        metric_size_key = (self._application.bk_biz_id, self._application.app_name, ConfigTypes.QUEUE_METRIC_BATCH_SIZE)
        trace_size_key = (self._application.bk_biz_id, self._application.app_name, ConfigTypes.QUEUE_TRACES_BATCH_SIZE)
        profile_size_key = (
            self._application.bk_biz_id,
            self._application.app_name,
            ConfigTypes.QUEUE_PROFILES_BATCH_SIZE,
        )

        res = {}

        log_config = config_cache["normal_type_configs"].get(log_size_key)
        if log_config:
            res["logs_batch_size"] = int(log_config.value)

        metric_config = config_cache["normal_type_configs"].get(metric_size_key)
        if metric_config:
            res["metrics_batch_size"] = int(metric_config.value)

        trace_config = config_cache["normal_type_configs"].get(trace_size_key)
        if trace_config:
            res["traces_batch_size"] = int(trace_config.value)

        profile_config = config_cache["normal_type_configs"].get(profile_size_key)
        if profile_config:
            res["profiles_batch_size"] = int(profile_config.value)

        return res

    def get_custom_service_config_with_cache(self, config_cache: dict):
        """使用缓存获取自定义服务配置"""
        key = (self._application.bk_biz_id, self._application.app_name)
        configs = config_cache["custom_service_configs"].get(key, [])

        if not configs:
            return {}

        res = []
        for item in configs:
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

    def get_resource_filter_config_with_cache(self, config_cache: dict):
        """使用缓存获取资源过滤配置"""
        key = (self._application.bk_biz_id, self._application.app_name)
        instance_configs = config_cache["instance_discover_configs"].get(key, [])

        if not instance_configs:
            # 使用全局配置
            instance_id_assemble_keys = config_cache["global_instance_discover"] or []
        else:
            instance_id_assemble_keys = [config.discover_key for config in instance_configs]

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

    def get_sub_configs_with_cache(self, config_cache: dict, unique_key: str, config_level):
        """使用缓存获取子配置"""
        apdex_configs = self.get_apdex_config_with_cache(config_cache, config_level)
        sampler_configs = self.get_random_sampler_config_with_cache(config_cache, config_level)
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

    def get_apdex_config_with_cache(self, config_cache: dict, config_level):
        """使用缓存获取 Apdex 配置"""
        key = (self._application.bk_biz_id, self._application.app_name, config_level)
        configs = config_cache["apdex_configs"].get(key, [])

        apdex_config = defaultdict(lambda: {"name": "apdex_calculator/standard", "type": "standard", "rules": []})
        for config in configs:
            apdex_config[config.config_key]["rules"].append(config.to_config_json())
        return apdex_config

    def get_random_sampler_config_with_cache(self, config_cache: dict, config_level):
        """使用缓存获取随机采样配置"""
        key = (self._application.bk_biz_id, self._application.app_name, config_level)
        configs = config_cache["sampler_configs"].get(key, [])

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

    def get_license_config_with_cache(self, config_cache: dict):
        """使用缓存获取许可证配置"""
        key = (self._application.bk_biz_id, self._application.app_name)
        config = config_cache["license_configs"].get(key)

        if not config:
            return {}

        return config.to_config_json()

    def get_config_with_cache(self, config_cache: dict, config_type: str, default_config: dict):
        """使用缓存获取配置"""
        key = (self._application.bk_biz_id, self._application.app_name, config_type)
        config = config_cache["normal_type_configs"].get(key)

        if not config:
            return {}

        try:
            value = json.loads(config.value)
            result_config = default_config.copy()
            result_config.update(value)
            return result_config
        except (json.JSONDecodeError, TypeError):
            return {}

    def get_probe_config_with_cache(self, config_cache: dict):
        """使用缓存获取探针配置"""
        key = (self._application.bk_biz_id, self._application.app_name)
        config = config_cache["probe_configs"].get(key)

        if not config:
            return {}, {}

        sdk_config = self.get_sdk_config(config)
        sdk_config_scope = self.get_sdk_config_scope(config)
        return sdk_config, sdk_config_scope

    def get_config(self, config_type: str, config: dict):
        """
        获取配置
        :param config_type: type 类型
        :param config: 配置
        :return:
        """

        params = {"bk_biz_id": self._application.bk_biz_id, "app_name": self._application.app_name}
        json_value = NormalTypeValueConfig.get_app_value(**params, config_type=config_type)

        if not json_value:
            return {}

        value = json.loads(json_value)

        config.update(value)

        return config

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

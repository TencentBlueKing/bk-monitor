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
from abc import ABC
from collections import defaultdict
from typing import List

from apm.constants import (
    DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG,
    DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG,
    GLOBAL_CONFIG_BK_BIZ_ID,
    ConfigTypes,
)
from apm.core.bk_collector_config import BkCollectorConfig
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
from bkmonitor.utils.common_utils import count_md5
from core.drf_resource import api

logger = logging.getLogger("apm")


class ConfigBuild(ABC):
    def build(self):
        pass


class ApplicationConfig(BkCollectorConfig):
    PLUGIN_APPLICATION_CONFIG_TEMPLATE_NAME = "bk-collector-application.conf"

    def __init__(self, application):
        self._application: ApmApplication = application

    def refresh(self):
        target_hosts = self.get_target_hosts()
        if not target_hosts:
            logger.info("no bk-collector node, otlp is disabled")
            return

        application_config = self.get_application_config()

        try:
            self.deploy(application_config, target_hosts)
        except Exception:  # noqa
            logger.exception("auto deploy bk-collector application config error")

    def get_application_config(self):
        config = {
            "bk_data_token": self._application.get_bk_data_token(),
            "bk_biz_id": self._application.bk_biz_id,
            "bk_app_name": self._application.app_name,
            "resource_filter_config": self.get_resource_filter_config(),
        }

        apdex_config = self.get_apdex_config(ApdexConfig.APP_LEVEL)
        sampler_config = self.get_random_sampler_config(ApdexConfig.APP_LEVEL)
        # dimensions_config = self.get_dimensions_config()

        custom_service_config = self.get_custom_service_config()
        qps_config = self.get_qps_config()
        license_config = self.get_license_config()
        queue_config = self.get_queue_config()
        attribute_config = self.get_config(ConfigTypes.DB_CONFIG, DEFAULT_APM_APPLICATION_ATTRIBUTE_CONFIG)
        sdk_config, sdk_config_scope = self.get_probe_config()
        db_slow_command_config = self.get_config(
            ConfigTypes.DB_SLOW_COMMAND_CONFIG, DEFAULT_APM_APPLICATION_DB_SLOW_COMMAND_CONFIG
        )
        profiles_drop_sampler_config = self.get_profiles_drop_sampler_config()
        traces_drop_sampler_config = self.get_traces_drop_sampler_config()

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

        if sdk_config and sdk_config_scope:
            config["sdk_config"] = sdk_config
            config["sdk_config_scope"] = sdk_config_scope

        if db_slow_command_config:
            config["db_slow_command_config"] = db_slow_command_config

        service_configs = self.get_sub_configs("service_name", ApdexConfig.SERVICE_LEVEL)
        if service_configs:
            config["service_configs"] = service_configs
        instance_configs = self.get_sub_configs("id", ApdexConfig.INSTANCE_LEVEL)
        if instance_configs:
            config["instance_configs"] = instance_configs

        return config

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

        res = {}
        if log_size:
            res["logs_batch_size"] = log_size
        if metric_size:
            res["metrics_batch_size"] = metric_size
        if trace_size:
            res["traces_batch_size"] = trace_size

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
            "drop": {"keys": ["resource.bk.data.token"]},
        }

    def get_sub_configs(self, unique_key: str, config_level):
        apdex_configs = self.get_apdex_config(config_level)
        sampler_configs = self.get_random_sampler_config(config_level)
        keys = set(sampler_configs.keys()) | set(apdex_configs.keys())
        configs = []
        for key in keys:
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

    def deploy(self, application_config, bk_host_ids: List[int]):
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

        applicaiton_subscription = SubscriptionConfig.objects.filter(
            bk_biz_id=self._application.bk_biz_id, app_name=self._application.app_name
        )
        if applicaiton_subscription.exists():
            try:
                logger.info("apm application config subscription task already exists.")
                sub_config_obj = applicaiton_subscription.first()
                subscription_params["subscription_id"] = sub_config_obj.subscription_id
                subscription_params["run_immediately"] = True

                old_subscription_params_md5 = count_md5(sub_config_obj.config)
                new_subscription_params_md5 = count_md5(subscription_params)
                if old_subscription_params_md5 != new_subscription_params_md5:
                    logger.info("apm application config subscription task config has changed, update it.")
                    result = api.node_man.update_subscription(subscription_params)
                    logger.info("update apm application config subscription successful, result:{}".format(result))
                    applicaiton_subscription.update(config=subscription_params)
                return sub_config_obj.subscription_id
            except Exception as e:  # noqa
                logger.exception(
                    "update apm application config subscription error:{}, params:{}".format(e, subscription_params)
                )
        else:
            try:
                logger.info("apm application config subscription task not exists, create it.")
                result = api.node_man.create_subscription(subscription_params)
                logger.info("create apm application config subscription successful, result:{}".format(result))

                # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                subscription_id = result["subscription_id"]
                SubscriptionConfig.objects.create(
                    bk_biz_id=self._application.bk_biz_id,
                    app_name=self._application.app_name,
                    config=subscription_params,
                    subscription_id=subscription_id,
                )

                result = api.node_man.run_subscription(
                    subscription_id=subscription_id, actions={self.PLUGIN_NAME: "INSTALL"}
                )
                logger.info("run apm application config subscription result:{}".format(result))
            except Exception as e:  # noqa
                logger.exception(
                    "create apm application config subscription error{}, params:{}".format(e, subscription_params)
                )

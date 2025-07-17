"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import base64
import gzip
import logging

from jinja2.sandbox import SandboxedEnvironment as Environment
from django.conf import settings
from kubernetes import client
from opentelemetry import trace

from apm.constants import (
    DEFAULT_APM_ATTRIBUTE_CONFIG,
    DEFAULT_APM_PLATFORM_AS_INT_CONFIG,
    DEFAULT_PLATFORM_API_NAME_CONFIG,
    DEFAULT_PLATFORM_LICENSE_CONFIG,
    GLOBAL_CONFIG_BK_BIZ_ID,
)
from apm.core.cluster_config import ClusterConfig
from apm.models import BcsClusterDefaultApplicationRelation
from apm.models.subscription_config import SubscriptionConfig
from bkmonitor.utils.bcs import BcsKubeClient
from bkmonitor.utils.bk_collector_config import BkCollectorConfig
from bkmonitor.utils.common_utils import count_md5
from constants.apm import BkCollectorComp, SpanKindKey
from constants.common import DEFAULT_TENANT_ID
from core.drf_resource import api

logger = logging.getLogger("apm")

tracer = trace.get_tracer(__name__)


class PlatformConfig(BkCollectorConfig):
    """
    平台相关配置生成、下发
    """

    PLUGIN_PLATFORM_CONFIG_TEMPLATE_NAME = "bk-collector-platform.conf"

    def __init__(self, bk_tenant_id: str):
        self.bk_tenant_id = bk_tenant_id

    @classmethod
    def refresh(cls, bk_tenant_id: str):
        """
        [主机下发模式：待废弃] 下发平台默认配置到主机上（通过节点管理）
        按租户：每个租户一份平台配置
        """
        # 1. 获取配置上下文
        platform_config = cls.get_platform_config()

        # 2. 下发给给定租户下
        proxy_bk_host_ids = cls.get_target_host_ids_by_bk_tenant_id(bk_tenant_id)
        try:
            if bk_tenant_id == DEFAULT_TENANT_ID:
                # 如果是 默认租户，需要增加全局配置中的主机
                proxy_bk_host_ids += cls.get_target_host_in_default_cloud_area()
            cls.deploy_to_nodeman(bk_tenant_id, platform_config, proxy_bk_host_ids)
        except Exception:  # noqa
            logger.exception(f"auto deploy TENANT_ID({bk_tenant_id}) bk-collector platform config error")

    @classmethod
    def refresh_k8s(cls):
        """
        下发平台默认配置到 K8S 集群（不区分租户，每个集群一份平台配置）

        # 1. 获取所有集群ID列表
        # 2. 针对每一个集群
        #    2.1 从集群中获取模版配置
        #    2.2 获取到模板，则下发，否则忽略该集群
        """
        cluster_mapping = ClusterConfig.get_cluster_mapping()

        if settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            # 补充中心化集群
            for cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
                cluster_mapping[cluster_id] = [0]

        for cluster_id, cc_bk_biz_ids in cluster_mapping.items():
            with tracer.start_as_current_span(
                f"cluster-id: {cluster_id}", attributes={"bk_biz_ids": cc_bk_biz_ids}
            ) as s:
                try:
                    platform_config_tpl = ClusterConfig.platform_config_tpl(cluster_id)
                    if platform_config_tpl is None:
                        # 如果集群中不存在 bk-collector 的平台配置模版，则不下发
                        continue

                    # bk_biz_id = cc_bk_biz_ids[0]
                    # if len(cc_bk_biz_ids) != 1:
                    #     logger.warning(
                    #         f"[post-deploy-bk_collector] cluster_id: {cluster_id} record multiple bk_biz_id!",
                    #     )

                    # Step1: 创建默认应用
                    # default_application = ApplicationHelper.create_default_application(bk_biz_id)

                    # Step2: 往集群的 bk-collector 下发配置
                    platform_config_context = PlatformConfig.get_platform_config(cluster_id)

                    platform_config = Environment().from_string(platform_config_tpl).render(platform_config_context)
                    PlatformConfig.deploy_to_k8s(cluster_id, platform_config)

                    # s.add_event("default_application", attributes={"id": default_application.id})
                    s.add_event("platform_secret", attributes={"name": BkCollectorComp.SECRET_PLATFORM_NAME})
                    s.set_status(trace.StatusCode.OK)
                except Exception as e:  # pylint: disable=broad-except
                    # 仅记录异常
                    s.record_exception(exception=e)
                    logger.error(f"refresh platform config to cluster: {cluster_id} failed, error: {e}")

    @classmethod
    def get_platform_config(cls, bcs_cluster_id=None):
        plat_config = {
            "apdex_config": cls.get_apdex_config(),
            "sampler_config": cls.get_sampler_config(),
            "token_checker_config": cls.get_token_checker_config(bcs_cluster_id),
            "resource_filter_config": cls.get_resource_filter_config(),
            "qps_config": cls.get_qps_config(),
            "metric_configs": cls.list_metric_config(),
            "license_config": cls.get_license_config(),
            "attribute_config": cls.get_attribute_config(),
        }

        if bcs_cluster_id and bcs_cluster_id not in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            resource_fill_dimensions_config = cls.get_resource_fill_dimensions_config(bcs_cluster_id)
            if resource_fill_dimensions_config:
                plat_config["resource_fill_dimensions_config"] = resource_fill_dimensions_config

        return plat_config

    @classmethod
    def get_attribute_config(cls):
        """attribute_config 信息"""

        attribute_config = DEFAULT_APM_ATTRIBUTE_CONFIG
        attribute_config.update(DEFAULT_APM_PLATFORM_AS_INT_CONFIG)
        if settings.APM_IS_DISTRIBUTE_PLATFORM_API_NAME_CONFIG:
            attribute_config.update(DEFAULT_PLATFORM_API_NAME_CONFIG)
        return attribute_config

    @classmethod
    def list_metric_config(cls):
        """
        获取APM内置指标
        bk_apm_count
        bk_apm_total
        bk_apm_duration
        bk_apm_duration_max
        bk_apm_duration_min
        bk_apm_duration_sum
        bk_apm_duration_bucket
        """
        metric_dimension_rules = cls._list_metric_rules()

        return {
            "metric_bk_apm_count_config": {
                "name": "traces_deriver/delta",
                "operations": [{"metric_name": "bk_apm_count", "type": "delta", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_total_config": {
                "name": "traces_deriver/count",
                "operations": [{"metric_name": "bk_apm_total", "type": "count", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_duration_config": {
                "name": "traces_deriver/duration",
                "operations": [{"metric_name": "bk_apm_duration", "type": "duration", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_duration_max_config": {
                "name": "traces_deriver/max",
                "operations": [{"metric_name": "bk_apm_duration_max", "type": "max", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_duration_min_config": {
                "name": "traces_deriver/min",
                "operations": [{"metric_name": "bk_apm_duration_min", "type": "min", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_duration_sum_config": {
                "name": "traces_deriver/sum",
                "operations": [{"metric_name": "bk_apm_duration_sum", "type": "sum", "rules": metric_dimension_rules}],
            },
            "metric_bk_apm_duration_delta_config": {
                "name": "traces_deriver/delta_duration",
                "operations": [
                    {"metric_name": "bk_apm_duration_delta", "type": "delta_duration", "rules": metric_dimension_rules}
                ],
            },
            "metric_bk_apm_duration_bucket_config": {
                "name": "traces_deriver/bucket",
                "operations": [
                    {
                        "metric_name": "bk_apm_duration_bucket",
                        "type": "bucket",
                        "rules": metric_dimension_rules,
                        # todo buckets 交由用户配置 暂时传递默认值
                        "buckets": [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
                    }
                ],
            },
        }

    @classmethod
    def get_qps_config(cls):
        return {"name": "rate_limiter/token_bucket", "type": "token_bucket", "qps": settings.APM_APP_QPS}

    @classmethod
    def get_apdex_config(cls):
        # 平台默认Apdex配置

        return {
            "name": "apdex_calculator/standard",
            "type": "standard",
            "rules": [
                {
                    "kind": SpanKindKey.UNSPECIFIED,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
                {
                    "kind": SpanKindKey.INTERNAL,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
                {
                    "kind": SpanKindKey.SERVER,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
                {
                    "kind": SpanKindKey.CLIENT,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
                {
                    "kind": SpanKindKey.PRODUCER,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
                {
                    "kind": SpanKindKey.CONSUMER,
                    "predicate_key": "",
                    "metric_name": "bk_apm_duration",
                    "destination": "apdex_type",
                    "apdex_t": settings.APM_APDEX_T_VALUE,  # unit: ms
                },
            ],
        }

    @classmethod
    def get_sampler_config(cls):
        return {
            "name": "sampler/random",
            "type": "random",
            "sampling_percentage": settings.APM_SAMPLING_PERCENTAGE,  # 100%
        }

    @classmethod
    def get_license_config(cls):
        return {"name": "license_checker/common", **DEFAULT_PLATFORM_LICENSE_CONFIG}

    @classmethod
    def get_token_checker_config(cls, bcs_cluster_id=None):
        # 需要判断是否有指定密钥，如有，优先级最高
        x_key = getattr(settings, settings.AES_X_KEY_FIELD)
        if settings.SPECIFY_AES_KEY != "":
            x_key = settings.SPECIFY_AES_KEY

        token_checker_config = {
            "name": "token_checker/aes256",
            "resource_key": "bk.data.token",
            "type": "aes256",
            "version": "v2",
            "salt": settings.BK_DATA_TOKEN_SALT,
            "decoded_key": x_key,
            "decoded_iv": settings.BK_DATA_AES_IV.decode()
            if isinstance(settings.BK_DATA_AES_IV, bytes)
            else settings.BK_DATA_AES_IV,
        }

        if bcs_cluster_id:
            # 集群内默认上报 APM 应用
            default_app_relation = BcsClusterDefaultApplicationRelation.objects.filter(
                cluster_id=bcs_cluster_id
            ).first()
            if default_app_relation:
                default_app = default_app_relation.application
                if not default_app:
                    logger.info(f"{bcs_cluster_id} relate apm application({default_app_relation.app_name}) not exist")
                else:
                    token_checker_config.update(cls.get_dataids_config_from_application(default_app))

        return token_checker_config

    @classmethod
    def get_dataids_config_from_application(cls, application):
        data_ids = {
            "bk_biz_id": application.bk_biz_id,
            "bk_app_name": application.app_name,
            "fixed_token": application.get_bk_data_token(),
        }
        metric_data_source = application.metric_datasource
        if application.is_enabled_metric and metric_data_source:
            data_ids["metric_data_id"] = metric_data_source.bk_data_id

        log_data_source = application.log_datasource
        if application.is_enabled_log and log_data_source:
            data_ids["log_data_id"] = log_data_source.bk_data_id

        trace_data_source = application.trace_datasource
        if application.is_enabled_trace and trace_data_source:
            data_ids["trace_data_id"] = trace_data_source.bk_data_id

        profile_data_source = application.profile_datasource
        if application.is_enabled_profiling and profile_data_source:
            data_ids["profile_data_id"] = profile_data_source.bk_data_id
        return data_ids

    @classmethod
    def get_resource_fill_dimensions_config(cls, bcs_cluster_id=None):
        """
        维度补充配置（目前先固定返回，暂不支持可配置）
        第一层，先根据上报的客户端IP，填充 resource 下的 net.host.ip 字段（如果不存在则赋值）
        第二层，根据 net.host.ip 字段，继续补充 k8s 下的 pod 相关信息
        """
        if bcs_cluster_id is None:
            return {}

        if bcs_cluster_id in settings.CUSTOM_REPORT_DEFAULT_DEPLOY_CLUSTER:
            # 中心化集群，可以接收到所有的数据，不对中心化集群做维度补充逻辑
            return {}

        bcs_client = BcsKubeClient(bcs_cluster_id)
        svc = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_service,
            namespace=ClusterConfig.bk_collector_namespace(bcs_cluster_id),
            label_selector="app.kubernetes.io/bk-component=bkmonitor-operator",
        )
        count = len(svc.items)
        if count != 1:
            logger.warning(f"The cluster({bcs_cluster_id}) has {count} bkmonitor-operator, it's ambiguous")
            return {}
        operator_service_name = svc.items[0].metadata.name

        cluster_cache_config = settings.K8S_COLLECTOR_CONFIG or {}
        cache_interval = cluster_cache_config.get(bcs_cluster_id, {}).get("cache", {}).get("interval", "10s")

        return {
            "name": "resource_filter/fill_dimensions",
            "from_record": [
                {
                    "source": "request.client.ip",
                    "destination": "resource.net.host.ip",
                }
            ],
            "from_cache": {
                "key": "resource.net.host.ip",
                "dimensions": ["k8s.namespace.name", "k8s.pod.name", "k8s.pod.ip", "k8s.bcs.cluster.id"],
                "cache": {
                    "key": "k8s.pod.ip",
                    "url": f"http://{operator_service_name}:8080/pods",
                    "timeout": "60s",
                    "interval": cache_interval,
                },
            },
        }

    @classmethod
    def get_resource_filter_config(cls):
        """获取bk.instance.id是由哪几个字段组成"""
        from apm.models.config import ApmInstanceDiscover

        instance_id_assemble_keys = [
            q.discover_key for q in ApmInstanceDiscover.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)
        ]
        return {
            "name": "resource_filter/instance_id",
            "assemble": [{"destination": "bk.instance.id", "separator": ":", "keys": instance_id_assemble_keys}],
            "drop": {"keys": ["resource.bk.data.token", "resource.tps.tenant.id"]},
            "default_value": [{"type": "string", "key": "resource.service.name", "value": "unknown_service"}],
        }

    @classmethod
    def _list_metric_rules(cls):
        """获取指标的统一维度"""
        from apm.models.config import ApmMetricDimension

        qs = ApmMetricDimension.objects.filter(bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID)
        metric_dimensions = {}
        for q in qs:
            metric_dimensions.setdefault(q.span_kind, {}).setdefault(q.predicate_key, []).append(q.dimension_key)

        return [
            {"kind": kind, "predicate_key": predicate_key, "dimensions": dimensions}
            for kind, kind_configs in metric_dimensions.items()
            for predicate_key, dimensions in kind_configs.items()
        ]

    @classmethod
    def deploy_to_nodeman(cls, bk_tenant_id, platform_config, bk_host_ids):
        """
        下发bk-collector的平台配置
        """
        if not bk_host_ids:
            logger.info("no bk-collector node, otlp is disabled")
            return

        scope = {
            "object_type": "HOST",
            "node_type": "INSTANCE",
            "nodes": [{"bk_host_id": bk_host_id} for bk_host_id in bk_host_ids],
        }
        subscription_params = {
            "scope": scope,
            "steps": [
                {
                    "id": cls.PLUGIN_NAME,
                    "type": "PLUGIN",
                    "config": {
                        "plugin_name": cls.PLUGIN_NAME,
                        "plugin_version": "latest",
                        "config_templates": [{"name": cls.PLUGIN_PLATFORM_CONFIG_TEMPLATE_NAME, "version": "latest"}],
                    },
                    "params": {"context": platform_config},
                }
            ],
        }

        platform_subscription = SubscriptionConfig.objects.filter(
            bk_tenant_id=bk_tenant_id, bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID, app_name=""
        )
        if platform_subscription.exists():
            try:
                logger.info("apm platform config subscription task already exists.")
                sub_config_obj = platform_subscription.first()
                subscription_params["subscription_id"] = sub_config_obj.subscription_id
                subscription_params["run_immediately"] = True

                old_subscription_params_md5 = count_md5(sub_config_obj.config)
                new_subscription_params_md5 = count_md5(subscription_params)
                if old_subscription_params_md5 != new_subscription_params_md5:
                    logger.info("apm platform config subscription task config has changed, update it.")
                    result = api.node_man.update_subscription(subscription_params)
                    logger.info(f"update apm platform config subscription successful, result:{result}")
                    platform_subscription.update(config=subscription_params)
                return sub_config_obj.subscription_id
            except Exception as e:  # noqa
                logger.exception(f"update apm platform config subscription error:{e}, params:{subscription_params}")
        else:
            try:
                logger.info("apm platform config subscription task not exists, create it.")
                result = api.node_man.create_subscription(subscription_params)
                logger.info(f"create apm platform config subscription successful, result:{result}")

                # 创建订阅成功后，优先存储下来，不然因为其他报错会导致订阅ID丢失
                subscription_id = result["subscription_id"]
                SubscriptionConfig.objects.create(
                    bk_tenant_id=bk_tenant_id,
                    bk_biz_id=GLOBAL_CONFIG_BK_BIZ_ID,
                    app_name="",
                    config=subscription_params,
                    subscription_id=subscription_id,
                )

                result = api.node_man.run_subscription(
                    bk_tenant_id=bk_tenant_id, subscription_id=subscription_id, actions={cls.PLUGIN_NAME: "INSTALL"}
                )
                logger.info(f"run apm platform config subscription result:{result}")
            except Exception as e:  # noqa
                logger.exception(f"create apm platform config subscription error{e}, params:{subscription_params}")

    @classmethod
    def deploy_to_k8s(cls, cluster_id, platform_config):
        gzip_content = gzip.compress(platform_config.encode())
        b64_content = base64.b64encode(gzip_content).decode()

        bcs_client = BcsKubeClient(cluster_id)
        namespace = ClusterConfig.bk_collector_namespace(cluster_id)
        secrets = bcs_client.client_request(
            bcs_client.core_api.list_namespaced_secret,
            namespace=namespace,
            label_selector=f"component={BkCollectorComp.LABEL_COMPONENT_VALUE},template=false,type={BkCollectorComp.LABEL_TYPE_PLATFORM_CONFIG}",
        )
        if len(secrets.items) > 0:
            # 存在，且与已有的数据不一致，则更新
            logger.info(f"{cluster_id} apm platform config already exists.")
            need_update = False
            sec = secrets.items[0]
            if isinstance(sec.data, dict):
                old_content = sec.data.get(BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME, "")
                old_platform_config = gzip.decompress(base64.b64decode(old_content)).decode()
                if old_platform_config != platform_config:
                    need_update = True
            else:
                need_update = True

            if need_update:
                logger.info(f"{cluster_id} apm platform config has changed, update it.")
                sec.data = {BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME: b64_content}
                bcs_client.client_request(
                    bcs_client.core_api.patch_namespaced_secret,
                    name=BkCollectorComp.SECRET_PLATFORM_NAME,
                    namespace=namespace,
                    body=sec,
                )
                logger.info(f"{cluster_id} apm platform config update successful.")
        else:
            # 不存在，则创建
            logger.info(f"{cluster_id} apm platform config not exists, create it.")
            sec = client.V1Secret(
                type="Opaque",
                metadata=client.V1ObjectMeta(
                    name=BkCollectorComp.SECRET_PLATFORM_NAME,
                    namespace=namespace,
                    labels={
                        "component": BkCollectorComp.LABEL_COMPONENT_VALUE,
                        "type": BkCollectorComp.LABEL_TYPE_PLATFORM_CONFIG,
                        "template": "false",
                    },
                ),
                data={BkCollectorComp.SECRET_PLATFORM_CONFIG_FILENAME_NAME: b64_content},
            )

            bcs_client.client_request(
                bcs_client.core_api.create_namespaced_secret,
                namespace=namespace,
                body=sec,
            )
            logger.info(f"{cluster_id} apm platform config create successful.")

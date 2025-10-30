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


class BkCollectorComp:
    """一些 bk-collector 的固定值"""

    # 默认的bk-collector部署的命名空间，如果有特殊的，需通过全局配置来控制 settings.K8S_OPERATOR_DEPLOY_NAMESPACE
    NAMESPACE = "bkmonitor-operator"

    DEPLOYMENT_NAME = "bkm-collector"

    # ConfigMap 模版
    # ConfigMap: 平台配置名称
    CONFIG_MAP_PLATFORM_TPL_NAME = "bk-collector-platform.conf.tpl"
    # ConfigMap: 应用配置名称
    CONFIG_MAP_APPLICATION_TPL_NAME = "bk-collector-application.conf.tpl"
    # ConfigMap: 自定义上报配置名称
    CONFIG_MAP_REPORT_V2_TPL_NAME = "bk-collector-report-v2.conf.tpl"
    CONFIG_MAP_NAME_MAP = {
        "apm": CONFIG_MAP_APPLICATION_TPL_NAME,
        "json": CONFIG_MAP_REPORT_V2_TPL_NAME,
        "prometheus": CONFIG_MAP_APPLICATION_TPL_NAME,
        "log": CONFIG_MAP_APPLICATION_TPL_NAME,
        "manual": CONFIG_MAP_APPLICATION_TPL_NAME,
    }

    # Secrets 配置
    SECRET_SUBCONFIG_MAP = {  # 这里的名字不能随意变，逻辑上依赖，包括数字，每种类型中的所有 key 必须都存在
        "platform": {
            "secret_name_tpl": "bk-collector-platform",
            "secret_data_key_tpl": "platform.conf",
            "secret_data_max_count": 1,  # 平台配置只会有一份
            "secret_extra_label": "type=platform",
        },
        "apm": {
            "secret_hash_ring_bucket_name_tpl": "bk-collector-subconfig-apm-{}-{}",
            "secret_data_key_tpl": "application-{}.conf",
            "secret_hash_ring_bucket_count": 20,  # 这个数值不能随意变动，如需变更，需先清理所有apm的secrets再重新下发
            "secret_extra_label": "type=subconfig,source=apm",
        },
        "json": {
            "secret_hash_ring_bucket_name_tpl": "bk-collector-subconfig-json-{}-{}",
            "secret_data_key_tpl": "report-v2-{}.conf",
            "secret_hash_ring_bucket_count": 100,  # 这个数值不能随意变动，如需变更，需先清理所有json的secrets再重新下发
            "secret_extra_label": "type=subconfig,source=custom_report_v2_json",
        },
        "prometheus": {
            "secret_hash_ring_bucket_name_tpl": "bk-collector-subconfig-prometheus-{}-{}",
            "secret_data_key_tpl": "application-{}.conf",
            "secret_hash_ring_bucket_count": 100,  # 这个数值不能随意变动，如需变更，需先清理所有prometheus的secrets再重新下发
            "secret_extra_label": "type=subconfig,source=custom_report_prometheus",
        },
        "log": {
            "secret_hash_ring_bucket_name_tpl": "bk-collector-subconfig-log-{}-{}",
            "secret_data_key_tpl": "application-{}.conf",
            "secret_hash_ring_bucket_count": 50,  # 这个数值不能随意变动，如需变更，需先清理所有log的secrets再重新下发
            "secret_extra_label": "type=subconfig,source=custom_log",
        },
        "manual": {
            "secret_hash_ring_bucket_name_tpl": "bk-collector-subconfig-manual-{}-{}",
            "secret_data_key_tpl": "{}.conf",
            "secret_hash_ring_bucket_count": 20,  # 这个数值不能随意变动
            "secret_extra_label": "type=subconfig,source=manual",
        },
    }
    SECRET_COMMON_LABELS = "component=bk-collector,template=false"

    # 缓存 KEY: 安装了 bk-collector 的集群 id 列表
    CACHE_KEY_CLUSTER_IDS = "bk-collector:clusters"

    @classmethod
    def get_secrets_config_map_by_protocol(cls, cluster_id: str, protocol: str):
        from django.conf import settings

        special_secrets_config = settings.CUSTOM_REPORT_K8S_SECRETS_CONFIG.get(cluster_id)
        merged_secrets_config = copy.deepcopy(cls.SECRET_SUBCONFIG_MAP)
        if special_secrets_config:
            merged_secrets_config.update(special_secrets_config)
        return merged_secrets_config.get(protocol)

    @classmethod
    def label_selector_to_dict(cls, label_selector: str) -> dict[str, str]:
        if not label_selector:
            return {}

        labels_dict = {}
        for pair in label_selector.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)  # split, first '=' only
                labels_dict[key.strip()] = value.strip()
            else:
                # if no value, give a default value, example: "a="
                labels_dict[pair.strip()] = ""

        return labels_dict

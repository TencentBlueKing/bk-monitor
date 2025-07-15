"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""


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

    # Secrets 配置
    SECRET_PLATFORM_NAME = "bk-collector-platform"
    SECRET_SUBCONFIG_APM_NAME = "bk-collector-subconfig-apm-{}-{}"  # 这里的名字不能随意变，逻辑上依赖
    SECRET_PLATFORM_CONFIG_FILENAME_NAME = "platform.conf"
    SECRET_APPLICATION_CONFIG_FILENAME_NAME = "application-{}.conf"  # 这里的名字不能随意变，逻辑上依赖
    SECRET_APPLICATION_CONFIG_MAX_COUNT = 20  # 每个 Secret 存放 20 个 APM 应用配置

    # Labels 过滤条件
    LABEL_COMPONENT_VALUE = "bk-collector"
    LABEL_TYPE_SUB_CONFIG = "subconfig"
    LABEL_TYPE_PLATFORM_CONFIG = "platform"
    LABEL_SOURCE_APPLICATION_CONFIG = "apm"
    LABEL_SOURCE_REPORT_V2_CONFIG = "report-v2"

    # 缓存 KEY: 安装了 bk-collector 的集群 id 列表
    CACHE_KEY_CLUSTER_IDS = "bk-collector:clusters"

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

from . import base


class EcosystemRepositoryName(metaclass=base.FieldMeta):
    class Meta:
        name = "ECOSYSTEM_REPOSITORY_NAME"
        scope = base.ScopeType.OPEN.value
        value = "bkmonitor-ecosystem"


class TermIntro(metaclass=base.FieldMeta):
    class Meta:
        name = "TERM_INTRO"
        scope = base.ScopeType.OPEN.value
        value = """* Traces：<a href="https://opentelemetry.io/docs/concepts/signals/traces/" target="_blank">调用链</a>，表示请求在应用程序的执行路径。
* Metrics：<a href="https://opentelemetry.io/docs/concepts/signals/metrics/" target="_blank">指标</a>，表示对运行服务的测量。
* Logs: <a href="https://opentelemetry.io/docs/concepts/signals/logs/" target="_blank">日志</a>，表示对事件的记录。
* Profiling: <a href="https://grafana.com/docs/pyroscope/latest/introduction/profiling/" target="_blank">性能分析</a>，表示对应用程序运行时资源的持续测量。
* Telemetry Data：观测数据，指代 Traces、Metrics、Logs、Profiling 等。
* APM：蓝鲸观测平台应用性能监控，提供四类观测数据开箱即用的观测能力。
* <a href="https://github.com/TencentBlueKing/bkmonitor-datalink/tree/master/pkg/collector" target="_blank">bk-collector</a>：腾讯蓝鲸的 APM 服务端组件，负责接收 Prometheus、OpenTelemetry、Jaeger、Skywalking 等主流开源组件的观测数据，并对数据进行清洗转发到观测平台链路。"""


class QuickStartOverview(metaclass=base.FieldMeta):
    class Meta:
        name = "QUICK_START_OVERVIEW"
        scope = base.ScopeType.OPEN.value
        value = """本示例仅演示如何将 <a href="https://opentelemetry.io/docs/concepts/signals/traces/" target="_blank">Traces</a>、<a href="https://opentelemetry.io/docs/concepts/signals/metrics/" target="_blank">Metrics</a>、<a href="https://opentelemetry.io/docs/concepts/signals/logs/" target="_blank">Logs</a>、<a href="https://grafana.com/docs/pyroscope/latest/introduction/profiling/" target="_blank">Profiling</a> 四类观测数据接入蓝鲸应用性能监控。"""


class MustConfigResources(metaclass=base.FieldMeta):
    class Meta:
        name = "MUST_CONFIG_RESOURCES"
        scope = base.ScopeType.OPEN.value
        value = """请在创建 <a href="https://opentelemetry.io/docs/specs/otel/protocol/exporter/" target="_blank">Exporter</a> 时准确传入以下信息：

| 属性                       | 说明                                          |
|--------------------------|---------------------------------------------|
| `bk.data.token`          | 【必须】APM 应用 `Token`                          |
| `service.name`           | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分              |
| `net.host.ip`            | 【可选】关联 CMDB 主机                              |
| `telemetry.sdk.language` | 【可选】标识应用对应的开发语言，SDK Default Resource 会提供该属性 |
| `telemetry.sdk.name`     | 【可选】OT SDK 名称，SDK Default Resource 会提供该属性   |
| `telemetry.sdk.version`  | 【可选】OT SDK 版本，SDK Default Resource 会提供该属性   |"""


# noqa


class MustConfigExporter(metaclass=base.FieldMeta):
    class Meta:
        name = "MUST_CONFIG_EXPORTER"
        scope = base.ScopeType.OPEN.value
        value = """请在创建 <a href="https://opentelemetry.io/docs/specs/otel/protocol/exporter/" target="_blank">Exporter</a> 时准确传入以下信息：

| 参数         | 说明                            |
|------------|-------------------------------|
| `endpoint` | 【必须】数据上报地址，请根据页面指引提供的接入地址进行填写 |"""


class MustConfigProfiling(metaclass=base.FieldMeta):
    class Meta:
        name = "MUST_CONFIG_PROFILING"
        scope = base.ScopeType.OPEN.value
        value = """<a href="https://grafana.com/docs/pyroscope/latest/" target="_blank">Pyroscope</a> 是 Grafana 旗下用于聚合连续分析数据的开源软件项目。

请在创建 `PyroscopeConfig` 时，准确传入以下信息：

| 属性                | 说明                                            |
|-------------------|-----------------------------------------------|
| `AuthToken`       | 【必须】APM 应用 `Token`                            |
| `ApplicationName` | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分                |
| `ServerAddress`   | 【可选】Profiling 数据上报地址，请根据页面指引提供的 HTTP 接入地址进行填写 |"""


class QuickStartRunParameters(metaclass=base.FieldMeta):
    class Meta:
        name = "QUICK_START_RUN_PARAMETERS"
        scope = base.ScopeType.OPEN.value
        value = """| 参数                 | 值（根据所填写接入信息生成）             | 说明                                                         |
| -------------------- | :--------------------------------------- | ------------------------------------------------------------ |
| `TOKEN`              | `"{{access_config.token}}"`              | 【必须】APM 应用 `Token`                                     |
| `SERVICE_NAME`       | `"{{service_name}}"`                     | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分 |
| `OTLP_ENDPOINT`      | `"{{access_config.otlp.http_endpoint}}"` | 【必须】OT 数据上报地址，支持以下协议：<br />  `gRPC`：`{{access_config.otlp.endpoint}}`<br /> `HTTP`：`{{access_config.otlp.http_endpoint}}`（demo 使用该协议演示上报） |
| `PROFILING_ENDPOINT` | `"{{access_config.profiling.endpoint}}"` | 【可选】Profiling 数据上报地址                               |
| `ENABLE_TRACES`      | `{{access_config.otlp.enable_traces}}`   | 是否启用调用链上报                                           |
| `ENABLE_METRICS`     | `{{access_config.otlp.enable_metrics}}`  | 是否启用指标上报                                             |
| `ENABLE_LOGS`        | `{{access_config.otlp.enable_logs}}`     | 是否启用日志上报                                             |
| `ENABLE_PROFILING`   | `{{access_config.profiling.enabled}}`   | 是否启用性能分析上报                                         |

* *<a href="https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/" target="_blank">OTLP Exporter Configuration</a>*"""

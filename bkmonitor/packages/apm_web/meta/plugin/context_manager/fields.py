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


class TermIntro(metaclass=base.FieldMeta):
    class Meta:
        name = "TERM_INTRO"
        scope = base.ScopeType.OPEN.value
        value = """* Traces：[调用链](https://opentelemetry.io/docs/concepts/signals/traces/)，表示请求在应用程序的执行路径。
* Metrics：[指标](https://opentelemetry.io/docs/concepts/signals/metrics/)，表示对运行服务的测量。
* Logs: [日志](https://opentelemetry.io/docs/concepts/signals/logs/)，表示对事件的记录。
* Telemetry Data：遥测数据，指代 Traces、Metrics、Logs、Profiling 等。
* APM：蓝鲸观测平台应用性能监控，提供四类遥测数据开箱即用的观测能力。
* [bk-collector](https://github.com/TencentBlueKing/bkmonitor-datalink/tree/master/pkg/collector)：腾讯蓝鲸的 APM 服务端组件，负责接收 Prometheus、OpenTelemetry、Jaeger、Skywalking 等主流开源组件的遥测数据，并对数据进行清洗转发到观测平台链路。"""


class QuickStartOverview(metaclass=base.FieldMeta):
    class Meta:
        name = "QUICK_START_OVERVIEW"
        scope = base.ScopeType.OPEN.value
        value = """本指南通过一个示例项目，介绍如何将 Traces、Metrics、Logs、Profiling 四类遥测数据接入蓝鲸应用性能监控。

入门项目功能齐全且可在开发环境运行，可以通过该项目快速接入并体验蓝鲸应用性能监控相关功能。"""


class MustConfigResources(metaclass=base.FieldMeta):
    class Meta:
        name = "MUST_CONFIG_RESOURCES"
        scope = base.ScopeType.OPEN.value
        value = """请在 [Resources](https://opentelemetry.io/docs/concepts/resources/) 添加以下属性，蓝鲸观测平台通过这些属性，将数据关联到具体的应用、资源实体：

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
        value = """请在创建 [Exporter](https://opentelemetry.io/docs/specs/otel/protocol/exporter/) 准确传入以下信息：

| 参数         | 说明                            |
|------------|-------------------------------|
| `endpoint` | 【必须】数据上报地址，请根据页面指引提供的接入地址进行填写 |"""


class MustConfigProfiling(metaclass=base.FieldMeta):
    class Meta:
        name = "MUST_CONFIG_PROFILING"
        scope = base.ScopeType.OPEN.value
        value = """[Pyroscope](https://grafana.com/docs/pyroscope/latest/) 是 Grafana 旗下用于聚合连续分析数据的开源软件项目。

请在创建 `PyroscopeConfig` 时，准确传入以下信息：

| 属性                | 说明                                            |
|-------------------|-----------------------------------------------|
| `AuthToken`       | 【必须】APM 应用 `Token`                            |
| `ApplicationName` | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分                |
| `ServerAddress`   | 【可选】Profiling 数据上报地址，请根据页面指引提供的 HTTP 接入地址进行填写 |"""


class DemoRunParameters(metaclass=base.FieldMeta):
    class Meta:
        name = "DEMO_RUN_PARAMETERS"
        scope = base.ScopeType.OPEN.value
        value = """运行参数说明：

| 参数                   | 默认值                                | 说明                                        |
|----------------------|------------------------------------|-------------------------------------------|
| `TOKEN`              | `""`                               | APM 应用 `Token`                            |
| `SERVICE_NAME`       | `"helloworld"`                     | 服务唯一标识，一个应用可以有多个服务，通过该属性区分                |
| `OTLP_ENDPOINT`      | `"http://127.0.0.1:4317"`          | OT 数据上报地址，请根据页面指引提供的 gRPC 接入地址进行填写        |
| `PROFILING_ENDPOINT` | `"http://127.0.0.1:4318/pyroscope"` | Profiling 数据上报地址，请根据页面指引提供的 HTTP 接入地址进行填写 |
| `ENABLE_TRACES`      | `false`                            | 是否启用调用链上报                                 |
| `ENABLE_METRICS`     | `false`                            | 是否启用指标上报                                  |
| `ENABLE_LOGS`        | `false`                            | 是否启用日志上报                                  |
| `ENABLE_PROFILING`   | `false`                            | 是否启用性能分析上报                                |"""

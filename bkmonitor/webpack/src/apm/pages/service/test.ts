/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
export const md = `
# 服务快速接入指引（Java）
本指南通过一个示例项目，介绍如何将 Traces、Metrics、Logs、Profiling 四类遥测数据接入蓝鲸应用性能监控。

入门项目功能齐全且可在开发环境运行，可以通过该项目快速接入并体验蓝鲸应用性能监控相关功能。

## 1. 前置准备

### 1.1 术语介绍

* Traces：[调用链](https://opentelemetry.io/docs/concepts/signals/traces/)，表示请求在应用程序的执行路径。
* Metrics：[指标](https://opentelemetry.io/docs/concepts/signals/metrics/)，表示对运行服务的测量。
* Logs: [日志](https://opentelemetry.io/docs/concepts/signals/logs/)，表示对事件的记录。
* Profiling: [性能分析](https://grafana.com/docs/pyroscope/latest/introduction/profiling/)，表示对应用程序运行时资源的持续测量。
* Telemetry Data：遥测数据，指代 Traces、Metrics、Logs、Profiling 等。
* APM：蓝鲸观测平台应用性能监控，提供四类遥测数据开箱即用的观测能力。
* [bk-collector](https://github.com/TencentBlueKing/bkmonitor-datalink/tree/master/pkg/collector)：腾讯蓝鲸的 APM 服务端组件，负责接收 Prometheus、OpenTelemetry、Jaeger、Skywalking 等主流开源组件的遥测数据，并对数据进行清洗转发到观测平台链路。

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件：
* Git
* Java 8+

### 1.3 初始化 demo

\`\`\`shell
git clone https://git.woa.com/bk-apm/bkmonitor-ecosystem.git.git
cd examples/java-examples/helloworld
gradle build
\`\`\`


## 2. 快速体验

### 2.1 运行样例

#### 2.1.1 运行

🌟 运行参数基于应用信息生成，请确保在您的应用也使用相同的上报地址和 Token。

\`\`\`shell
TOKEN="xxx" \
SERVICE_NAME="helloworld" \
OTLP_ENDPOINT="http://127.0.0.1:4317" \
PROFILING_ENDPOINT="http://127.0.0.1:4318/pyroscope" \
ENABLE_PROFILING="true" \
ENABLE_TRACES="true" \
ENABLE_METRICS="true" \
ENABLE_LOGS="true" \
./gradlew run
\`\`\`

访问 👉 [http://localhost:8080/helloworld](http://localhost:8080/helloworld)。

#### 2.1.2 运行参数说明

运行参数说明：

| 参数                   | 默认值                                | 说明                                        |
|----------------------|------------------------------------|-------------------------------------------|
| \`TOKEN\`              | \`""\`                               | APM 应用 \`Token\`                            |
| \`SERVICE_NAME\`       | \`"helloworld"\`                     | 服务唯一标识，一个应用可以有多个服务，通过该属性区分                |
| \`OTLP_ENDPOINT\`      | \`"http://127.0.0.1:4317"\`          | OT 数据上报地址，请根据页面指引提供的 gRPC 接入地址进行填写        |
| \`PROFILING_ENDPOINT\` | \`"http://127.0.0.1:4318/pyroscope"\` | Profiling 数据上报地址，请根据页面指引提供的 HTTP 接入地址进行填写 |
| \`ENABLE_TRACES\`      | \`false\`                            | 是否启用调用链上报                                 |
| \`ENABLE_METRICS\`     | \`false\`                            | 是否启用指标上报                                  |
| \`ENABLE_LOGS\`        | \`false\`                            | 是否启用日志上报                                  |
| \`ENABLE_PROFILING\`   | \`false\`                            | 是否启用性能分析上报                                |

### 2.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。


## 3. 快速接入

### 3.1 Traces、Metrics、Logs

#### 3.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Java SDK 并将遥测数据发送到 bk-collector 的方式，可以参考 [service/impl/otlp/OtlpService.java](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java) 进行接入

#### 3.1.2 关键配置

请在 [Resources](https://opentelemetry.io/docs/concepts/resources/) 添加以下属性，蓝鲸观测平台通过这些属性，将数据关联到具体的应用、资源实体：

| 属性                       | 说明                                          |
|--------------------------|---------------------------------------------|
| \`bk.data.token\`          | 【必须】APM 应用 \`Token\`                          |
| \`service.name\`           | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分              |
| \`net.host.ip\`            | 【可选】关联 CMDB 主机                              |
| \`telemetry.sdk.language\` | 【可选】标识应用对应的开发语言，SDK Default Resource 会提供该属性 |
| \`telemetry.sdk.name\`     | 【可选】OT SDK 名称，SDK Default Resource 会提供该属性   |
| \`telemetry.sdk.version\`  | 【可选】OT SDK 版本，SDK Default Resource 会提供该属性   |

示例项目在 [service/impl/otlp/OtlpService.java getResource](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java) 提供了创建样例：

\`\`\`java
private Resource getResource() {
    Resource extraResource = Resource.builder()
            // ❗❗【非常重要】请传入应用 Token
            .put(AttributeKey.stringKey("bk.data.token"), this.config.getToken())
            //❗❗【非常重要】应用服务唯一标识
            .put(AttributeKey.stringKey("service.name"), this.config.getServiceName())
            .build();
    // getDefault 提供了部分 SDK 默认属性
    return Resource.getDefault()
            .merge(extraResource)
            // ...其他 Resource
}
\`\`\`

请在创建 [Exporter](https://opentelemetry.io/docs/specs/otel/protocol/exporter/) 时准确传入以下信息：

| 参数         | 说明                            |
|------------|-------------------------------|
| \`endpoint\` | 【必须】数据上报地址，请根据页面指引提供的接入地址进行填写 |

示例项目在 [service/impl/otlp/OtlpService.java getTracerProvider](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java)  提供了创建样例：

\`\`\`java
private SdkTracerProvider getTracerProvider(Resource resource) {
    return SdkTracerProvider.builder()
            .setResource(resource)
            .addSpanProcessor(
                    BatchSpanProcessor.builder(
                                    OtlpGrpcSpanExporter.builder()
                                            //❗️❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
                                            .setEndpoint(this.config.getEndpoint())
                                            .build())
                            .build())
            .build();
}
\`\`\`

#### 3.1.3 使用场景

示例项目整理常见的使用场景，集中在：

\`\`\`java
public String handleHelloWorld(HttpExchange exchange) throws Exception {
    Span span = this.tracer.spanBuilder("Handle/HelloWorld").startSpan();
    try (Scope ignored = span.makeCurrent()) {
        // Logs（日志）
        this.logsDemo(exchange);

        String country = choiceCountry();
        logger.info("get country -> {}", country);

        // Metrics（指标） - Counter 类型
        this.metricsCounterDemo(country);
        // Metrics（指标） - Histograms 类型
        this.metricsHistogramDemo();

        // Traces（调用链）- 自定义 Span
        this.tracesCustomSpanDemo();
        // Traces（调用链）- Span 事件
        this.tracesSpanEventDemo();
        // Traces（调用链）- 模拟错误
        tracesRandomErrorDemo();

        return generateGreeting(country);
    } catch (Exception e) {
        span.recordException(e);
        throw e;
    } finally {
        span.end();
    }
}
\`\`\`

对于 OpenTelemetry SDK API 的使用，在文档 [Java（OpenTelemetry SDK）接入](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/README.md) 提供了更详细的说明。

同时可以参考代码进行使用：[service/impl/http/HelloWorldHttpHandler.java](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/http/HelloWorldHttpHandler.java)。

### 3.2 Profiling

[Pyroscope](https://grafana.com/docs/pyroscope/latest/) 是 Grafana 旗下用于聚合连续分析数据的开源软件项目。

请在创建 \`PyroscopeConfig\` 时，准确传入以下信息：

| 属性                | 说明                                            |
|-------------------|-----------------------------------------------|
| \`AuthToken\`       | 【必须】APM 应用 \`Token\`                            |
| \`ApplicationName\` | 【必须】服务唯一标识，一个应用可以有多个服务，通过该属性区分                |
| \`ServerAddress\`   | 【必须】Profiling 数据上报地址，请根据页面指引提供的 HTTP 接入地址进行填写 |

示例项目提供集成 Pyroscope Java SDK 并将性能数据发送到 bk-collector 的方式，可以参考 [service/impl/profiling/ProfilingService.java](https://git.woa.com/bk-apm/bkmonitor-ecosystem/tree/main/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/profiling/ProfilingService.java) 进行接入：

\`\`\`java
this.pyroscopeConfig = new io.pyroscope.javaagent.config.Config.Builder()
        //❗❗【非常重要】请传入应用 Token
        .setAuthToken(config.getToken())
        //❗❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
        .setServerAddress(config.getProfilingEndpoint())
        //❗❗【非常重要】应用服务唯一标识
        .setApplicationName(this.config.getServiceName())
        .setProfilingEvent(EventType.ITIMER)
        .setFormat(Format.JFR)
        .build();
\`\`\`


## 4. 了解更多

* [应用性能监控（APM）数据接入指南](https://iwiki.woa.com/p/4012525704)
* [各语言、框架接入代码样例](https://git.woa.com/bk-apm/bkmonitor-ecosystem.git)

`;

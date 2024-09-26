# 服务快速接入指引（C++）

本指南通过一个示例项目，介绍如何将 Traces、Metrics、Logs、Profiling 四类遥测数据接入蓝鲸应用性能监控。

入门项目功能齐全且可在开发环境运行，可以通过该项目快速接入并体验蓝鲸应用性能监控相关功能。

## 1. 前置准备

### 1.1 术语介绍

* Traces：[调用链](https://opentelemetry.io/docs/concepts/signals/traces/)，表示请求在应用程序的执行路径。
* Metrics：[指标](https://opentelemetry.io/docs/concepts/signals/metrics/)，表示对运行服务的测量。
* Logs: [日志](https://opentelemetry.io/docs/concepts/signals/logs/)，表示对事件的记录。
* Telemetry Data：遥测数据，指代 Traces、Metrics、Logs、Profiling 等。
* APM：蓝鲸观测平台应用性能监控，提供四类遥测数据开箱即用的观测能力。
* [bk-collector](https://github.com/TencentBlueKing/bkmonitor-datalink/tree/master/pkg/collector)：腾讯蓝鲸的 APM 服务端组件，负责接收 Prometheus、OpenTelemetry、Jaeger、Skywalking 等主流开源组件的遥测数据，并对数据进行清洗转发到观测平台链路。

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件： 
* Git
* Docker

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}.git
cd examples/cpp-examples/helloworld
docker build -t cpp-helloworld .
```

## 2. 快速接入

### 2.1 Traces、Metrics、Logs

#### 2.1.1

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Cpp SDK 并将遥测数据发送到 bk-collector 的方式，可以参考下面的代码：
* Traces：[include/otlp/tracer_common.h]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/tracer_common.h)
* Metrics：[include/otlp/meter_common.h]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/meter_common.h)
* Logs：[include/otlp/logger_common.h]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/logger_common.h)

在 `main` 文件中启动注册：

```cpp
#include "otlp/resource_common.h"
#include "otlp/tracer_common.h"
#include "otlp/meter_common.h"
#include "otlp/logger_common.h"

int main() {
    const Config &config = Config::getInstance();
    auto resource = CreateResource(config);
    
    initTracer(config, resource);
    initMeter(config, resource);
    initLogger(config, resource);
    
    // .. 业务启动代码
    
    cleanupTracer(config);
    cleanupMeter(config);
    cleanupLogger(config);
    
    return 0;
}
```

#### 2.1.2 使用场景

示例项目整理常见的使用场景，集中在：

```cpp
std::shared_ptr<HttpRequestHandler::OutgoingResponse>
Handler::handleHelloWorld(const std::shared_ptr<HttpRequestHandler::IncomingRequest> &request) {
    const Config &config = Config::getInstance();
    auto logger = getLogger(config.ServiceName);

    auto span = get_tracer(config.ServiceName)->StartSpan("Handle/HelloWorld");
    auto scope = get_tracer(config.ServiceName)->WithActiveSpan(span);

    // Logs（日志）
    helloWorldHelper.logsDemo(request);

    auto country = helloWorldHelper.choiceCountry();
    logger->Info("get country -> " + country);

    // Metrics（指标） - Counter 类型
    helloWorldHelper.metricsCounterDemo(country);
    // Metrics（指标） - Histograms 类型
    helloWorldHelper.metricsHistogramDemo();

    // Traces（调用链）- 自定义 Span
    HelloWorldHelper::tracesCustomSpanDemo();
    // Traces（调用链）- Span 事件
    HelloWorldHelper::tracesSpanEventDemo();

    // Traces（调用链）- 模拟错误
    if (auto err = helloWorldHelper.tracesRandomErrorDemo()) {
        auto response = ResponseFactory::createResponse(Status::CODE_500, err->what());

        span->End();
        return response;
    }

    auto greeting = HelloWorldHelper::generateGreeting(country);
    auto response = ResponseFactory::createResponse(Status::CODE_200, greeting.c_str());

    span->End();
    return response;
}
```

可以参考代码进行使用：[src/server.cpp]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/src/server.cpp)。

### 2.2 构建

引入 OpenTelemetry C++ SDK 需要重新编译项目，示例项目提供 Dockerfile 以供参考：[Dockerfile]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/Dockerfile)。

## 3. 快速体验

### 3.1 运行样例

```shell
docker run -e TOKEN="{{access_config.token}}" \
-e SERVICE_NAME="{{service_name}}" \
-e OTLP_ENDPOINT="{{access_config.otlp.endpoint}}" \
-e ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
-e ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
-e ENABLE_LOGS="{{access_config.otlp.enable_logs}}" cpp-helloworld:latest -p 8080:8080
```

访问 👉 [http://localhost:8080/helloworld](http://localhost:8080/helloworld)。

### 3.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。

## 4. 了解更多

* [应用性能监控（APM）数据接入指南]({{APM_ACCESS_URL}})
* [各语言、框架接入代码样例]({{ECOSYSTEM_REPOSITORY_URL}})

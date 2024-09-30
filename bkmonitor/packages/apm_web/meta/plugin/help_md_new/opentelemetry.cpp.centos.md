# 服务快速接入指引（C++）

{{QUICK_START_OVERVIEW}}

## 1. 前置准备

### 1.1 术语介绍

{{TERM_INTRO}}

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件： 
* Git
* Docker

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}
cd examples/cpp-examples/helloworld
docker build -t cpp-helloworld:latest .
```


## 2. 快速体验

### 2.1 运行样例

#### 2.1.1 运行

🌟 运行参数基于应用信息生成，请确保在您的应用也使用相同的上报地址和 Token。

```shell
docker run -e TOKEN="{{access_config.token}}" \
-e SERVICE_NAME="{{service_name}}" \
-e OTLP_ENDPOINT="{{access_config.otlp.endpoint}}" \
-e ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
-e ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
-e ENABLE_LOGS="{{access_config.otlp.enable_logs}}" \
cpp-helloworld:latest -p 8080:8080
```

#### 2.1.2 运行参数说明

{{QUICK_START_RUN_PARAMETERS}}

### 2.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。

## 3. 快速接入

### 3.1 Traces、Metrics、Logs

#### 3.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Cpp SDK 并将遥测数据发送到 bk-collector 的方式，可以参考下面的代码：
* Traces：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/tracer_common.h" target="_blank">include/otlp/tracer_common.h</a>
* Metrics：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/meter_common.h" target="_blank">include/otlp/meter_common.h</a>
* Logs：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/logger_common.h" target="_blank">include/otlp/logger_common.h</a>

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

#### 3.1.2 关键配置

{{MUST_CONFIG_RESOURCES}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/resource_common.h" target="_blank">include/otlp/meter_common.h</a> 提供了创建样例：

```cpp
resource_sdk::Resource CreateResource(const Config &config) {
    // 使用 SDK 默认属性
    auto defaultResource = resource_sdk::Resource::GetDefault();
    auto resourceAttributes = resource_sdk::ResourceAttributes{
            //❗️❗【非常重要】请传入应用 Token 
            {"bk.data.token",                                 config.Token},
            //❗️❗【非常重要】应用服务唯一标识
            {resource_sdk::SemanticConventions::kServiceName, config.ServiceName},
            ...
    };
    return defaultResource.Merge(resource_sdk::Resource::Create(resourceAttributes));
}
```

{{MUST_CONFIG_EXPORTER}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/include/otlp/tracer_common.h" target="_blank">include/otlp/tracer_common.h</a> 提供了创建样例：

```cpp
void initTracer(const Config &config, const resource_sdk::Resource &resource) {
    otel_exporter::OtlpGrpcExporterOptions otlpOptions;
    //❗️❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
    otlpOptions.endpoint = config.OtlpEndpoint;
    auto exporter = otel_exporter::OtlpGrpcExporterFactory::Create(otlpOptions);
    ...
```

#### 3.1.3 使用场景

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

对于 OpenTelemetry SDK API 的使用，在文档 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/README.md" target="_blank">C++（OpenTelemetry SDK）接入</a> 提供了更详细的说明。

同时可以参考代码进行使用：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/src/server.cpp" target="_blank">src/server.cpp</a>。

### 3.2 构建

引入 OpenTelemetry C++ SDK 需要重新编译项目，示例项目提供 Dockerfile 以供参考：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/cpp-examples/helloworld/Dockerfile" target="_blank">Dockerfile</a>。


## 4. 了解更多

* <a href="{{APM_ACCESS_URL}}" target="_blank">应用性能监控（APM）数据接入指南</a>
* <a href="{{ECOSYSTEM_REPOSITORY_URL}}" target="_blank">各语言、框架接入代码样例</a>

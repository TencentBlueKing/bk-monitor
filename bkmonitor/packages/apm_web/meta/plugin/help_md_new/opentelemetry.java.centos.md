# 服务快速接入指引（Java）

{{QUICK_START_OVERVIEW}}

## 1. 前置准备

### 1.1 术语介绍

{{TERM_INTRO}}

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件：
* Git
* Java 8+

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}.git
cd examples/java-examples/helloworld
gradle build
```


## 2. 快速体验

### 2.1 运行样例

#### 2.1.1 运行

🌟 运行参数基于应用信息生成，请确保在您的应用也使用相同的上报地址和 Token。

```shell
TOKEN="{{access_config.token}}" \
SERVICE_NAME="{{service_name}}" \
OTLP_ENDPOINT="{{access_config.otlp.endpoint}}" \
PROFILING_ENDPOINT="{{access_config.profiling.endpoint}}" \
ENABLE_PROFILING="{{access_config.profiling.enabled}}" \
ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
ENABLE_LOGS="{{access_config.otlp.enable_logs}}" ./gradlew run
```

访问 👉 [http://localhost:8080/helloworld](http://localhost:8080/helloworld)。

#### 2.1.2 运行参数说明

{{DEMO_RUN_PARAMETERS}}

### 2.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。


## 3. 快速接入

### 3.1 Traces、Metrics、Logs

#### 3.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Java SDK 并将遥测数据发送到 bk-collector 的方式，可以参考 [service/impl/otlp/OtlpService.java]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java) 进行接入

#### 3.1.2 关键配置

{{MUST_CONFIG_RESOURCES}}

示例项目在 [service/impl/otlp/OtlpService.java getResource]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java) 提供了创建样例：

```java
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
```

{{MUST_CONFIG_EXPORTER}}

示例项目在 [service/impl/otlp/OtlpService.java getTracerProvider]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/otlp/OtlpService.java)  提供了创建样例：

```java
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
```

#### 3.1.3 使用场景

示例项目整理常见的使用场景，集中在：

```java
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
```

对于 OpenTelemetry SDK API 的使用，在文档 [Java（OpenTelemetry SDK）接入]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/README.md) 提供了更详细的说明。

同时可以参考代码进行使用：[service/impl/http/HelloWorldHttpHandler.java]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/http/HelloWorldHttpHandler.java)。

### 3.2 Profiling

{{MUST_CONFIG_PROFILING}}

示例项目提供集成 Pyroscope Java SDK 并将性能数据发送到 bk-collector 的方式，可以参考 [service/impl/profiling/ProfilingService.java]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/java-examples/helloworld/src/main/java/com/tencent/bkm/demo/helloworld/service/impl/profiling/ProfilingService.java) 进行接入：

```java
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
```


## 4. 了解更多

* [应用性能监控（APM）数据接入指南]({{APM_ACCESS_URL}})
* [各语言、框架接入代码样例]({{ECOSYSTEM_REPOSITORY_URL}})

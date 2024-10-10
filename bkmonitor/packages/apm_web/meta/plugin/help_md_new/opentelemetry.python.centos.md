# 服务快速接入指引（Python）

{{QUICK_START_OVERVIEW}}

## 1. 前置准备

### 1.1 术语介绍

{{TERM_INTRO}}

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件：
* Git
* Python 3.8+

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}
cd examples/python-examples/helloworld
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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
ENABLE_LOGS="{{access_config.otlp.enable_logs}}" \
python main.py
```

#### 2.1.2 运行参数说明

{{QUICK_START_RUN_PARAMETERS}}

### 2.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。


## 3. 快速接入

### 3.1 Traces、Metrics、Logs

#### 3.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Python SDK 并将遥测数据发送到 bk-collector 的方式，可以参考 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/services/otlp.py" target="_blank">services/otlp.py</a> 进行接入

#### 3.1.2 关键配置

{{MUST_CONFIG_RESOURCES}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/services/otlp.py" target="_blank">services/otlp.py _create_resource</a> 提供了创建样例：

```python
def _create_resource(self) -> Resource:
    # ...
    initial_resource = Resource.create(
        {
            # ❗❗【非常重要】请传入应用 Token
            "bk.data.token": self.config.token,
            # ❗❗【非常重要】应用服务唯一标识
            ResourceAttributes.SERVICE_NAME: self.config.service_name,
            # ...
        }
    )

    return get_aggregated_resources(detectors, initial_resource)
```

{{MUST_CONFIG_EXPORTER}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/services/otlp.py" target="_blank">services/otlp.py _setup_traces</a> 提供了创建样例：

```python
def _setup_traces(self, resource: Resource):
    # ❗️❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
    otlp_exporter = OTLPSpanExporter(endpoint=self.config.endpoint, insecure=True)
    span_processor = BatchSpanProcessor(otlp_exporter)
    self.tracer_provider = TracerProvider(resource=resource)
    self.tracer_provider.add_span_processor(span_processor)
    if self.config.enable_profiling:
        self.tracer_provider.add_span_processor(PyroscopeSpanProcessor())
    trace.set_tracer_provider(self.tracer_provider)
```

#### 3.1.3 使用场景

示例项目整理常见的使用场景，集中在：

```python
class HelloWorldHandler:
    ...
    def handle(self) -> str:
        # 不自动设置异常状态和记录异常，以展示手动设置方法 (traces_random_error_demo)
        with self.tracer.start_as_current_span(
            "handle/hello_world", record_exception=False, set_status_on_exception=False
        ):
            country = self.choice_country()
            otel_logger.info("get country -> %s", country)

            # Logs（日志）
            self.logs_demo(request)

            # Metrics（指标） - Counter 类型
            self.metrics_counter_demo(country)
            # Metrics（指标） - Histograms 类型
            self.metrics_histogram_demo()

            # Traces（调用链）- 自定义 Span
            self.traces_custom_span_demo()
            # Traces（调用链）- Span 事件
            self.traces_span_event_demo()
            # Traces（调用链）- 模拟错误
            self.traces_random_error_demo()

            return self.generate_greeting(country)
```

对于 OpenTelemetry SDK API 的使用，在文档 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/README.md" target="_blank">Python（OpenTelemetry SDK）接入</a> 提供了更详细的说明。

同时可以参考代码进行使用：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/services/server.py" target="_blank">services/server.py</a>。

### 3.2 Profiling

{{MUST_CONFIG_PROFILING}}

示例项目提供集成 Pyroscope Python SDK 并将性能数据发送到 bk-collector 的方式，可以参考 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/python-examples/helloworld/services/profiling.py" target="_blank">services/profiling.py</a> 进行接入：

```python
self.config = ProfilingConfig(
    #❗❗【非常重要】请传入应用 Token
    token=config.token,
    enabled=config.enable_profiling,
    #❗❗【非常重要】应用服务唯一标识
    service_name=config.service_name,
    #❗❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
    address=config.profiling_endpoint,
)
```


## 4. 了解更多

* <a href="{{APM_ACCESS_URL}}" target="_blank">应用性能监控（APM）数据接入指南</a>
* <a href="{{ECOSYSTEM_REPOSITORY_URL}}" target="_blank">各语言、框架接入代码样例</a>

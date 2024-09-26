# 服务快速接入指引（Go）

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
* Go 1.21 或更高版本

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}.git
cd examples/go-examples/helloworld
go mod tidy
```

## 2. 快速接入

### 2.1 Traces、Metrics、Logs

#### 2.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Go SDK 并将遥测数据发送到 bk-collector 的方式，可以参考 [service/otlp/otlp.go]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/otlp/otlp.go) 进行接入

#### 2.1.2 使用场景

示例项目整理常见的使用场景，集中在：

```go
func HelloWorld(w http.ResponseWriter, req *http.Request) {
	ctx, span := tracer.Start(req.Context(), "Handle/HelloWorld")
	defer span.End()

	// Logs（日志）
	logsDemo(ctx, req)

	country := choiceCountry()
	logger.InfoContext(ctx, fmt.Sprintf("get country -> %s", country))

	// Metrics（指标） - Counter 类型
	metricsCounterDemo(ctx, country)
	// Metrics（指标） - Histograms 类型
	metricsHistogramDemo(ctx)

	// Traces（调用链）- 自定义 Span
	tracesCustomSpanDemo(ctx)
	// Traces（调用链）- Span 事件
	tracesSpanEventDemo(ctx)
	// Traces（调用链）- 模拟错误
	if err := tracesRandomErrorDemo(ctx, span); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	greeting := generateGreeting(country)
	w.Write([]byte(greeting))
}
```

可以参考代码进行使用：[service/http/helloworld.go]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/http/helloworld.go)。

### 2.2 Profiling

Pyroscope 是 Grafana 旗下用于聚合连续分析数据的开源软件项目。

示例项目提供集成 Pyroscope Go SDK 并将性能数据发送到 bk-collector 的方式，可以参考 [service/profiling/profiling.go]({{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/profiling/profiling.go) 进行接入。

## 3. 快速体验

### 3.1 运行样例

```shell
TOKEN="{{access_config.token}}" \
SERVICE_NAME="{{service_name}}" \
OTLP_ENDPOINT="{{access_config.otlp.endpoint}}" \
PROFILING_ENDPOINT="{{access_config.profiling.endpoint}}" \
ENABLE_PROFILING="{{access_config.profiling.enabled}}" \
ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
ENABLE_LOGS="{{access_config.otlp.enable_logs}}" go run main.go
```

访问 👉 [http://localhost:8080/helloworld](http://localhost:8080/helloworld)。

### 3.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。

## 4. 了解更多

* [应用性能监控（APM）数据接入指南]({{APM_ACCESS_URL}})
* [各语言、框架接入代码样例]({{ECOSYSTEM_REPOSITORY_URL}})

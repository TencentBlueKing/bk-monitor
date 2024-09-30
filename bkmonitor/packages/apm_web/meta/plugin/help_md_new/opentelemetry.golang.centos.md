# 服务快速接入指引（Go）

{{QUICK_START_OVERVIEW}}

## 1. 前置准备

### 1.1 术语介绍

{{TERM_INTRO}}

### 1.2 开发环境要求

在开始之前，请确保您已经安装了以下软件：
* Git
* Go 1.21 或更高版本

### 1.3 初始化 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}
cd examples/go-examples/helloworld
go mod tidy
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
go run main.go
```

#### 2.1.2 运行参数说明

{{QUICK_START_RUN_PARAMETERS}}

### 2.2 查看数据

等待片刻，便可在「服务详情」看到应用数据。

## 3. 快速接入

### 3.1 Traces、Metrics、Logs

#### 3.1.1 接入

OpenTelemetry 提供标准化的框架和工具包，用于创建和管理 Traces、Metrics、Logs 数据。

示例项目提供集成 OpenTelemetry Go SDK 并将遥测数据发送到 bk-collector 的方式，可以参考 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/otlp/otlp.go" target="_blank">service/otlp/otlp.go</a> 进行接入

#### 3.1.2 关键配置

{{MUST_CONFIG_RESOURCES}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/otlp/otlp.go" target="_blank">service/otlp/otlp.go newResource</a> 提供了创建样例：

```go
func (s *Service) newResource() (*resource.Resource, error) {
	extraRes, err := resource.New(
		...
		resource.WithAttributes(
			// ❗❗【非常重要】应用服务唯一标识
			semconv.ServiceNameKey.String(s.config.ServiceName),
			// ❗❗【非常重要】请传入应用 Token 
			attribute.Key("bk.data.token").String(s.config.Token),
		),
	)
	// resource.Default() 提供了部分 SDK 默认属性
	res, err := resource.Merge(resource.Default(), extraRes)
	return res, nil
}
```

{{MUST_CONFIG_EXPORTER}}

示例项目在 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/otlp/otlp.go" target="_blank">service/otlp/otlp.go newTracerExporter</a> 提供了创建样例：

```go
func (s *Service) newTracerExporter(ctx context.Context) (*otlptrace.Exporter, error) {
    // ❗❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
	// 格式为 ip:port 或 domain:port，不要带 schema
    gRPCConn, err = grpc.NewClient(s.config.Endpoint, grpc.WithTransportCredentials(insecure.NewCredentials()))
	return newGRPCTracerExporter(ctx, gRPCConn)
}
```

#### 3.1.3 使用场景

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

对于 OpenTelemetry SDK API 的使用，在文档 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/README.md" target="_blank">Go（OpenTelemetry SDK）接入</a> 提供了更详细的说明。 

同时可以参考代码进行使用：<a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/http/helloworld.go" target="_blank">service/http/helloworld.go</a>。

### 3.2 Profiling

{{MUST_CONFIG_PROFILING}}

示例项目提供集成 Pyroscope Go SDK 并将性能数据发送到 bk-collector 的方式，可以参考 <a href="{{ECOSYSTEM_CODE_ROOT_URL}}/examples/go-examples/helloworld/service/profiling/profiling.go" target="_blank">service/profiling/profiling.go</a> 进行接入:

```go
profiler, _ = pyroscope.Start(
    pyroscope.Config{
        //❗❗【非常重要】请传入应用 Token
        AuthToken: s.config.Token,
        //❗❗【非常重要】应用服务唯一标识
        ApplicationName: s.config.ServiceName,
        //❗❗【非常重要】数据上报地址，请根据页面指引提供的接入地址进行填写
        ServerAddress: s.config.Addr,
        Logger:        pyroscope.StandardLogger,
        ProfileTypes: []pyroscope.ProfileType{
            pyroscope.ProfileCPU
        }
    }
)
```

## 4. 了解更多

* <a href="{{APM_ACCESS_URL}}" target="_blank">应用性能监控（APM）数据接入指南</a>
* <a href="{{ECOSYSTEM_REPOSITORY_URL}}" target="_blank">各语言、框架接入代码样例</a>

1. 下载opentelemetry的Trace SDK包
    ```sh
    go get go.opentelemetry.io/otel \
            go.opentelemetry.io/otel/trace \
            go.opentelemetry.io/otel/sdk  
    ```
2. 下载所需要的上报导出包
    ```sh
    # grpc方式上报
    go get go.opentelemetry.io/otel/exporters/otlp/otlptrace \^^ 
           go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc
    # http方式上报
    go get go.opentelemetry.io/otel/exporters/otlp/otlptrace \
           go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp
    ```
3. 初始化Trace SDK(可以按照以下方式初始化SDK)
    ```go
    package demo

    import (
        "context"
        "log"

        "go.opentelemetry.io/otel"
        "go.opentelemetry.io/otel/exporters/otlp/otlptrace"
        "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp"
        "go.opentelemetry.io/otel/sdk/resource"
        sdktrace "go.opentelemetry.io/otel/sdk/trace"
        semconv "go.opentelemetry.io/otel/semconv/v1.7.0"
        "go.opentelemetry.io/otel/trace"
    )

    // newResource returns a resource describing this application.
    func newResource() *resource.Resource {
        r, _ := resource.Merge(
            resource.Default(),
            resource.NewWithAttributes(
                semconv.SchemaURL,
                semconv.ServiceNameKey.String("YourServiceName"),
                semconv.ServiceVersionKey.String("v0.1.0"),
                attribute.String("net.host.name", "{host name}"),
                attribute.String("net.host.ip", "{host ip}"),
                // 如果你的程序不用监听端口 可以不用设置这个参数
                attribute.String("net.host.port", "{process listen ip}"),
                attribute.String("bk.data.token", "{access_token}"),
            ),
        )
        return r
    }

    func newHttpExporterClient() otlptrace.Client{
        return otlptracehttp.NewClient(
            otlptracehttp.WithEndpoint("http://localhost:55678"),
            otlptracehttp.WithURLPath("/v1/trace"),
            otlptracehttp.WithInsecure()
        )
    }

    func newGrpcExporterClient() otlptrace.Client{
        return otlptracegrpc.NewClient(
            otlptracegrpc.WithEndpoint("http://localhost:55678"),
            otlptracegrpc.WithInsecure()
        )
    }

    func installTrace(ctx context.Context) func() {
        // http use this
        // client := newHttpExporterClient()

        // grpc use this
        client := newGrpcExporterClient()
        exporter, err := otlptrace.New(ctx, client)
        if err != nil {
            log.Fatalf("creating OTLP trace exporter: %v", err)
        }

        tracerProvider := sdktrace.NewTracerProvider(
            sdktrace.WithBatcher(exporter),
            sdktrace.WithResource(newResource()),
        )
        otel.SetTracerProvider(tracerProvider)

        return func() {
            if err := tracerProvider.Shutdown(ctx); err != nil {
                log.Fatalf("stopping tracer provider: %v", err)
            }
        }
    }

    func main() {
        ctx := context.Background()
        // Registers a tracer Provider globally.
        cleanup := installExportPipeline(ctx)
        defer cleanup()
    }
    ```
4. 程序埋点([使用参考](https://opentelemetry.io/docs/instrumentation/go/getting-started/))
    ```go
    // Poll asks a user for input and returns the request.
    func (a *App) Poll(ctx context.Context) (uint, error) {
    _, span := otel.Tracer(name).Start(ctx, "Poll")
    defer span.End()

    a.l.Print("What Fibonacci number would you like to know: ")

    var n uint
    _, err := fmt.Fscanf(a.r, "%d", &n)

    // Store n as a string to not overflow an int64.
    nStr := strconv.FormatUint(uint64(n), 10)
    span.SetAttributes(attribute.String("request.n", nStr))

    return n, err
    }
    ```

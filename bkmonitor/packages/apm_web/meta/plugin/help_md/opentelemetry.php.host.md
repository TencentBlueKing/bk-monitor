1. 安装`opentelemetry`的`API SDK`包
    ```sh
    pip install opentelemetry-api
    pip install opentelemetry-sdk
    ```
2. 安装你想要的[拓展插件](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation)
    ```sh
    pip install opentelemetry-instrumentation-{instrumentation}
    ```
3. 安装exporter
    ```sh
    # http上报使用该expoter
    pip install opentelemetry-exporter-otlp-proto-http

    # grpc上报使用该expoter
    pip install opentelemetry-exporter-otlp-proto-grpc
    ```
4. 初始化代码
    ```python
    from opentelemetry import trace
    from opentelemetry.exporter.jaeger.thrift import JaegerExporter
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # Trace 初始化
    tracer_provider = TracerProvider(
        resource=Resource.create(
            {
                SERVICE_NAME: "Your Service Name.",
                "net.host.name": "localhost",
                "net.host.ip": "192.168.99.1",
                "net.host.port": "8080",
                            "bk.data.token": "{access token}" 
            }
        ),
    )

    # http exporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    otlp_exporter = OTLPSpanExporter(
        endpoint="http://localhost:4318/v1/traces"
    )

    # grpc exporter
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    otlp_exporter = OTLPSpanExporter(
        endpoint="localhost:4318",
        insecure=True,
    )

    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)
    ```
5. 代码埋点
    ```python
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("foo"):
        with tracer.start_as_current_span("bar"):
            with tracer.start_as_current_span("baz"):
                print("Hello world from OpenTelemetry Python!")
    ```

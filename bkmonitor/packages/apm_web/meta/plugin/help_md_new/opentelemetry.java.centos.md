# 服务快速接入指引（Java）

{{QUICK_START_OVERVIEW}}

## 1. 环境要求

在开始之前，请确保您已经安装了以下软件：
* Git
* Docker


## 2. 初始化示例 demo

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}
cd {{ECOSYSTEM_REPOSITORY_NAME}}/examples/java-examples/helloworld
docker build -t helloworld-java:latest .
```


## 3. 运行示例 demo

复制以下命令参数在你的终端运行：

```shell
# 如果本地该端口已被占用，请替换为其他可用端口
DEMO_PORT=8080
docker run -e TOKEN="{{access_config.token}}" \
-e SERVICE_NAME="{{service_name}}" \
-e OTLP_ENDPOINT="{{access_config.otlp.http_endpoint}}" \
-e PROFILING_ENDPOINT="{{access_config.profiling.endpoint}}" \
-e ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
-e ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
-e ENABLE_LOGS="{{access_config.otlp.enable_logs}}" \
-e ENABLE_PROFILING="{{access_config.profiling.enabled}}" \
-p $DEMO_PORT:8080 helloworld-java:latest
```

运行参数说明：

{{QUICK_START_RUN_PARAMETERS}}

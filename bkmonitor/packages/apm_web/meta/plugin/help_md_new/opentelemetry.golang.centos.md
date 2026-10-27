# 服务快速接入指引（Go）

{{QUICK_START_OVERVIEW}}

## 1. 接入样例获取

```shell
git clone {{ECOSYSTEM_REPOSITORY_URL}}
cd {{ECOSYSTEM_REPOSITORY_NAME}}/examples/go-examples/helloworld
docker build -t helloworld-go:latest .
```

- *[1] Git 用于获取样例，Docker（或兼容容器工具）用于构建和运行容器样例，仅供快速验证。*
- *[2] 数据上报不依赖 Git 或 Docker，已有业务可直接参考后文的上报协议或 SDK 配置接入。*


## 2. 运行示例 demo

复制以下命令参数在你的终端运行：

```shell
docker run -e TOKEN="{{access_config.token}}" \
-e SERVICE_NAME="{{service_name}}" \
-e OTLP_ENDPOINT="{{access_config.otlp.http_endpoint}}" \
-e PROFILING_ENDPOINT="{{access_config.profiling.endpoint}}" \
-e ENABLE_TRACES="{{access_config.otlp.enable_traces}}" \
-e ENABLE_METRICS="{{access_config.otlp.enable_metrics}}" \
-e ENABLE_LOGS="{{access_config.otlp.enable_logs}}" \
-e ENABLE_PROFILING="{{access_config.profiling.enabled}}" helloworld-go:latest
```
* 样例已设置定时请求以产生监控数据，如需本地访问调试，可增加运行参数 `-p {本地端口}:8080`。

运行参数说明：

{{QUICK_START_RUN_PARAMETERS}}

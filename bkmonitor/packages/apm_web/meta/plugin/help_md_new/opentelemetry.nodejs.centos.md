# 服务快速接入指引（JavaScript）

👏 欢迎共建最佳实践样例

## 1. 前置准备

### 1.1 术语介绍

* Traces：[调用链](https://opentelemetry.io/docs/concepts/signals/traces/)，表示请求在应用程序的执行路径。
* Metrics：[指标](https://opentelemetry.io/docs/concepts/signals/metrics/)，表示对运行服务的测量。
* Logs: [日志](https://opentelemetry.io/docs/concepts/signals/logs/)，表示对事件的记录。
* Telemetry Data：遥测数据，指代 Traces、Metrics、Logs、Profiling 等。
* APM：蓝鲸观测平台应用性能监控，提供四类遥测数据开箱即用的观测能力。
* [bk-collector](https://github.com/TencentBlueKing/bkmonitor-datalink/tree/master/pkg/collector)：腾讯蓝鲸的 APM 服务端组件，负责接收 Prometheus、OpenTelemetry、Jaeger、Skywalking 等主流开源组件的遥测数据，并对数据进行清洗转发到观测平台链路。

## 2. 了解更多

* [应用性能监控（APM）数据接入指南]({{APM_ACCESS_URL}})
* [各语言、框架接入代码样例]({{ECOSYSTEM_REPOSITORY_URL}})
* [OpenTelemetry JavaScript SDK & API](https://opentelemetry.io/zh/docs/languages/js/)

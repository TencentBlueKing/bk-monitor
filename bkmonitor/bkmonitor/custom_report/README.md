# custom report

该目录包含了《自定义上报》相关的配置下发抽象逻辑

### 上报数据类型

- 指标
  - 自定义 Json V2格式
  - Prometheus 格式
- 事件
  - 自定义 Json 格式
- 日志
  - OTel 格式
- APM
  - 指标 OTel 格式
  - 日志 OTel 格式
  - 调用链 OTel 格式
  - 性能分析 pprof 格式


### Collector 提供的上报配置分类
- platform：平台配置，所有配置下发的前提，需要优先下发
- report_v2：自定义 Json V2 格式的配置
- subconfig：Prometheus & OTel 格式的配置
- report: 【已废弃】


### Collector 部署模式（对应多种下发方式）
- 二进制部署
  - 直连区域：所有的配置
  - 云区域：云区域归属业务的所有配置。云区域和业务关系（n: m）
- K8S 集群部署
  - 公共集群：所有的配置
  - 独立集群：集群归属业务的所有配置。集群和业务关系（n: 1）
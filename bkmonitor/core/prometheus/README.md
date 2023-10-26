# 监控平台可观测性 - 指标定义

## 指标定义

### 定义方式

所有指标定义统一在 `core/prometheus/metrics.py` 文件中声明

### 支持的指标类型

- Histogram
    直方图类型。通过预先设置多个数值桶，来观察数值的分布情况。多用于收集耗时信息。比如：某个API的请求耗时、某个模块的处理耗时

- Counter
    计数器类型。单调递增的整数，多用于统计次数信息。比如：某个模块处理成功和失败的次数

### 定义示例

```python
# Histogram
ACCESS_DATA_PROCESS_TIME = Histogram(
    name="bkmonitor_access_data_process_time",                                      # 指标英文名
    documentation="Access-Data模块处理耗时",                                          # 指标详细描述
    labelnames=("strategy_group_key",),                                             # 该指标的维度字段列表
    buckets=(0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 7.5, 10.0, 30.0, INF),     # 预设的桶分布。若没有特殊需求，该参数不给，使用默认即可
)

# Counter
ACCESS_DATA_PROCESS_COUNT = Counter(                              
    name="bkmonitor_access_data_process_count",                  # 指标英文名
    documentation="Access-Data模块处理次数",                       # 指标详细描述
    labelnames=("strategy_group_key", "status", "exception"),    # 该指标的维度字段列表
)
```

## 使用示例

### Histogram

统计耗时的两种方式

1. 直接写入值

```python
import time

from core.prometheus import metrics

start_time = time.time()
alert.process()
end_time = time.time()

metrics.ALERT_PROCESS_TIME.labels(
    bk_data_id=self.bk_data_id,
    topic=self.topic,
    strategy_id=event.strategy_id,
).observe(end_time - start_time)
```

2. 使用上下文管理器

```python
from core.prometheus import metrics

with metrics.ALERT_PROCESS_TIME.labels(
    bk_data_id=self.bk_data_id,
    topic=self.topic,
    strategy_id=event.strategy_id,
).time():
    alert.process()
```

### Counter

```python
from core.prometheus import metrics

# 加 1
metrics.ALERT_PROCESS_COUNT.labels(
    bk_data_id=bk_data_id, topic=topic, status=metrics.StatusEnum.from_exc(exc), exception=exc
).inc()

# 加 N
metrics.ALERT_PROCESS_COUNT.labels(
    bk_data_id=bk_data_id, topic=topic, status=metrics.StatusEnum.from_exc(exc), exception=exc
).inc(N)

```

### 数据上报

请注意！通过以上方式进行了指标统计，并不代表数据已经真正上报。必须调用预设的上报函数 `report_all` 才能完成上报。
由于上报会走 udp 网络请求。建议每完成一轮完整处理流程再进行一次上报，避免产生过多的网络请求，从而影响业务处理性能

```python
from core.prometheus import metrics

# 1. 统计耗时
with metrics.ALERT_PROCESS_TIME.labels(
    bk_data_id=self.bk_data_id,
    topic=self.topic,
    strategy_id=event.strategy_id,
).time():
    alert.process()

# 2. 统计次数
metrics.ALERT_PROCESS_COUNT.labels(
    bk_data_id=bk_data_id, topic=topic, status=metrics.StatusEnum.from_exc(exc), exception=exc
).inc()

# 3. 必须调用 report_all 才会将上述两个指标统一进行上报
metrics.report_all()
```


## 当前支持的指标及含义说明

| 名称                                             | 描述                           | 类型        |
|------------------------------------------------|------------------------------|-----------|
| bkmonitor_datasource_query_time                | 各数据源查询请求耗时                   | histogram |
| bkmonitor_datasource_query_count               | 各数据源查询请求次数                   | counter   |
| bkmonitor_access_data_process_time             | access(data) 模块处理耗时          | histogram |
| bkmonitor_access_data_process_count            | access(data) 模块处理次数          | counter   |
| bkmonitor_access_data_process_pull_data_count  | access(data) 模块数据拉取条数        | counter   |
| bkmonitor_access_event_process_time            | access(event) 模块处理耗时         | histogram |
| bkmonitor_access_event_process_count           | access(event) 模块处理次数         | counter   |
| bkmonitor_access_event_process_pull_data_count | access(event) 模块数据拉取条数       | counter   |
| bkmonitor_access_process_push_data_count       | access 模块数据推送条数              | counter   |
| bkmonitor_detect_process_time                  | detect 模块处理耗时                | histogram |
| bkmonitor_detect_process_count                 | detect 模块处理次数                | counter   |
| bkmonitor_detect_process_data_count            | detect 模块数据推送条数              | counter   |
| bkmonitor_trigger_process_time                 | trigger 模块处理耗时               | histogram |
| bkmonitor_trigger_process_count                | trigger 模块处理次数               | counter   |
| bkmonitor_trigger_process_pull_data_count      | trigger 模块数据拉取条数             | counter   |
| bkmonitor_trigger_process_push_data_count      | trigger 模块数据推送条数             | counter   |
| bkmonitor_nodata_process_time                  | nodata 模块处理耗时                | histogram |
| bkmonitor_nodata_process_count                 | nodata 模块处理次数                | counter   |
| bkmonitor_nodata_process_pull_data_count       | nodata 模块数据拉取条数              | counter   |
| bkmonitor_nodata_process_push_data_count       | nodata 模块数据推送条数              | counter   |
| bkmonitor_alert_process_time                   | alert(builder) 模块处理耗时        | histogram |
| bkmonitor_alert_process_count                  | alert(builder) 模块处理次数        | counter   |
| bkmonitor_alert_manage_time                    | alert(manager) 模块处理耗时        | histogram |
| bkmonitor_alert_manage_count                   | alert(manager) 模块处理次数        | counter   |
| bkmonitor_alert_process_pull_event_count       | alert(builder) 模块事件拉取条数      | counter   |
| bkmonitor_alert_process_drop_event_count       | alert(builder) 模块事件丢弃条数      | counter   |
| bkmonitor_alert_process_push_data_count        | alert(builder) 模块数据推送条数      | counter   |
| bkmonitor_alert_process_latency                | 告警从 access 到 alert 模块的整体处理延迟 | histogram |
| bkmonitor_alert_manage_push_data_count         | alert(manager) 模块数据推送条数      | counter   |
| bkmonitor_composite_process_time               | composite 模块处理耗时             | histogram |
| bkmonitor_composite_process_count              | composite 模块处理次数             | counter   |
| bkmonitor_composite_push_action_count          | composite 模块动作推送条数           | counter   |
| bkmonitor_composite_push_event_count           | composite 模块事件推送条数           | counter   |
| bkmonitor_converge_process_time                | converge 模块处理耗时              | histogram |
| bkmonitor_converge_process_count               | converge 模块处理次数              | counter   |
| bkmonitor_converge_push_converge_count         | converge 模块收敛记录推送条数          | counter   |
| bkmonitor_converge_push_action_count           | converge 模块动作记录推送条数          | counter   |
| bkmonitor_action_create_process_time           | action 模块动作创建耗时              | histogram |
| bkmonitor_action_create_process_count          | action 模块动作创建次数              | counter   |
| bkmonitor_action_create_push_count             | action 模块数据推送条数              | counter   |
| bkmonitor_action_execute_time                  | action 模块动作执行耗时              | histogram |
| bkmonitor_action_execute_count                 | action 模块动作执行次数              | counter   |
| bkmonitor_action_execute_latency               | 动作从 alert 到 action 模块的整体执行延迟 | histogram |
| bkmonitor_action_notice_api_call_count         | 通知类 API 调用次数                 | counter   |
| bkmonitor_alarm_cache_task_time                | 数据缓存任务执行耗时                   | histogram |
| bkmonitor_mail_report_send_latency             | 邮件订阅报表发送延迟                   | histogram |
| bkmonitor_mail_report_send_count               | 邮件订阅报表发送数量                   | counter   |
| bkmonitor_cron_task_execute_time               | 周期任务执行时间                     | histogram |
| bkmonitor_cron_task_execute_count              | 周期任务执行次数                     | counter   |

提示：可通过以下脚本对表格进行更新

```python
from core.prometheus.base import REGISTRY
for collector in REGISTRY._collector_to_names:
    print("| %s | %s | %s |" % (collector._name, collector._documentation, collector._type))
```

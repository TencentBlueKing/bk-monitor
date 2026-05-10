# Composite

模块负责对已有告警执行关联策略检测，并在命中时生成新的“关联告警事件”，再交回统一告警链路继续处理。

## 功能

### 模块职责

- 对单条已有告警执行动作信号检测
- 对单条已有告警执行关联策略检测
- 当关联策略命中时，生成新的 `data_type=alert` 事件
- 将新事件重新投递到统一监控事件 Kafka，由后续统一 alert builder 生成新的关联告警

### 模块边界

- `composite` 的输入不是原始采集事件，而是“已经生成的告警”
- `composite` 不直接创建 `AlertDocument`
- `composite` 的职责是“判定是否应该产出新的关联告警事件”
- 新事件最终变成告警，仍由统一 `alert` 模块负责

## 数据来源

`composite` 的主入口由 `alert` 模块触发。

在 `alarm_backends/service/alert/processor.py` 中：

- `send_signal(alerts)` 会遍历本轮状态有变化的告警
- 对未被熔断的告警调用 `check_action_and_composite.delay(alert_key=alert.key, alert_status=alert.status)`

因此，`composite` 的输入来源是：

- 新产生的异常告警
- 状态发生变化的告警（异常、恢复、关闭）

但前提是：

- 告警没有被熔断

## 适用场景与边界

### 会进入 composite 检测的告警

- 当前告警不是关联告警策略自身生成的告警
- 当前告警不是无数据告警
- 当前业务下存在与这条告警相关的关联策略

### 不会继续做关联检测的告警

- 当前告警本身已经是关联告警策略产生的告警
  - 目的是避免递归触发关联检测
- 当前告警是无数据告警
  - `process()` 中显式跳过
- 当前告警被熔断
  - `alert.processor.send_signal()` 中不会投递到 `composite`

## 数据处理流程

### 1. 任务入口 check_action_and_composite

入口在：

- `alarm_backends/service/composite/tasks.py`

任务函数：

- `check_action_and_composite(alert_key, alert_status, composite_strategy_ids=None, retry_times=0)`

处理流程：

1. 根据 `alert_key` 获取当前告警
2. 若告警不存在，则延迟重试
3. 若告警没有 `bk_biz_id`，直接跳过
4. 实例化 `CompositeProcessor`
5. 调用 `processor.process()`

标准任务输入示意：

```python
{
  "alert_key": {
    "alert_id": "...",
    "strategy_id": ...,
    "dedupe_md5": "..."
  },
  "alert_status": "ABNORMAL|RECOVERED|CLOSED",
  "composite_strategy_ids": [...],
  "retry_times": 0
}
```

### 2. process() 总流程

`CompositeProcessor.process()` 的逻辑分两段：

1. `process_single_strategy()`
   处理当前告警自身的动作信号
2. 关联策略检测
   - 若当前告警本身是关联告警，跳过
   - 若当前告警是无数据告警，跳过
   - 否则 `pull()` 拉取关联策略并逐个执行 `process_composite_strategy()`

### 3. pull() 拉取关联策略

`pull()` 的逻辑：

- 如果任务没有显式传入 `composite_strategy_ids`
- 则根据当前告警去 `StrategyCacheManager.get_fta_alert_strategy_ids(...)` 查询关联策略 ID

查询方式分两种：

- 如果当前告警有 `strategy_id`，按 `strategy_id` 查
- 否则按 `alert_name` 查

随后通过：

- `StrategyCacheManager.get_strategy_by_ids(self.strategy_ids)`

拿到完整策略快照。

### 4. process_composite_strategy() 进行关联检测

这是模块的核心函数。

位置：

- `alarm_backends/service/composite/processor.py`

处理步骤：

1. `cal_match_query_configs(strategy)`
   判断当前告警命中了哪些 `query_config`
2. 若没有任何命中配置，直接退出
3. `cal_public_dimensions(strategy)`
   计算该关联策略所有 `query_config` 的公共维度
4. 从当前告警的事件内容中提取这些公共维度值
5. 对维度值计算 `dimension_hash = count_md5(dimension_values)`
6. 对 `(strategy_id, dimension_hash)` 加锁，避免并发重复生成
7. `get_alert_by_alias(...)`
   将各 query_config 当前状态装配为表达式上下文
8. `do_detect(...)`
   计算 detect 表达式是否命中，并判断是触发还是关闭
9. 若未命中，直接退出
10. 若命中，则调用 `add_event(...)`
11. 调用 `push_events()` 将新事件回灌到统一事件入口
12. 更新 `COMPOSITE_DETECT_RESULT` 缓存

## 关联检测的关键判断

### query_config 匹配条件

`CompositeProcessor.is_valid_datasource()` 目前只认可两类输入告警：

#### 1. BK_FTA 的 alert 类型

满足以下条件：

- `data_source_label == BK_FTA`
- `data_type_label == ALERT`
- `query_config["alert_name"] == self.alert.alert_name`

注意这里是：

- `BK_FTA + ALERT`

不是 `BK_FTA + EVENT`。

这说明 `composite` 模块处理的是“已经生成出来的告警”，不是原始 `bk_fta` 事件。

#### 2. BK_MONITOR_COLLECTOR 的 alert 类型

满足以下条件：

- `data_source_label == BK_MONITOR_COLLECTOR`
- `data_type_label == ALERT`
- `query_config["bkmonitor_strategy_id"] == self.alert.strategy_id`

### 公共维度的作用

`cal_public_dimensions(strategy)` 会取所有 `query_config.agg_dimension` 的交集。

这些公共维度有两个作用：

1. 用来计算 `dimension_hash`
2. 用来构造新关联事件的 `tags` 和 `dedupe_keys`

这意味着：

- 关联告警最终按什么维度归并
- 在 `process_composite_strategy()` 里就已经决定了

## 标准输出

`process_composite_strategy()` 命中后，并不会直接创建告警，而是先调用 `add_event()` 生成一条新的事件。

### add_event() 产出的事件特征

关键字段包括：

- `event_id = "{dimension_hash}.{now_time}"`
- `plugin_id = settings.MONITOR_EVENT_PLUGIN_ID`
- `strategy_id = 当前关联策略ID`
- `alert_name = 当前关联策略名称`
- `status = ABNORMAL 或 CLOSED`
- `severity = detect 命中的 level`
- `data_type = alert`
- `metric = 关联策略所有 query_config 的 metric_id`
- `extra_info.origin_alarm.data.dimensions = 当前命中的公共维度`
- `extra_info.strategy = 当前关联策略快照`

标准输出示意：

```json
{
  "event_id": "{dimension_hash}.{now_time}",
  "plugin_id": "bkmonitor",
  "strategy_id": 1001,
  "alert_name": "关联告警策略名",
  "description": "满足表达式 A and B",
  "severity": 2,
  "tags": [
    {
      "key": "ip",
      "value": "127.0.0.1",
      "display_key": "IP",
      "display_value": "127.0.0.1"
    }
  ],
  "target_type": "HOST",
  "target": "127.0.0.1",
  "status": "ABNORMAL",
  "metric": [
    "bk_fta.alert.xxx"
  ],
  "category": "os",
  "data_type": "alert",
  "dedupe_keys": [
    "tags.ip"
  ],
  "time": 1710000000,
  "bk_ingest_time": 1710000001,
  "bk_clean_time": 1710000001,
  "bk_biz_id": 2,
  "extra_info": {
    "origin_alarm": {
      "data": {
        "dimensions": {
          "ip": "127.0.0.1"
        },
        "value": 1
      }
    },
    "strategy": {
      "id": 1001
    }
  }
}
```

## 输出后的去向

`push_events()` 会调用：

- `MonitorEventAdapter.push_to_kafka(self.events)`

因此 `composite` 产出的事件会被重新投递到监控事件 Kafka，而不是在本模块内直接落成告警。

后续链路是：

1. 新的 `data_type=alert` 事件进入统一事件消费链路
2. 统一 alert builder 消费这条事件
3. alert builder 判断是创建新的关联告警，还是更新已有的关联告警

所以更准确地说：

- `composite` 是“关联告警事件生产模块”
- `alert` 才是“关联告警落库模块”

## Redis / 缓存说明

`composite` 相关的关键缓存包括：

- `COMPOSITE_DIMENSION_KEY_LOCK`
  - 维度锁，避免同一 `(strategy_id, dimension_hash)` 并发重复处理
- `COMPOSITE_DETECT_RESULT`
  - 缓存某个 `(strategy_id, dimension_hash)` 最近一次关联表达式检测结果
- `COMPOSITE_CHECK_RESULT`
  - 记录某个 query_config 在某个维度上的异常告警集合，用于表达式求值
- `ALERT_DETECT_RESULT`
  - 当前告警动作信号处理结果缓存
- `ALERT_FIRST_HANDLE_RECORD`
  - 首次处理记录，避免重复推送动作

## 与其他模块的关系

### 与 alert 模块

- `alert.processor.send_signal()` 负责把状态变化的告警投递给 `composite`
- `composite` 生成的新事件，最终仍回到 `alert` 模块继续生成告警

### 与 action 模块

- `process_single_strategy()` 中会根据当前告警状态生成动作信号
- `push_actions()` 通过 `create_actions.delay(**action)` 投递到动作执行链路

### 与 MonitorEventAdapter

- `add_event()` 中使用 `MonitorEventAdapter.extract_target(...)` 统一解析目标
- `push_events()` 中使用 `MonitorEventAdapter.push_to_kafka(...)` 统一投递事件

## 一句话总结

`composite` 模块并不直接“创建关联告警对象”，而是对已有告警做关联策略检测；当 `process_composite_strategy()` 命中时，它会生成一条新的 `data_type=alert` 事件并重新投递到统一事件入口，后续再由统一 alert builder 生成最终的关联告警。

## 其他

- 模块需统计指标数据，能代表目前的处理能力
- 完善的日志记录
- 单元测试

# Trigger

模块负责对接各种触发逻辑

## 功能

- 支持的触发方式
    - 仅支持单指标检测
    - x 个周期内满足 y 次，则触发一个事件

- 触发依据
    1. 相同维度会累计次数
    2. 主机、进程监控需要去除部分可能发生漂移的维度

## 模块设计

待补充

## 数据处理流程

- 从 ANOMALY_SIGNAL_KEY 拉取一条记录，获取出现异常点的策略(strategy_id)和监控项(item_id)
- 从 ANOMALY_LIST_KEY 中拉取对应策略监控项的异常检测结果 anomaly_points（多条）
- 对于每一条检测结果 anomaly_point，执行以下操作
    - 从 anomaly_point 获取 strategy_snapshot_key ，进而获取检测出异常时使用的策略快照数据 strategy
    - 从 `strategy.query_config` 中获取 check_window_unit：监控周期对应字段 `agg_interval`，多个 `query_config`
      取最小周期，取不到用默认值 60s
    - 从 `strategy.detects[].trigger_config` 中获取
        - check_window -> check_window_size: 不同告警级别对应的周期大小
        - count -> trigger_count: 不同告警级别对应的触发次数
    - 从 anomaly_point 中解析出
        - dimensions_md5: 维度 MD5
        - source_time: 数据时间
    - 将 anomaly_point 中检测出的异常等级从高到低排列
        - 从 CHECK_RESULT_CACHE_KEY 中获取对应维度和级别的检测结果，时间范围为 (source_time - check_window_unit *
          check_window_size + 1) ~ source_time
        - 统计结果中带有 ANOMALY_LABEL 后缀的点的数量
            - 若数量大于或等于 trigger_count，则触发一条异常事件
            - 否则，继续检测下一个等级
        - 算法级别从高到低判断，如果高级别算法已经触发，则无需判断低级别
- 按告警等级拆分为多条，保存到 AnomalyRecord 表中
- 按触发告警的等级及 anomaly_timestamps 生成 EventRecord
- 格式化为自愈事件记录
- 推送事件记录到输出队列

## 无数据检测

> 流程同「数据处理流程」，有以下适配

- anomaly_point 无数据类型检测：`data.dimensions` 中存在 `__NO_DATA_DIMENSION__=true`
- 从 `strategy.items[].no_data_config` 中获取
    - continuous -> check_window_size: 不同告警级别对应的周期大小
    - continuous -> trigger_count: 不同告警级别对应的触发次数

## 相关数据说明

### 标准输入数据

```json
{
  "data": {
    "record_id": "{dimensions_md5}.{timestamp}",
    "value": 1.38,
    "values": {
      "timestamp": 1569246480,
      "load5": 1.38
    },
    "dimensions": {
      "ip": "127.0.0.1"
    },
    "time": 1569246480
  },
  "anomaly": {
    "1": {
      "anomaly_message": "",
      "anomaly_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
      "anomaly_time": "2019-10-10 10:10:00"
    }
  },
  "strategy_snapshot_key": "cache.strategy.snapshot.{strategy_id}.{update_time}"
}
```

### 标准输出数据

原始输出数据（EventRecord）

```json
{
  "data": {
    "record_id": "{dimensions_md5}.{timestamp}",
    "value": 1.38,
    "values": {
      "timestamp": 1569246480,
      "load5": 1.38
    },
    "dimensions": {
      "ip": "127.0.0.1"
    },
    "time": 1569246480
  },
  "anomaly": {
    "1": {
      "anomaly_message": "",
      "anomaly_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
      "anomaly_time": "2019-10-10 10:10:00"
    }
  },
  "strategy_snapshot_key": "xxx",
  "trigger": {
    "level": "1",
    "anomaly_ids": [
      "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}"
    ]
  }
}
```

经过 `MonitorEventAdapter.adapt` 转化后的自愈事件记录

```json
{
  "event_id": "{dimensions_md5}.{timestamp}.{strategy_id}.{item_id}.{level}",
  "plugin_id": "bkmonitor",
  "strategy_id": 1,
  "alert_name": "test",
  "description": "异常测试",
  "severity": 2,
  "tags": [],
  "target_type": "HOST",
  "target": "127.0.0.1",
  "status": "ABNORMAL",
  "metric": [
    "bk_monitor.system.cpu_detail.idle"
  ],
  "category": "os",
  "data_type": "time_series",
  "dedupe_keys": [],
  "time": 1569246480,
  "anomaly_time": 1569246240,
  "bk_ingest_time": 1705852861,
  "bk_clean_time": 1705852861,
  "bk_biz_id": 2,
  "extra_info": {
    "origin_alarm": {
      "trigger_time": 1705852861,
      "data": {
        "record_id": "{dimensions_md5}.{timestamp}",
        "value": 1.38,
        "values": {
          "timestamp": 1569246480,
          "load5": 1.38
        },
        "dimensions": {
          "ip": "127.0.0.1"
        },
        "time": 1569246480
      },
      "trigger": {
        "level": "2",
        "anomaly_ids": [
          "55a76cf628e46c04a052f4e19bdb9dbf.1569246240.1.1.2",
          "55a76cf628e46c04a052f4e19bdb9dbf.1569246360.1.1.2",
          "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2"
        ]
      },
      "anomaly": {
        "1": {
          "anomaly_message": "异常测试",
          "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.1",
          "anomaly_time": "2019-10-10 10:10:00"
        },
        "2": {
          "anomaly_message": "异常测试",
          "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.2",
          "anomaly_time": "2019-10-10 10:10:00"
        },
        "3": {
          "anomaly_message": "异常测试",
          "anomaly_id": "55a76cf628e46c04a052f4e19bdb9dbf.1569246480.1.1.3",
          "anomaly_time": "2019-10-10 10:10:00"
        }
      },
      "dimension_translation": {},
      "strategy_snapshot_key": "xxx"
    }
  }
}
```

## 流程

1. 拉取异常（异常包括：数据和配置）
2. 将异常写入 MySQL
3. 根据触发条件判断
4. 满足则输出到事件队列

## 其他

- 模块需统计指标数据，能代表目前的处理能力
- 完善的日志记录
- 单元测试
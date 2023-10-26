## 代码目录

### access

用来做数据接入，对接不同的数据源。

- 接入原始数据
    - 输入拉取数据的相关配置（从配置文件或缓存获取）
    - 数据拉取
    - 维度补充
    - 范围过滤
    - 输出标准数据

- 接入事件数据
    - 事件原始数据拉取
    - 维度补充
    - 范围过滤
    - 输出标准事件数据

- 接入告警数据
    - 告警原始数据拉取
    - 输出标准动作数据


### detect

用来做数据检测，对接不同的检测算法。得到一个个异常

- 输入标准数据
- 算法检测（包括多指标计算，多指标关联）
- 输出异常


### trigger

用来出事件检测

- 输入异常 + detect的检测结果
- 触发判断
- 输出事件


### recovery

用来做恢复检测

- 输入未恢复事件 + detect的检测结果
- 恢复判断
- 输出动作
    - 目前恢复的动作只有一种、就是恢复通知


### event

用来做事件关联，事件分析

- 输入事件
- 关联分析
- 输出动作
    - 目前动作只有一种、就是通知


### action

用来执行通知动作

- 通知汇总
- 通知屏蔽
- 通知发送


### selfmon

用来做自监控

- 处理日志文件（rotate） 
- 采集监控数据，做简单判断，并发送告警
- Qos检测


## redis 使用

### key的命名规则

- 统一前缀：`{app_code}.{platform}[.{env}].`

    - platform: ee, ce, te
    - env 为production 则不用填\[env]

- 前缀后对接对应services名称： access，detect等
    - 配置相关： 
      - 策略详情：config.strategy_{strategy_id}
        - 例： bk_monitor.ee.config.strategy_1001 或 bk_monitor.ee\[test].config.strategy_1001 
      - 策略ID列表: config.strategy_ids
      - 结果表信息: config.result_table_{source_type}_{table_id}
    - access拉取的时序数据：
        - 时序数据：access.data.strategy_{strategy_id}
            - 例：bk_monitor.ee.access.data.stragety_1001
        - 事件：access.evnet.strategy_{strategy_id}
        - 告警：access.alert.strategy_{strategy_id}
    - detect：
        - 异常数据：detect.

 
### redis中的db分配

    [7，8，9，10]，一共四个db
    
- db:7. [不重要，可清理] 日志相关数据使用log配置
- db:8. [一般，可清理]   配置相关缓存使用cache配置，例如：cmdb的数据、策略、屏蔽等配置数据
- db:9. [重要，不可清理] 各个services之间交互的队列，使用queue配置
- db:9. [重要，不可清理] celery的broker，使用celery配置
- db:10. [重要，不可清理] service自身的数据，使用service配置


### redis使用

- 所有的key必须带上前缀。第三方组除外，比如celery产生的
- 所有的key必须增加上过期时间
 
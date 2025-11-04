# FTA Action
模块负责执行动作

*action 相关队列及对应功能:*

- alarm-fta-action-worker: action 分发
- alarm-action-cron-worker: action 维护，同步至 ES， 轮值排班
- alarm-action-worker: 自愈套餐执行
- alarm-webhook-action-worker: webhook，队列 推送
- alarm-notice-action-worker: 通知执行(配置环境变量启用: ENABLE_NOTICE_QUEUE)


## 功能

- 配置来源
    - 来源文件
    - 来源配置中心（zk、consul、redis等）


- 数据来源
    - 目前从redis中拉取动作（FTA_ACTION_LIST）

- 支持的动作类型：
    - notice 
    - sops
    - itsm
    - job
    - webhook
    - collect

 
- 输出动作结果
 


## 其他

- 模块需统计指标数据，能代表目前的处理能力
- 完善的日志记录
- 单元测试（service/tests）
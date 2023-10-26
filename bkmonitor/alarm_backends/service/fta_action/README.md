# FTA Action
模块负责执行动作

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
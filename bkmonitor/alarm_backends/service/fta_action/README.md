# FTA Action
模块负责执行动作

## *action 相关队列及对应功能:*

- alarm-fta-action-worker: action 分发
  - celery_action,celery_interval_action
- alarm-action-cron-worker: action 维护，同步至 ES， 轮值排班
  - celery_action_cron
- alarm-action-worker: 自愈套餐执行
  - celery_running_action
- alarm-webhook-action-worker: webhook，message_queue 推送
  - celery_webhook_action
- alarm-notice-action-worker: 通知执行(配置环境变量启用: ENABLE_NOTICE_QUEUE)
  - celery_notice_action

## 模块概述

FTA Action 模块是蓝鲸监控平台中负责执行告警处理动作的核心组件，实现了完整的告警自愈和通知机制。该模块基于 Celery 分布式任务队列，支持多种类型的处理动作，包括通知、Webhook、作业执行、标准运维等。

## 架构设计

### 核心组件

- **BaseActionProcessor**: 所有动作处理器的基类，提供统一的执行框架和生命周期管理
- **ActionProcessor**: 各类型动作的具体处理器实现
- **ActionContext**: 动作执行上下文，提供告警信息、目标信息等执行环境
- **PushActionProcessor**: 动作分发器，负责将动作推送到相应的执行队列

### 处理器类型

1. **通知处理器** (`notice/processor.py`)
   - 支持多种通知方式：邮件、短信、语音、企业微信等
   - 实现通知汇总和防重复机制
   - 支持间隔式和递增式通知模式

2. **Webhook 处理器** (`webhook/processor.py`)
   - 支持 HTTP/HTTPS 回调
   - 可配置请求方法、头部、认证等
   - 提供重试和超时机制

3. **作业处理器** (`job/processor.py`)
   - 集成蓝鲸作业平台
   - 支持脚本执行和文件分发

4. **标准运维处理器** (`sops/processor.py`)
   - 集成标准运维流程
   - 支持流程模板执行

5. **消息队列处理器** (`message_queue/processor.py`)
   - 支持消息队列推送
   - 可配置队列参数和消息格式

## 核心功能

### 1. 动作创建与分发
- 根据策略配置自动创建处理动作
- 支持多种触发信号：异常、恢复、无数据等
- 智能分发到对应的执行队列

### 2. 执行生命周期管理
- **创建阶段**: 根据告警和策略生成动作实例
- **分发阶段**: 将动作推送到相应的执行队列
- **执行阶段**: 调用具体的处理器执行动作
- **回调阶段**: 处理异步执行结果和状态更新
- **结束阶段**: 记录执行结果和清理资源

### 3. 重试与容错机制
- 支持可配置的重试次数和间隔
- 区分不同类型的失败原因
- 提供超时保护机制
- 支持手动重试和跳过

### 4. 审批流程
- 集成 ITSM 审批流程
- 支持异常防御审批
- 自动创建和跟踪审批单据

### 5. 通知汇总与防重
- 相同维度告警的通知汇总
- 语音告警防重复机制
- 支持多种通知渠道和方式

### 6. 上下文管理
- 提供丰富的执行上下文信息
- 支持 Jinja2 模板渲染
- 动态获取告警、目标、业务等信息

### 7. 熔断保护机制
- 支持基于策略、业务、数据源等维度的熔断规则
- 创建阶段熔断（message_queue）和执行阶段熔断（其他类型）
- 通知类动作熔断时保存参数支持后续重放
- 完整的熔断日志和告警流水记录

## 队列架构

模块采用多队列架构，实现任务的分类处理和负载均衡：

- **分发队列**: 负责动作的创建和初始分发
- **执行队列**: 处理具体的动作执行逻辑
- **维护队列**: 处理定时任务和数据同步
- **专用队列**: 针对特定类型动作的优化处理

## 关键特性

### 高可用性
- 支持集群部署和负载均衡
- 提供完善的错误处理和恢复机制
- 实现任务状态的持久化存储
- **熔断保护**：防止告警风暴和系统异常时的动作执行风暴

### 可扩展性
- 插件化的处理器架构
- 支持自定义动作类型
- 灵活的配置和模板系统

### 可观测性
- 完整的执行日志记录
- 详细的性能指标监控
- 支持执行链路追踪
- 熔断状态监控和告警

### 安全性
- 支持多种认证方式
- 提供数据加密和脱敏
- 实现权限控制和审计

## 熔断功能

### 熔断机制

FTA Action 模块集成了完整的熔断保护机制，用于应对以下异常场景：

1. **告警风暴**：产生大量误告时，在执行阶段进行熔断，通知类动作会记录参数支持后续重放
2. **告警状态维护异常**：告警频繁创建关闭时，message_queue 在创建阶段熔断，其他类型在执行阶段熔断

### 熔断维度

支持基于以下维度的熔断规则：
- `strategy_id`：策略ID熔断
- `bk_biz_id`：业务ID熔断  
- `data_source_label`：数据源标签熔断
- `data_type_label`：数据类型标签熔断
- `strategy_source`：数据源组合熔断

### 使用示例

```python
from alarm_backends.core.cache.circuit_breaking import (
    set_strategy_circuit_breaking,
    set_bk_biz_id_circuit_breaking,
    clear,
)

# 设置策略熔断
set_strategy_circuit_breaking(
    module="action",
    strategy_ids=[12345, 67890],
    description="紧急熔断异常策略"
)

# 设置业务熔断  
set_bk_biz_id_circuit_breaking(
    module="action",
    bk_biz_ids=["100", "200"], 
    description="业务维护期间熔断"
)

# 清空熔断规则
clear("action")
```

详细使用说明请参考：`alarm_backends.core.circuit_breaking` 模块文档
# CollectInstanceStatusResource

## 基本信息

- **源文件**：`resources/status.py`
- **HTTP 端点**：`GET collect_instance_status`
- **resource 路径**：`resource.collecting.collect_instance_status`
- **功能**：获取采集配置下发实例的运行状态（默认不进行差异比对）
- **适配复杂度**：🟡 中（节点结构 + 实例字段转换，同 CollectRunningStatusResource）
- **注意**：继承自 `CollectTargetStatusResource`，仅覆盖了 `RequestSerializer`（`diff` 默认为 `False`）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| diff | bool | 否 | False | 是否只返回差异（默认不diff） |

## 出参

与 `CollectTargetStatusResource` 相同。

## bk-monitor-base 适配分析

> 继承自 `CollectTargetStatusResource`，默认 `diff=False`。
> 适配要点与 `CollectRunningStatusResource` 相同：虽然免去 diff 逻辑，但节点结构转换和实例字段补充仍需处理。
> 详见 [collect_running_status.md](./collect_running_status.md) 和 [collect_target_status.md](./collect_target_status.md)

### 补充说明
- 被 datalink 模块使用，用于策略详情展示（作为中间数据源）
- 节点结构/字段差异参见父类 spec 中的详细对比

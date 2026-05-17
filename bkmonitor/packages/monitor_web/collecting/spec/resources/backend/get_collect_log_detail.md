# GetCollectLogDetailResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`GET get_collect_log_detail`
- **resource 路径**：`resource.collecting.get_collect_log_detail`
- **功能**：获取采集下发单台主机/实例的详细日志信息
- **适配复杂度**：🟢 低～中（nodeman 主路径低；多安装器统一略增）

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| instance_id | str | 是 | - | 主机/实例ID |
| task_id | int | 是 | - | 任务ID |

## 出参

```python
# installer.instance_status() 返回值，具体结构取决于安装器实现
dict  # 包含实例的详细日志和状态信息
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `get_collect_installer()`
- `installer.instance_status(instance_id)`

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`get_nodeman_collect_log_detail()`**：对应旧版「单主机/实例采集日志详情」；与节点管理路径上的日志查询直接对齐（旧实现中的 `installer.instance_status` 类能力由该 operation 覆盖 nodeman 场景）。
- **`get_installer()`**：非节点管理插件类型若另有日志接口，需对照 base 是否在其它 API 中暴露；本 Resource 命名以 nodeman 为主时应优先走 **`get_nodeman_collect_log_detail()`**。

### 需 SaaS 层保留的逻辑
- **多插件类型分支**：若仅 nodeman 有专用日志 detail API，K8s/SQL 场景可能仍需 SaaS 调用对应 installer 方法或其它 base 接口，需按类型分发。
- **入参 `task_id`**：旧版未充分使用；若 base 接口要求任务 id，在 SaaS 从状态/重试结果中补齐。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`、`instance_id`、`task_id` → 映射为 deployment + 实例 + 任务等 base 要求字段（以 `get_nodeman_collect_log_detail` 签名为准）。
- **出参**：将 base 返回的日志/状态 dict 映射为当前前端契约；字段名差异在 SaaS 做别名。

### 修订后的适配复杂度评估
- **🟢 低**（nodeman 主路径）；若需统一多安装器日志形态则为 **🟢 低～中**。

### 风险点
- 仅 nodeman 有专用函数名时，其它类型易遗漏适配。
- `task_id` 与 base 必填项不一致会导致查询失败，需在调用链上明确来源。

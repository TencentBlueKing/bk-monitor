# RetryTargetNodesResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST retry`
- **resource 路径**：`resource.collecting.retry_target_nodes`
- **功能**：重试单个失败的实例或主机
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| instance_id | str | 是 | - | 需要重试的实例ID |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `get_collect_installer()`
- `installer.retry(instance_ids=[instance_id])`

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`retry_metric_plugin_deployment()`**：对应旧版对失败实例/主机重试；与 Installer 的 **`retry`** 能力一致。
- **`get_installer()`**：按插件类型选择 NodemanInstaller / K8sInstaller / SQLInstaller。

### 需 SaaS 层保留的逻辑
- 一般无需额外业务层；若需限制重试频率、权限二次校验，可在 SaaS 网关保留。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`、`instance_id` → 映射为 deployment 标识，并将 `instance_id` 传入 base 的实例列表参数（如 `instance_ids=[instance_id]`，以实际 API 为准）。
- **出参**：维持 `"success"` 字符串；若 base 返回任务/操作 id，SaaS 可选择性记录。

### 修订后的适配复杂度评估
- **🟢 低**：重试链路已在 base 打通，适配以参数映射为主。

### 风险点
- 不同 Installer 对 `instance_id` 格式要求需与旧版一致，避免 SQL/K8s/节点管理语义差异。

## 公共函数提取

与 `BatchRetryConfigResource`、`BatchRetryResource` 共享安装器获取逻辑。

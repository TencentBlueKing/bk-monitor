# ToggleCollectConfigStatusResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST toggle`
- **resource 路径**：`resource.collecting.toggle_collect_config_status`
- **功能**：启用或停用采集配置
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| action | str | 是 | - | 操作类型：`enable` / `disable` |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

### ORM 模型依赖
- `CollectConfigMeta`（含 `select_related("deployment_config")`）

### deploy 依赖
- `get_collect_installer()`：获取安装器
- `installer.start()` / `installer.stop()`：启动/停止

### 业务校验
- 检查 `last_operation` 防止重复启停

## bk-monitor-base 适配分析

### Base 已有能力（直接映射）
- **`start_metric_plugin_deployment()`**：对应 `action=enable` / 旧版启动。
- **`stop_metric_plugin_deployment()`**：对应 `action=disable` / 旧版停止。
- **Installer 能力**：Base Installer 已提供 `start` / `stop`；与上层 operation 一并构成完整启停链路。
- **`get_installer()`**：按插件类型选择 NodemanInstaller / K8sInstaller / SQLInstaller。

### 需 SaaS 层保留的逻辑
- **`last_operation` 等防重复启停**：若 base operation 未内建与旧版完全一致的前置校验，可在 SaaS 在调用前读取状态或依赖 base 返回的业务错误码做分支。
- **审计/操作日志**：若需与现网 SaaS 行为一致，可在网关层保留。

### 入参/出参转换要点
- **入参**：`bk_biz_id`、`id`、`action`（`enable`/`disable`）→ 映射为对应 deployment 标识并路由到 `start_*` / `stop_*`。
- **出参**：维持 `"success"` 字符串契约即可；若 base 返回结构化结果，SaaS 仅取成功/失败语义。

### 修订后的适配复杂度评估
- **🟢 低**：启停与安装器能力已在 `metric_plugin` 域就绪，适配以参数映射与错误码转换为主。

### 风险点
- 与旧版「重复操作」校验语义不一致时，需产品/接口层明确以 base 为准还是在 SaaS 补一层。

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `get_collect_config_or_raise` | 获取采集配置，不存在则抛异常 | 多个 Resource |
| `get_collect_installer` | 获取安装器实例 | 所有部署操作类 Resource |

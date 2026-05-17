# RunCollectConfigResource

## 基本信息

- **源文件**：`resources/backend.py`
- **HTTP 端点**：`POST run`
- **resource 路径**：`resource.collecting.run_collect_config`
- **功能**：主动执行部分实例或节点
- **适配复杂度**：🟢 低

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| action | str | 否 | "install" | 操作类型 |
| scope | object | 否 | - | 事件订阅监听的范围 |
| scope.node_type | str | 是 | - | 采集对象类型：TOPO / INSTANCE |
| scope.nodes | list | 是 | - | 节点列表 |

## 出参

```python
"success"  # 字符串
```

## 核心依赖

- `CollectConfigMeta`（含 `select_related("deployment_config")`）
- `get_collect_installer()`
- `installer.run(action, scope)`

## bk-monitor-base 适配分析

### 需 base 补齐的能力
- 安装器 `run()` 接口

### 风险点
- 逻辑简单，风险低

## 公共函数提取

安装器获取逻辑可与其他部署操作类 Resource 共享。

# FrontendCollectConfigDetailResource

## 基本信息

- **源文件**：`resources/frontend.py`
- **HTTP 端点**：`GET frontend_config_detail`
- **resource 路径**：`resource.collecting.frontend_collect_config_detail`
- **功能**：获取采集配置详细信息，供前端展示用（基本信息 + 运行参数 + 指标预览 + 采集目标）
- **适配复杂度**：🟡 中

## 入参（RequestSerializer）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| bk_biz_id | int | 是 | - | 业务ID |
| id | int | 是 | - | 采集配置ID |
| with_target_info | bool | 否 | True | 是否返回采集目标配置 |

## 出参

```python
{
    "basic_info": {
        "name": str,
        "target_object_type": str,
        "collect_type": str,
        "plugin_display_name": str,
        "plugin_id": str,
        "period": int,
        "bk_biz_id": int,
        "label_info": dict,
        "create_time": datetime,
        "create_user": str,
        "update_time": datetime,
        "update_user": str,
    },
    "runtime_params": [
        {
            "name": str,     # 参数描述或名称
            "value": Any,    # 参数值
            "type": str,     # 参数类型
        }
    ],
    "metric_list": [
        {
            "id": str,       # table_name
            "name": str,     # table_desc
            "list": [
                {
                    "metric": str,        # monitor_type
                    "englishName": str,    # name
                    "aliaName": str,       # description
                    "type": str,
                    "unit": str,
                }
            ],
            "table_id": str,
        }
    ],
    "subscription_id": int,
    "extend_info": dict,      # params 原始值
    "target_info": dict,      # 可选，来自 frontend_collect_config_target_info
}
```

## 核心依赖

### 内部 Resource 依赖
- `resource.collecting.collect_config_detail`：获取底层详情
- `resource.collecting.frontend_collect_config_target_info`：获取采集目标（可选）

### 特殊逻辑
- **SNMP 类型**：config_json 中有 `auth_json` 嵌套，需展平
- **mode 处理**：`mode != "collector"` 的统一为 `"plugin"`

## bk-monitor-base 适配分析

### 可适配部分
- 本 Resource 是纯展示层，主要是对 `collect_config_detail` 返回值的二次加工
- 适配关键在于底层 `collect_config_detail` 的适配

### 需 base 补齐的能力
- 无额外需求，依赖 `CollectConfigDetailResource` 的适配

### 风险点
- `config_json` 字段结构需与 base 侧对齐（特别是 SNMP 的 `auth_json`）
- `metric_json` 字段结构需与 base 侧对齐

## 公共函数提取

| 可提取逻辑 | 描述 | 复用场景 |
|-----------|------|---------|
| `format_runtime_params` | 运行参数格式化 | 前端详情 |
| `format_metric_list` | 指标列表格式化 | 前端详情 |

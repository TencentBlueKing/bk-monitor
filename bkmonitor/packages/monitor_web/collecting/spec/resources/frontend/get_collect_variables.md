# GetCollectVariablesResource

## 基本信息

- **源文件**：`resources/frontend.py`
- **HTTP 端点**：`GET get_collect_variables`
- **resource 路径**：`resource.collecting.get_collect_variables`
- **功能**：获取采集配置可用的模板变量列表（纯静态数据）
- **适配复杂度**：🟢 低

## 入参

无入参（无 RequestSerializer）。

## 出参

```python
[
    {
        "name": str,          # 变量名，如 "{{ target.host.bk_host_innerip }}"
        "description": str,   # 描述，如 "主机内网IP"
        "example": str,       # 示例，如 "127.0.0.1"
    }
]
```

## 核心依赖

无。纯静态数据返回。

## bk-monitor-base 适配分析

### 适配建议
- **可直接复用**，无需 base 侧任何改动
- 本 Resource 无 ORM、无外部 API 依赖，只是返回一组静态的变量定义
- 新老版本可共用同一个实现

### 风险点
- 无风险

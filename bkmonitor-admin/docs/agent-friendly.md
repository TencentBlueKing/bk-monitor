# AI 友好与 Agent 能力设计

## 目标

`bkmonitor-admin` 需要同时对两类 AI 友好：

- 对编码 AI 友好：AI 助手能快速理解项目结构、资源边界、接口协议和实现约束。
- 对运行时 AI Agent 友好：未来 AI 排障 Agent 能安全、稳定、可解释地调用后台 API。

第一期虽然不做 AI 排障功能，但 API、类型和页面结构要为后续能力留好接口。

## 对编码 AI 友好

### 稳定目录结构

使用 feature-first 结构，让 AI 可以通过目录直接定位资源：

```text
features/
├── kernel-rpc/
├── datasource/
└── result-table/
```

每个 feature 内部保持相似结构：

```text
api.ts
schemas.ts
types.ts
queries.ts
components/
pages/
```

### 单一事实源

资源字段、过滤条件、响应结构不要散落在页面里。推荐顺序：

1. 后端 RPC 描述 / OpenAPI / JSON Schema
2. 前端 Zod schema
3. TypeScript 类型由 schema 推导
4. 页面组件只消费类型化数据

### 小组件与明确命名

AI 更容易安全修改小而明确的文件。页面建议拆分：

- `DatasourceListPage`
- `DatasourceFilters`
- `DatasourceTable`
- `DatasourceDetailPanel`
- `DatasourceRelationTabs`

避免单个文件同时包含请求、状态、表格、详情和格式化逻辑。

### 文档即上下文

每个资源文档必须说明：

- 资源定位
- 涉及模型
- 列表字段
- 详情字段
- 过滤条件
- 关联关系
- 大数据量风险
- 后端接口需求
- 一期验收标准

## 对运行时 AI Agent 友好

### 工具注册模型

未来可以把每个后端操作描述为一个 Agent Tool：

```json
{
  "name": "datasource.detail",
  "description": "根据 bk_data_id 查询 DataSource 详情及关联信息",
  "safety_level": "read",
  "input_schema": {},
  "output_schema": {},
  "examples": []
}
```

Tool 调用必须绑定环境上下文。`environment_id` 可以来自会话上下文，但在调用记录和响应 meta 中必须显式呈现。

### 安全级别

建议保留以下 safety level：

| 级别 | 说明 | 一期是否允许 |
| --- | --- | --- |
| read | 只读查询 | 是 |
| inspect | 只读但可能访问较高成本或敏感上下文 | 可选 |
| dry_run | 生成变更计划但不执行 | 否 |
| write | 修改数据或触发刷新 | 否 |
| destructive | 删除、禁用、不可逆操作 | 否 |

第一期所有能力都应是 `read`。如果后续加入刷新路由、修复配置等能力，需要先进入 `dry_run`，再由用户确认执行。

### 稳定响应 envelope

建议所有 Agent-facing API 使用统一 envelope：

```json
{
  "data": {},
  "trace_id": "00-...",
  "warnings": [],
  "meta": {
    "environment_id": "prod-main",
    "operation": "datasource.detail",
    "safety_level": "read"
  }
}
```

列表接口：

```json
{
  "data": {
    "items": [],
    "page": 1,
    "page_size": 20,
    "total": 0
  },
  "trace_id": "00-...",
  "warnings": [],
  "meta": {
    "environment_id": "prod-main",
    "operation": "datasource.list",
    "safety_level": "read"
  }
}
```

错误结构：

```json
{
  "code": "DATASOURCE_NOT_FOUND",
  "message": "未找到匹配的数据源",
  "details": {
    "bk_data_id": 50010,
    "bk_tenant_id": "system"
  },
  "trace_id": "00-..."
}
```

### 可发现能力

除了现有 `kernel_rpc.__meta__`，后续建议提供更适合 Agent 的能力发现接口：

- `admin.meta.list_tools`
- `admin.meta.get_tool`

每个 tool 描述：

- name
- title
- description
- resource
- safety_level
- input_schema
- output_schema
- examples
- related_tools
- cost_hint

### 可解释调用链

未来 AI 排障时，每一步应能记录：

- 用户目标
- 选择的 tool
- 当前环境
- 入参
- 输出摘要
- 原始输出引用
- 下一步建议
- 是否需要人工确认

第一期只读页面可以先保留 trace、复制参数、复制结果等基础能力。

## API 命名建议

使用资源命名空间：

- `datasource.list`
- `datasource.detail`
- `result_table.list`
- `result_table.detail`
- `result_table.field_list`
- `result_table.field_options`

命名不要直接暴露 Django 模型内部方法，也不要用含糊动词，例如 `get_info`、`query_data`。

## 大数据量约束

AI Agent 很容易因为“想看全量”而触发高成本查询，所以接口层必须限制：

- 必须分页。
- 必须设置最大 `page_size`。
- 大字段默认不返回。
- 支持 `include` 参数按需展开关联信息。
- 对高成本查询返回 warning。

示例：

```json
{
  "table_id": "system.cpu",
  "environment_id": "prod-main",
  "include": ["options", "datasources"],
  "exclude": ["fields"]
}
```

字段列表必须单独调用 `result_table.field_list`。

---
name: bk-log-query
description: 蓝鲸监控日志统一查询与提取。根据用户意图自动路由到索引集日志查询、K8s/Host/自定义应用 场景查询或临时日志提取，将自然语言转换为 query_string 并返回日志明细。用户提到查询日志、搜索日志、检索日志、容器/Pod 日志、主机日志、自定义应用 日志、错误日志、日志聚类、字段分析、日志提取时使用。不用于日志接入或创建告警。
---

# 日志查询与提取

## 环境与依赖

同一目标监控网关下的 `log-query`、`log-scene-search` 和 `log-extract`；只使用目标环境实际提供的查询场景。

先确认目标环境和 `bk_biz_id`，再发现该环境已授权的 MCP 工具并读取实时 schema。下文的 Server 后缀不是可直接调用的完整名称；无法唯一定位或缺少依赖时停止相应步骤，不跨环境回退。宿主提供认证入口时使用该入口完成认证，不在 Skill 中保存凭据。

把用户的日志查询需求转换为 query_string，通过路由判断选择最优查询路径，返回日志明细或提取日志文件。

## 触发场景

当用户表达以下意图时使用本技能：

- 查询、搜索、检索日志内容或日志明细。
- 按关键字、字段、时间范围筛选日志。
- 查看某个服务、容器、主机、Pod、集群的日志。
- 查询自定义应用服务、调用目标、环境、实例或 Trace ID 日志。
- 查询错误日志、异常日志、特定级别的日志。
- 分析日志模式、聚类、字段分布。
- 从主机上提取未上报的日志文件。
- 查看日志上下文、前后日志。

## 不适用场景

- 创建日志关键字告警策略进入 告警策略配置能力。
- 告警根因分析、告警诊断进入 告警诊断能力。
- 指标查询、时序数据查询进入 指标查询能力。
- 告警日报、周报进入 告警报表能力。
- 日志接入、新建或修改采集项、清洗、存储进入 `bk-log-ingest`。

## 查询路由判断

根据用户意图和资源类型选择查询路径：

### 路由规则

| 用户意图特征 | 查询路径 | MCP Server |
| --- | --- | --- |
| 提及容器、Pod、Deployment、K8s、集群 | IaaS 容器日志查询 | `log-scene-search` |
| 提及主机 IP、服务器、物理机 | IaaS 主机日志查询 | `log-scene-search` |
| 提及 自定义应用、服务名、目标服务、实例 IP、Trace ID，且场景发现包含自定义应用|自定义应用场景日志查询 | `log-scene-search` |
| 指定索引集名称或 ID | 索引集日志查询 | `log-query` |
| 提及日志文件路径、未采集日志、临时提取 | 临时日志提取 | `log-extract` |
| 无明确资源类型 | 先列出索引集让用户选择 | `log-query` |

## 当前能力边界

- **索引集日志查询**：支持 query_string 检索、字段分析、日志聚类、上下文查看；需先获取 `index_set_id`。
- **场景日志查询**：支持 K8s、主机和实际场景发现返回的自定义应用等场景；路由维度和内容字段必须以实时场景 schema 为准，不能根据示例固定。
- **临时日志提取**：支持从主机提取未上报的日志文件；需用户确认后才能创建提取任务，涉及安全校验。
- 查询时间跨度不得超过 1 天（86400 秒），超过需分批查询后合并。
- 时间戳必须动态计算，不使用固定历史值。
- 每次调用 MCP 前先读取目标 server/tool 的最新 schema。
- 表中名称是监控 MCP Server 后缀；完整名称以已确认目标网关和发布环境的工具发现结果为准，客户端前缀可能不同。
- 临时日志提取当前存在公开 schema 与服务端契约漂移的已知风险；若实时 schema 缺少业务、主机、路径或过滤等关键字段，停止写操作并报告契约缺口，不猜参数或绕过 schema。

## 自然语言转 query_string

将用户的自然语言描述转换为日志平台 query_string 语法：

| 用户表达 | query_string |
| --- | --- |
| 查询 ERROR 级别日志 | `level:ERROR` |
| 包含 exception 关键字 | `exception` 或 `log:*exception*` |
| 状态码 500 的请求 | `status:500` |
| 路径包含 /api/ | `path:*api*` |
| 同时满足多个条件 | `level:ERROR AND status:500` |
| 满足任一条件 | `level:ERROR OR level:WARN` |
| 排除某个值 | `NOT level:DEBUG` |
| 某个字段存在 | `_exists_:trace_id` |
| Trace ID 精确匹配 | `trace_id:"abc123"` |

组合条件必须显式使用大写 `AND`、`OR`、`NOT` 并用括号表达优先级。**不得把空格当作隐式 `AND`**，因为真实环境中可能扩大查询范围。

## 通用安全规则

1. 所有操作限定在用户明确的 `bk_biz_id`。当前日志 MCP 不提供业务名称解析能力；用户只给业务名时必须要求提供 `bk_biz_id`，不得返回静态或猜测的业务候选。
2. 时间范围未指定时默认查询最近 1 小时，不主动扩大范围。
3. 查询接口默认限制 10-50 条以支持计数和去重，但面向用户默认只展示 3 条日志样例；用户明确要求更多时再增加。
4. 日志提取涉及主机执行，必须展示目标范围、路径、时间范围，获得用户明确确认后才创建任务。
5. 不把接口错误、中间状态或未完成的查询描述成最终结果。

## 索引集日志查询流程

适用于：用户指定了索引集，或需要精确的日志检索、聚类分析。

1. **获取索引集**：调用 `list_index_sets` 列出业务下所有索引集。
2. **确认索引集**：若用户未指定，展示索引集列表让用户选择；若已指定，按名称或 ID 定位。
3. **获取字段**：调用 `get_index_set_fields` 获取字段映射，用于构建 query_string。
4. **构建查询**：将用户意图转换为 query_string。
5. **执行搜索**：调用 `search_logs` 执行查询，返回日志明细。
6. **可选扩展**：
   - 日志聚类：调用 `search_log_clustering_pattern`。
   - 字段分析：调用 `analyze_field`。
   - 上下文查看：调用 `search_index_set_context`。

## 场景日志查询流程

适用于：查询 K8s 容器日志、主机日志和实时发现的自定义应用等场景日志。

1. **获取场景**：调用 `list_log_scenes` 列出业务可用的日志场景（如 k8s、host）。
2. **解析维度**：根据场景定义解析路由维度：
   - `choices_type: static` → 静态值，直接使用。
   - `choices_type: dynamic` → 调用 `list_scene_dimension_values` 获取合法值。
   - `choices_type: free_input` → 日志内容字段，用于 query_string。
3. **获取字段**：调用 `get_scene_log_fields` 获取场景下的字段映射。
4. **构建条件**：组装 `table_id_conditions`（路由条件）和 `query_string`（内容过滤）。
5. **执行搜索**：调用 `search_logs`（target_type=scene）执行查询。

场景 schema 是唯一事实来源：

- 只有实时 schema 中 `choices_type=dynamic/static` 的字段才能放入 `table_id_conditions`。
- `choices_type=free_input` 或字段发现返回的日志字段放入 `query_string`。
- 不得因为示例中出现过某字段，就把它固定当成路由维度。
- 例如某些 K8s 场景中，`cluster_id` 是路由维度，命名空间是内容字段 `__ext.io_kubernetes_pod_namespace`；若实时 schema 不同，按实时 schema 调整。

### K8s 容器日志查询示例

```
用户："查询 BCS-K8S-00000 集群 default 命名空间的 ERROR 日志"

路由条件 (table_id_conditions):
[[
  {"field_name": "scene", "value": ["k8s"], "op": "eq"},
  {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"}
]]

内容过滤 (query_string):
"__ext.io_kubernetes_pod_namespace:\"default\" AND level:ERROR"
```

### Host Scene 无结果边界

Host Scene 与指定索引集中的 `serverIp` 可能使用不同场景表和字段口径。Host Scene 无结果时必须提示：“场景无结果不代表所有索引集都没有该 IP 数据”，并建议用户选择索引集后按其真实主机字段继续检索。

###自定义应用场景查询

当 `list_log_scenes` 返回自定义应用场景时，先根据实时 schema 区分路由维度和内容字段，再支持服务名、目标服务、命名空间、环境、级别、容器、实例 IP、Trace ID 和无结果查询。字段名必须来自 `get_scene_log_fields`，不得固定假设。

## 临时日志提取流程

适用于：日志未上报到平台，需要从主机直接提取日志文件。

### 安全校验

提取前必须校验：
- **路径安全**：只能提取策略允许的目录和文件类型。
- **目标安全**：只能操作有权限的主机或拓扑节点。
- **时间安全**：时间范围合理，避免提取过大文件。
- **数据量安全**：评估目标主机数和文件大小，防止资源滥用。

### 执行流程

1. **获取拓扑**：调用 `list_log_extract_topology` 获取用户可访问的拓扑节点。
2. **查询主机**：调用 `search_log_extract_hosts` 定位目标主机。
3. **校验路径**：调用 `list_log_extract_allowed_paths` 确认允许的目录和文件类型。
4. **发现文件**（可选）：调用 `search_log_extract_files` 预览匹配的文件列表。
5. **展示确认**：向用户展示目标主机、路径、时间范围、过滤条件，获得明确确认。
6. **创建任务**：调用 `create_log_extract_task` 创建提取任务。
7. **轮询状态**：调用 `get_log_extract_task` 轮询任务状态，直到 `terminal: true`。
8. **获取下载**：若 `downloadable: true`，在用户请求时调用 `get_log_extract_download_url`。

每次提取调用都必须以实时公开 schema 为准，并核对以下契约完整性：

- allowed-path：能表达 `bk_biz_id` 和服务端要求的主机对象；
- file-search：能表达业务、主机、路径、递归和时间范围；
- create-task：能表达业务、主机、文件路径、过滤类型和过滤内容；
- poll/download：能表达业务和任务 ID。

任一步 schema 缺失关键字段或类型与上一步返回对象不兼容时，停止执行，输出缺失字段、工具名和 request_id（若有），不得依据示例强行提交。

下载时保留签名 URL 中的原始文件名。下载后如需解压，先检测真实文件类型再选择解压方式，不根据 `.tgz`、`.tar.gz` 后缀直接推断压缩格式。

### 提取过滤类型

| filter_type | 说明 | filter_content 字段 |
| --- | --- | --- |
| `""` | 不过滤，提取完整文件 | `{}` |
| `line_range` | 按行号范围 | `start_line`, `end_line` |
| `match_word` | 按关键字匹配 | `keyword`, `keyword_type` |
| `tail_line` | 提取最后 N 行 | `line_num` |
| `match_range` | 按起止标记 | `start`, `end` |

## 输出要求

**重要：输出前必须加载 [output-format.md](./references/output-format.md) 并严格遵循格式规范。**

### 格式规范要点

1. **元信息块必须包含**：查询路径、条件信息、时间范围
2. **日志样例默认 3 条**：第 1 条完整展示 MCP 返回的日志原文，不截断、不改写、不做语义总结；第 2、3 条只展示语义摘要
3. **表格只使用 Markdown 语法**；禁止用制表符、空格或 Unicode 边框字符手动画表格，长字段降级为列表
4. **确认提示使用分隔线**：`━━━` 包裹关键信息
5. **禁止事项**：不用 emoji（警告 ⚠️ 除外）、不编造数据、不省略关键参数

### 各阶段输出

- **查询前**：展示查询路径、索引集/场景、query_string、时间范围；需要选择时列出选项
- **查询后**：展示原始返回数、去重后数量、去重口径、默认 3 条日志样例和可用操作列表
- **提取前**：展示安全校验结果 + 确认框（主机、路径、过滤、警告）
- **提取后**：展示任务 ID、状态、下载提示
- **失败时**：展示错误信息、已完成步骤、建议下一步

查询结果还必须遵守：

- 重复记录同时展示“原始返回数”和“去重后数量”，说明去重键或口径，并保留查看原始记录的入口。
- 第 1 条样例无论长度都必须展示完整原文，内容与 MCP 返回一致；第 2、3 条可对超长日志生成语义摘要，并提供查看完整原文的入口。
- 用户错误默认输出归一化类别（索引集不存在、字段不存在、聚类未配置、参数错误、鉴权失败、提取失败、任务过期）和处理建议；保留 request_id 供排障，不直接倾倒多层内部异常。

## 按需加载资源

| 资源 | 何时加载 |
| --- | --- |
| [output-format.md](./references/output-format.md) | **每次输出前必须加载**，定义输出格式规范 |
| [mcp-workflow.md](./references/mcp-workflow.md) | 需要选择工具、编排查询流程时 |
| [query-string-syntax.md](./references/query-string-syntax.md) | 构建复杂 query_string 时 |
| [examples.md](./references/examples.md) | 需要典型查询示例或边界处理时 |

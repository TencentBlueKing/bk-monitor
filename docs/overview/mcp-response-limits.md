# MCP Resource 响应大小限制与 Review 结果

## 本次交付范围

本次先交付当前已覆盖的工具，不继续扩展 BKLOG 场景检索、APM、Profile、事件和 ES 等剩余读取链路。以下内容作为本次需求和后续提交的范围说明：

- 新增 Global Settings `MCP_MAX_RESPONSE_BYTES`，默认 5 MiB；已接入的 MCP Resource 共用 JSON 输出上限。
- 解析前限读覆盖 `execute_range_query`、`execute_sql_query`、`search_logs` 索引集分支、`analyze_field`、`find_relations`、`find_relations_range`；OpenClaw 日志的索引集路径复用相同保护。
- 新增运行逻辑在 `kernel_api/resource`，必要配置声明保留在默认配置和 Global Settings 注册处；原始 UQ / Grafana、公共客户端、鉴权及非 MCP 调用保持原逻辑。
- 已完成 97 项专项与 808 项原生 MCP 回归，共 905 项本地检查。预发布真实链路、实际容器大响应并发回放尚未完成，不把本次交付描述为所有 MCP 的 OOM 问题已解决。

本次实现按范围约束收敛：运行逻辑只在 `kernel_api/resource/`，另保留 Global Settings 的静态默认值和注册项。公共 Resource、公共 HTTP 客户端、原始 UQ / Grafana 接口、渲染器、鉴权中间件和网关 Schema 均已恢复，未修改原接口。

## 通用能力与实际覆盖

`mcp_response.MCPResource` 提供通用 JSON 输出限制，指标、日志、APM、告警、事件、关联关系、日志采集/提取、OpenClaw、运营数据和 Unified MCP 封装共用同一个配置。22 个 MCP 封装模块通过 Resource 继承引用接入；执行逻辑集中在三个 Resource 文件中。

- `mcp_response.py`：识别 MCP 请求、读取动态配置、检查 API JSON 字节数、提供可复用的有界 JSON 读取。
- `mcp_uq.py`：MCP 专用有界 UQ 读取适配器，统一复用原 UQ 参数校验、空间/租户和关联查询灰度路由。
- `mcp_metrics_query.py`：复用原 Grafana 校验与格式化方法，PromQL 读取委托 `mcp_uq.py`。
- `metrics.py`：MCP 请求进入专用读取适配器；非 MCP 请求继续调用原 `resource.grafana.graph_promql_query`。

通用的是输出大小限制。解析前的有界读取已接入范围查询、SQL、索引集日志、字段分析和两个关系查询；其余 MCP 封装仍主要是输出检查，不能代替解析前保护。这里的 UQ 适配器是 Resource 内的调用封装，不修改 UQ 服务和 `api/unify_query` 原始客户端。

原来直接复用 `metadata`、`monitor_web` 等目录原始 Resource 的独立 MCP 路由，不会因为本次改动被自动接管。若要覆盖，需要在我们自己的 Resource 中新增封装并单独接入。显式 `HttpResponse`、SSE 和文件流不按 JSON 检查，后台无请求上下文的任务也不自动认定为 MCP。

## Review 发现与修复

| 问题 | 处理 |
| --- | --- |
| 上版公共客户端改变了所有 MCP 上游调用的压缩协商、重定向和读取行为 | 撤回公共客户端修改，有界读取只在我们范围查询的专用适配器执行 |
| 上版公共 Resource / 渲染器拦截范围过大 | 撤回，只有显式继承 MCPResource 的封装启用检查 |
| 非 MCP 请求可能因 MCP 配置错误受到影响 | 非 MCP 分支先返回原校验结果，不读取限制值、不改变输入输出 |
| 旧请求来源配置为空时，缺失请求头可能与空配置误匹配 | 要求实际请求来源头非空后再比较 |
| 渲染探针可能给已包装的业务字典补 trace_id | 只对顶层副本构造渲染探针，返回原业务对象 |
| Native Unified 快速路径在 Resource 返回后再加 status/tool_name/meta 包装 | 校验时计入该包装，不改原中间件 |
| 额外的序列、点数和进程内并发限制扩大了兼容性风险 | 本次撤回，只保留明确要求的最大响应体限制；其他优化作为后续建议 |
| 上游错误正文可能经异常、日志和 API 包装再次放大 | 第一批共用 UQ 适配器仅保留前 512 个字符，并标明截断 |

输出校验位于 `validate_response_data` 中，仍在原 Resource 的异常和指标处理范围内。正常请求参数、序列化器、权限、查询步长和成功结果结构均保持原有契约。超限抛出 `ValidationError`，含 `reason=result_too_large`、当前字节上限及缩小查询的提示，不静默截断，不自动重试。

原生入口和历史 API 沿用各自既有错误协议；部分历史接口使用 HTTP 200 携带业务错误码，调用方仍需检查业务结果。写操作的输出校验发生在执行后，超限不代表写操作被撤销，不能据此盲目重试。

## Global Settings 生效机制

```python
MCP_MAX_RESPONSE_BYTES = 5 * 1024 * 1024  # 默认 5 MiB，单位为字节
```

唯一的新配置同时定义于 `config/default.py` 和 `bkmonitor/define/global_config.py` 的 `ADVANCED_OPTIONS`，注册为最小值为 1 的 IntegerField。部署沿用项目既有配置初始化流程。

这两个声明缺一不可：`DynamicSettings.__getattr__` 先读取静态属性，再查动态配置。仅在 `getattr` 中给默认值，不能代替静态声明。实现每次读取 `settings.MCP_MAX_RESPONSE_BYTES`，没有模块级取值或额外缓存；默认值、注册字段和真实动态读取链路已有测试。

配置修改沿用现有缓存机制，并非所有 worker 保存后立即更新：

- 本进程经 `settings.KEY = value` 写入时，会清理本进程内存缓存及 Redis；下一次读取生效。
- 直接保存 GlobalConfig / 数据库时，现有模型没有主动清理这两层缓存。单层 TTL 为 180 秒，其他 worker 若在旧 Redis 值到期前回填本地缓存，延迟可能接近 360 秒。
- 配置缓存过期后，新值会实际改变响应放行结果，无需重启。跨 worker 立即失效需要改公共动态配置机制，超出本次约定范围。

限制分别约束范围查询上游解压后的 JSON 和 Resource 按实际 API 编码构造的响应。计数包含 ASCII 转义、API 包装、字段转换，以及 Native Unified 的额外包装。网关之后追加的 MCP / JSON-RPC 包装不在监控侧计数内，网关仍需自己的上限。

## 第一批 UQ 调用的读取保护

专用适配器按操作白名单复用原 UQ Resource 的参数校验，以及现有空间路由、租户推导和查询来源标记；保留 `query_raw` 的 `_from → from` 转换、`query_reference` 的默认值和关系查询的 v1/v1beta3 选择。由于原 UQ 客户端没有可覆写的读取钩子，适配器显式保留请求构造部分，不修改或 monkeypatch 原客户端。原接口将来调整这些契约时，需要同步适配器并运行对比测试。

新路径使用 `stream=True`，每次最多读取 64 KiB，临近上限时只读取剩余额度加一个字节。超限发生在 JSON 解析前，异常、正常、解析失败和上游错误都会关闭连接。gzip 使用有界解压；成功和错误响应都受相同字节限制。

该路径协商 `gzip, identity`，不自动跟随重定向，避免跳转时提前读取完整响应。这些行为只存在于 MCP 专用适配器，需在预发布确认 UQ 路由直接返回预期 JSON。普通调用保留原 HTTP 行为。

5 MiB 是 JSON 字节上限，不等于单请求的内存上限。对于没有接入有界读取的其他工具，业务端仍可能先构造完整大对象，再被输出检查拒绝。

## 剩余读取链路与最小接入方案

当前不能宣布整体问题已解决。已有通用输出检查及第一批 UQ 限读，仍缺少 BKLOG、APM 等其他主数据读取的保护、累计结果预算及真实容器并发回放。下面的优先级根据代码读取和聚合方式判断，不是线上流量或内存实测排序。

### 剩余链路

| 优先级 | MCP / 调用点 | 实际读取链路与内存风险 | 只在 Resource 目录接入的办法 |
| --- | --- | --- | --- |
| 已接入，待容量验证 | `execute_range_query` | MCP 专用 UQ 客户端解析前限读；后续仍需 JSON 对象和图表格式化内存 | 共用第一批读取适配器，错误正文已摘要化；在实际内存限制下回放后验收 |
| 本轮已接入 | `execute_sql_query`、`search_logs(index_set)` | 原 `query_raw` 完整读取路径已在 MCP 分支替换；默认条数、`keep_columns` 本身不是字节上限 | 共用 MCP UQ 限读适配器，保留 `_from` 到 `from` 转换、空间和租户规则 |
| 本轮已接入 | `analyze_field` | MCP 分支通过适配器调用 `query_reference`；`limit` 仍按原契约允许为空 | 覆盖 `/query/ts/reference` 的解析前字节限额，不另改查询规模 |
| 本轮已接入 | `find_relations`、`find_relations_range` | MCP 分支通过适配器调用两个关联查询；多个查询和关联结果仍可能扩大对象内存 | 解析前限读，沿用 relation v1 / v1beta3 动态路由 |
| P1 | `search_logs(scene)`、日志上下文、日志聚类 | `call_log_api` → `LogSearchAPIGWResource` → 公共 `APIResource.session` → 完整响应。scene 的 `keep_columns` 目前在返回后才投影；上下文 size 没有声明最大值 | Resource 内创建独立 BKLOG 客户端，在该实例的 Session 接入有界传输，保留原 URL 模板、身份、标准结果和错误处理 |
| P2 | Span 列表、Trace / Span 详情、OpenClaw Trace | Span 列表经过 `api.apm_api`，但 API 角色的 `KernelAPIResource` 会本地直调视图，再执行 `json.loads(response.rendered_content)`。详情进入 `QueryProxy / SpanQuery / UnifyQuerySet`，有 `list(...)`、缓存和多数据源合并 | 用 MCP 专用查询器把 UQ 执行点接到限读器，逐批检查累计结果后再追加；绕开本地完整渲染往返，保留现有数据源范围、字段和权限逻辑 |
| P2 | `query_graph_profile` | `GrafanaQueryProfileResource` → `ProfileQueryViewSet` → Doris / BKDATA 查询或 eBPF 分支 → `TreeConverter` → Grafana 数组。单个 stacktrace 还会再次 `json.loads` 并生成树节点 | MCP 专用 Profile 查询与转换入口；上游限读之外，须在展开堆栈、树和数组前限制累计帧数、深度和节点数。仅给 HTTP 加限制不够 |
| P2 | `search_event_log` | 普通与 APM 事件最终进入 `EventLogsResource` → `list(queryset)` → 多个富化处理器。QuerySet 遍历会先物化 `_result_cache`，之后还可能扩大对象数量 | MCP 专用有界查询集 / 编译执行入口；不能先 `list(queryset)` 再检查。富化阶段保留累计预算 |
| P2 | 告警列表 / 关联事件、部分运营指标 | 告警由 `AlertQueryHandler` / Document 直接执行 ES 查询；其他路径包含 ORM、BKDATA 及逐项汇总。不会全部经过 Requests Session | Resource 内显式创建有结果限制的查询对象；要保证解析前限额，还需 MCP 独立 ES 传输或原始 JSON 查询适配器。ES SDK 返回对象后再检查仍然太晚 |
| 后续复用 | 文件、主机、索引集、结果表和其他目录 | BKLOG API、ORM 或目录树；例如 `SearchLogExtractFilesResource` 先取得完整 files，再执行切片，返回少不代表读取少 | HTTP 路径复用 P1 独立客户端；ORM 路径在查询前做数量/字段约束并有界遍历。数量限制不能替代单条大字段的字节保护 |
| 范围外缺口 | 直接挂原始 Resource 的 metadata、dashboard 等独立路由，以及执行前的权限目录查询 | 不经过此次 MCPResource 封装；Native Unified 快速路径也不能假定一定经过 `ExecuteToolResource` | 仅在 Resource 目录新增类，不能自动改变已指向原始类的路由。需要后续明确路由/分发迁移范围；本次不把这些路径算作已受保护 |

可核查的主要代码位置：

- UQ 完整读取：`api/unify_query/default.py:155`；公共 API 完整读取：`core/drf_resource/contrib/api.py:282`。
- 日志入口：`kernel_api/resource/log_search.py` 中 `_search_by_scene`、`_search_by_index_set`、`FieldAnalyzeResource`；原生身份处理：`kernel_api/unified_mcp/permissions.py:359` 的 `call_log_api`。
- 本地 HTTP 形态往返：`core/drf_resource/contrib/nested_api.py:66`、`:104`；它说明为什么只挂 Session 不足以保护 APM。
- Span 批量物化：`apm/core/handlers/query/span_query.py:74`、`bkmonitor/data_source/models/query.py:75`；多数据源合并：`bkmonitor/data_source/unify_query/query.py` 的 `query_log`。
- Profile 树展开：`packages/apm_web/profile/diagrams/tree_converter.py:80`；告警 ES 读取：`packages/fta_web/alert/handlers/alert.py:805`。
- 文件切片发生在读取之后：`kernel_api/resource/log_extract.py:175`。以上路径均相对于 `bkmonitor/`。

### 第一批实施结果：补齐直接 UQ 调用

这一批已实现，运行代码全部在 `kernel_api/resource`，沿用现有 `MCP_MAX_RESPONSE_BYTES`，没有增加或调整配置，没有修改公共 UQ / HTTP / Resource / 鉴权 / 渲染器。与时间跨度防御一样，入口限定在我们的 MCP Resource；不同的是字节数需要在读取时判断，不能等完整结果返回。

| 文件 | 本轮完成的变更 |
| --- | --- |
| 新增 `mcp_uq.py` | 将现有 PromQL 适配器的请求构造提炼为显式白名单操作：`query_data_by_promql`、`query_raw`、`query_reference`、`query_multi`、`query_multi_resource_range`。复用原客户端的参数校验、空间路由、租户和来源头，统一有界读取 |
| `mcp_metrics_query.py` | PromQL 委托新适配器，删除重复的 UQ 请求构造，保留已有 Grafana 处理流程 |
| `metrics.py` | 仅 MCP 分支把 SQL 的 `query_raw` 调用换为新适配器，非 MCP 分支仍调用原 API |
| `log_search.py` | 仅 MCP 分支接入索引集查询的 `query_raw` 与字段分析的 `query_reference` |
| `relation.py` | 仅 MCP 分支接入两个关联查询操作，保留业务灰度决定的 v1 / v1beta3 路由 |

即 1 个新文件、4 个现有文件，补齐 5 个剩余 UQ 调用点，并让已完成的范围查询共用同一实现。这里的“最小”只表示该批次范围，不代表所有 MCP 已完成解析前保护。

适配器必须显式处理原 `QueryRawResource.perform_request` 的 `_from → from` 转换；不能直接把所有原始参数 POST 到固定地址。不要把 HTTP 字节保护误写成请求 `limit` 参数，也不要静默修改业务查询。

### 第二批最小方案：BKLOG 独立客户端

新增 `mcp_http.py`，先只由 `log_search.py` 的 scene、context、pattern 三类读取调用。新建具体 APIResource 的实例，给这个实例自己的 Session 装有界 HTTPAdapter；不修改全局 `api.log_search` 单例、原类或公共 Session。

选择 HTTPAdapter 的原因：已核对本机 Requests 的实现，Adapter 返回之后 Session 才处理重定向和非 stream 的 `r.content`。限读应放在这个返回点之前，并覆盖每一跳，而不是在 `client.request()` 返回后再包装 Response。需将现有读取器拆出“有界字节读取”底层，供原客户端后续 JSON / 错误处理消费，避免解析后重新拼成 JSON。

此方案保留原客户端的认证头、URL 参数、超时、标准结果和权限错误协议。原生日志分支必须保留 `call_log_api` 已有的新实例、`cacheless`、当前用户名和租户注入规则；大查询还须避免先从旧缓存反序列化超大对象。重定向累计正文也要限额，不能每跳都读到上限后全部留在 history 中。

`scene_search` 当前参数 Schema 没有明确的返回字段投影参数。不能凭空透传 `keep_columns` 就宣称已经在上游裁剪；仍需实际字节限读，字段投影能力另行核实。

### 复杂链路的最小原则

Trace、事件的 QuerySet / 编译器可以由 MCP 专用子类承接，但原查询执行器仍会落回公共 UQ；需要在我们目录内显式替换这个执行点，并在 `_result_cache` / `list(...)` 形成之前检查累计结果。只换成迭代器名称，底层仍整批解析，也不算有界。

Profile 需要 MCP 专用 BKDATA/eBPF 查询入口与有界转换器。现有业务编排内部硬编码调用全局客户端，不能声称只给新实例挂 Session 就会自动接管。应复用参数校验、SQL 生成和输出格式，仅替换必要的执行/转换编排；缺少实例注入点的部分需要单独做行为对比。

所有多批、多数据源、关系展开、树和富化合并都必须在追加前检查累计保留结果；每次 HTTP 都小于 5 MiB，累计几百次仍可能耗尽内存。现有配置是响应字节上限，不是 Python RSS 硬限额。对象展开预算、最大批次数与并发额度需要压测标定，不能只看序列化字节数估算。

### 什么条件下才能说 OK

1. 每一条纳入验收的主读取链路都有明确的解析前限额；本地构造、缓存命中与批量聚合有相应保护，并列出范围外路径。
2. 普通 API、非 MCP 请求及成功结果与原逻辑对比一致，保留鉴权、租户和关联灰度路由；超限不静默返回部分数据。
3. 超限、正常、超时、重定向和解析错误均关闭连接。返回简短错误摘要，不把大段上游正文再次放进异常响应和日志；第一批已补齐这项行为。
4. 用实际容器内存限制回放大响应并发、临界大小、慢读和多页累积，观察 SaaS 与网关 RSS 峰值和重启。范围查询原有离线测试不能替代这一步。
5. 给并发量设置可验收的边界。补齐每请求限读仍不能保证无限并发安全；网关聚合在途限制或 MCP Resource 内的进程级保护应单独标定并明确适用范围。

本轮已实施第一批 UQ 接入，并增加原始客户端/非 MCP 对比测试；第二批及复杂链路尚未实施。第一批可以准备预发布验证，不能作为所有 MCP 的 OOM 问题已解决的上线结论。

## 已完成的离线验证与后续验收

2026-10-21 同步 `master` 至 `99ce4a9fbc` 并恢复改动后重新验证，共 905 项通过（170.98 秒）：97 项专项检查、808 项原生 MCP 回归。专项覆盖五种 UQ 操作的原始序列化器、请求体/租户/路由对比、五个调用点的 MCP/非 MCP 分支、动态配置读取、错误摘要、读取超时关闭连接，以及不联网的真实 HTTP chunked 报文与 gzip 解析。Ruff、格式和 `git diff --check` 通过。

本轮开始前已保存改动文件哈希，完成后确认运行代码增量恰好是上表五个 Resource 文件；Global Settings 两处声明保持原样。共享 UQ 客户端、关系路由函数、公共 Resource/HTTP/渲染器和鉴权文件还逐个与 HEAD 比对，保持一致。这里验证的是本批增量，工作区仍保留前阶段已完成的通用输出限制。

本地检查覆盖：非 MCP 原样返回、空来源配置、不同 MCP 结果、字节边界、API 包装与原生 Unified 包装、业务对象不被修改、gzip 内存边界、连接关闭、旧新 UQ 路由/租户/请求体一致、Grafana 参数及输出一致，以及真实 DynamicSettings 的缓存更新逻辑。

配置测试运行真实 DynamicSettings / LazySettings 读取方法，以可控时钟模拟两层缓存及数据库传输。已验证配置从旧值更新后会改变实际放行结果，也重现了跨 worker 回填导致的延迟；不是线上配置修改或真实数据库验收。

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONPATH=.:bkmonitor bkmonitor/.venv/bin/python -m pytest \
  -c /dev/null -p no:cacheprovider \
  bkmonitor/kernel_api/tests/test_mcp_response_limits.py \
  bkmonitor/kernel_api/tests/test_native_mcp_permissions.py
```

重型 Resource 方法测试从实际源码 AST 加载，空间、鉴权和传输适配器使用模拟；Graph 对比使用实际参数校验和基础格式化，热力图、空点等处理器使用相同测试适配器，不等同于完整业务回放。有界读取使用真实 Requests / urllib3 / gzip，JSON 编码使用现有 DatetimeEncoder。本地 Django 3.2.25 与项目声明的 4.2.27 不同，完整依赖环境和预发布链路仍需验证。

后续优先评估 UQ 执行预算、网关跨 worker / 副本的在途并发与内存预算、同查询合并及有总字节上限的短缓存、MCP 精简格式和大结果异步导出。需要使用实际容器限制回放约 60 MiB × 10 并发及 90 MiB × 2 并发，检查 RSS、重启、GC/CPU、错误识别和重试行为。仅限制返回体不能承诺任意并发下不会 OOM。

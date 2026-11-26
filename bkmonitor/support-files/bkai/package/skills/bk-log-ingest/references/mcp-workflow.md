# 接入 MCP 编排

采集读写只使用目标监控网关的 `log-collector`；主机目标定位额外使用同环境 CMDB MCP 的四个工具，见 [host-target-resolve.md](host-target-resolve.md)。完整 Server 名称和参数以目标环境工具发现结果为准。鉴权失败时使用宿主认证入口；依赖仍不可用则停止，不跨环境调用。写操作只有用户确认**采集配置表单页**之后才能带 `confirm=true`。用户一确认（直接下发或下发并清洗），立刻 `fast_create_log_collector`，保证采集已在下发状态。清洗字段列表确认后才写清洗接口。

## 确认表单页

禁止用纯文本清单。三种类型的表单页见 [confirm-forms.md](confirm-forms.md)。

- 主机：配置表单 + 采集目标表 + 日志路径表
- 容器日志：配置表单 + 采集配置范围竖表（一条 config 一张，可含 Container / Node，含路径行）
- 容器标准输出：配置表单 + 采集配置范围竖表（一条 config 一张，仅 Container，无路径行）

Windows Event 未沉淀：用用户已给的原文列出，没给的标「待补充」，先问完再出可确认表单。不要套上面三页。

出表单前先解析存储集群名称，填进「存储集群」。禁止写「公共集群」。主机采集还要先完成目标定位（名称/IP → 内部 ID），定位失败不要出可下发表单。

## 工具

采集读写使用 `log-collector`。不要改用日志查询工具提交采集配置；主机目标是否属于本业务必须通过同环境 CMDB 核实。

| 步骤 | 工具 |
| --- | --- |
| 查已有项 | `list_log_collectors`（查启用项必须 `enabled=true`） |
| 读详情 | `get_log_collector` |
| 主机目标定位 | CMDB `CMDB MCP`：`open_list_biz_hosts`、`open_search_biz_inst_topo`、`open_search_dynamic_group`、`open_execute_dynamic_group`。细则见 [host-target-resolve.md](host-target-resolve.md) |
| 下发采集 | `fast_create_log_collector` / `fast_update_log_collector` |
| 写清洗和存储 | `update_log_collector_clean_config` |
| 看下发状态 | `get_log_collector_status` |
| 拉清洗样例 | 本 MCP **没有** `search_logs`。用 `get_log_collector` 的 `index_set` 确认已创建；用 `get_log_collector_status` 看是否已上报。没有样例则请用户手贴，不要改调其他 MCP（含 CMDB） |

`fast_create_log_collector` 创建时不能带清洗、存储、上报链路。创建结果是直接入库 + 平台默认集群。产品要求的过期时间 / 副本 / 分片 / 指定集群 / 清洗，一律在创建成功后用清洗写接口补上。

## 存储集群

本 MCP 没有集群列表。确认表必须展示集群**名称**，不要写「公共集群」。

- 用户指定了名称：就用该名称；写入前必须能对上 `cluster_id`，对不上就问清，不要猜。
- 用户未指定：由系统选定。出表单前 `list_log_collectors` 取同业务最近创建项，`get_log_collector` 读 `storage.display_name`（没有则 `cluster_name`）和 `cluster_id`。确认表只填名称。
- 本次 `fast_create` 成功后，以本次 `get_log_collector` 的 `storage.cluster_id` 为准写入；若名称与表单不一致，改用回读名称并告知用户。

## 主机目标定位（出表单前）

仅主机采集。容器日志 / 标准输出不要调 CMDB。

1. 用户给 IP、主机名、模块名、集群名或动态分组名。不要问 ID。
2. 按 [host-target-resolve.md](host-target-resolve.md) 在 `bk_biz_id` 下解析。云区域用主机记录，禁止默认 `0`。
3. 命中 0 条、拓扑不存在、或名称撞车尚未选清：停，不出确认表。
4. 确认表只填名称/IP；把 `target_node_type` + `target_nodes` 留到创建时用。动态拓扑和动态分组不要展开成 IP 再提交。

## 直接下发

用户确认后立刻执行，不要再问：

1. `fast_create_log_collector`（`confirm=true`）
   - 主机：`environment=linux`，`target_*` + `params.paths`，名称+英文名+`row`/`section`，`data_encoding`，`tail_files`
   - 容器日志：`environment=container`，`bcs_cluster_id` + `configs`（每条含 `collector_type`、`params.paths`、范围选择器）。`label_selector` 即使为空也要带。不要传主机 `target_nodes`
2. `get_log_collector` 取 `collector_config_id`、`table_id`、`storage.cluster_id`
3. `update_log_collector_clean_config`：`etl_config=bk_log_text`，`fields=[]`，原文保留、失败日志保留，存储用用户值或默认（过期 3、副本 0、分片 3）。未指定集群则用步骤 2 的 `cluster_id`
4. `get_log_collector_status` 看到终态再汇报

编辑已有采集：采集范围（`tail_files`）不要改。只改采集用 `fast_update_log_collector`（无 `confirm` 字段，不要传）；容器 `configs` 是整表替换。只改存储/清洗用清洗写接口，`table_id` 必须原样带回。

## 下发并清洗

1. 用户确认后立刻按「直接下发」第 1–2 步创建采集（不要等清洗模式或样例）。此时采集已在下发状态，向用户说明。
2. 用户选清洗模式；没选就问，不要默认。
3. 拉样例：优先本采集已上报日志，没有才让用户手贴。规则见 [clean.md](clean.md)。
4. 给出字段清洗结果页（设置表单 + 字段列表表格），再确认。
5. `update_log_collector_clean_config` 一次写入清洗 + 存储。
6. 回读 `get_log_collector`，用回读字段表向用户确认生效值。

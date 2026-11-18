# 日志清洗

仅在确认表单里用户选择「下发并清洗」后进入。进入前采集必须已经创建、处于下发状态。主机、容器日志、容器标准输出同一套规则和同一张字段列表。

## 模式

必须让用户选一种：

| 用户说法 | `etl_config` | 还要有 |
| --- | --- | --- |
| JSON、json | `bk_log_json` | 字段列表（可按样例 JSON 展开） |
| 分隔符 | `bk_log_delimiter` | `etl_params.separator` + 按列的 `fields`（含 `field_index`） |
| 正则 | `bk_log_regexp` | `etl_params.separator_regexp` + 命名分组对应的 `fields` |

没选模式不要开始猜字段。

## 样例

优先级：**本采集已上报的日志 > 用户手动输入**。下发前不要向用户要样例。

1. 用本次 `get_log_collector` 的 `index_set.index_set_id` 确认采集已建好。
2. **不要**调用 `log-query` 或其他环境的 `search_logs`。拉样例只用 `log-collector`，该 MCP 没有查日志工具。不要用 CMDB 查样例。
3. 可结合 `get_log_collector_status` 短轮询几次，判断是否已有上报。
4. 确认没有可用样例，才请用户手动贴样例。
5. 有样例才填字段「值」、才按 JSON/分隔符/正则展开用户字段。没有样例就留空，不要编。

## 默认值

用户没说就用，并写进字段清洗结果：

| 项 | 写入 |
| --- | --- |
| 原始日志保留 | `etl_params.retain_original_text: true` |
| 失败日志保留 | `etl_params.enable_retain_content: true`，`record_parse_failure: true` |
| 指定日志时间 = 日志上报时间 | 所有用户字段 `is_time: false`，不要把某个抽取字段标成时间 |

用户要丢弃原文、丢弃失败日志、或指定某字段为日志时间时，再改对应项，并在结果里标明。

## 字段清洗结果页

配完后先给用户看，确认前不写清洗接口。用表格承载，不要用段落罗列。版式见 [confirm-forms.md](confirm-forms.md) 第 4 节。

**清洗设置表单**

| 配置项 | 内容 |
| --- | --- |
| 清洗模式 | JSON / 分隔符 / 正则 |
| 原始日志 | 保留（默认） |
| 指定日志时间 | 日志上报时间（默认） |
| 失败日志 | 保留（默认） |

**字段列表**

默认四列，**禁止出现「别名」**：

| 字段名 | 类型 | 分词 | 值 |
| --- | --- | --- | --- |

有字段与内置名冲突时，插入一列，表头必须写成 **字段冲突【调整为】**（不要写「别名」）：

| 字段名 | 字段冲突【调整为】 | 类型 | 分词 | 值 |
| --- | --- | --- | --- | --- |

冲突行填调整后的入库名（写入时对应 `alias_name`）；无冲突行该单元格留空。常见冲突：`log`、`time`。

「值」有样例才写。只提交用户字段（`is_built_in: false`）。内置字段不要进这张表，也不要塞进 `fields`。直接入库时 `fields` 为空数组。

## 和存储一起写

清洗写入是整包替换，必须同时带存储：

- `storage_cluster_id`：用户指定的集群，或本次创建后回读的 `storage.cluster_id`
- `retention`：默认 3，用户改过则用用户值
- `storage_replies`：默认 0
- `es_shards`：默认 3
- `allocation_min_days`：用户未提则 0
- `table_id`：必须抄自 `get_log_collector` 的现有数据名，不能改名
- `confirm: true`

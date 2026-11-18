# 主机采集目标定位

只用于主机采集。用户只给 **IP、主机名、模块名、集群名、动态分组名**。不要向用户要 `bk_host_id`、`bk_inst_id`、模块 ID、分组 ID。确认表同样只展示名称/IP。

出确认表单前必须在本业务内定位成功。定位失败、对不上、业务拓扑不存在：停，不要出可下发表单，也不要用其他采集项里的历史主机冒充本业务成员。

采集接口仍要 ID。解析结果只留给 `fast_create` / `fast_update`，不要写进确认表。

## 用哪些 MCP

采集读写仍走 `log-collector`，主机目标定位使用同一环境的 CMDB MCP。通过工具发现确定完整 Server 名称并读取实时 schema；鉴权失败时使用宿主提供的认证入口，依赖不可用则停止。

不要用 CMDB 去查日志、洗数据、列采集项。不要调用其他环境 CMDB，或 `open_search_module`（它强制先传 `bk_set_id`）。

一套采集只能有一种 `target_node_type`。IP/主机名、模块/集群、动态分组不要混在同一条采集里；用户混说了就问清选哪一种。

## 只用这 4 个 CMDB 工具

| 用户给的 | 工具 | 提交 |
| --- | --- | --- |
| IP、主机名 | `open_list_biz_hosts`（`host_property_filter` 滤 `bk_host_innerip` 或 `bk_host_name`） | `INSTANCE`：`ip` + `bk_cloud_id`（用主机记录上的值）。可带 `bk_host_id` |
| 模块名、集群名 | `open_search_biz_inst_topo`（树上按 `bk_inst_name` 找 `module` / `set`） | `TOPO`：`bk_obj_id` + `bk_inst_id` |
| 动态分组名 | `open_search_dynamic_group` 找到分组；`open_execute_dynamic_group` 只预览成员 | `DYNAMIC_GROUP`：`bk_inst_id` + `bk_obj_id=DYNAMIC_GROUP` |

模块下要预览主机：还是 `open_list_biz_hosts`，带 `bk_module_ids`。预览不要改提交类型。

`open_list_biz_hosts` 必填 `page`、`fields`。`fields` 至少要：`bk_host_id`、`bk_host_innerip`、`bk_cloud_id`、`bk_host_name`。有云区域名也要带上。

## 解析流程

像 IP 的按 IP 查。否则按用户说法分流：说模块/集群走拓扑树；说动态分组走分组；说主机/没说走主机名。说不清就问，不要三种都碰运气。

```
IP / 主机名
  → open_list_biz_hosts（本业务、精确匹配）
  → 0 条：不属于该业务，停
  → 1 条：INSTANCE，bk_cloud_id 用这条记录的，禁止默认 0
  → 同 IP 多云区域：用云区域名称让用户选，不要甩 ID

模块名 / 集群名
  → open_search_biz_inst_topo
  → 0 个：停
  → 1 个：TOPO { bk_obj_id=module|set, bk_inst_id }
  → 同名多个：用「集群名 / 模块名」让用户选
  → 预览可用 list_biz_hosts(bk_module_ids)，提交仍是 TOPO，不要拆成 IP

动态分组名
  → open_search_dynamic_group，按名称精确匹配
  → 0 个：停
  → 1 个：execute 预览成员（可把数量/若干 IP 告诉用户）→ DYNAMIC_GROUP
  → 同名多个：用分组名列表让用户选
  → 提交不要把成员展开成 INSTANCE
```

整业务、业务下全部主机：不要默认成目标。用户明确要整个业务时才 `TOPO` + `bk_obj_id=biz`。

## 确认表怎么填

见 [confirm-forms.md](confirm-forms.md)「采集目标」表。

| 目标类型 | 云区域 | 对象 |
| --- | --- | --- |
| 静态拓扑 | 云区域**名称**（没有名称再写记录里的云区域，不要问用户要 ID） | IP；有主机名可写成 `IP（主机名）` |
| 动态拓扑 | 空 | `集群名` 或 `集群名 / 模块名` |
| 动态分组 | 空 | 分组名 |

禁止把 `bk_host_id`、`bk_inst_id`、模块 ID、分组 ID 写进表。

## 禁止

- 向用户要任何 CMDB / 主机 / 模块 / 分组 ID
- 云区域默认成 `0`
- 动态拓扑、动态分组展开成 IP 再当静态主机交
- 定位失败仍出确认表或调用 `fast_create`
- 用其他采集项的 `bk_host_id` 顶替本次定位
- 为圈选再加 CMDB 工具（查业务、跨业务反查 IP、云区域字典、按集群搜模块、拓扑路径）

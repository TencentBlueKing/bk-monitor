# 主机采集字段

只用于接入类型 = 主机采集。`environment=linux`。名称、数据名、行/段日志、路径、字符集、采集范围、存储、清洗与容器日志相同。

## 名称

- 采集名称 → `collector_config_name`，最长 50 字。
- 数据名 → `collector_config_name_en`。默认把采集名称转成英文标识：仅字母数字下划线，5–50 位，不能以数字开头时加前缀。中文名转拼音或用户已给的英文，统一小写+下划线。
- 创建后英文名/数据名不能改。确认表单里要展示最终数据名。

## 日志类型

| 用户说法 | `collector_scenario_id` | 额外必填 |
| --- | --- | --- |
| 未说、行日志、单行 | `row` | 无 |
| 段日志、多行 | `section` | `params.multiline_pattern`（行首正则）。没有正则就停，不要提交 |

段日志未要求最多行数、超时时，不要主动改这些值。

## 采集目标

必填。`target_object_type` 默认 `HOST`。用户只给 IP 或名称，不要要 ID。出确认表前必须按 [host-target-resolve.md](host-target-resolve.md) 在本业务定位；一套采集只能一种 `target_node_type`。

| 用户说法 | `target_node_type` | 提交 `target_nodes`（内部，确认表不展示） |
| --- | --- | --- |
| 静态拓扑、指定 IP/主机名 | `INSTANCE` | `ip` + `bk_cloud_id`（用 CMDB 主机记录，禁止默认 0）；可带 `bk_host_id` |
| 动态拓扑、业务/集群/模块 | `TOPO` | `bk_inst_id` + `bk_obj_id`（`biz` / `set` / `module`）。按名称在拓扑树定位，不要展开成 IP |
| 动态分组 | `DYNAMIC_GROUP` | `bk_inst_id` + `bk_obj_id=DYNAMIC_GROUP`。按分组名定位，预览成员不要改成 INSTANCE |
| 服务模板 / 集群模板 | `SERVICE_TEMPLATE` / `SET_TEMPLATE` | 名称解析尚未打通；用户只给了名称就问清，不要猜 ID |

目标说不清就问，不要把业务下全部主机当成目标。确认时写在「采集目标」表，只填名称/IP，不要写成一行 IP 文本，不要填 ID。见 [confirm-forms.md](confirm-forms.md)。

## 路径、字符集、采集范围

- 路径 → `params.paths`，绝对路径，可多个，可通配符。
- 字符集 → `data_encoding`，默认 `UTF-8`。
- 采集范围 → `params.tail_files`。默认 `true`（仅采集下发后的日志）。用户明确要全量再设 `false`。创建完成后禁止再改这一项。

## 不要问、不要改

上报链路（data link）用户不可调。创建和更新都不要带、不要提，除非用户主动问——主动问时说明暂不可调整。

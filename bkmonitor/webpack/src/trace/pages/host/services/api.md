# Host 页面 Service API 文档

> 模块路径：`src/trace/pages/host/services/`
> 类型定义：`src/trace/pages/host/types/`

---

## host-service.ts

### getHostInfoList

获取基础主机列表（不含指标），用于主机列表首屏渲染。

| 项               | 值                                            |
| ---------------- | --------------------------------------------- |
| **Service 签名** | `() => Promise<IHostBaseInfo[]>`              |
| **HTTP**         | `POST /rest/v2/performance/search_host_info/` |
| **请求参数**     | 无（`bk_biz_id` 由 `monitor-api` 自动注入）   |

#### 返回数据类型

```typescript
type IBkObjNameMap = Record<string, string>;

interface IHostModule {
  bk_inst_id: number;
  bk_inst_name: string;
  bk_obj_name_map: IBkObjNameMap;
  id: string;
  topo_link: string[];
  topo_link_display: string[];
}

interface IHostBaseInfo {
  bk_biz_id: number;
  bk_cloud_id: number;
  bk_cloud_name: string;
  bk_host_id: number;
  bk_host_innerip: string;
  bk_host_name: string;
  bk_host_outerip: string;
  bk_os_name: string;
  bk_os_type: string;
  display_name: string;
  ignore_monitoring: boolean;
  is_shielding: boolean;
  module: IHostModule[];
  region: string;
}

// Service 返回类型
type GetHostInfoListResult = IHostBaseInfo[];
```

#### 返回示例

```json
[
  {
    "display_name": "11.147.2.124",
    "bk_host_id": 10001,
    "bk_biz_id": 2,
    "bk_cloud_id": 0,
    "bk_cloud_name": "默认管控区域",
    "bk_host_innerip": "11.147.2.124",
    "bk_host_outerip": "",
    "bk_os_type": "1",
    "bk_os_name": "linux(centos)",
    "region": "广东省",
    "bk_host_name": "VM-2-124-tencentos",
    "ignore_monitoring": false,
    "is_shielding": false,
    "module": [
      {
        "id": "module|101",
        "bk_inst_id": 101,
        "bk_inst_name": "lde_Pool",
        "topo_link": ["biz|2", "module|101"],
        "topo_link_display": ["EDTEST", "lde_Pool"],
        "bk_obj_name_map": { "biz": "业务", "module": "模块" }
      }
    ]
  }
]
```

---

### getHostMetricInfoList

获取带指标数据的主机列表，用于主机列表补充渲染。

| 项               | 值                                              |
| ---------------- | ----------------------------------------------- |
| **Service 签名** | `() => Promise<IHostMetricInfo[]>`              |
| **HTTP**         | `POST /rest/v2/performance/search_host_metric/` |

**请求参数**：

```typescript
interface SearchHostMetricParams {
  bk_biz_id: number;
  bk_host_ids: number[];
}
```

| 参数          | 类型       | 必填 | 说明         |
| ------------- | ---------- | ---- | ------------ |
| `bk_biz_id`   | `number`   | 是   | 业务 ID      |
| `bk_host_ids` | `number[]` | 是   | 主机 ID 列表 |

#### 返回数据类型

```typescript
interface IHostAlarmCount {
  count: number;
  level: number;
}

interface IHostComponent {
  display_name: string;
  ports: number[];
  protocol: string;
  status: number;
}

interface IHostMetricInfo extends IHostBaseInfo {
  alarm_count: IHostAlarmCount[];
  bk_host_innerip_v6: string;
  bk_host_outerip_v6: string;
  bk_state: string;
  component: IHostComponent[];
  cpu_load: number;
  cpu_usage: number;
  disk_in_use: number;
  io_util: number;
  mem_usage: number;
  psc_mem_usage: number;
  status: number;
}

// Service 返回类型
type GetHostMetricInfoListResult = IHostMetricInfo[];
```

#### 返回示例

```json
[
  {
    "display_name": "11.147.2.124",
    "bk_host_id": 10001,
    "bk_biz_id": 2,
    "bk_cloud_id": 0,
    "bk_cloud_name": "默认管控区域",
    "bk_host_innerip": "11.147.2.124",
    "bk_host_outerip": "",
    "bk_host_innerip_v6": "",
    "bk_host_outerip_v6": "",
    "bk_os_type": "1",
    "bk_os_name": "linux(centos)",
    "region": "广东省",
    "bk_host_name": "VM-2-124-tencentos",
    "ignore_monitoring": false,
    "is_shielding": false,
    "bk_state": "",
    "module": [
      {
        "id": "module|101",
        "bk_inst_id": 101,
        "bk_inst_name": "lde_Pool",
        "topo_link": ["biz|2", "module|101"],
        "topo_link_display": ["EDTEST", "lde_Pool"],
        "bk_obj_name_map": { "biz": "业务", "module": "模块" }
      }
    ],
    "status": 0,
    "cpu_load": 1.23,
    "cpu_usage": 45.6,
    "disk_in_use": 62.1,
    "io_util": 12.3,
    "mem_usage": 78.5,
    "psc_mem_usage": 65.0,
    "alarm_count": [{ "count": 2, "level": 1 }],
    "component": [
      {
        "display_name": "mysql",
        "status": 0,
        "ports": [3306],
        "protocol": "TCP"
      }
    ]
  }
]
```

---

### getHostTopoTreeByBizId

根据业务 ID 获取主机拓扑树。

| 项               | 值                                                       |
| ---------------- | -------------------------------------------------------- |
| **Service 签名** | `(bizId?: number \| string) => Promise<IHostTopoTree[]>` |
| **HTTP**         | `POST /rest/v2/commons/get_topo_tree/`                   |
| **默认参数**     | `bizId = window.cc_biz_id`                               |

**请求参数**（Service 内部组装）：

```typescript
interface GetTopoTreeParams {
  bk_biz_id: number | string;
  condition_list: [];
  instance_type: 'host';
  remove_empty_nodes: false;
}
```

| 参数                 | 类型               | 必填 | 说明                         |
| -------------------- | ------------------ | ---- | ---------------------------- |
| `bk_biz_id`          | `number \| string` | 是   | 业务 ID                      |
| `condition_list`     | `[]`               | 是   | 过滤条件，固定 `[]`          |
| `instance_type`      | `'host'`           | 是   | 实例类型                     |
| `remove_empty_nodes` | `boolean`          | 是   | 是否移除空节点，固定 `false` |

#### 返回数据类型

```typescript
interface IHostTopoHostNode {
  alias_name: string;
  bk_biz_id: number;
  bk_cloud_id: number;
  bk_host_id: number;
  bk_host_innerip: string;
  bk_host_innerip_v6: string;
  bk_host_name: string;
  display_name: string;
  id: string;
  ip: string;
  name: string;
  os_type: string;
}

interface IHostTopoInstNode {
  bk_biz_id: number;
  bk_inst_id: number;
  bk_inst_name: string;
  bk_obj_id: string;
  bk_obj_name: string;
  children: IHostTopoTreeNode[];
  id: string;
  name: string;
}

type IHostTopoTreeNode = IHostTopoHostNode | IHostTopoInstNode;
type IHostTopoTree = IHostTopoInstNode;

// Service 返回类型
type GetHostTopoTreeByBizIdResult = IHostTopoTree[];
```

#### 返回示例

```json
[
  {
    "bk_biz_id": 2,
    "bk_inst_id": 2,
    "bk_inst_name": "EDTEST",
    "bk_obj_id": "biz",
    "bk_obj_name": "业务",
    "id": "biz|2",
    "name": "EDTEST",
    "children": [
      {
        "bk_biz_id": 2,
        "bk_inst_id": 101,
        "bk_inst_name": "lde_Pool",
        "bk_obj_id": "module",
        "bk_obj_name": "模块",
        "id": "module|101",
        "name": "lde_Pool",
        "children": [
          {
            "alias_name": "VM-2-124-tencentos",
            "bk_biz_id": 2,
            "bk_cloud_id": 0,
            "bk_host_id": 10001,
            "bk_host_innerip": "11.147.2.124",
            "bk_host_innerip_v6": "",
            "bk_host_name": "VM-2-124-tencentos",
            "display_name": "11.147.2.124",
            "id": "10001",
            "ip": "11.147.2.124",
            "name": "11.147.2.124",
            "os_type": "linux"
          }
        ]
      }
    ]
  }
]
```

---

## process-service.ts

### getHostProcessList

获取选中主机的进程列表。 **数据不太够，需要安装设计稿中补充字段**

| 项               | 值                                                             |
| ---------------- | -------------------------------------------------------------- |
| **Service 签名** | `(params: GetHostProcessListParams) => Promise<ProcessItem[]>` |
| **HTTP**         | `POST /rest/v2/scene_view/get_host_process_list/`              |

**请求参数**：

```typescript
interface GetHostProcessListParams {
  bk_target_cloud_id?: string;
  bk_target_ip?: string;
  start_time: number;
  end_time: number;
}
```

| 参数                 | 类型     | 必填                         | 说明                    |
| -------------------- | -------- | ---------------------------- | ----------------------- |
| `bk_target_ip`       | `string` | 与 `bk_target_cloud_id` 配套 | 目标主机 IP             |
| `bk_target_cloud_id` | `string` | 与 `bk_target_ip` 配套       | 云区域 ID               |
| `start_time`         | `number` | 是                           | 时间范围起始（Unix 秒） |
| `end_time`           | `number` | 是                           | 时间范围结束（Unix 秒） |

> 底层接口还支持 `bk_biz_id`、`bk_host_id`，接入时由 Service 层补充。

#### 返回数据类型

```typescript
enum EProcessPortStatus {
  Normal = 0,
  Abnormal = 1,
}

interface ProcessItem {
  bindIp: string;
  cpuUsage: number;
  hostIp: string;
  id: string;
  memRss: number;
  memUsage: number;
  name: string;
  pid: number;
  port: number;
  portStatus: EProcessPortStatus;
  protocol: string;
  startCommand: string;
  uptime: number;
  user: string;
}

// Service 返回类型
type GetHostProcessListResult = ProcessItem[];
```

#### 返回示例

```json
[
  {
    "id": "bash@123.234.34.34",
    "name": "bash",
    "pid": 10086,
    "protocol": "TCP",
    "bindIp": "0.0.0.0",
    "port": 18000,
    "portStatus": 1,
    "user": "root",
    "hostIp": "123.234.34.34",
    "cpuUsage": 19,
    "memRss": 96468992,
    "memUsage": 23,
    "uptime": 23040,
    "startCommand": "agent run p/opt/datadog-agent/run/agent.pid"
  },
  {
    "id": "mysqld@43.84.75.498",
    "name": "mysqld",
    "pid": 10088,
    "protocol": "TCP",
    "bindIp": "0.0.0.0",
    "port": 3306,
    "portStatus": 0,
    "user": "user01",
    "hostIp": "43.84.75.498",
    "cpuUsage": 12,
    "memRss": 134217728,
    "memUsage": 35,
    "uptime": 86400,
    "startCommand": "/usr/sbin/mysqld --defaults-file=/etc/my.cnf"
  }
]
```

---

## graph-service.ts

### getHostViewsPanels

获取主机详情视图的图表面板配置。 **新 API 根据原 host scene panel配置拆分**

| 项               | 值                                   |
| ---------------- | ------------------------------------ |
| **Service 签名** | `() => Promise<HostViewsRowPanel[]>` |

**请求参数**：无

#### 返回数据类型

```typescript
enum HostViewsPanelType {
  Graph = 'graph',
  Row = 'row',
}

interface PanelMetric {
  alias: string;
  field: string;
  method: string;
}

interface PanelQueryConfig {
  data_source_label: string;
  data_type_label: string;
  filter_dict: { targets: string[] };
  functions: { id: string; params: { id: string; value: string }[] }[];
  group_by: string[];
  interval: number | string;
  metrics: PanelMetric[];
  table: string;
  where: unknown[];
}

interface PanelTarget {
  alias: string;
  api: string;
  data: {
    expression: string;
    query_configs: PanelQueryConfig[];
  };
  data_type: string;
  datasource: string;
  ignore_group_by: string[];
}

interface HostViewsGraphPanel {
  id: string;
  subTitle: string;
  targets: PanelTarget[];
  title: string;
  type: HostViewsPanelType.Graph;
  matchDisplay?: { os_type?: string };
}

interface HostViewsRowPanel {
  id: string;
  panels: HostViewsGraphPanel[];
  title: string;
  type: HostViewsPanelType.Row;
}

// Service 返回类型
type GetHostViewsPanelsResult = HostViewsRowPanel[];
```

#### 返回示例

```json
[
  {
    "id": "cpu",
    "title": "CPU",
    "type": "row",
    "panels": [
      {
        "id": "bk_monitor.time_series.system.load.load5",
        "type": "graph",
        "title": "5分钟平均负载",
        "subTitle": "system.load.load5",
        "matchDisplay": { "os_type": "linux" },
        "targets": [
          {
            "alias": "",
            "api": "grafana.graphUnifyQuery",
            "datasource": "time_series",
            "data_type": "time_series",
            "ignore_group_by": ["bk_host_id"],
            "data": {
              "expression": "A",
              "query_configs": [
                {
                  "metrics": [{ "field": "load5", "method": "$method", "alias": "A" }],
                  "interval": "$interval",
                  "table": "system.load",
                  "data_source_label": "bk_monitor",
                  "data_type_label": "time_series",
                  "group_by": ["$group_by"],
                  "where": [],
                  "functions": [
                    {
                      "id": "time_shift",
                      "params": [{ "id": "n", "value": "$time_shift" }]
                    }
                  ],
                  "filter_dict": {
                    "targets": ["$current_target", "$compare_targets"]
                  }
                }
              ]
            }
          }
        ]
      }
    ]
  }
]
```

---

### getProcessViewsPanels

获取进程详情视图的图表面板配置（模块级缓存，整页生命周期内只取一次）。**新 API 根据原 host scene panel配置拆分**

| 项               | 值                                   |
| ---------------- | ------------------------------------ |
| **Service 签名** | `() => Promise<HostViewsRowPanel[]>` |

**请求参数**：无

> 进程图表面板 `id` 约定为 `process.{指标 id}`，作为 panel 与 order 的关联键。

#### 返回数据类型

```typescript
// 与 getHostViewsPanels 相同，返回 HostViewsRowPanel[]
// 进程面板 id 前缀为 process.{指标 id}

type GetProcessViewsPanelsResult = HostViewsRowPanel[];
```

#### 返回示例

```json
[
  {
    "id": "cpu",
    "title": "CPU",
    "type": "row",
    "panels": [
      {
        "id": "process.bk_monitor.time_series.system.proc.cpu_usage_pct",
        "type": "graph",
        "title": "进程 CPU 使用率",
        "subTitle": "system.bk_monitor.time_series.system.proc.cpu_usage_pct",
        "targets": [
          {
            "alias": "",
            "api": "grafana.graphUnifyQuery",
            "datasource": "time_series",
            "data_type": "time_series",
            "ignore_group_by": ["bk_host_id"],
            "data": {
              "expression": "A",
              "query_configs": [
                {
                  "metrics": [{ "field": "cpu_usage_pct", "method": "$method", "alias": "A" }],
                  "interval": "$interval",
                  "table": "system.proc",
                  "data_source_label": "bk_monitor",
                  "data_type_label": "time_series",
                  "group_by": ["$group_by"],
                  "where": [],
                  "functions": [],
                  "filter_dict": {
                    "targets": ["$current_target", "$compare_targets"]
                  }
                }
              ]
            }
          }
        ]
      }
    ]
  }
]
```

---

### getHostMetricGroupPanelOrder

获取主机详情视图的指标分组排序与显隐配置。

| 项               | 值                                       |
| ---------------- | ---------------------------------------- |
| **Service 签名** | `() => Promise<MetricGroupPanelOrder[]>` |

**请求参数**：无

#### 返回数据类型

```typescript
interface MetricOrderPanel {
  hidden: boolean;
  id: string;
  title: string;
}

interface MetricGroupPanelOrder {
  id: string;
  panels: MetricOrderPanel[];
  title: string;
}

// Service 返回类型
type GetHostMetricGroupPanelOrderResult = MetricGroupPanelOrder[];
```

#### 返回示例

```json
[
  {
    "id": "cpu",
    "title": "CPU",
    "panels": [
      {
        "id": "bk_monitor.time_series.system.load.load5",
        "title": "5分钟平均负载",
        "hidden": false
      },
      {
        "id": "bk_monitor.time_series.system.cpu_summary.usage",
        "title": "CPU 使用率",
        "hidden": false
      }
    ]
  },
  {
    "id": "memory",
    "title": "内存",
    "panels": [
      {
        "id": "bk_monitor.time_series.system.mem.free",
        "title": "物理内存空闲量",
        "hidden": false
      },
      {
        "id": "bk_monitor.time_series.system.mem.pct_used",
        "title": "物理内存使用率",
        "hidden": true
      }
    ]
  }
]
```

---

### getProcessMetricGroupPanelOrder

获取进程详情视图的指标分组排序与显隐配置（模块级缓存，整页生命周期内只取一次）。

| 项               | 值                                       |
| ---------------- | ---------------------------------------- |
| **Service 签名** | `() => Promise<MetricGroupPanelOrder[]>` |

**请求参数**：无

#### 返回数据类型

```typescript
// 与 getHostMetricGroupPanelOrder 相同

type GetProcessMetricGroupPanelOrderResult = MetricGroupPanelOrder[];
```

#### 返回示例

```json
[
  {
    "id": "__UNGROUP__",
    "title": "未分组的指标",
    "panels": [
      { "id": "port_status", "title": "端口状态", "hidden": false },
      { "id": "run_time", "title": "运行时长", "hidden": false },
      {
        "id": "bk_monitor.time_series.system.proc.cpu_usage_pct",
        "title": "进程 CPU 使用率",
        "hidden": false
      },
      {
        "id": "bk_monitor.time_series.system.proc.mem_usage_pct",
        "title": "进程内存使用率",
        "hidden": false
      }
    ]
  }
]
```

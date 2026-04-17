# Issue Top-N 接口文档

> **版本**: v1.0
> **更新时间**: 2026-04-16
> **状态**: 待实现

---

## 接口信息

| 项目 | 值 |
|------|-----|
| **接口名称** | Issue Top-N 统计 |
| **请求方式** | POST |
| **接口地址** | `/fta/issue/issue/top_n` |
| **内容类型** | application/json |

---

## 请求参数

### 参数列表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|:----:|--------|------|
| `bk_biz_ids` | `int[]` | 是 | - | 业务 ID 列表，用于权限过滤 |
| `fields` | `string[]` | 是 | - | 需要统计的字段列表 |
| `size` | `int` | 否 | `10` | 每个字段返回的 Top N 数量 |
| `start_time` | `int` | 否 | - | 开始时间戳（秒级） |
| `end_time` | `int` | 否 | - | 结束时间戳（秒级） |
| `need_time_partition` | `bool` | 否 | `true` | 是否需要时间分片（>7 天自动分片） |
| `status` | `string[]` | 否 | - | 状态过滤 |
| `priority` | `string[]` | 否 | - | 优先级过滤 |
| `assignee` | `string[]` | 否 | - | 负责人过滤 |
| `conditions` | `object[]` | 否 | `[]` | 高级过滤条件 |
| `query_string` | `string` | 否 | `""` | ES 查询字符串 |

> **重要说明**：
> - `fields` 支持 `+`/`-` 前缀控制排序，如 `+status` 表示升序，`-status` 表示降序（默认降序）
> - `size` 最大值为 10000
> - 时间范围超过 7 天时，建议启用 `need_time_partition`

### 枚举值说明

#### status 可用值

| 值 | 说明 |
|------|------|
| `pending_review` | 待审核 |
| `unresolved` | 未解决 |
| `resolved` | 已解决 |
| `rejected` | 拒绝 |
| `MY_ISSUE` | 我负责的（虚拟状态） |
| `NO_ASSIGNEE` | 未分派的（虚拟状态） |

#### priority 可用值

| 值 | 说明 |
|------|------|
| `P0` | 高优先级 |
| `P1` | 中优先级 |
| `P2` | 低优先级 |

#### fields 可用字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | Keyword | 状态 |
| `priority` | Keyword | 优先级 |
| `assignee` | Keyword | 负责人（空字符串表示未指派） |
| `strategy_id` | Keyword | 策略 ID |
| `strategy_name` | Text.raw | 策略名称 |
| `bk_biz_id` | Keyword | 业务 ID |
| `labels` | Keyword[] | 标签（数组） |
| `is_regression` | Boolean | 是否回归 |
| `tags.*` | Keyword | 自定义标签（如 `tags.service`） |
| `id` | Keyword | Issue ID（特殊处理：返回最新 N 个） |
| `impact_dimensions` | Keyword[] | 影响范围维度统计 |
| `impact_scope.{维度}.{ID字段}` | Keyword | 影响范围实例统计（维度和 ID 字段由前端指定，见下表） |

#### 特殊字段说明

##### 1. `id` 字段

按 `create_time` 降序返回最新的 N 个 Issue，而非聚合统计。返回格式与其他 Top-N 字段统一，每个 Issue 的 `count` 固定为 1，`name` 与 `id` 保持一致（即 `name` = Issue ID）。

**请求示例**：
```json
{
    "bk_biz_ids": [2],
    "fields": ["id"],
    "size": 10
}
```

**响应示例**：
```json
{
    "field": "id",
    "is_char": true,
    "bucket_count": 10,
    "buckets": [
        {"id": "1744291200a1b2c3d4", "name": "1744291200a1b2c3d4", "count": 1},
        {"id": "1744291100b2c3d4e5", "name": "1744291100b2c3d4e5", "count": 1}
    ]
}
```

##### 2. `impact_dimensions` 字段

统计 Issue 包含的影响范围维度分布。维度固定为 9 个，`size` 参数无效，始终返回全部维度。

**可用维度值**：

| 维度值 | 中文名 |
|--------|--------|
| `set` | 集群 |
| `host` | 主机 |
| `service_instances` | 服务实例 |
| `cluster` | bcs集群 |
| `node` | node |
| `service` | service |
| `pod` | pod |
| `apm_app` | apm_app |
| `apm_service` | apm_service |

**请求示例**：
```json
{
    "bk_biz_ids": [2],
    "fields": ["impact_dimensions"],
    "size": 10
}
```

**响应示例**：
```json
{
    "field": "impact_dimensions",
    "is_char": false,
    "bucket_count": 9,
    "buckets": [
        {"id": "host", "name": "主机", "count": 150},
        {"id": "cluster", "name": "bcs集群", "count": 80},
        {"id": "set", "name": "集群", "count": 60}
    ]
}
```

##### 3. `impact_scope.{维度}.{ID字段}` 字段

统计各维度下具体实例的 Issue 分布。后端负责将 ID 值翻译为展示名（如 bk_host_id → IP）。

**字段格式**：`impact_scope.{dimension}.{id_field}`

**9 个维度的 ID 字段映射表**：

| 维度 | ID 字段 | 示例字段 | 翻译来源 |
|------|---------|----------|----------|
| `set` | `set_id` | `impact_scope.set.set_id` | CMDB 批量查询 |
| `host` | `bk_host_id` | `impact_scope.host.bk_host_id` | CMDB 批量查询 |
| `service_instances` | `bk_service_instance_id` | `impact_scope.service_instances.bk_service_instance_id` | CMDB 批量查询 |
| `cluster` | `bcs_cluster_id` | `impact_scope.cluster.bcs_cluster_id` | 容器平台 API |
| `node` | `node` | `impact_scope.node.node` | 容器平台 API |
| `service` | `service` | `impact_scope.service.service` | 容器平台 API |
| `pod` | `pod` | `impact_scope.pod.pod` | 容器平台 API |
| `apm_app` | `app_name` | `impact_scope.apm_app.app_name` | APM 服务 |
| `apm_service` | `service_name` | `impact_scope.apm_service.service_name` | APM 服务 |

**请求示例**：
```json
{
    "bk_biz_ids": [2],
    "fields": ["impact_scope.host.bk_host_id", "impact_scope.cluster.bcs_cluster_id"],
    "size": 10
}
```

**响应示例**：
```json
{
    "field": "impact_scope.host.bk_host_id",
    "is_char": true,
    "bucket_count": 10,
    "buckets": [
        {"id": "1001", "name": "192.168.1.101", "count": 25},
        {"id": "1002", "name": "192.168.1.102", "count": 18}
    ]
}
```

### conditions 格式

`conditions` 用于高级过滤，支持多种过滤方式。

#### 基本格式

```json
{
    "key": "字段名",
    "value": ["值 1", "值 2"],
    "method": "过滤方法"
}
```

#### method 可用值

| 值 | 说明 | 示例 |
|------|------|------|
| `eq` | 等于 | `{"key": "priority", "value": ["P0"], "method": "eq"}` |
| `neq` | 不等于 | `{"key": "status", "value": ["resolved"], "method": "neq"}` |
| `include` | 包含（多个值满足其一即可） | `{"key": "priority", "value": ["P0", "P1"], "method": "include"}` |
| `exclude` | 排除（多个值都排除） | `{"key": "status", "value": ["rejected"], "method": "exclude"}` |
| `reg` | 正则匹配 | `{"key": "strategy_name", "value": ["CPU.*"], "method": "reg"}` |
| `nreg` | 正则不匹配 | `{"key": "strategy_name", "value": ["测试.*"], "method": "nreg"}` |

#### 影响范围过滤（特殊）

支持两种层级：

**1. 维度级过滤**：判断 Issue 是否包含某类影响范围维度

```json
{
    "key": "impact_dimensions",
    "value": ["host", "cluster"],
    "method": "eq"
}
```

**2. 实例级过滤**：按具体实例 ID 过滤

```json
{
    "key": "impact_scope.host.bk_host_id",
    "value": ["1", "2", "3"],
    "method": "include"
}
```

---

## 请求示例

### 示例 1：统计状态分布

```json
{
    "bk_biz_ids": [2],
    "fields": ["status"],
    "size": 10,
    "start_time": 1741334400,
    "end_time": 1741420800,
    "need_time_partition": false
}
```

### 示例 2：统计优先级和负责人分布

```json
{
    "bk_biz_ids": [2],
    "fields": ["priority", "assignee"],
    "size": 20,
    "need_time_partition": true
}
```

### 示例 3：统计标签分布（多值字段）

```json
{
    "bk_biz_ids": [2],
    "fields": ["labels"],
    "size": 50,
    "start_time": 1740729600,
    "end_time": 1741420800
}
```

### 示例 4：带过滤条件的策略分布

```json
{
    "bk_biz_ids": [2],
    "fields": ["strategy_name"],
    "size": 20,
    "status": ["unresolved"],
    "conditions": [
        {
            "key": "priority",
            "value": ["P0", "P1"],
            "method": "include"
        }
    ]
}
```

### 示例 5：统计我负责的 Issue 状态分布

```json
{
    "bk_biz_ids": [2],
    "fields": ["status"],
    "status": ["MY_ISSUE"]
}
```

### 示例 6：长时间范围（自动分片）

```json
{
    "bk_biz_ids": [2],
    "fields": ["status", "priority"],
    "size": 10,
    "start_time": 1738339200,
    "end_time": 1741420800,
    "need_time_partition": true
}
```

### 示例 7：带 query_string 的复杂查询

```json
{
    "bk_biz_ids": [2],
    "fields": ["strategy_name"],
    "query_string": "name:(主机 OR CPU) AND priority:P0",
    "size": 20
}
```

### 示例 8：统计最新的 10 个 Issue

```json
{
    "bk_biz_ids": [2],
    "fields": ["id"],
    "size": 10
}
```

### 示例 9：统计影响范围维度分布

```json
{
    "bk_biz_ids": [2],
    "fields": ["impact_dimensions"],
    "size": 10
}
```

### 示例 10：统计主机维度的 Top-N 实例

```json
{
    "bk_biz_ids": [2],
    "fields": ["impact_scope.host.bk_host_id"],
    "size": 20
}
```

### 示例 11：同时统计多个维度的实例

```json
{
    "bk_biz_ids": [2],
    "fields": ["impact_scope.host.bk_host_id", "impact_scope.cluster.bcs_cluster_id"],
    "size": 10
}
```

---

## 响应结构

### 响应体

```json
{
    "doc_count": 150,
    "fields": [
        {
            "field": "status",
            "is_char": false,
            "bucket_count": 4,
            "buckets": [
                {
                    "id": "unresolved",
                    "name": "未解决",
                    "count": 80
                }
            ]
        }
    ]
}
```

### 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `doc_count` | `int` | 符合条件的 Issue 总数 |
| `fields` | `object[]` | 各字段的统计结果数组 |

### fields 数组单项

| 字段 | 类型 | 说明 |
|------|------|------|
| `field` | `string` | 字段名 |
| `is_char` | `bool` | 是否为字符字段（字符字段可能需要翻译） |
| `bucket_count` | `int` | 桶数量（实际返回的 bucket 数量） |
| `buckets` | `object[]` | 桶数组，按 count 降序排列 |

### buckets 数组单项

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 桶 ID（字段原始值） |
| `name` | `string` | 桶名称（翻译后的展示名） |
| `count` | `int` | 该桶的文档数量 |

---

## 完整响应示例

### 示例 1：状态分布响应

```json
{
    "doc_count": 150,
    "fields": [
        {
            "field": "status",
            "is_char": false,
            "bucket_count": 4,
            "buckets": [
                {
                    "id": "unresolved",
                    "name": "未解决",
                    "count": 80
                },
                {
                    "id": "pending_review",
                    "name": "待审核",
                    "count": 40
                },
                {
                    "id": "resolved",
                    "name": "已解决",
                    "count": 25
                },
                {
                    "id": "rejected",
                    "name": "拒绝",
                    "count": 5
                }
            ]
        }
    ]
}
```

### 示例 2：多字段统计响应

```json
{
    "doc_count": 150,
    "fields": [
        {
            "field": "priority",
            "is_char": false,
            "bucket_count": 3,
            "buckets": [
                {
                    "id": "P2",
                    "name": "低",
                    "count": 70
                },
                {
                    "id": "P1",
                    "name": "中",
                    "count": 60
                },
                {
                    "id": "P0",
                    "name": "高",
                    "count": 20
                }
            ]
        },
        {
            "field": "assignee",
            "is_char": true,
            "bucket_count": 4,
            "buckets": [
                {
                    "id": "zhangsan",
                    "name": "zhangsan",
                    "count": 50
                },
                {
                    "id": "lisi",
                    "name": "lisi",
                    "count": 40
                },
                {
                    "id": "",
                    "name": "未指派",
                    "count": 35
                },
                {
                    "id": "wangwu",
                    "name": "wangwu",
                    "count": 25
                }
            ]
        }
    ]
}
```

### 示例 3：标签分布（多值字段）响应

```json
{
    "doc_count": 100,
    "fields": [
        {
            "field": "labels",
            "is_char": true,
            "bucket_count": 5,
            "buckets": [
                {
                    "id": "网络",
                    "name": "网络",
                    "count": 50
                },
                {
                    "id": "存储",
                    "name": "存储",
                    "count": 30
                },
                {
                    "id": "计算",
                    "name": "计算",
                    "count": 20
                },
                {
                    "id": "数据库",
                    "name": "数据库",
                    "count": 15
                },
                {
                    "id": "中间件",
                    "name": "中间件",
                    "count": 10
                }
            ]
        }
    ]
}
```

---

## 错误响应

### 错误格式

```json
{
    "error": "错误信息",
    "code": "错误码"
}
```

### 常见错误

| 错误码 | HTTP 状态码 | 说明 |
|--------|-----------|------|
| `INVALID_PARAM` | 400 | 参数格式错误 |
| `UNAUTHORIZED` | 401 | 未授权访问 |
| `FORBIDDEN` | 403 | 无权限访问指定业务 |
| `SERVER_ERROR` | 500 | 服务器内部错误 |

### 错误示例

**参数格式错误：**

```json
{
    "error": "size 字段必须为正整数",
    "code": "INVALID_PARAM"
}
```

**无权限访问：**

```json
{
    "error": "无权访问业务 ID: 999",
    "code": "FORBIDDEN"
}
```

---

## 字段翻译说明

接口会自动对以下字段进行翻译：

| 字段 | 翻译来源 | 示例 |
|------|---------|------|
| `status` | `IssueStatus.CHOICES` | `unresolved` → `未解决` |
| `priority` | `IssuePriority.CHOICES` | `P0` → `高` |
| `bk_biz_id` | 业务名称缓存 | `2` → `蓝鲸` |
| `strategy_id` | 策略名称缓存 | `1001` → `主机 CPU 使用率过高` |
| `id` | Issue 名称（name = id） | `1744291200a1b2c3d4` → `1744291200a1b2c3d4` |
| `impact_dimensions` | `ImpactScopeDimension.get_display_name()` | `host` → `主机` |
| `impact_scope.{维度}.{ID字段}` | 后端调用对应 API 翻译 | `1001` → `192.168.1.101` |

**字符字段**（`is_char: true`）默认不翻译，直接展示原始值。

**特殊字段翻译说明**：

1. **`id` 字段**：按 create_time 降序排序获取最新 N 个 Issue，`name` 与 `id` 保持一致（均返回 Issue ID），`count` 固定为 1
2. **`impact_dimensions`**：使用 `ImpactScopeDimension.get_display_name()` 翻译，维度固定 9 个
3. **`impact_scope.{维度}.{ID字段}`**：后端负责翻译，翻译来源：
   - `host` / `set` / `service_instances` → CMDB 批量查询接口
   - `cluster` / `node` / `service` / `pod` → 容器平台 API
   - `apm_app` / `apm_service` → APM 服务
   - 翻译失败时降级返回原始 ID 值

---

## 特殊说明

### 空值处理

- `assignee` 为空字符串时，展示为"未指派"
- 某字段无数据时，`buckets` 为空数组
- 无符合条件的 Issue 时，`doc_count` 为 0

### 多值字段

`labels` 和 `tags.*` 是多值字段，ES 聚合时会自动展开：

```
Issue A: labels = ["网络", "存储"]
Issue B: labels = ["网络", "计算"]

聚合结果:
- 网络：2
- 存储：1
- 计算：1
```

### 时间分片

当 `need_time_partition: true` 且时间范围 > 7 天时：

1. 自动按天切分查询
2. 并行执行各分片查询
3. 合并结果（`doc_count` 累加，`buckets` 按 key 合并）

**前端无感知**，返回格式与单次查询一致。

---

## 前端使用建议

### 1. 状态分布展示

```javascript
// 请求
const response = await resource.issue.issue_top_n({
    bk_biz_ids: [2],
    fields: ['status'],
    size: 10
});

// 渲染
response.fields[0].buckets.forEach(bucket => {
    console.log(`${bucket.name}: ${bucket.count}`);
});
```

### 2. 点击下钻

```javascript
// 用户点击"未解决"桶
const selectedStatus = 'unresolved';

// 更新列表过滤条件
issueListStore.filters.status = [selectedStatus];
issueListStore.refresh();
```

### 3. 多选支持

```javascript
// 按住 Ctrl 多选
const selectedStatuses = ['unresolved', 'pending_review'];

// 更新过滤
issueListStore.filters.status = selectedStatuses;
issueListStore.refresh();
```

---

## 性能建议

| 场景 | 建议 |
|------|------|
| 单次查询字段数 | ≤ 5 个 |
| size 最大值 | 10000（硬限制） |
| 时间范围 > 7 天 | 启用 `need_time_partition` |
| 标签字段统计 | 限制 `size ≤ 50` |
| 高频调用 | 考虑前端缓存（TTL: 30s） |

---

## 变更历史

| 版本 | 日期 | 变更内容 |
|------|------|---------|
| v1.0 | 2026-04-16 | 初始版本 |
| v1.1 | 2026-04-16 | 补充特殊字段设计：`id`、`impact_dimensions`、`impact_scope.{维度}.{ID字段}` |
| v1.3 | 2026-04-16 | 移除 top_n_result 接口；id 字段 name 与 id 保持一致；impact_scope 维度和 ID 字段由前端指定 |

---

**文档结束**

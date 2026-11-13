# 日志查询示例

以下均为合成示例；业务、资源、接收对象和查询字段在执行时以用户选择及工具发现结果为准。

本文档提供典型日志查询场景的完整示例。

本文所有返回数据和输出块均为 `mock response`，仅说明结构。实际调用必须使用实时 schema、动态时间和工具返回值；占位符如 `${NOW_SECONDS}`、`${INDEX_SET_ID_FROM_LIST}` 不得原样提交。

## 场景一：索引集日志查询

### 用户请求

> "查询示例业务的应用日志索引集中最近 1 小时的 ERROR 日志"

### 执行流程

**Step 1: 列出索引集**

```json
// 调用 list_index_sets
{
  "query_param": {
    "bk_biz_id": "<bk_biz_id>"
  }
}
```

Mock response（仅说明结构，不是实时数据）：
```json
{
  "data": [
    {"index_set_id": "<index_set_id_a>", "index_set_name": "应用日志"},
    {"index_set_id": "<index_set_id_b>", "index_set_name": "系统日志"}
  ]
}
```

**Step 2: 获取字段映射**

```json
// 调用 get_index_set_fields
{
  "query_param": {
    "bk_biz_id": "<bk_biz_id>",
    "index_set_id": "<index_set_id_a>"
  }
}
```

返回字段包含 `level`, `log`, `serverIp`, `dtEventTimeStamp` 等。

**Step 3: 执行搜索**

```json
// 调用 search_logs
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "index_set_id": "<index_set_id_a>",
    "query_string": "level:ERROR",
    "start_time": "${START_TIME_SECONDS}",
    "end_time": "${NOW_SECONDS}",
    "limit": 20,
    "order_by": ["-dtEventTimeStamp"]
  }
}
```

### Mock response（输出结构）

查询路径：索引集日志查询
索引集：应用日志 (ID: <index_set_id_a>)
查询条件：level:ERROR
时间范围：最近 1 小时
原始返回数：156 条
去重后数量：${MOCK_DEDUPLICATED_TOTAL} 条（去重口径：${DEDUPLICATION_KEY_OR_NONE}）

#### 样例 1：原始日志

````text
${MOCK_RAW_LOG_1}
````

#### 样例 2-3：语义摘要

| 样例 | 时间 | 来源 | 语义摘要 |
| ---: | --- | --- | --- |
| 2 | ${LOG_TIME_2} | payment-service | 请求等待 30000ms 后超时 |
| 3 | ${LOG_TIME_3} | ${MOCK_SOURCE_3} | ${MOCK_SEMANTIC_SUMMARY_3} |

可用操作：
- 查看日志聚类模式
- 分析 level 字段分布
- 查看某条日志的上下文

---

## 场景二：K8s 容器日志查询

### 用户请求

> "查询 BCS-K8S-00000 集群 default 命名空间的 nginx 容器日志"

### 执行流程

**Step 1: 列出日志场景**

```json
// 调用 list_log_scenes
{
  "query_param": {
    "bk_biz_id": "<bk_biz_id>"
  }
}
```

Mock response：场景 `k8s` 当前仅将 `cluster_id` 暴露为动态路由维度。命名空间、容器等条件必须在字段发现后通过 `query_string` 表达；若实时 schema 不同，以实时结果为准。

**Step 2: 获取集群列表**

```json
// 调用 list_scene_dimension_values
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "scene": "k8s",
    "dimension_key": "cluster_id",
    "filters": []
  }
}
```

**Step 3: 获取场景字段**

```json
// 调用 get_scene_log_fields
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "table_id_conditions": [
      [
        {"field_name": "scene", "value": ["k8s"], "op": "eq"},
        {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"}
      ]
    ]
  }
}
```

确认返回字段包含命名空间字段，例如示例模型中的 `__ext.io_kubernetes_pod_namespace`。

**Step 4: 构建命名空间内容过滤**

命名空间不加入 `table_id_conditions`；使用字段发现返回的真实字段名，在下一步放入 `query_string`。

**Step 5: 执行场景搜索**

```json
// 调用 search_logs (target_type=scene)
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "target_type": "scene",
    "table_id_conditions": [
      [
        {"field_name": "scene", "value": ["k8s"], "op": "eq"},
        {"field_name": "cluster_id", "value": ["BCS-K8S-00000"], "op": "eq"}
      ]
    ],
    "query_string": "__ext.io_kubernetes_pod_namespace:\"default\" AND container_name:nginx",
    "start_time": "${START_TIME_SECONDS}",
    "end_time": "${NOW_SECONDS}",
    "limit": 20
  }
}
```

### Mock response（输出结构）

查询路径：IaaS 容器日志查询
场景：k8s
路由条件：
  - 集群: BCS-K8S-00000
内容过滤：__ext.io_kubernetes_pod_namespace:"default" AND container_name:nginx
时间范围：最近 1 小时
原始返回数：89 条
去重后数量：${MOCK_DEDUPLICATED_TOTAL} 条（去重口径：${DEDUPLICATION_KEY_OR_NONE}）

#### 样例 1：原始日志

````text
${MOCK_RAW_NGINX_LOG_1}
````

#### 样例 2-3：语义摘要

| 样例 | 时间 | 来源 | 语义摘要 |
| ---: | --- | --- | --- |
| 2 | ${LOG_TIME_2} | ${MOCK_POD_2} | ${MOCK_SEMANTIC_SUMMARY_2} |
| 3 | ${LOG_TIME_3} | ${MOCK_POD_3} | ${MOCK_SEMANTIC_SUMMARY_3} |

---

## 场景三：日志聚类分析

### 用户请求

> "分析应用日志的 ERROR 模式，看看有哪些类型的错误"

### 执行流程

**Step 1: 搜索日志聚类模式**

```json
// 调用 search_log_clustering_pattern
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "index_set_id": "<index_set_id_a>",
    "start_time": "${START_TIME_MILLISECONDS}",
    "end_time": "${NOW_MILLISECONDS}",
    "pattern_level": "05",
    "show_new_pattern": false,
    "keyword": "*",
    "size": 10
  }
}
```

**Step 2: 下钻到原始日志（可选）**

```json
// 调用 search_logs，使用聚类签名过滤
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "index_set_id": "<index_set_id_a>",
    "query_string": "*",
    "conditions": {
      "field_list": [
        {"field_name": "__dist_05", "op": "eq", "value": ["pattern_signature_abc"]}
      ],
      "condition_list": []
    },
    "start_time": "${START_TIME_SECONDS}",
    "end_time": "${NOW_SECONDS}",
    "limit": 10
  }
}
```

### Mock response（输出结构）

```
日志聚类分析结果（敏感度: 05）
时间范围：最近 1 小时

模式 #1 (出现 45 次)
  模式: Connection refused to <*> server at <*>:<*>
  代表日志: Connection refused to database server at <host-ip>:3306

模式 #2 (出现 32 次)
  模式: Request timeout after <*>ms for <*>
  代表日志: Request timeout after 30000ms for /api/orders

模式 #3 (出现 28 次)
  模式: Failed to authenticate user <*>: invalid <*>
  代表日志: Failed to authenticate user admin: invalid password

可操作：选择某个模式查看原始日志
```

---

## 场景四：临时日志提取

### 用户请求

> "从 <host-ip> 主机提取 /data/logs/app.log 的最后 1000 行"

### 执行流程

**Step 1: 查询可访问主机**

```json
// 调用 search_log_extract_hosts
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "search_content": "<host-ip>"
  }
}
```

**Step 2: 校验允许的路径**

```json
// 调用 list_log_extract_allowed_paths
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "ip_list": [
      {"bk_host_id": "<bk_host_id>"}
    ]
  }
}
```

返回允许的路径包含 `/data/logs/`。

**Step 3: 展示确认信息**

```
日志提取确认
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
目标主机: <host-ip> (bk_host_id: <bk_host_id>)
提取路径: /data/logs/app.log
过滤方式: 提取最后 1000 行
时间范围: 全部

安全校验:
✓ 路径在允许列表中
✓ 主机在授权范围内
✓ 数据量可控

是否确认创建提取任务？
```

**Step 4: 创建提取任务（用户确认后）**

```json
// 调用 create_log_extract_task
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "ip_list": [
      {"bk_host_id": "<bk_host_id>"}
    ],
    "file_path": ["/data/logs/app.log"],
    "filter_type": "tail_line",
    "filter_content": {
      "line_num": 1000
    }
  }
}
```

**Step 5: 轮询任务状态**

```json
// 调用 get_log_extract_task
{
  "query_param": {
    "bk_biz_id": "<bk_biz_id>",
    "task_id": 789
  }
}
```

**Step 6: 任务完成后通知用户**

```
日志提取完成
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
任务 ID: 789
状态: downloadable
目标: <host-ip>:/data/logs/app.log
提取行数: 1000 行

如需下载，请告诉我。
```

---

## 场景五：字段分布分析

### 用户请求

> "分析最近 1 小时 level 字段的分布"

### 执行流程

```json
// 调用 analyze_field
{
  "body_param": {
    "bk_biz_id": "<bk_biz_id>",
    "index_set_id": "<index_set_id_a>",
    "field_name": "level",
    "start_time": "${START_TIME_SECONDS}",
    "end_time": "${NOW_SECONDS}",
    "group_by": true,
    "limit": "10",
    "order_by": "value"
  }
}
```

### Mock response（输出结构）

```
字段分布分析: level
时间范围：最近 1 小时
索引集：应用日志

分布统计:
| 字段值 | 数量 | 占比 |
| --- | ---: | ---: |
| INFO | 45,230 | 78.5% |
| WARN | 8,120 | 14.1% |
| ERROR | 3,856 | 6.7% |
| DEBUG | 412 | 0.7% |

建议：ERROR 日志占比 6.7%，可进一步分析错误类型
```

---

## 场景六：自定义应用 日志查询

### 用户请求

> "查询示例业务中服务 A 调用目标服务 B 的 ERROR 日志，Trace ID 为 abc123"

### 执行流程

1. 调用 `list_log_scenes`，确认实时返回中存在自定义应用场景。
2. 根据场景 schema 获取动态路由维度；不得从本示例固定字段名。
3. 使用路由条件调用 `get_scene_log_fields`，确认服务名、目标服务、级别和 Trace ID 的真实字段。
4. 使用显式 `AND` 构造内容过滤，例如：

```text
${SCENE_SERVICE_FIELD}:"A" AND ${SCENE_TARGET_SERVICE_FIELD}:"B" AND ${SCENE_LEVEL_FIELD}:ERROR AND ${SCENE_TRACE_FIELD}:"abc123"
```

5. 调用场景 `search_logs`。输出必须展示实际路由条件、原始返回数、去重后数量和去重口径。

### 无结果

自定义应用 查询无结果时回显实时字段和条件，建议核对服务名、环境、实例和时间范围；不得改用静态字段名重复查询。

---

## 边界情况处理

### 索引集不存在

```
未找到名为 "xxx" 的索引集。

示例业务 下可用的索引集：
1. 应用日志 (ID: <index_set_id_a>)
2. 系统日志 (ID: <index_set_id_b>)
3. 访问日志 (ID: 103)

请选择要查询的索引集。
```

### 字段不存在

```
字段 "error_level" 在该索引集中不存在。

可用的类似字段：
- level (类型: keyword)
- log_level (类型: keyword)

是否使用 "level" 字段进行查询？
```

### 查询无结果

```
查询条件：level:FATAL AND path:/api/*
时间范围：最近 1 小时
原始返回数：0 条
去重后数量：0 条（去重口径：${DEDUPLICATION_KEY_OR_NONE}）

建议：
1. 放宽时间范围（如最近 24 小时）
2. 修改查询条件（如 level:ERROR）
3. 确认是否有该级别的日志上报
```

### 提取路径不在允许列表

```
⚠️ 安全校验失败

请求路径: /etc/passwd
允许的路径:
- /data/logs/ (*.log, *.txt)
- /var/log/ (*.log)

该路径不在日志提取策略允许的范围内，无法提取。
```

### 查询跨度超过限制

```
⚠️ 查询跨度超过限制

请求时间范围: 7 天
最大允许跨度: 1 天

建议：
1. 分批查询（每批 ≤24 小时）
2. 缩小时间范围

是否按天分批查询并合并结果？
```

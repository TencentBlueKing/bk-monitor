### 功能描述

导入 AsCode 配置

### 请求参数

| 字段      | 类型      | 必选 | 描述                  |
|---------|---------|----|---------------------|
| bk_biz_id | int | 否  | 业务ID，与space_uid至少需要提供一个 |
| space_uid | str | 否  | 空间UID，与bk_biz_id至少需要提供一个 |
| configs | dict    | 是  | 文件内容，key为文件路径，value为文件内容字符串 |
| app     | str  | 否  | 配置分组，默认as_code       |
| overwrite | bool    | 否  | 是否跨分组覆盖同名配置，默认false |
| incremental | bool | 否 | 是否增量导入，默认false |

**参数约束：**
- `bk_biz_id` 和 `space_uid` 至少需要提供一个
- 如果只提供 `space_uid`，系统会自动转换为对应的 `bk_biz_id`

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "configs": {
      "rule/xxx.yaml": "xxxx",
      "notice/xxx.yaml": "xxxx"
    },
    "app": "as_code",
    "overwrite": false,
    "incremental": false
}
```

### 响应参数

| 字段      | 类型     | 描述       |
|---------|--------|----------|
| result  | bool   | 请求是否成功   |
| code    | int    | 返回的状态码   |
| message | string | 描述信息     |
| data    | dict   | 导入结果数据   |

#### data字段说明

| 字段      | 类型        | 描述                           |
|---------|-----------|------------------------------|
| result  | bool      | 导入是否成功                       |
| message | string    | 导入描述信息，失败时包含错误数量信息           |
| data    | dict/null | 导入返回数据，成功时为空字典，失败时为null     |
| errors  | dict      | 错误信息，key为配置文件路径，value为错误详情 |

### 响应参数示例

**成功响应：**
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "result": true,
        "message": "",
        "data": {},
        "errors": {}
    }
}
```

**失败响应：**
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "result": false,
        "message": "2 configs import failed",
        "data": null,
        "errors": {
            "rule/xxx.yaml": "配置解析失败: 缺少必填字段",
            "notice/yyy.yaml": "告警组不存在"
        }
    }
}
```

所有配置类型的 YAML / JSON 语法错误及不支持的文件扩展名，统一通过 `errors` 按完整文件路径返回。遇到首个文件解析错误时立即结束本次导入，后续保存、下发和全量清理均不执行。

### RecordingRule 配置

`recording_rule/` 目录支持 RecordingRule V4 的 YAML / JSON 文件，一个文件可以包含多个 group。示例文件 `recording_rule/cpu.yaml`：

```yaml
groups:
  - name: cpu_summary
    interval: 1min
    bkmonitor:
      auto_refresh: false
      desired_status: running
    rules:
      - record: cpu_usage_avg
        expr: avg(system_cpu_usage)
```

- 导入请求只进行本地格式检查、规则匹配和声明保存，不调用 unify-query 或 BKBase。保存结束后，将新增或配置有变更的规则汇总为一个异步任务，在 metadata 数据库事务提交后投递，逐条进行预解析和下发；`auto_refresh` 控制后续后台刷新，不阻止本次异步执行。
- 重复导入相同配置不重新下发；仅移动文件或调整托管分组不触发下发。配置变更包括计算规则、周期、标签、描述、data_label、期望状态和 auto_refresh。
- 按当前租户、空间、app 和 group 名称匹配有效对象，移动文件不重建规则；同一批 group 名称不能重复。
- `overwrite=true` 允许接管同空间其他 app 的同名有效对象；多个候选时返回错误。
- `incremental=false` 且本次包含 RecordingRule 文件时，新增／更新声明保存成功后，立即软删除当前 app 下未出现的规则，将 Flow 删除一并交给异步任务；新配置异步下发失败不阻止旧 Flow 删除。未包含该类型时不清理 RecordingRule。
- 格式或保存错误通过 errors 按文件和 group 位置返回。部分保存失败时，仍投递已成功保存的变更，但不清理遗漏规则。任务投递失败通过 errors.recording_rule 返回，并说明声明已经保存。
- 导入成功表示声明保存和任务投递成功，不代表预计算已经下发生效。异步预解析、下发和删除结果通过现有规则状态、事件及日志查看；单条失败不阻止其他规则执行。相同配置再次导入不会重试失败任务，可使用现有手动下发或后台刷新机制。
- 软删除规则不参与导入匹配或导出；同名配置再次导入会创建新规则。Admin 接口保持原有行为。
- RecordingRule 配置不包含业务、空间或租户字段，这些信息来自请求上下文；规则支持 `expr` 或现有结构化 `query`，二选一。

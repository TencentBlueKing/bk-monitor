### 功能描述

导入YAML配置

#### 接口参数

| 字段      | 类型      | 必选 | 描述                  |
|---------|---------|----|---------------------|
| configs | dict    | 是  | yaml配置              |
| app     | string  | 否  | 配置分组，默认defult       |
| bk_biz_id | integer | 是  | 业务ID                |
| overwrite | dict    | 否  | 是否跨分组覆盖同名配置，默认false |

#### 示例数据

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "configs": {
      "rule/xxx.yaml": "xxxx",
      "notice/xxx.yaml": "xxxx"
    },
    "app": "default",
    "bk_biz_id": 2,
    "overwrite": false
}
```

### 响应参数

| 字段    | 类型        | 描述         |
| ------- |-----------| ------------ |
| result  | bool      | 请求是否成功 |
| message | string    | 描述信息     |
| data    | dict/null | 返回数据     |

#### 示例数据

```json
{
    "message": "",
    "data": {},
    "result": true
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

- 导入先解析本批 RecordingRule 配置，再保存声明并立即解析下发；`auto_refresh` 控制后续后台刷新，不阻止本次导入下发。
- 按当前租户、空间、app 和 group 名称匹配有效对象，移动文件不重建规则；同一批 group 名称不能重复。
- `overwrite=true` 允许接管同空间其他 app 的同名有效对象；多个候选时返回错误。
- `incremental=false` 且本次包含 RecordingRule 文件时，新增／更新和下发均成功后，软删除当前 app 下未出现的规则。未包含该类型时不清理 RecordingRule。
- 导入出错通过 errors 返回，包含文件和 group 位置。下发失败保留声明，错误中携带规则 ID，且本次不清理旧规则。已成功下发的其他 group 不回滚。
- 软删除规则不参与导入匹配或导出；同名配置再次导入会创建新规则。Admin 接口保持原有行为。
- RecordingRule 配置不包含业务、空间或租户字段，这些信息来自请求上下文；规则支持 `expr` 或现有结构化 `query`，二选一。

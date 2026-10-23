### 功能描述

导出YAML配置

#### 接口参数

| 字段      | 类型      | 必选 | 描述                            |
|---------|---------|----|-------------------------------|
| bk_biz_id | integer | 是  | 业务ID                          |
| dashboard_for_external | boolean | 否  | 是否以外部导出模式导出grafana仪表盘，默认false |

#### 示例数据

```json
{
    "bk_biz_id": 2,
    "dashboard_for_external": true,
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
    "data": {
      "rule": {
        "xxx.yaml": "xxxx"
      },
      "notice": {
        "xxx.yaml": "xxxx",
        "yyy/zzz.yaml": "xxxx"
      },
      "grafana": {
        "xxx.yaml": "xxxx"
      },
      "action": {
        "xxx.yaml": "xxxx"
      }
    },
    "result": true
}
```

### RecordingRule 配置

增加 `recording_rule_ids` 参数：不传或 null 导出全部有效规则，空列表不导出，非空列表按 ID 筛选。同时支持 app 筛选，只返回当前认证租户、请求空间下未软删除的规则。

响应新增 `data.recording_rule`，值为文件名到 YAML 内容字符串的映射。文件使用 `groups` 格式，可以直接用于通用导入。来源文件为 JSON 时转换为 YAML 扩展名。

`lock_filename=false` 优先保留来源路径；开启时使用规则稳定输出表名生成文件名。RecordingRule 的配置不嵌入数据库 ID，`with_id` 不改变该类型的导出内容；重导入通过 app 和 group 名称匹配。

压缩包导出／导入同样支持该类型，目录为 `configs/recording_rule/`。只指定 RecordingRule ID 导出压缩包时，仅导出选中的 RecordingRule；只指定告警策略 ID 时，不额外导出 RecordingRule。

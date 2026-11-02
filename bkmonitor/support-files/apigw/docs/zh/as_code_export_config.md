### 功能描述

导出 AsCode 配置

### 请求参数

| 字段      | 类型      | 必选 | 描述                            |
|---------|---------|----|-------------------------------|
| bk_biz_id | int | 否  | 业务ID                          |
| space_uid | string | 否 | 空间UID |
| app | string | 否 | 配置分组，默认为None（导出所有分组） |
| action_ids | list[int] | 否 | 处理套餐ID列表，默认为None（导出所有） |
| rule_ids | list[int] | 否 | 告警策略ID列表，默认为None（导出所有） |
| notice_group_ids | list[int] | 否 | 告警组ID列表，默认为None（导出所有） |
| assign_group_ids | list[int] | 否 | 分派规则组ID列表，默认为None（导出所有） |
| dashboard_uids | list[string] | 否 | 仪表盘UID列表，默认为None（导出所有） |
| dashboard_for_external | bool | 否  | 是否以外部导出模式导出grafana仪表盘，默认false |
| lock_filename | bool | 否 | 是否锁定文件名，默认false |
| with_id | bool | 否 | 是否在导出配置中包含ID字段，默认false |

**参数约束：**
- `bk_biz_id` 和 `space_uid` 至少需要提供一个
- 如果只提供 `space_uid`，系统会自动转换为对应的 `bk_biz_id`

### 请求参数示例

```json
{
    "bk_biz_id": 2,
    "app": "as_code",
    "rule_ids": [1, 2, 3],
    "notice_group_ids": [10, 20],
    "dashboard_for_external": true,
    "lock_filename": false,
    "with_id": false
}
```

### 响应参数

| 字段      | 类型     | 描述       |
|---------|--------|----------|
| result  | bool   | 请求是否成功   |
| code    | int    | 返回的状态码   |
| message | string | 描述信息     |
| data    | dict   | 导出的配置数据 |

#### data字段说明

| 字段           | 类型   | 描述                                      |
|--------------|------|------------------------------------------|
| rule         | dict | 告警策略配置，key为文件路径，value为YAML格式的配置内容    |
| notice       | dict | 告警组配置，key为文件路径，value为YAML格式的配置内容      |
| action       | dict | 处理套餐配置，key为文件路径，value为YAML格式的配置内容     |
| grafana      | dict | Grafana仪表盘配置，key为文件路径，value为JSON格式的配置内容 |
| assign_group | dict | 分派规则组配置，key为文件路径，value为YAML格式的配置内容    |

**说明：**
- 文件路径格式：如果配置有子目录，格式为 `子目录|文件名.yaml`，否则为 `文件名.yaml`
- 配置内容为字符串格式，需要解析后使用

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "rule": {
            "strategy1.yaml": "name: 策略1\ntype: monitor\n...",
            "subdir|strategy2.yaml": "name: 策略2\ntype: monitor\n..."
        },
        "notice": {
            "notice_group1.yaml": "name: 告警组1\nusers: [...]\n...",
            "subdir|notice_group2.yaml": "name: 告警组2\nusers: [...]\n..."
        },
        "action": {
            "action1.yaml": "name: 处理套餐1\nplugin_id: webhook\n..."
        },
        "grafana": {
            "dashboard1.json": "{\"dashboard\": {...}}",
            "folder|dashboard2.json": "{\"dashboard\": {...}}"
        },
        "assign_group": {
            "assign_group1.yaml": "name: 分派组1\nrules: [...]\n..."
        }
    }
}
```

### RecordingRule 配置

增加 `recording_rule_ids` 参数：不传或 null 导出全部有效规则，空列表不导出，非空列表按 ID 筛选。同时支持 app 筛选，只返回当前认证租户、请求空间下未软删除的规则。

响应新增 `data.recording_rule`，值为文件名到 YAML 内容字符串的映射。文件使用 `groups` 格式，可以直接用于通用导入。来源文件为 JSON 时转换为 YAML 扩展名。

`lock_filename=false` 优先保留来源路径；开启时使用规则稳定输出表名生成文件名。RecordingRule 的配置不嵌入数据库 ID，`with_id` 不改变该类型的导出内容；重导入通过 app 和 group 名称匹配。

压缩包导出／导入同样支持该类型，目录为 `configs/recording_rule/`。只指定 RecordingRule ID 导出压缩包时，仅导出选中的 RecordingRule；只指定告警策略 ID 时，不额外导出 RecordingRule。

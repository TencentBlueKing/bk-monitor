### 功能描述

批量更新策略局部配置

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段      | 类型 | 必选 | 描述           |
| -------- | ---- | ---- | -------------- |
| edit_data | dict | 是   | 待修改数据 |
| ids       | list | 是   | 待修改策略ID列表 |
| bk_biz_id | int  | 是   | 业务ID         |

#### edit_data

| 字段                | 类型    | 必选 | 描述       |
| ------------------ | ------- | ---------- | ---------- |
| is_enabled          | bool | 否  | 启用状态   |
| notice_group_list   | list    | 否 | 告警组配置 |
| labels              | list    | 否  | 策略标签   |
| trigger_config      | dict    | 否  | 触发条件   |
| recovery_config     | dict    | 否  | 恢复条件   |
| alarm_interval      | int     | 否  | 通知间隔   |
| send_recovery_alarm | bool    | 否  | 恢复通知   |
| message_template    | string  | 否  | 通知模板   |
| no_data_config      | dict    | 否 | 无数据配置 |
| target              | list    | 否  | 监控目标   |
| strategy_config     | dict    | 否  | 策略配置 patch，见下文 |

#### strategy_config

通过 `edit_data.strategy_config` 更新指定字段，例如只修改策略名称和通知组：

```json
{
    "bk_biz_id": 2,
    "ids": [1001],
    "edit_data": {
        "strategy_config": {
            "name": "APM 服务异常",
            "notice": {"user_groups": [1, 2]}
        }
    }
}
```

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| name | string | 否 | 策略名称，同业务内不能重名 |
| scenario | string | 否 | 监控场景 |
| items | list[dict] | 否 | 按 ID 更新监控项，未列出的监控项保留 |
| detects | list[dict] | 否 | 整体替换检测配置，使用策略保存接口的检测配置结构 |
| notice | dict | 否 | 仅支持 `user_groups`，不联动修改处理套餐 |
| labels | list[string] | 否 | 最终完整标签列表，空列表清空标签 |
| expected_labels | list[string] | 否 | 读取时的完整标签快照，须与 `labels` 同传，锁内比对不一致时拒绝更新 |

`items` 中每个对象支持以下字段：

| 字段 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| id | int | 条件必选 | 必须属于目标策略，仅数据库和 patch 均只有一个监控项时可省略 |
| name | string | 否 | 监控项名称 |
| expression | string | 否 | 查询表达式，允许空字符串 |
| functions | list[dict] | 否 | 表达式函数，空列表清空 |
| metric_type | string | 否 | 指标类型 |
| query_configs | list[dict] | 否 | 整体替换查询配置，不能为空，按数据源类型校验 |
| algorithms | list[dict] | 否 | 整体替换算法配置，使用策略保存接口的算法结构 |

字段未传时保留已有配置，`null` 不是保留或清空指令。`items: []` 表示不修改监控项，`notice: {}` 表示不修改通知组，`notice.user_groups: []` 清空通知组。算法和检测配置还须满足完整策略的组合校验。

`strategy_config`、其监控项和通知对象拒绝未声明字段。`strategy_config` 必须单独使用，不能与 `edit_data` 中的旧字段混传；旧请求不传此字段时保持原行为。

先读取标签、保留部分标签再提交完整列表的调用方，应同时传入 `expected_labels`，避免覆盖读取之后发生的并发编辑。标签快照比较忽略顺序及首尾 `/`。

仅保存规范化后发生变化的配置；内容相同的请求不刷新更新时间、不清空 AsCode 字段、不新增历史。每条策略的配置写入使用独立的后端数据库事务，失败时回滚该策略的主表和子配置；批量请求中此前已经成功的策略保持已提交状态。

#### 示例数据

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "ids": [
        23121
    ],
    "edit_data": {
        "notice_group_list": [
            4644
        ]
    },
    "bk_biz_id": 883
}
```

### 响应参数

| 字段    | 类型   | 描述               |
| ------- | ------ | ------------------ |
| result  | bool   | 请求是否成功       |
| code    | int    | 返回的状态码       |
| message | string | 描述信息           |
| data    | list   | 更新成功的策略id表 |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    23121
  ]
}
```

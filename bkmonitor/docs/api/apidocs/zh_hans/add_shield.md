### 功能描述

创建屏蔽配置

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段             | 类型   | 必选 | 描述                                                         |
| ---------------- | ------ | ---- | ------------------------------------------------------------ |
| bk_biz_id        | int    | 是   | 业务ID                                                       |
| category         | string | 是   | 屏蔽类型(范围："scope", 策略："strategy", 事件："event", 告警："alert") |
| description      | string | 是   | 说明                                                         |
| begin_time       | string | 是   | 开始时间                                                     |
| end_time         | string | 是   | 结束时间                                                     |
| cycle_config     | dict   | 是   | 屏蔽配置                                                     |
| shield_notice    | bool   | 是   | 是否发送屏蔽通知                                             |
| notice_config    | dict   | 否   | 通知配置                                                     |
| dimension_config | dict   | 是   | 屏蔽维度                                                     |
| end_policy       | string | 否   | 屏蔽结束处理方式，默认 `notify_once`。可选值见下文           |

#### 屏蔽结束处理方式(end_policy)

| 取值 | 行为 |
| ---- | ---- |
| notify_once | 默认值，与历史行为一致：告警仍会生成；屏蔽期间拦截通知和处理；结束后对未恢复告警各补发一次解除屏蔽通知 |
| close | `begin_time` 落在本条屏蔽当时生效窗内的告警，期间不发送通知、不执行处理套餐；屏蔽结束（到期或提前解除）时关闭这些告警，不补发、不补执行。屏蔽开始前已存在的告警不受本条 `close` 影响。关闭后同维度再次异常将作为新告警按原策略通知 |

约束：

- 创建时省略该字段视为 `notify_once`。
- 创建后不可修改；如需另一种方式，请新建屏蔽。
- 快捷屏蔽（`is_quick=true` 或 `category` 为 `alert` / `event`）不支持 `close`，传入将被拒绝。

#### 屏蔽配置(cycle_config)

| 字段       | 类型   | 必选 | 描述                                               |
| ---------- | ------ | ---- | -------------------------------------------------- |
| begin_time | string | 否   | 开始时间(每天)                                     |
| end_time   | string | 否   | 结束时间(每天)                                     |
| type       | int    | 是   | 屏蔽周期类型（单次：1，每天：2，每周：3，每月：4） |
| day_list   | list   | 否   | 周期为月时，需要屏蔽的天                           |
| week_list  | list   | 否   | 周期为星期是，需要屏蔽的天                         |

#### 通知配置(notice_config)

| 字段            | 类型 | 必选 | 描述                                                         |
| --------------- | ---- | ---- | ------------------------------------------------------------ |
| notice_time     | int  | 是   | 屏蔽开始/结束前N分钟通知                                     |
| notice_way      | list | 是   | 通知类型，可选值"weixin", "mail", "sms", "voice"             |
| notice_receiver | list | 是   | 通知人，包含运维人员、产品人员、测试人员、开发人员、主备人员、备份负责人 |

#### 屏蔽维度(dimension_config)

屏蔽维度与屏蔽类型(category)相关

##### "scope"

| 字段       | 类型   | 必选 | 描述                                          |
| ---------- | ------ | ---- | --------------------------------------------- |
| scope_type | string | 是   | 屏蔽范围，可选值"instance","ip", "node","biz" |
| target     | list   | 否   | 根据范围类型对应的实例列表                    |
| metric_id  | list   | 否   | 指标id                                        |

##### "strategy"

| 字段       | 类型   | 必选 | 描述                         |
| ---------- | ------ | ---- | ---------------------------- |
| id         | list   | 是   | 策略id                       |
| level      | list   | 否   | 告警等级                     |
| scope_type | string | 否   | 屏蔽范围，可选值"ip", "node" |
| target     | list   | 否   | 根据范围类型对应的实例列表   |

##### "event"

| 字段 | 类型   | 必选 | 描述   |
| ---- | ------ | ---- | ------ |
| id   | string | 是   | 事件id |

##### "alert"

| 字段      | 类型 | 必选 | 描述   |
| --------- | ---- | ---- | ------ |
| alert_ids | list | 是   | 告警id |

> 注：scope和strategy里的target是根据scope_type去选择的。instances对应的是instances_id，ip对应的是{ip,bk_cloud_id}，node对应的是{bk_obj_id, bk_inst_id}，biz则不需要传入任何东西

#### 示例数据

基于范围的屏蔽

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "category":"scope",
    "begin_time":"2019-11-21 00:00:00",
    "end_time":"2019-11-23 23:59:59",
    "cycle_config":{
        "begin_time":"",
        "end_time":"",
        "day_list":[],
        "week_list":[],
        "type":1
    },
    "shield_notice":true,
    "notice_config":{
        "notice_time":5,
        "notice_way":["weixin"],
        "notice_receiver":[
            {
                "id":"user1",
                "type":"user"
            }
        ]
    },
    "description":"test",
    "end_policy":"close",
    "dimension_config":{
        "scope_type":"instance",
        "target":[8]
    },
    "bk_biz_id":2
}
```

基于策略的屏蔽

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "category":"strategy",
    "begin_time":"2019-11-21 00:00:00",
    "end_time":"2019-11-23 23:59:59",
    "cycle_config":{
        "begin_time":"",
        "end_time":"",
        "day_list":[],
        "week_list":[],
        "type":1
    },
    "shield_notice":true,
    "notice_config":{
        "notice_time":5,
        "notice_way":["weixin"],
        "notice_receiver":[
            {
                "id":"user1",
                "type":"user"
            }
        ]
    },
    "description":"test",
    "dimension_config":{
        "id": 1,
        "level":[1]
    },
    "bk_biz_id":2
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 屏蔽配置id   |

#### 示例数据

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "id": 1
    },
    "result": true
}
```

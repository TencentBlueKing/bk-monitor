### 功能描述

查询屏蔽详情


### 请求参数

| 字段      | 类型 | 必选 | 描述   |
| --------- | ---- | ---- | ------ |
| id        | int  | 是   | 屏蔽ID |
| bk_biz_id | int  | 是   | 业务ID |

### 请求参数示例

```json
{
    "id": 1,
    "bk_biz_id": 2
}
```

### 响应参数

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | dict   | 数据         |

#### data字段说明

| 字段             | 类型   | 描述                                                                                |
| ---------------- | ------ | ----------------------------------------------------------------------------------- |
| id               | int    | 屏蔽ID                                                                              |
| bk_biz_id        | int    | 业务ID                                                                              |
| category         | string | 屏蔽类型(范围："scope", 策略："strategy", 事件："event", 告警："alert", 维度："dimension") |
| description      | string | 说明                                                                                |
| begin_time       | string | 开始时间                                                                            |
| end_time         | string | 结束时间                                                                            |
| cycle_config     | dict   | 屏蔽配置                                                                            |
| shield_notice    | bool   | 是否发送屏蔽通知                                                                    |
| notice_config    | dict   | 通知配置                                                                            |
| dimension_config | dict   | 屏蔽维度                                                                            |
| scope_type       | string | 范围类型                                                                            |
| status           | int    | 当前状态，屏蔽中(1)，过期(2)，解除(3)                                               |
| is_enabled       | bool   | 是否启用                                                                            |
| source           | string | 来源                                                                                |
| create_time      | string | 创建时间                                                                            |
| update_time      | string | 更新时间                                                                            |
| create_user      | string | 创建人                                                                              |
| update_user      | string | 更新人                                                                              |
| label            | string | 标签                                                                                |

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

| 字段       | 类型   | 描述                                          |
| ---------- | ------ | --------------------------------------------- |
| scope_type | string | 屏蔽范围，可选值"instance","ip", "node","biz" |
| target     | list   | 根据范围类型对应的实例列表                    |
| metric_id  | list   | 指标id                                        |

##### "strategy"

| 字段                 | 类型 | 描述                         |
| -------------------- | ---- | ---------------------------- |
| id                   | list | 策略id，元素类型：int        |
| level                | list | 告警等级，元素类型：int      |
| scope_type           | string | 屏蔽范围，可选值"ip", "node" |
| target               | list | 根据范围类型对应的实例列表   |
| dimension_conditions | list | 维度条件列表，元素类型：dict |

###### dimension_conditions元素说明

| 字段      | 类型   | 描述                                                                 |
| --------- | ------ | -------------------------------------------------------------------- |
| key       | string | 维度键名                                                             |
| value     | list   | 维度值列表，元素类型：string                                         |
| method    | string | 匹配方法，可选值："eq"(等于)、"neq"(不等于)、"include"(包含)、"exclude"(不包含)、"reg"(正则)，默认"eq" |
| condition | string | 条件关系，可选值："and"(且)、"or"(或)，默认"and"                 |
| name      | string | 维度名称                                                             |

##### "event"

| 字段 | 类型   | 描述   |
| ---- | ------ | ------ |
| id   | string | 事件id |

##### "alert"

| 字段         | 类型 | 描述                                                                                |
| ------------ | ---- | ----------------------------------------------------------------------------------- |
| alert_id     | string | 单个告警ID                                                                          |
| alert_ids    | list | 告警ID列表，元素类型：string                                                        |
| dimensions   | dict | 告警维度配置，key为告警ID(string)，value为该告警保留的维度键名列表(list[string])   |
| bk_topo_node | dict | 拓扑节点配置，key为告警ID(string)，value为拓扑节点列表(list[dict])，节点dict包含bk_obj_id和bk_inst_id |

##### "dimension"

| 字段                 | 类型 | 描述                     |
| -------------------- | ---- | ------------------------ |
| dimension_conditions | list | 维度条件列表，元素类型：dict |

###### dimension_conditions元素说明

| 字段      | 类型   | 描述                                                                 |
| --------- | ------ | -------------------------------------------------------------------- |
| key       | string | 维度键名                                                             |
| value     | list   | 维度值列表，元素类型：string                                         |
| method    | string | 匹配方法，可选值："eq"(等于)、"neq"(不等于)、"include"(包含)、"exclude"(不包含)、"reg"(正则)，默认"eq" |
| condition | string | 条件关系，可选值："and"(且)、"or"(或)，默认"and"                 |
| name      | string | 维度名称                                                             |
> 注：scope和strategy里的target是根据scope_type去选择的。instances对应的是instances_id，ip对应的是{ip,bk_cloud_id}，node对应的是{bk_obj_id, bk_inst_id}，biz则不需要传入任何东西

### 响应参数示例

#### 基于范围的屏蔽

```json
{
    "code": 200,
    "message": "ok",
    "result": true,
    "data": {
        "id": 1,
        "scope_type": "instance",
        "status": 1,
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
        "dimension_config":{
            "scope_type":"instance",
            "target":[8]
        },
        "bk_biz_id":2
    }
}

```

#### 基于策略的屏蔽

```json
{
    "result": true,
    "code": 200,
    "messgae" : "ok",
    "data": {
        "id": 1,
        "scope_type": "instance",
        "status": 1,
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
        "dimension_config":{
            "scope_type":"instance",
            "target":[8]
        },
        "bk_biz_id":2
    }
}
```

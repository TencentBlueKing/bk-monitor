### 功能描述

导入策略到 APM 服务

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段               | 类型     | 必选 | 描述                                             |
|------------------|--------|----|------------------------------------------------|
| bk_biz_id        | int    | 否  | 业务id                                           |
| space_uid        | int    | 否  | 项目空间id，bk_biz_id、space_uid 至少传一个               |
| app_name         | string | 是  | 应用名称                                           |
| group_type       | string | 是  | 策略组类型，可选：<br />`rpc` - RPC 服务                  |
| apply_types      | list   | 是  | 策略类型列表，不同 `group_type`具有不同类型，详见下方 `apply_type` |
| apply_services   | list   | 否  | 服务列表，不填默认导入到所有同类服务                             |
| notice_group_ids | list   | 否  | 告警组 ID 列表                                      |
| config           | string | 否  | 额外配置，JSON 序列化字符串，详见下方 `config`                 |

##### apply_type

1）rpc

| 类型       | 描述                      |
|----------|-------------------------|
| callee   | 被调策略                    |
| caller   | 主调策略                    |
| panic    | 异常退出策略，仅对 tRPC-Go 生效    |
| resource | 服务容量策略，仅对使用 BCS 集群内上报生效 |

##### config

1）rpc

```json
{
  // 主调策略类型额外配置
  "caller":{
    // 下钻维度
    "group_by":[
      "callee_method"
    ],
    // 过滤规则
    "filter_dict":{
      "namespace":"Development"
    }
  },
  // 被调策略类型额外配置
  "callee":{
    "group_by":[
      "callee_method"
    ]
  }
}
```

#### 请求示例

```json
{
  "bk_biz_id": 2,
  "app_name": "test",
  "group_type": "rpc",
  "apply_types": ["callee", "caller", "panic"],
  "notice_group_ids": [988],
  "config": "{\"caller\": {\"group_by\": [\"callee_method\"]}, \"callee\": {\"group_by\": [\"callee_method\"]}}"
}
```

### 返回结果

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 数据     |

#### data字段说明

data 字段无内容

#### 结果示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": null
}
```
### 功能描述

获取存储列表
根据给定的过滤参数（暂无），返回符合条件的存储集群列表

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
| ---- | ---- | ---- | ---- |
| --   | --   | --   | --   |

#### 请求示例

```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
}
```

### 返回结果

| 字段    | 类型   | 描述         |
| ------- | ------ | ------------ |
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息     |
| data    | list   | data         |

#### data字段说明

| 字段         | 类型   | 描述         |
| ------------ | ------ | ------------ |
| storage_name | string | 存储类型名称 |

#### 结果示例

```json
{
    "message":"OK",
    "code":200,
    "data":[{
    	"storage_name": "influxdb",
     }],
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```
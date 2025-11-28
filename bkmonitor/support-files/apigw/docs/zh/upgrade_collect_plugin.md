### 功能描述

采集配置插件升级

### 请求参数

| 字段        | 类型   | 必选 | 描述       |
|-----------|------|----|----------|
| bk_biz_id | int  | 是  | 业务 ID    |
| id        | int  | 是  | 采集配置 ID  |
| params    | Dict | 是  | 采集配置参数   |
| realtime  | bool | 否  | 是否实时刷新缓存 |

#### params

插件特定的配置参数，根据具体插件而定

| 字段        | 类型   | 必选 | 描述    |
|-----------|------|----|-------|
| collector | Dict | 是  | 采集器配置 |
| plugin    | Dict | 是  | 插件配置  |

**常见插件params参数示例：**

##### script 插件

```json
{
    "collector": {},
    "plugin": {
        "param_test": "test_value",  // param_test 是自定义的参数名
        "服务实例维度注入": {}
    }
}

```

##### bk-pull插件

```json
{
    "collector": {
        "metrics_url": "http://www.test.com",
        "username": "",
        "password": ""
    },
    "plugin": {}
}
```

##### JMX插件

```json
{
    "collector": {
        "host": "127.0.0.1",
        "port": "6666"
    },
    "plugin": {
        "jmx_url": "http://www.test1.com",
        "username": "root",
        "password": true
    }
}
```

##### exporter 插件

```json
{
    "collector": {
        "host": "127.0.0.1",
        "port": "23100"
    },
    "plugin": {
        "--web.listen-address": "${host}:${port}"
    }
}
```

### 请求参数示例

```json
{
  "bk_biz_id": 2,
  "id": 280,
  "params": {
        "collector": {
            "host": "127.0.0.1",
            "port": "23100"
        },
        "plugin": {
            "--web.listen-address": "${host}:${port}"
        }
  },
  "realtime": false
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段            | 类型  | 描述        |
|---------------|-----|-----------|
| id            | int | 采集配置 ID   |
| deployment_id | int | 部署版本历史 ID |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 280,
    "deployment_id": 1
  }
}
```

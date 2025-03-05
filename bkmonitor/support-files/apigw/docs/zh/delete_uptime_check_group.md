### 功能描述

删除拨测任务组


#### 接口参数

| 字段   | 类型  | 必选 | 描述               |
| ---- |-----|----|------------------|
| group_id | int | 是  | 拨测任务组ID          |

#### 示例数据
```json
{
    "bk_app_code": "xxx",
    "bk_app_secret": "xxxxx",
    "bk_token": "xxxx",
    "group_id": 10001
}
```

### 响应参数
| 字段       | 类型   | 描述         |
|----------| ------ | ------------ |
| result   | bool   | 请求是否成功 |
| code     | int    | 返回的状态码 |
| message  | string | 描述信息     |
| data     | dict   | 数据         |

####  data字段说明
| 字段           | 类型  | 描述      |
|:-------------|-----|---------|
| group_id     | int | 拨测任务组ID |
| result       | str | 描述信息    |

#### 示例数据
```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "group_id": 10001,
        "result": "删除成功"
    }
}
```

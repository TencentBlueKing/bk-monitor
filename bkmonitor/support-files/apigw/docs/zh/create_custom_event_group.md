### 功能描述

创建自定义事件


#### 接口参数

| 字段          | 类型   | 必选 | 描述      |
|-------------|------|----|---------|
| bk_biz_id   | int  | 是  | 业务ID    |
| name        | str  | 是  | 名称      |
| scenario    | str  | 是  | 监控对象    |
| is_platform | bool | 否  | 是否为平台事件 |
| data_label  | str  | 是  | 数据标签    |

#### 请求示例

```json
{
  "name": "test_custom_event_group",
  "scenario": "apm",
  "data_label": "test_custom_event_group",
  "is_platform": false,
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 响应数据   |

#### data 响应数据

| 字段                | 类型  | 描述     |
|-------------------|-----|--------|
| bk_event_group_id | int | 事件分组ID |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "bk_event_group_id": 32
  }
}
```
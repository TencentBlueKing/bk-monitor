### 功能描述

创建自定义指标


#### 接口参数

| 字段                   | 类型   | 必选 | 描述                 |
|----------------------|------|----|--------------------|
| bk_biz_id            | int  | 是  | 业务ID               |
| name                 | str  | 是  | 指标名称               |
| scenario             | str  | 是  | 监控场景               |
| table_id             | str  | 否  | 结果表ID              |
| metric_info_list     | list | 否  | 指标信息列表             |
| is_platform          | bool | 否  | 是否为平台级指标，默认值False  |
| data_label           | str  | 是  | 数据标签               |
| protocol             | str  | 否  | 上报协议，默认值json       |
| desc                 | str  | 否  | 描述                 |
| is_split_measurement | bool | 否  | 是否启动自动分表逻辑，默认值True |

#### 请求示例

```json
{
  "name": "test_ts",
  "scenario": "application_check",
  "data_label": "test_ts",
  "is_platform": false,
  "protocol": "json",
  "desc": "",
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| resul   | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 结果     |

#### data 响应数据

| 字段                   | 类型  | 描述     |
|----------------------|-----|--------|
| time_series_group_id | int | 指标分组ID |
| bk_data_id           | int | 数据ID   |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "time_series_group_id": 462,
    "bk_data_id": 1573950
  }
}
```


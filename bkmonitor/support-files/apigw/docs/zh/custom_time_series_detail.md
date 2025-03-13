### 功能描述

自定义时序详情


#### 接口参数

| 字段                   | 类型   | 必选 | 描述                              |
|----------------------|------|----|---------------------------------|
| bk_biz_id            | int  | 是  | 业务ID                            |
| time_series_group_id | int  | 是  | 时序分组ID                          |
| model_only           | bool | 否  | 直接获取CustomTSTable表中的数据，默认值False |
| with_target          | bool | 否  | 是否查询target维度数据                  |

#### 请求示例

```json
{
  "time_series_group_id": 600,
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

| 列名称                  | 类型         | 描述        |
|----------------------|------------|-----------|
| time_series_group_id | int        | 时序分组ID    |
| is_readonly          | bool       | 时间序列是否为只读 |
| create_time          | str        | 创建时间      |
| create_user          | str        | 创建用户      |
| update_time          | str        | 最后更新时间    |
| update_user          | str        | 最后更新的用户   |
| is_deleted           | bool       | 是否被删除     |
| bk_data_id           | int        | 数据ID      |
| bk_biz_id            | int        | 业务ID      |
| name                 | str        | 名称        |
| scenario             | str        | 监控场景      |
| table_id             | str        | 结果表ID     |
| is_platform          | bool       | 是否是平台级    |
| data_label           | str        | 数据标签      |
| protocol             | str        | 上报协议      |
| desc                 | str        | 描述        |
| scenario_display     | list       | 场景显示名称的列表 |
| access_token         | str        | 访问令牌      |
| metric_json          | list[dict] | 指标配置      |
| target               | list       | 目标列表      |

#### data.metric_json 指标配置

| 列名称    | 类型         | 描述   |
|--------|------------|------|
| fields | list[dict] | 字段配置 |

#### data.metric_json.fields

| 列名称          | 类型   | 必选 | 描述         |
|--------------|------|----|------------|
| unit         | str  | 是  | 字段单位       |
| name         | str  | 是  | 字段名        |
| description  | str  | 是  | 字段描述       |
| monitor_type | str  | 是  | 字段类型，指标或维度 |
| type         | str  | 是  | 字段类型       |
| label        | list | 否  | 分组标签,默认值[] |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "time_series_group_id": 461,
    "is_readonly": false,
    "create_time": "2025-01-21 10:06:10+0800",
    "create_user": "admin",
    "update_time": "2025-01-21 11:03:56+0800",
    "update_user": "admin",
    "is_deleted": false,
    "bk_data_id": 1573949,
    "bk_biz_id": 2,
    "name": "test_ts",
    "scenario": "apm",
    "table_id": "2_bkmonitor_time_series_1573949.__default__",
    "is_platform": false,
    "data_label": "test_ts",
    "protocol": "json",
    "desc": "",
    "scenario_display": [
      "用户体验",
      "APM"
    ],
    "access_token": "xxxx",
    "metric_json": [
      {
        "fields": []
      }
    ],
    "target": []
  }
}
```


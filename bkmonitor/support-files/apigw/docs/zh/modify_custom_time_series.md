### 功能描述

修改自定义指标


#### 接口参数

| 列名称                  | 类型         | 必选 | 描述         |
|----------------------|------------|----|------------|
| bk_biz_id            | int        | 是  | 业务ID       |
| name                 | str        | 否  | 指标名称       |
| time_series_group_id | int        | 是  | 自定义时序ID    |
| metric_json          | list[dict] | 否  | 指标配置，默认值[] |
| is_platform          | bool       | 否  | 是否为平台级指标   |
| data_label           | str        | 否  | 数据标签       |
| operator             | str        | 否  | 操作者        |

#### metric_json 指标配置

| 列名称    | 类型         | 必选 | 描述   |
|--------|------------|----|------|
| fields | list[dict] | 是  | 字段信息 |

#### metric_json.fields

| 列名称          | 类型   | 必选 | 描述         |
|--------------|------|----|------------|
| unit         | str  | 是  | 字段单位       |
| name         | str  | 是  | 字段名        |
| description  | str  | 是  | 字段描述       |
| monitor_type | str  | 是  | 字段类型，指标或维度 |
| type         | str  | 是  | 字段类型       |
| label        | list | 否  | 分组标签,默认值[] |

#### 请求示例

```json
{
  "time_series_group_id": 474,
  "name": "ctenet_v3_bkbase_test",
  "data_label": "ctenet_v3_bkbase_test",
  "is_platform": false,
  "metric_json": [
    {
      "fields": [
        {
          "name": "cpu_load",
          "monitor_type": "metric",
          "unit": "",
          "description": "",
          "type": "float",
          "label": []
        },
        {
          "name": "module",
          "monitor_type": "dimension",
          "unit": "",
          "description": "",
          "type": "string",
          "label": []
        },
        {
          "name": "target",
          "monitor_type": "dimension",
          "unit": "",
          "description": "",
          "type": "string",
          "label": []
        },
        {
          "name": "location",
          "monitor_type": "dimension",
          "unit": "",
          "description": "",
          "type": "string",
          "label": []
        },
        {
          "name": "gpu_load",
          "monitor_type": "metric",
          "unit": "",
          "description": "",
          "type": "float",
          "label": []
        }
      ],
      "table_name": "base",
      "table_desc": "默认分类"
    }
  ],
  "bk_biz_id": 2
}
```

### 响应参数

| 字段      | 类型         | 描述     |
|---------|------------|--------|
| resul   | bool       | 请求是否成功 |
| code    | int        | 返回的状态码 |
| message | str        | 描述信息   |
| data    | list[dict] | 响应数据   |

#### data 响应数据

| 字段                   | 类型         | 描述        |
|----------------------|------------|-----------|
| time_series_group_id | int        | 时间序列组ID   |
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
| is_platform          | bool       | 否为平台级指标   |
| data_label           | str        | 数据标签      |
| protocol             | str        | 上报协议      |
| desc                 | str        | 描述        |
| scenario_display     | list[str]  | 场景显示名称的列表 |
| access_token         | str        | 访问令牌      |
| metric_json          | list[dict] | 指标配置      |
| target               | list       | 目标列表      |

#### data.metric_json 指标配置

| 字段     | 类型         | 描述      |
|--------|------------|---------|
| fields | list[dict] | 包含的字段列表 |

#### data.metric_json.fields 指标配置字段信息

| 字段             | 类型         | 描述         |
|----------------|------------|------------|
| name           | str        | 字段名        |
| monitor_type   | str        | 字段类型，指标或维度 |
| unit           | str        | 字段单位       |
| description    | str        | 字段描述       |
| type           | str        | 字段类型       |
| dimension_list | list[dict] | 维度列表       |
| id             | str        | 维度标识符      |
| name           | str        | 维度名称       |
| label          | list       | 分组标签       |

#### 响应示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "time_series_group_id": 474,
    "is_readonly": false,
    "create_time": "2024-08-19 15:43:19+0800",
    "create_user": "admin",
    "update_time": "2025-01-21 11:02:13+0800",
    "update_user": "admin",
    "is_deleted": false,
    "bk_data_id": 1573082,
    "bk_biz_id": 2,
    "name": "ctenet_v3_bkbase_test",
    "scenario": "apm",
    "table_id": "2_bkmonitor_time_series_1573082.__default__",
    "is_platform": false,
    "data_label": "ctenet_v3_bkbase_test",
    "protocol": "json",
    "desc": "ctenet_v3_bkbase_test",
    "scenario_display": [
      "用户体验",
      "APM"
    ],
    "access_token": "xxxx",
    "metric_json": [
      {
        "fields": [
          {
            "name": "cpu_load",
            "monitor_type": "metric",
            "unit": "",
            "description": "",
            "type": "float",
            "dimension_list": [
              {
                "id": "module",
                "name": ""
              },
              {
                "id": "target",
                "name": ""
              },
              {
                "id": "location",
                "name": ""
              }
            ],
            "label": []
          },
          {
            "name": "module",
            "monitor_type": "dimension",
            "unit": "",
            "description": "",
            "type": "string"
          },
          {
            "name": "target",
            "monitor_type": "dimension",
            "unit": "",
            "description": "",
            "type": "string"
          },
          {
            "name": "location",
            "monitor_type": "dimension",
            "unit": "",
            "description": "",
            "type": "string"
          },
          {
            "name": "gpu_load",
            "monitor_type": "metric",
            "unit": "",
            "description": "",
            "type": "float",
            "dimension_list": [
              {
                "id": "module",
                "name": ""
              },
              {
                "id": "target",
                "name": ""
              },
              {
                "id": "location",
                "name": ""
              }
            ],
            "label": []
          }
        ]
      }
    ],
    "target": []
  }
}
```


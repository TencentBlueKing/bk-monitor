# RUM 检索接口协议

## 1 公共数据结构

### 1.1 Filter

过滤条件，用于 `list_records`、`get_fields_option_values`、`generate_query_string` 等接口的 `filters` 参数。

| 参数名称     | 类型     | 必填 | 描述                     |
|----------|--------|----|------------------------|
| key      | String | 是  | 查询键                    |
| operator | String | 是  | 操作符                    |
| value    | Array  | 是  | 查询值列表（元素类型为任意 JSON 值）  |
| options  | Object | 否  | 操作符选项，见 Filter.options |

- Filter.options

| 参数名称           | 类型      | 必填 | 描述                            |
|----------------|---------|----|-------------------------------|
| is_wildcard    | Boolean | 否  | 是否使用通配符，默认 `false`            |
| group_relation | String  | 否  | 分组关系，枚举值：`AND` / `OR`，默认 `OR` |

---

## 2 RUM 接口

### 2.1 list_records - 分页查询记录列表

POST /rum/search/list_records/

#### 2.1.1 Request

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| offset       | Integer       | 否  | 分页偏移量，默认 0，最小 0                                                     |
| limit        | Integer       | 否  | 每页数量，默认 10，最小 1                                                     |
| sort         | Array[String] | 否  | 排序条件，字段名前加 `-` 表示降序，默认 `[]`                                         |
| filters      | Array[Filter] | 否  | 过滤条件，见 [1.1 Filter](#filter)，默认 `[]`                                |
| query_string | String        | 否  | 查询字符串，默认 `""`                                                       |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [
    {
      "key": "attributes.span_type",
      "operator": "equal",
      "value": [
        "http"
      ]
    }
  ],
  "start_time": 1785999805,
  "end_time": 1786003405,
  "offset": 0,
  "limit": 10,
  "sort": [
    "-start_time"
  ]
}
```

#### 2.1.2 Response

返回包含 `total` 和 `data` 字段的分页结构。

```json
{
  "list": [
    {
      "span_id": "29926da51cae17cf",
      "trace_id": "206fa04fb665bf8ef1fba9255b59c3e1",
      "span_name": "browser.resource",
      "start_time": 1783338028554800,
      "end_time": 1783338029588300,
      "elapsed_time": 1033500,
      "attributes.span_type": "resource",
      "status.code": 0
    }
  ]
}
```

### 2.2 view_config - 页面视图配置

GET /rum/search/view_config/?app_name=rum-demo&bk_biz_id=2

#### 2.2.1 Request

| 参数名称       | 类型      | 必填 | 描述                                                                  |
|------------|---------|----|---------------------------------------------------------------------|
| bk_biz_id  | Integer | 是  | 业务 ID                                                               |
| app_name   | String  | 是  | 应用名称                                                                |
| mode       | String  | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time | Integer | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time   | Integer | 是  | 结束时间（Unix 秒级时间戳）                                                    |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "start_time": 1785999805,
  "end_time": 1786003405
}
```

#### 2.2.2 Response

顶层结构：

| 参数名称           | 类型            | 描述                    |
|----------------|---------------|-----------------------|
| default_sort   | Array[String] | 默认排序条件，字段名前加 `-` 表示降序 |
| fields         | Array[Field]  | 顶层字段列表（不属于任何分组）       |
| groups         | Array[Group]  | 分组列表，每个分组包含若干字段       |
| display_fields | Array[String] | 列表页默认展示的字段名列表         |

- Field

| 参数名称                 | 类型                 | 描述                                  |
|----------------------|--------------------|-------------------------------------|
| field_name           | String             | 字段名                                 |
| field_alias          | String             | 字段别名，无别名时与 `field_name` 相同          |
| field_type           | String             | 字段类型（如 `keyword`、`long`、`double` 等） |
| field_unit           | String             | 字段单位（可选，如 `us`、`ms`）                |
| is_searchable        | Boolean            | 是否支持搜索                              |
| is_agg               | Boolean            | 是否支持聚合统计                            |
| is_list              | Boolean            | 是否支持在列表中展示                          |
| supported_operations | Array[Operation]   | 支持的操作符列表                            |
| option_values        | Array[OptionValue] | 预设枚举值列表（可选，有预设值时返回）                 |

- Operation

| 参数名称        | 类型     | 描述  |
|-------------|--------|-----|
| operator    | String | 操作符 |
| label       | String | 标签  |
| placeholder | String | 占位符 |

- OptionValue

| 参数名称  | 类型     | 描述   |
|-------|--------|------|
| value | String | 枚举值  |
| alias | String | 枚举别名 |

- Group

| 参数名称   | 类型           | 描述        |
|--------|--------------|-----------|
| name   | String       | 分组标识      |
| alias  | String       | 分组别名      |
| fields | Array[Field] | 该分组下的字段列表 |

```json
{
  "default_sort": [
    "-end_time"
  ],
  "fields": [
    {
      "field_name": "span_name",
      "field_alias": "Span 名称",
      "field_type": "keyword",
      "is_searchable": true,
      "is_agg": true,
      "is_list": true,
      "supported_operations": []
    },
    {
      "field_name": "elapsed_time",
      "field_alias": "耗时",
      "field_type": "long",
      "field_unit": "us",
      "is_searchable": true,
      "is_agg": true,
      "is_list": true,
      "supported_operations": []
    },
    {
      "field_name": "attributes.span_type",
      "field_alias": "Span 类型",
      "field_type": "keyword",
      "is_searchable": true,
      "is_agg": true,
      "is_list": true,
      "supported_operations": [],
      "option_values": [
        {
          "value": "view",
          "alias": "视图"
        },
        {
          "value": "resource",
          "alias": "资源加载"
        }
      ]
    }
  ],
  "groups": [
    {
      "name": "DEVICE_BROWSER",
      "alias": "终端 & 浏览器",
      "fields": [
        {
          "field_name": "resource.user_agent.name",
          "field_alias": "代理名称",
          "field_type": "keyword",
          "is_searchable": true,
          "is_agg": true,
          "is_list": true,
          "supported_operations": []
        }
      ]
    },
    {
      "name": "WEB_VITALS",
      "alias": "网页指标（Web Vitals）",
      "fields": [
        {
          "field_name": "LCP",
          "field_alias": "最大内容绘制",
          "field_type": "double",
          "field_unit": "ms",
          "is_searchable": true,
          "is_agg": true,
          "is_list": false,
          "supported_operations": []
        }
      ]
    }
  ],
  "display_fields": [
    "span_name",
    "attributes.span_type",
    "end_time",
    "elapsed_time",
    "status.code",
    "attributes.view.url_template",
    "user.id"
  ]
}
```

### 2.3 get_fields_option_values - 批量查询字段可选枚举值

POST /rum/search/get_fields_option_values/

#### 2.3.1 Request

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| fields       | Array[String] | 是  | 查询字段列表                                                              |
| limit        | Integer       | 否  | 每个字段返回的枚举值数量，默认 10，最小 1                                             |
| filters      | Array[Filter] | 否  | 过滤条件，见 [1.1 Filter](#filter)，默认 `[]`                                |
| query_string | String        | 否  | 查询字符串，默认 `""`                                                       |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999805,
  "end_time": 1786003405,
  "fields": [
    "attributes.span_type",
    "kind",
    "status.code"
  ],
  "limit": 10
}
```

#### 2.3.2 Response

返回以字段名为 key、可选枚举值列表为 value 的字典。

```json
{
  "attributes.span_type": [
    "http",
    "resource",
    "document",
    "route",
    "action"
  ],
  "kind": [
    "1",
    "3",
    "2",
    "5",
    "4"
  ],
  "status.code": [
    "0",
    "1",
    "2"
  ]
}
```

### 2.4 generate_query_string - 过滤条件转查询字符串

POST /rum/search/generate_query_string/

#### 2.4.1 Request

| 参数名称      | 类型            | 必填 | 描述                                                                  |
|-----------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id | Integer       | 是  | 业务 ID                                                               |
| app_name  | String        | 是  | 应用名称                                                                |
| mode      | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| filters   | Array[Filter] | 否  | 查询条件列表，默认 `[]`                                                      |

- Filter

见 [1.1 Filter](#filter)。

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "filters": [
    {
      "key": "attributes.span_type",
      "operator": "equal",
      "value": [
        "http",
        "resource"
      ],
      "options": {
        "is_wildcard": false,
        "group_relation": "OR"
      }
    }
  ]
}
```

#### 2.4.2 Response

返回转换后的查询字符串（String）。

```json
"attributes.span_type: (\"http\" OR \"resource\")"
```


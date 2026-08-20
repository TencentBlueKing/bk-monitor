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
        "resource"
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

返回包含 `list` 字段的分页结构。

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
    "attributes.user.id"
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

### 2.5 fields_topk - 字段 Top-K

POST /rum/search/fields_topk/

#### 2.5.1 Request

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| fields       | Array[String] | 是  | 查询字段名称                                                              |
| limit        | Integer       | 否  | 返回数量限制，默认 5，最小 1                                                    |
| filters      | Array[Filter] | 否  | 过滤条件，默认 `[]`                                                        |
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
    "kind"
  ],
  "limit": 5
}
```

#### 2.5.2 Response

返回字段 Top-K 统计列表，每个元素对应一个查询字段。

| 参数名称           | 类型              | 描述        |
|----------------|-----------------|-----------|
| field          | String          | 字段名称      |
| distinct_count | Integer         | 该字段的去重值数量 |
| list           | Array[TopKItem] | Top-K 值列表 |

- TopKItem

| 参数名称        | 类型      | 描述              |
|-------------|---------|-----------------|
| value       | String  | 字段值             |
| count       | Integer | 该值出现的次数         |
| proportions | Float   | 该值占总数的百分比（不含 %） |

```json
[
  {
    "field": "kind",
    "distinct_count": 5,
    "list": [
      {
        "value": "1",
        "count": 4127148,
        "proportions": 88.504
      },
      {
        "value": "3",
        "count": 294804,
        "proportions": 6.321
      },
      {
        "value": "2",
        "count": 241082,
        "proportions": 5.169
      },
      {
        "value": "5",
        "count": 94,
        "proportions": 0.002
      },
      {
        "value": "4",
        "count": 93,
        "proportions": 0.001
      }
    ]
  }
]
```

### 2.6 field_statistics_info - 字段统计信息

POST /rum/search/field_statistics_info/

#### 2.6.1 Request

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| field        | Field         | 是  | 字段描述对象，见下表                                                          |
| filters      | Array[Filter] | 否  | 过滤条件，默认 `[]`                                                        |
| query_string | String        | 否  | 查询字符串，默认 `""`                                                       |

- Field

| 参数名称       | 类型     | 必填 | 描述   |
|------------|--------|----|------|
| field_name | String | 是  | 字段名称 |
| field_type | String | 是  | 字段类型 |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999917,
  "end_time": 1786003517,
  "field": {
    "field_name": "span_name",
    "field_type": "keyword"
  }
}
```

#### 2.6.2 Response

| 参数名称           | 类型      | 描述                                       |
|----------------|---------|------------------------------------------|
| total_count    | Integer | 查询时间范围内的记录总数                             |
| field_count    | Integer | 该字段有值的记录数                                |
| distinct_count | Integer | 该字段的去重值数量                                |
| field_percent  | Float   | 字段覆盖率（`field_count / total_count × 100`） |
| value_analysis | Object  | 数值类字段的统计分析，字符串类字段不返回此字段                  |

- value_analysis（仅数值类字段返回）

| 参数名称   | 类型    | 描述  |
|--------|-------|-----|
| avg    | Float | 平均值 |
| min    | Float | 最小值 |
| max    | Float | 最大值 |
| median | Float | 中位数 |

- 字符串类

```json
{
  "distinct_count": 544,
  "field_count": 4647434,
  "total_count": 4647434,
  "field_percent": 100
}
```

- 数值类

```json
{
  "total_count": 1284935,
  "field_count": 1284935,
  "distinct_count": 4,
  "field_percent": 100,
  "value_analysis": {
    "avg": 1.097,
    "min": 1,
    "max": 4,
    "median": 1
  }
}
```

### 2.7 field_statistics_graph - 字段统计图表

POST /rum/search/field_statistics_graph/

#### 2.7.1 Request

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| field        | Field         | 是  | 字段描述对象，见下表                                                          |
| filters      | Array[Filter] | 否  | 过滤条件，默认 `[]`                                                        |
| query_string | String        | 否  | 查询字符串，默认 `""`                                                       |

- Field（`field_type=keyword` 时 `values` 传 topk5 的值；`field_type` 为数字类型时 `values` 至少需要 4 个值，传 topk 接口返回的
  `list[*].value`）

| 参数名称       | 类型                    | 必填 | 描述                                                                       |
|------------|-----------------------|----|--------------------------------------------------------------------------|
| field_name | String                | 是  | 字段名称                                                                     |
| field_type | String                | 是  | 字段类型，枚举值：`keyword` / `numeric`                                           |
| values     | Array[Integer/String] | 否  | 数值类：min_value, max_value, distinct_count, interval_num<br/>字符类：传 topk 的值 |

```json
{
  "bk_biz_id": 2,
  "app_name": "rum-demo",
  "mode": "span",
  "query_string": "",
  "filters": [],
  "start_time": 1785999917,
  "end_time": 1786003517,
  "field": {
    "field_name": "span_name",
    "field_type": "keyword",
    "values": [
      "build-metadata-query",
      "check-must-query-feature-flag",
      "query-ts-to-query-metric",
      "http-api-metadata",
      "jwt-auth"
    ]
  }
}
```

#### 2.7.2 Response

| 参数名称   | 类型            | 描述     |
|--------|---------------|--------|
| series | Array[Series] | 图表数据序列 |

- Series

| 参数名称                   | 类型           | 描述                        |
|------------------------|--------------|---------------------------|
| dimensions             | Object       | 维度键值对，key 为字段名，value 为维度值 |
| target                 | String       | 查询目标描述字符串                 |
| metric_field           | String       | 指标字段名                     |
| datapoints             | Array[Array] | 数据点列表，每个元素为 `[值, 毫秒时间戳]`  |
| alias                  | String       | 别名                        |
| stat                   | Object       | 统计信息                      |
| type                   | String       | 图表类型（如 `bar`）             |
| dimensions_translation | Object       | 维度翻译映射                    |
| unit                   | String       | 单位                        |

```json
{
  "series": [
    {
      "dimensions": {
        "span_name": "build-metadata-query"
      },
      "target": "count(span_name){span_name=build-metadata-query}",
      "metric_field": "_result_",
      "datapoints": [
        [
          3498,
          1785999840000
        ]
      ],
      "alias": "_result_",
      "stat": {},
      "type": "bar",
      "dimensions_translation": {},
      "unit": ""
    }
  ],
  "metrics": []
}
```

### 2.8 download_topk - 下载 Top-K 数据为 CSV

POST /rum/search/download_topk/

#### 2.8.1 Request

与 [field_topk](#25-field_topk---字段-top-k) 接口参数完全一致。

| 参数名称         | 类型            | 必填 | 描述                                                                  |
|--------------|---------------|----|---------------------------------------------------------------------|
| bk_biz_id    | Integer       | 是  | 业务 ID                                                               |
| app_name     | String        | 是  | 应用名称                                                                |
| mode         | String        | 否  | 查询层级模式，枚举值：<br/>- `span`<br/>- `view`<br/>- `session`<br/>默认 `span` |
| start_time   | Integer       | 是  | 开始时间（Unix 秒级时间戳）                                                    |
| end_time     | Integer       | 是  | 结束时间（Unix 秒级时间戳）                                                    |
| fields       | Array[String] | 是  | 查询字段名称                                                              |
| limit        | Integer       | 否  | 返回数量限制，默认 5，最小 1                                                    |
| filters      | Array[Filter] | 否  | 过滤条件，默认 `[]`                                                        |
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
    "kind"
  ],
  "limit": 5
}
```

#### 2.8.2 Response

返回 CSV 格式的二进制文件内容（`bytes`），响应头 `Content-Type: text/csv`，文件名格式为
`topk_{bk_biz_id}_{app_name}_{field}.csv`。

CSV 列结构（无表头行）：

| 列序号   | 描述                 |
|-------|--------------------|
| 第 1 列 | 字段值（value）         |
| 第 2 列 | 出现次数（count）        |
| 第 3 列 | 占比百分比（如 `88.504%`） |

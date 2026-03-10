### 功能描述

查询监控结果表

### 请求参数

| 字段                | 类型     | 必选 | 描述                                   |
|-------------------|--------|----|--------------------------------------|
| datasource_type   | string | 否  | 需要过滤的结果表类型, 如system                  |
| bk_biz_id         | int    | 否  | 获取指定业务下的结果表信息                        |
| is_public_include | int    | 否  | 是否包含全业务结果表, 0为不包含, 非0为包含全业务结果表       |
| is_config_by_user | bool   | 否  | 是否需要包含非用户配置的结果表内容，默认为True            |
| with_option       | bool   | 否  | 是否包含option字段信息，默认为True               |
| page              | int    | 否  | 页码，默认为1                              |
| page_size         | int    | 否  | 每页数量，默认为0（不分页时返回所有数据，分页时page_size>0） |

### 请求参数示例

```json
{
	"bk_biz_id": 123,
	"is_public_include": 1,
	"datasource_type": "system",
	"is_config_by_user": true,
	"with_option": true,
	"page": 1,
	"page_size": 10
}
```

### 响应参数

| 字段         | 类型        | 描述                    |
|------------|-----------|-----------------------|
| result     | bool      | 请求是否成功                |
| code       | int       | 返回的状态码                |
| message    | string    | 描述信息                  |
| data       | dict/list | 数据，分页时为dict，非分页时为list |
| request_id | string    | 请求ID                  |

#### data字段说明

**分页返回**（当 `page_size > 0` 时）：

| 字段    | 类型   | 描述            |
|-------|------|---------------|
| count | int  | 结果表总数         |
| info  | list | 结果表列表，元素说明见下方 |

**非分页返回**（当 `page_size = 0` 时）：

`data` 直接为结果表列表（list），元素说明见下方。

#### data.info（分页）或 data（非分页）列表项字段说明

| 字段               | 类型     | 描述                                                                |
|------------------|--------|-------------------------------------------------------------------|
| table_id         | string | 结果表ID                                                             |
| bk_tenant_id     | string | 租户ID                                                              |
| table_name_zh    | string | 结果表中文名                                                            |
| is_custom_table  | bool   | 是否自定义结果表                                                          |
| scheme_type      | string | 结果表schema配置方案，free(无schema配置), dynamic(动态schema), fixed(固定schema) |
| default_storage  | string | 默认存储方案                                                            |
| creator          | string | 创建者                                                               |
| create_time      | string | 创建时间, 格式为【2018-10-10 10:00:00】                                    |
| last_modify_user | string | 最后修改者                                                             |
| last_modify_time | string | 最后修改时间【2018-10-10 10:00:00】                                       |
| bk_biz_id        | int    | 业务ID                                                              |
| label            | string | 结果表标签                                                             |
| is_enable        | bool   | 是否启用                                                              |
| data_label       | string | 数据标签                                                              |
| field_list       | list   | 字段列表，具体说明见下方                                                      |
| bk_data_id       | int    | 数据源ID                                                             |
| type_label       | string | 数据类型标签                                                            |
| source_label     | string | 数据来源标签                                                            |
| option           | dict   | 结果表选项配置（当with_option=true时返回）                                     |
| storage_list     | list   | 所有存储列表，元素为string（当with_option=true时返回）                            |

##### field_list 字段列表的具体参数说明

| 键值                | 类型          | 描述                                          |
|-------------------|-------------|---------------------------------------------|
| field_name        | string      | 字段名                                         |
| type              | string      | 字段类型，可以为float, string, boolean和timestamp    |
| description       | string      | 字段描述信息                                      |
| tag               | string      | 字段标签，可以为metric, dimension, timestamp, group |
| alias_name        | string      | 入库别名                                        |
| default_value     | string/null | 字段默认值                                       |
| is_config_by_user | bool        | 用户是否启用该字段配置                                 |
| unit              | string      | 字段单位                                        |
| is_disabled       | bool        | 是否禁用                                        |
| option            | dict        | 字段选项配置，键为选项名，值为选项配置（当with_option=true时返回）   |

### 响应参数示例

#### 非分页返回示例（page_size=0）

```json
{
    "message":"OK",
    "code":200,
    "data":[{
    	"table_id": "system.cpu",
    	"bk_tenant_id": "default",
    	"table_name_zh": "CPU使用率",
    	"is_custom_table": false,
    	"scheme_type": "fixed",
    	"default_storage": "influxdb",
    	"creator": "admin",
    	"create_time": "2018-10-10 10:10:10",
    	"last_modify_user": "admin",
    	"last_modify_time": "2018-10-10 10:10:10",
    	"bk_biz_id": 0,
    	"label": "os",
    	"is_enable": true,
    	"data_label": "system",
    	"field_list": [{
    		"field_name": "usage",
    		"type": "float",
    		"tag": "metric",
    		"description": "CPU使用率",
    		"alias_name": "",
    		"default_value": null,
    		"is_config_by_user": true,
    		"unit": "percent",
    		"is_disabled": false,
    		"option": {}
    	}],
    	"bk_data_id": 1001,
    	"type_label": "time_series",
    	"source_label": "bk_monitor",
    	"option": {},
    	"storage_list": ["influxdb"]
    }],
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```

#### 分页返回示例（page_size>0）

```json
{
    "message":"OK",
    "code":200,
    "data":{
        "count": 100,
        "info": [{
            "table_id": "system.cpu",
            "bk_tenant_id": "default",
            "table_name_zh": "CPU使用率",
            "is_custom_table": false,
            "scheme_type": "fixed",
            "default_storage": "influxdb",
            "creator": "admin",
            "create_time": "2018-10-10 10:10:10",
            "last_modify_user": "admin",
            "last_modify_time": "2018-10-10 10:10:10",
            "bk_biz_id": 0,
            "label": "os",
            "is_enable": true,
            "data_label": "system",
            "field_list": [{
                "field_name": "usage",
                "type": "float",
                "tag": "metric",
                "description": "CPU使用率",
                "alias_name": "",
                "default_value": null,
                "is_config_by_user": true,
                "unit": "percent",
                "is_disabled": false,
                "option": {}
            }],
            "bk_data_id": 1001,
            "type_label": "time_series",
            "source_label": "bk_monitor",
            "option": {},
            "storage_list": ["influxdb"]
        }]
    },
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```

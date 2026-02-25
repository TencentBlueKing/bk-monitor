### 功能描述

修改监控结果表

### 请求参数

| 字段                   | 类型     | 必选 | 描述                                                                                                                            |
|----------------------|--------|----|-------------------------------------------------------------------------------------------------------------------------------|
| table_id             | string | 是  | 结果表ID                                                                                                                         |
| operator             | string | 是  | 操作者                                                                                                                           |
| label                | string | 否  | 结果表标签，此处记录的是二级标签，对应一级标签将由二级标签推导得到                                                                                             |
| bk_biz_id_alias      | string | 否  | 过滤条件业务ID别名                                                                                                                    |
| field_list           | list   | 否  | 全量的字段列表                                                                                                                       |
| query_alias_settings | list   | 否  | 查询别名设置，字段查询别名的配置                                                                                                              |
| table_name_zh        | string | 否  | 结果表中文名                                                                                                                        |
| default_storage      | string | 否  | 结果表默认存储类型                                                                                                                     |
| external_storage     | dict   | 否  | 额外存储配置，格式为{${storage_type}: ${storage_config}}, storage_type可为kafka, influxdb, redis; storage_config与default_storage_config一致 |
| is_enable            | bool   | 否  | 是否启用结果表                                                                                                                       |
| is_time_field_only   | bool   | 否  | 默认字段是否仅需要time，默认为False，该字段仅在field_list参数为非空时生效                                                                                |
| option               | dict   | 否  | 结果表选项内容                                                                                                                       |
| is_reserved_check    | bool   | 否  | 检查内置字段，默认为True                                                                                                                |
| time_option          | dict   | 否  | 时间字段选项配置                                                                                                                      |
| data_label           | string | 否  | 数据标签                                                                                                                          |
| need_delete_storages | dict   | 否  | 需要删除的额外存储                                                                                                                     |

**注意**： 上述的`label`都应该通过`metadata_list_label`接口获取，不应该自行创建

###### 参数: default_storage_config及storage_config -- 在influxdb下支持的参数

| 键值                   | 类型     | 是否必选 | 默认值 | 描述                      |
|----------------------|--------|------|-----|-------------------------|
| source_duration_time | string | 否    | 30d | 元数据保存时间, 需要符合influxdb格式 |

###### 参数: default_storage_config及storage_config -- 在kafka下支持的参数

| 键值        | 类型  | 是否必选 | 默认值     | 描述                                                           |
|-----------|-----|------|---------|--------------------------------------------------------------|
| partition | int | 否    | 1       | 存储partition数量，注意：此处只是记录，如果是超过1个topic的配置，需要手动通过kafka命令行工具进行扩容 |
| retention | int | 否    | 1800000 | kafka数据保存时长，默认是半小时，单位ms                                      |

###### 参数: default_storage_config及storage_config -- 在redis下支持的参数

| 键值          | 类型     | 是否必选 | 默认值   | 描述            |
|-------------|--------|------|-------|---------------|
| is_sentinel | bool   | 否    | False | 是否哨兵模式        |
| master_name | string | 否    | ""    | 哨兵模式下master名称 |

**注意**: 由于redis默认使用队列方式，消费后就丢弃，因此未有时长配置

###### 参数: default_storage_config及storage_config -- 在elasticsearch下支持的参数

| 键值               | 类型     | 是否必选 | 默认值  | 描述                              |
|------------------|--------|------|------|---------------------------------|
| retention        | int    | 否    | 30   | 保留index时间，单位为天，默认保留30天          |
| slice_size       | int    | 否    | 500  | 需要切分的大小阈值，单位为GB，默认为500GB        |
| slice_gap        | int    | 否    | 120  | index分片时间间隔，单位分钟，默认2小时          |
| index_settings   | string | 是    | -    | 索引创建配置, json格式                  |
| mapping_settings | string | 否    | -    | 索引mapping配置，**不包含字段定义**， json格式 |
| alias_name       | string | 否    | None | 入库别名                            |
| option           | string | 否    | {}   | 字段选项配置，键为选项名，值为选项配置             |

**注意**: 上述信息是否可以修改，主要决定于该修改参数是否会导致历史数据丢失

| 键值                | 类型     | 是否必选 | 默认值  | 描述                       |
|-------------------|--------|------|------|--------------------------|
| field_name        | string | 是    | -    | 字段名                      |
| field_type        | string | 是    | -    | 字段类型                     |
| description       | string | 否    | ""   | 字段描述                     |
| tag               | string | 是    | -    | 字段类型，可以为metric或dimension |
| alias_name        | string | 否    | ""   | 字段别名，入库时可以改为此别名写入        |
| option            | dict   | 否    | {}   | 字段配置选项                   |
| is_config_by_user | bool   | 否    | true | 是否启用                     |

### 请求参数示例

```json
{
	"table_id": "system.cpu",
	"operator": "admin",
	"field_list": [{
		"field_name": "usage",
		"field_type": "double",
		"description": "CPU使用率",
		"tag": "metric",
		"alias_name": "usage_alias",
		"option": {},
		"is_config_by_user": true
	}],
	"label": "os",
	"table_name_zh": "CPU性能数据",
	"default_storage": "influxdb"
}
```

### 响应参数

| 字段         | 类型     | 描述     |
|------------|--------|--------|
| result     | bool   | 请求是否成功 |
| code       | int    | 返回的状态码 |
| message    | string | 描述信息   |
| data       | dict   | 数据     |
| request_id | string | 请求ID   |

#### data字段说明

| 字段               | 类型     | 描述                                                                |
|------------------|--------|-------------------------------------------------------------------|
| table_id         | string | 结果表ID                                                             |
| bk_tenant_id     | string | 租户ID                                                              |
| table_name_zh    | string | 结果表中文名                                                            |
| is_custom_table  | bool   | 是否自定义结果表                                                          |
| scheme_type      | string | 结果表schema配置方案，free(无schema配置), dynamic(动态schema), fixed(固定schema) |
| default_storage  | string | 默认存储方案                                                            |
| storage_list     | list   | 所有存储列表，元素为string                                                  |
| creator          | string | 创建者                                                               |
| create_time      | string | 创建时间, 格式为【2018-10-10 10:00:00】                                    |
| last_modify_user | string | 最后修改者                                                             |
| last_modify_time | string | 最后修改时间【2018-10-10 10:00:00】                                       |
| field_list       | list   | 字段列表                                                              |
| bk_biz_id        | int    | 业务ID                                                              |
| option           | dict   | 结果表选项内容                                                           |
| label            | string | 结果表标签                                                             |
| bk_data_id       | int    | 数据源ID                                                             |
| is_enable        | bool   | 是否启用                                                              |
| data_label       | string | 数据标签                                                              |

#### data.field_list字段说明

| 键值                | 类型          | 描述                                          |
|-------------------|-------------|---------------------------------------------|
| field_name        | string      | 字段名                                         |
| type              | string      | 字段类型，可以为float, string, boolean和timestamp    |
| tag               | string      | 字段标签，可以为metric, dimension, timestamp, group |
| default_value     | string/null | 字段默认值                                       |
| is_config_by_user | bool        | 用户是否启用该字段配置                                 |
| description       | string      | 字段描述信息                                      |
| unit              | string      | 字段单位                                        |
| alias_name        | string      | 入库别名                                        |
| option            | dict        | 字段选项配置，键为选项名，值为选项配置                         |
| is_disabled       | bool        | 是否禁用                                        |

### 响应参数示例

```json
{
    "message":"OK",
    "code":200,
    "data":{
    	"table_id": "system.cpu",
    	"bk_tenant_id": "default",
    	"table_name_zh": "CPU性能数据",
    	"is_custom_table": false,
    	"scheme_type": "fixed",
    	"default_storage": "influxdb",
    	"storage_list": ["influxdb"],
    	"creator": "admin",
    	"create_time": "2018-10-10 10:10:10",
    	"last_modify_user": "admin",
    	"last_modify_time": "2018-10-10 10:10:10",
    	"field_list": [{
    		"field_name": "usage",
    		"type": "float",
    		"tag": "metric",
    		"default_value": null,
    		"is_config_by_user": true,
    		"description": "CPU使用率",
    		"unit": "percent",
    		"alias_name": "",
    		"option": {},
    		"is_disabled": false
    	}],
    	"bk_biz_id": 0,
    	"option": {},
    	"label": "os",
    	"bk_data_id": 1001,
    	"is_enable": true,
    	"data_label": "system"
    },
    "result":true,
    "request_id":"408233306947415bb1772a86b9536867"
}
```

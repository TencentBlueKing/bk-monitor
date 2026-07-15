## 功能描述

查询指定索引集的日志聚类（Pattern）结果，返回数据指纹列表及占比、同比、告警等信息。

## 请求参数

### 鉴权头

| 参数名称    | 参数类型 | 必须 | 参数说明     |
| ----------- | -------- | ---- | ------------ |
| app_code    | string   | 是   | 蓝鲸应用ID   |
| app_secret  | string   | 是   | 蓝鲸应用秘钥 |
| bk_username | string   | 是   | 用户名称     |

鉴权信息通过请求头 `X-Bkapi-Authorization` 传递，取值为上述字段构成的 JSON 字符串。

### 路径参数

| 字段         | 类型       | 必选 | 描述                                  |
| ------------ | ---------- | ---- | ------------------------------------- |
| index_set_id | int/string | 是   | 索引集 ID，也支持 `flow-{flow_id}`    |

### 参数列表

| 字段              | 类型         | 必选 | 描述                                 |
| ----------------- | ------------ | ---- | ------------------------------------ |
| bk_biz_id         | string       | 否   | 业务 ID                              |
| keyword           | string       | 否   | 搜索关键字                           |
| start_time        | string       | 是   | 开始时间                             |
| end_time          | string       | 是   | 结束时间                             |
| addition          | list[object] | 否   | 检索条件                             |
| pattern_level     | string       | 是   | 敏感度，枚举 `01` `03` `05` `07` `09`|
| begin             | int          | 否   | 数据开始位置                         |
| size              | int          | 否   | 返回条数                             |
| year_on_year_hour | int          | 否   | 同比周期，单位小时，可自定义         |
| show_new_pattern  | bool         | 是   | 是否只显示新类                       |
| group_by          | list         | 否   | 分组字段                             |

#### addition 检索条件

| 参数名称 | 参数类型 | 必须 | 参数说明                                                                 |
| -------- | -------- | ---- | ------------------------------------------------------------------------ |
| fields   | string   | 是   | 检索字段                                                                 |
| operator | string   | 是   | 操作符：is/is one of/is not/is not one of/gt/gee/lt/lte/exists/does not exists |
| value    | string   | 是   | 检索条件值                                                               |

## 请求参数示例

```json
{
    "bk_biz_id": "2",
    "keyword": "*",
    "start_time": "2023-02-07 14:32:35",
    "end_time": "2023-02-07 14:47:35",
    "addition": [],
    "begin": 0,
    "size": 10000,
    "pattern_level": "05",
    "year_on_year_hour": 0,
    "show_new_pattern": false,
    "group_by": []
}
```

## 返回结果示例

```json
{
    "result": true,
    "code": 0,
    "message": "",
    "data": [
        {
            "pattern": "xxxxx",
            "count": 16471,
            "signature": "c0cc23b8686d931187fcd5ad636ce630",
            "percentage": 59.99927145563165,
            "is_new_class": false,
            "year_on_year_count": 0,
            "year_on_year_percentage": 100,
            "group": [""],
            "monitor": {
                "is_active": false,
                "strategy_id": null
            }
        }
    ]
}
```

### 返回结果说明

| 参数名称                | 参数类型 | 参数说明   |
| ----------------------- | -------- | ---------- |
| pattern                 | string   | Pattern    |
| count                   | int      | 数量       |
| signature               | string   | 数据指纹   |
| percentage              | float    | 占比       |
| is_new_class            | bool     | 是否为新类 |
| year_on_year_count      | int      | 同比数量   |
| year_on_year_percentage | int      | 同比变化   |
| group                   | list     | 分组字段   |
| monitor                 | object   | 告警信息   |
| monitor.is_active       | bool     | 是否开启   |
| monitor.strategy_id     | int      | 策略 ID    |

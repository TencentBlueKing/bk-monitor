### 功能描述

新建或更新报表

### 请求参数

| 字段                 | 类型   | 必选 | 描述                |
|--------------------|------|----|-------------------|
| id                 | int  | 否  | 报表ID（更新时必填）       |
| name               | str  | 是  | 报表名称              |
| bk_biz_id          | int  | 是  | 业务ID              |
| scenario           | str  | 是  | 订阅场景              |
| subscriber_type    | str  | 是  | 订阅人类型             |
| channels           | list | 是  | 频道列表              |
| frequency          | dict | 是  | 频率配置              |
| content_config     | dict | 是  | 内容配置              |
| scenario_config    | dict | 是  | 场景配置              |
| start_time         | int  | 否  | 开始时间（Unix时间戳，秒）   |
| end_time           | int  | 否  | 结束时间（Unix时间戳，秒）   |
| is_manager_created | bool | 否  | 是否由管理员创建（默认false） |
| is_enabled         | bool | 否  | 是否启用（默认true）      |

#### channels 元素字段说明

| 字段           | 类型   | 必选 | 描述    |
|--------------|------|----|-------|
| is_enabled   | bool | 是  | 是否启用  |
| subscribers  | list | 是  | 订阅者列表 |
| channel_name | str  | 是  | 渠道名称  |
| send_text    | str  | 否  | 发送文本  |

#### channels.subscribers 元素字段说明

| 字段         | 类型   | 必选 | 描述                        |
|------------|------|----|---------------------------|
| id         | str  | 是  | 订阅者ID                     |
| type       | str  | 否  | 订阅者类型 ("user" 或者 "group") |
| is_enabled | bool | 是  | 是否启用                      |

#### frequency 字段说明

| 字段         | 类型        | 必选 | 描述   |
|------------|-----------|----|------|
| type       | int       | 是  | 频率类型 |
| day_list   | list[int] | 是  | 日期列表 |
| week_list  | list[int] | 是  | 周几列表 |
| run_time   | str       | 是  | 运行时间 |
| hour       | float     | 否  | 小时频率 |
| data_range | dict      | 否  | 数据范围 |

#### frequency.data_range 字段说明

| 字段         | 类型  | 必选 | 描述       |
|------------|-----|----|----------|
| time_level | str | 是  | 数据范围时间等级 |
| number     | int | 是  | 数据范围时间   |

#### content_config 字段说明

| 字段              | 类型   | 必选 | 描述     |
|-----------------|------|----|--------|
| title           | str  | 是  | 标题     |
| is_link_enabled | bool | 是  | 是否启用链接 |

#### scenario_config 字段说明

| 字段                  | 类型   | 必选 | 描述      |
|---------------------|------|----|---------|
| index_set_id        | int  | 是  | 索引集ID   |
| is_show_new_pattern | bool | 是  | 是否显示新模式 |
| pattern_level       | str  | 是  | 模式级别    |
| log_display_count   | int  | 是  | 日志显示数量  |
| year_on_year_change | str  | 是  | 同比变化    |
| year_on_year_hour   | int  | 是  | 同比小时    |
| generate_attachment | bool | 是  | 是否生成附件  |

### 请求参数示例

```json
{
  "id": 123,
  "name": "日志聚类报表",
  "bk_biz_id": 2,
  "scenario": "clustering",
  "subscriber_type": "self",
  "channels": [
    {
      "is_enabled": true,
      "subscribers": [
        {
          "id": "admin",
          "type": "user",
          "is_enabled": true
        }
      ],
      "channel_name": "user",
      "send_text": "订阅报表内容"
    }
  ],
  "frequency": {
    "type": 4,
    "day_list": [1, 15],
    "week_list": [],
    "run_time": "09:00",
    "data_range": {
      "time_level": "day",
      "number": 1
    }
  },
  "content_config": {
    "title": "日志聚类报表",
    "is_link_enabled": true
  },
  "scenario_config": {
    "index_set_id": 789,
    "is_show_new_pattern": true,
    "pattern_level": "09",
    "log_display_count": 100,
    "year_on_year_change": "rise",
    "year_on_year_hour": 0,
    "generate_attachment": true
  },
  "start_time": 1696118400,
  "end_time": 1704067200,
  "is_manager_created": false,
  "is_enabled": true
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | int    | 报表ID   |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": 123
}
```

### 功能描述

获取已存在报表

### 请求参数

| 字段           | 类型  | 必选 | 描述               |
|--------------|-----|----|------------------|
| scenario     | str | 是  | 订阅场景             |
| query_type   | str | 否  | 查询类型             |
| bk_biz_id    | int | 是  | 业务ID             |
| index_set_id | int | 否  | 索引集ID（仅日志聚类场景需要） |

### 请求参数示例

```json
{
  "scenario": "clustering",
  "query_type": "self",
  "bk_biz_id": 2,
  "index_set_id": 789
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | list   | 报表列表   |

#### data 元素字段说明

| 字段                 | 类型   | 描述              |
|--------------------|------|-----------------|
| id                 | int  | 报表ID            |
| name               | str  | 报表名称            |
| bk_biz_id          | int  | 业务ID            |
| scenario           | str  | 订阅场景            |
| subscriber_type    | str  | 订阅人类型           |
| frequency          | dict | 频率配置            |
| content_config     | dict | 内容配置            |
| scenario_config    | dict | 场景配置            |
| start_time         | int  | 开始时间（Unix时间戳，秒） |
| end_time           | int  | 结束时间（Unix时间戳，秒） |
| is_manager_created | bool | 是否由管理员创建        |
| is_enabled         | bool | 是否启用            |
| is_deleted         | bool | 是否删除            |
| send_mode          | str  | 发送模式            |
| send_round         | int  | 最近一次发送轮次        |
| create_user        | str  | 创建人             |
| create_time        | str  | 创建时间            |
| update_user        | str  | 更新人             |
| update_time        | str  | 更新时间            |

#### frequency 字段说明

| 字段         | 类型        | 描述   |
|------------|-----------|------|
| type       | int       | 频率类型 |
| day_list   | list[int] | 日期列表 |
| week_list  | list[int] | 周几列表 |
| run_time   | str       | 运行时间 |
| hour       | float     | 小时频率 |
| data_range | dict      | 数据范围 |

#### frequency.data_range 字段说明

| 字段 | 类型 | 描述 |
|------------|-----|----|----------|
| time_level | str | 数据范围时间等级 |
| number | int | 数据范围时间 |

#### content_config 字段说明

| 字段 | 类型 | 描述 |
|-----------------|------|----|--------|
| title | str | 标题 |
| is_link_enabled | bool | 是否启用链接 |

#### scenario_config 字段说明

| 字段 | 类型 | 描述 |
|---------------------|------|----|---------|
| index_set_id | int | 索引集ID |
| is_show_new_pattern | bool | 是否显示新模式 |
| pattern_level | str | 模式级别 |
| log_display_count | int | 日志显示数量 |
| year_on_year_change | str | 同比变化 |
| year_on_year_hour | int | 同比小时 |
| generate_attachment | bool | 是否生成附件 |

### 响应参数示例

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 123,
      "name": "日志聚类报表",
      "bk_biz_id": 2,
      "scenario": "clustering",
      "subscriber_type": "self",
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
      "is_enabled": true,
      "send_mode": "periodic",
      "create_user": "admin",
      "create_time": "2024-01-01T10:00:00",
      "update_user": "admin",
      "update_time": "2024-01-15T10:00:00"
    }
  ]
}
```

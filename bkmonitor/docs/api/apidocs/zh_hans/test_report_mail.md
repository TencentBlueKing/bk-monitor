### 功能描述

订阅报表测试

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段              | 类型   | 必选 | 描述     |
|-----------------|------|----|--------|
| creator         | str  | 是  | 创建者    |
| mail_title      | str  | 是  | 邮件标题   |
| receivers       | list | 是  | 接收者    |
| channels        | list | 否  | 频道     |
| is_link_enabled | bool | 否  | 是否启用链接 |
| report_contents | list | 是  | 报告内容   |
| frequency       | dict | 否  | 频率     |

#### receivers

| 字段         | 类型   | 必选 | 描述       |
|------------|------|----|----------|
| is_enabled | bool | 是  | 是否启动订阅   |
| id         | str  | 是  | 用户名或组ID  |
| name       | str  | 否  | 用户名或组名   |
| group      | str  | 否  | 所属组别     |
| type       | str  | 是  | 类型（用户或组） |

#### channels

| 字段           | 类型   | 必选 | 描述   |
|--------------|------|----|------|
| is_enabled   | bool | 是  | 是否启动 |
| channel_name | str  | 是  | 渠道名称 |
| subscribers  | list | 否  | 订阅人员 |

#### channels.subscribers

| 字段         | 类型   | 必选 | 描述                        |
|------------|------|----|---------------------------|
| id         | str  | 是  | 订阅者ID                     |
| type       | str  | 否  | 订阅者类型 ("user" 或者 "group") |
| is_enabled | bool | 是  | 是否启用                      |

#### report_contents

| 字段               | 类型        | 必选 | 描述         |
|------------------|-----------|----|------------|
| content_title    | str       | 是  | 子内容标题      |
| content_details  | str       | 是  | 子内容说明      |
| row_pictures_num | int       | 是  | 一行几幅图      |
| graphs           | list[str] | 是  | 图表Panels信息 |

#### frequency

| 字段         | 类型        | 必选 | 描述   |
|------------|-----------|----|------|
| type       | int       | 是  | 频率类型 |
| day_list   | list[int] | 是  | 几天   |
| week_list  | list[int] | 是  | 周几   |
| run_time   | str       | 是  | 运行时间 |
| hour       | float     | 否  | 小时频率 |
| data_range | dict      | 否  | 数据范围 |

#### frequency.data_range

| 字段         | 类型  | 必选 | 描述       |
|------------|-----|----|----------|
| time_level | str | 是  | 数据范围时间等级 |
| number     | int | 是  | 数据范围时间   |

#### 示例数据

```json
{
  "creator": "张三",
  "mail_title": "邮件标题xxx",
  "receivers": [
    {
      "is_enabled": true,
      "id": "001",
      "name": "李四",
      "group": "用户组1",
      "type": "user"
    },
    {
      "is_enabled": true,
      "id": "003",
      "name": "用户组3",
      "type": "group"
    }
  ],
  "channels": [
    {
      "is_enabled": true,
      "channel_name": "email",
      "subscribers": [
        {
          "id": "001",
          "type": "user",
          "is_enabled": true
        }
      ]
    }
  ],
  "is_link_enabled": true,
  "report_contents": [
    {
      "content_title": "456asd",
      "content_details": "xxxx",
      "row_pictures_num": 2,
      "graphs": [
        "2-bLlNuRLWz-8"
      ]
    }
  ],
  "frequency": {
    "type": 4,
    "day_list": [
      1
    ],
    "week_list": [],
    "run_time": "09:00"
  }
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | str  | 描述信息   |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": "success"
}
```

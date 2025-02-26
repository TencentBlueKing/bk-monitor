### 功能描述

启动图片渲染任务

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| type | string | 是   | 任务类型，dashboard: 仪表盘 |
| options | object | 是   | 任务参数   |

#### options 参数

##### dashboard options

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| bk_biz_id | integer | 是   | 业务id   |
| dashboard_uid | string | 是   | 仪表盘uid   |
| panel_id | string | 否   | 面板id, 如果为空，则渲染整个仪表盘   |
| height | integer | 否   | 高度, px, 仅在panel_id不为空时有效   |
| width | integer | 是   | 宽度, px   |
| variables | object | 否   | 变量，{"xxx": ["yyy"]}   |
| start_time | integer | 是   | 开始时间, 时间戳，单位秒   |
| end_time | integer | 是   | 结束时间, 时间戳，单位秒   |
| scale | integer | 否   | 像素密度, 默认2, 最大4, 越大越清晰，但是图片大小也越大   |
| with_panel_title | boolean | 否   | 是否显示面板标题, 仅在panel_id不为空时有效   |

#### 示例数据

```json
{
    "type": "dashboard",
    "options": {
        "bk_biz_id": 1,
        "dashboard_uid": "xxx",
        "panel_id": "xxx",
        "height": 300,
        "width": 300,
        "variables": {"xxx": ["yyy"]},
        "start_time": 1719859200,
        "end_time": 1719862800
    }
}
```

### 响应参数

| 字段名  | 类型   | 描述         |
| ------- | ------ | ------------ |
| task_id | string | 任务id     |

#### 示例数据

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "task_id": "xxxxxxxxxxxxx"
    },
    "result": true
}
```
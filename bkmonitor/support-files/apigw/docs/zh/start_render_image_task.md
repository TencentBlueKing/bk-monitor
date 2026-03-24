### 功能描述

启动图片渲染任务


### 请求参数

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| type | string | 是   | 任务类型，dashboard: 仪表盘 |
| options | object | 是   | 任务参数   |

#### options

| 字段名 | 类型   | 必选 | 描述     |
| ------ | ------ | ---- | -------- |
| bk_biz_id | integer | 是   | 业务id   |
| dashboard_uid | string | 是   | 仪表盘uid   |
| panel_id | string | 否   | 面板id, 如果为空或null，则渲染整个仪表盘，默认值：null   |
| height | integer | 否   | 高度, px, 仅在panel_id不为空时有效，默认值：300   |
| width | integer | 是   | 宽度, px   |
| variables | object | 否   | 变量，{"xxx": ["yyy"]}，默认值：{}   |
| start_time | integer | 是   | 开始时间, 时间戳，单位秒   |
| end_time | integer | 是   | 结束时间, 时间戳，单位秒   |
| scale | integer | 否   | 像素密度, 默认值：2   |
| with_panel_title | boolean | 否   | 是否显示面板标题, 仅在panel_id不为空时有效，默认值：true   |
| image_format | string | 否   | 图片格式，可选值：jpeg、png，默认值：jpeg   |
| image_quality | integer | 否   | 图片质量，取值范围：0-100，默认值：85   |
| transparent | boolean | 否   | 是否透明背景，默认值：false   |

### 请求参数示例

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
| task_id | string | 任务id，UUID格式的字符串     |

### 响应参数示例

```json
{
    "message": "OK",
    "code": 200,
    "data": {
        "task_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "result": true
}
```
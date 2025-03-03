### 功能描述

校验自定义指标名称是否合法

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段                   | 类型  | 必选 | 描述      |
|----------------------|-----|----|---------|
| time_series_group_id | int | 否  | 自定义时序ID |
| name                 | str | 是  | 名称      |
| bk_biz_id            | int | 是  | 业务ID    |

#### 请求示例

```json
{
  "name": "test_ts",
  "bk_biz_id": 2
}
```

### 响应参数

| 字段            | 类型           | 描述     |
|---------------|--------------|--------|
| resul         | bool         | 请求是否成功 |
| code          | int          | 返回的状态码 |
| message       | str          | 描述信息   |
| data          | bool \| null | 结果     |
| error_details | dict         | 错误信息   |

#### error_details 错误信息

| 字段            | 类型  | 描述   |
|---------------|-----|------|
| type          | str | 错误类型 |
| code          | int | 状态码  |
| overview      | str | 概览信息 |
| detail        | str | 细节信息 |
| popup_message | str | 弹框颜色 |

#### 响应示例: 校验通过

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": true
}
```

#### 响应示例: 校验失败

```json
{
  "result": false,
  "code": 3335006,
  "name": "自定义名称校验不通过",
  "message": "自定义指标名称已存在",
  "data": null,
  "error_details": {
    "type": "CustomValidationNameError",
    "code": 3335006,
    "overview": "自定义指标名称已存在",
    "detail": "None",
    "popup_message": "warning"
  }
}
```


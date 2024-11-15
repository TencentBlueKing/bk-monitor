### 功能描述

删除一个应用

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段           | 类型   | 必选 | 描述         |
| -------------- | ------ | ---- | ------------ |
| application_id | int    | 否   | 应用id       |
| bk_biz_id      | int    | 否   | 业务id       |
| app_name       | string | 否   | 应用名       |
| space_uid      | string | 否   | 空间唯一标识 |

- 至少要传 application_id，或 bk_biz_id + app_name，或 bk_biz_id + space_uid

#### 请求示例

- ```json
  {
      "bk_biz_id ": "xxx",
      "app_name": "xxx"
  }
  或者
  {
      "application_id ": 123
  }
  ```


### 返回结果

无返回内容


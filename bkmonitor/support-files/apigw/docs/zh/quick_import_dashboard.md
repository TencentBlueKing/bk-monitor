### 功能描述

快速导入仪表盘

### 请求参数

{{ common_args_desc }}

#### 接口参数

| 字段 | 类型 | 必选 | 描述 |
|------|------|------|------|
| bk_biz_id | integer | 是 | 业务ID |
| dash_name | string | 是 | 仪表盘名称（如果不以 .json 结尾会自动添加 .json 后缀） |
| folder_name | string | 否 | 仪表盘文件夹名称，默认为空字符串。如果指定且不为 "General"，会在不存在时自动创建该文件夹 |

#### 请求示例

```json
{
    "bk_biz_id": 2,
    "dash_name": "default_dashboard",
    "folder_name": "监控面板"
}
```

### 返回结果

| 字段 | 类型 | 描述 |
|------|------|------|
| result | bool | 请求是否成功 |
| code | int | 返回的状态码 |
| message | string | 描述信息 |
| data | null | 数据（成功时为空） |
| request_id | string | 请求ID |

#### 结果示例

**成功响应**：
```json
{
    "message": "OK",
    "code": 200,
    "data": null,
    "result": true,
    "request_id": "..."
}
```

**失败响应**：
```json
{
    "message": "bk_biz_id[2], quick import dashboard[default_dashboard.json] failed",
    "code": 500,
    "data": null,
    "result": false,
    "request_id": "..."
}
```

### 说明

1. **仪表盘名称处理**：如果 `dash_name` 参数不以 `.json` 结尾，系统会自动添加 `.json` 后缀
2. **文件夹处理**：
   - 如果 `folder_name` 为空或为 "General"，仪表盘将导入到默认目录（General）
   - 如果指定了 `folder_name` 且不为 "General"，系统会：
     - 先查找是否存在同名文件夹
     - 如果不存在，会自动创建该文件夹
     - 然后将仪表盘导入到该文件夹中
3. **仪表盘文件来源**：系统会从预置的仪表盘文件中查找对应的 JSON 文件进行导入

### 功能描述

快速导入预定义的仪表盘模板到指定业务和文件夹

### 请求参数

| 字段          | 类型      | 必选 | 描述                                                |
|-------------|---------|----|---------------------------------------------------|
| bk_biz_id   | integer | 是  | 业务ID                                              |
| dash_name   | string  | 是  | 仪表盘名称（如果不以 .json 结尾会自动添加 .json 后缀）                |
| folder_name | string  | 否  | 仪表盘文件夹名称，默认为空字符串。如果指定且不为 "General"，会在不存在时自动创建该文件夹 |

### 请求示例

**导入到默认目录**：

```json
{
    "bk_biz_id": 2,
    "dash_name": "system_monitor"
}
```

**导入到指定文件夹**：

```json
{
    "bk_biz_id": 2,
    "dash_name": "system_monitor.json",
    "folder_name": "系统监控"
}
```

### 响应参数

| 字段      | 类型     | 描述             |
|---------|--------|----------------|
| result  | bool   | 请求是否成功         |
| code    | int    | 返回的状态码         |
| message | string | 描述信息           |
| data    | null   | 返回数据（成功时为null） |

### 响应参数示例

**成功响应**：

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": null
}
```

**失败响应**：

```json
{
    "result": false,
    "code": 500,
    "message": "bk_biz_id[2], quick import dashboard[system_monitor.json] failed",
    "data": null
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

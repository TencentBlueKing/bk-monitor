### 功能描述

导出插件

### 请求参数

| 字段        | 类型     | 必选 | 描述                |
|-----------|--------|----|-------------------|
| plugin_id | string | 是  | 插件ID（通过URL路径参数传递） |

### 请求参数示例

```bash
GET /api/v4/collector_plugin/{plugin_id}/export_plugin/
```

示例：

```bash
GET /api/v4/collector_plugin/example_plugin/export_plugin/
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段           | 类型     | 描述                             |
|--------------|--------|--------------------------------|
| download_url | string | 插件包下载地址，可通过该URL下载导出的插件tar.gz文件 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "download_url": "http://example.com/media/export/example_plugin_1.0.0.tar.gz"
    }
}
```

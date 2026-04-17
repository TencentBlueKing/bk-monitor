### 功能描述

获取BCS集群灰度ID名单

### 请求参数

无

### 请求参数示例

无

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段                       | 类型        | 描述               |
|--------------------------|-----------|------------------|
| enable_bsc_gray_cluster  | bool      | 是否启用BCS集群灰度功能    |
| bcs_gray_cluster_id_list | list[str] | BCS灰度集群ID列表，默认为空 |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "enable_bsc_gray_cluster": false,
        "bcs_gray_cluster_id_list": []
    }
}
```

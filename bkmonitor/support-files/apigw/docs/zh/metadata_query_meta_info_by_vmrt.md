### 功能描述

根据VMRT查询关联元数据信息

### 请求参数

| 字段   | 类型  | 必选 | 描述        |
|------|-----|----|-----------|
| vmrt | str | 是  | VM 结果表 ID |

### 请求参数示例

```json
{
    "vmrt": "vm_result_table_id_1"
}
```

### 响应参数

| 字段      | 类型     | 描述     |
|---------|--------|--------|
| result  | bool   | 请求是否成功 |
| code    | int    | 返回的状态码 |
| message | string | 描述信息   |
| data    | dict   | 返回数据   |

#### data 字段说明

| 字段                 | 类型  | 描述         |
|--------------------|-----|------------|
| bk_data_id         | int | 数据源 ID     |
| data_name          | str | 数据源名称      |
| monitor_table_id   | str | 监控平台结果表 ID |
| vm_result_table_id | str | VM 结果表 ID  |
| bk_biz_id          | int | 业务 ID      |

### 响应参数示例

```json
{
    "result": true,
    "code": 200,
    "message": "OK",
    "data": {
        "bk_data_id": 1001,
        "data_name": "my_data_source",
        "monitor_table_id": "system.cpu_detail",
        "vm_result_table_id": "vm_result_table_id_1",
        "bk_biz_id": 2
    }
}
```

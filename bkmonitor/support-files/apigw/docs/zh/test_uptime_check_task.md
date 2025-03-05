### 功能描述

测试连通性


#### 接口参数

| 字段           | 类型        | 必选 | 描述                       |
|--------------|-----------|----|--------------------------|
| bk_biz_id    | int       | 是  | 业务ID                     |
| protocol     | str       | 是  | 协议                       |
| node_id_list | list[int] | 是  | 拨测节点ID列表(列表内的节点ID为int类型) |
| config       | dict      | 是  | 拨测配置                     |

#### config

| 字段                  | 类型        | 必选 | 描述                     |
|---------------------|-----------|----|------------------------|
| method              | str       | 否  | HTTP 方法，默认值为 "GET"     |
| authorize           | dict      | 否  | 授权配置                   |
| body                | dict      | 否  | 请求体                    |
| query_params        | list      | 否  | 查询参数                   |
| headers             | list      | 否  | 请求头                    |
| response_code       | str       | 否  | 响应代码                   |
| port                | str       | 否  | 端口                     |
| node_list           | list      | 否  | 主机列表                   |
| ip_list             | list[str] | 否  | IP 列表                  |
| output_fields       | list[str] | 否  | 输出字段                   |
| target_ip_type      | int       | 否  | 目标 IP 类型，默认值为 0        |
| dns_check_mode      | str       | 否  | DNS 检查模式，默认值为 "single" |
| request             | str       | 否  | 请求内容                   |
| request_format      | str       | 否  | 请求格式                   |
| wait_empty_response | bool      | 否  | 是否等待空响应                |
| max_rtt             | int       | 否  | 最大往返时间                 |
| total_num           | int       | 否  | 总数                     |
| size                | int       | 否  | 数据包大小                  |
| send_interval       | str       | 否  | 发送间隔                   |
| target_labels       | dict      | 否  | 目标标签                   |
| url_list            | list[str] | 否  | URL 列表                 |
| period              | int       | 是  | 周期                     |
| response_format     | str       | 否  | 响应格式                   |
| response            | str       | 否  | 响应内容                   |
| timeout             | int       | 否  | 超时时间                   |
| urls                | str       | 否  | URL                    |
| hosts               | list      | 否  | 主机列表                   |

#### config.authorize

| 字段                   | 类型   | 必选 | 描述                                                          |
|----------------------|------|----|-------------------------------------------------------------|
| insecure_skip_verify | bool | 否  | 是否跳过 SSL 验证                                                 |
| auth_type            | str  | 是  | 授权类型，包括 "none"、"basic_auth"、"bearer_token" 和 "tencent_auth" |
| auth_config          | dict | 否  | 授权配置，包含具体的认证信息                                              |

#### config.body

| 字段           | 类型   | 必选 | 描述                                                                           |
|--------------|------|----|------------------------------------------------------------------------------|
| data_type    | str  | 否  | 数据类型，默认值为 "text"，可选值包括 "default"、"raw"、"form_data" 和 "x_www_form_urlencoded" |
| params       | list | 否  | 请求参数列表，包含键值对                                                                 |
| content      | str  | 否  | 请求内容，可以为空                                                                    |
| content_type | str  | 否  | 内容类型，默认值为 "text"，可选值包括 "text"、"json"、"html" 和 "xml"                          |

#### config.body.params

| 字段         | 类型   | 必选 | 描述                |
|------------|------|----|-------------------|
| key        | str  | 是  | 键，最大长度为 64 个字符    |
| value      | str  | 否  | 值，可以为空，默认值为空字符串   |
| desc       | str  | 否  | 描述，可以为空，默认值为空字符串  |
| is_builtin | bool | 否  | 是否为内置项，默认值为 False |
| is_enabled | bool | 否  | 是否启用，默认值为 True    |

#### config.query_params

| 字段         | 类型   | 必选 | 描述                  |
|------------|------|----|---------------------|
| key        | str  | 是  | 参数的键，最大长度为 64 个字符   |
| value      | str  | 否  | 参数的值，可以为空，默认值为空字符串  |
| desc       | str  | 否  | 参数的描述，可以为空，默认值为空字符串 |
| is_builtin | bool | 否  | 是否为内置项，默认值为 False   |
| is_enabled | bool | 否  | 是否启用，默认值为 True      |

#### config.headers

| 字段         | 类型  | 描述        |
|------------|-----|-----------|
| is_enabled | str | 是否可用      |
| key        | str | 请求头的key   |
| value      | str | 请求头的value |
| desc       | str | 请求头的描述    |
| index      | str | 请求的位置索引   |

#### config.node_list

| 字段          | 类型  | 必选 | 描述                     |
|-------------|-----|----|------------------------|
| bk_host_id  | int | 否  | 主机 ID，允许为空             |
| ip          | str | 否  | 主机 IP，可以为空             |
| outer_ip    | str | 否  | 外部 IP，可以为空，兼容通过文件导入的任务 |
| target_type | str | 否  | 目标类型，可以为空              |
| bk_biz_id   | int | 否  | 业务 ID，允许为空             |
| bk_inst_id  | int | 否  | 实例 ID，允许为空             |
| bk_obj_id   | str | 否  | 对象 ID，可以为空             |
| node_path   | str | 否  | 节点路径，可以为空              |

#### config.target_labels

- 字段名是 目标主机IP 或者是 url
- 字段值是 目标主机的标签

#### config.hosts

| 字段          | 类型  | 必选 | 描述   |
|-------------|-----|----|------|
| bk_host_id  | int | 否  | 主机ID |
| ip          | str | 否  | 主机IP |
| outer_ip    | str | 否  | 外部IP |
| target_type | str | 否  | 目标类型 |
| bk_biz_id   | int | 否  | 业务ID |
| bk_inst_id  | int | 否  | 实例ID |
| bk_obj_id   | str | 否  | 对象ID |
| node_path   | str | 否  | 节点路径 |

#### 示例数据

```json
{
  "bk_biz_id": 2,
  "protocol": "HTTP",
  "node_id_list": [
    10017
  ],
  "config": {
    "period": 60,
    "timeout": 3000,
    "response": "",
    "response_format": "nin",
    "method": "GET",
    "url_list": [
      "http://www.baidu.com"
    ],
    "headers": [],
    "body": {
      "data_type": "default",
      "content_type": "",
      "content": "",
      "params": []
    },
    "authorize": {
      "auth_config": {},
      "auth_type": "none",
      "insecure_skip_verify": false
    },
    "query_params": [],
    "response_code": ""
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
  "data": "已成功探测目标服务，保存任务中..."
}
```

### 功能描述

导出 Profile 性能分析数据，支持将指定时间范围和过滤条件的 Profile 数据导出为压缩格式文件。适用于 APM 性能分析场景的数据备份和离线分析。

### 请求参数

| 字段                 | 类型           | 必选 | 描述                                           |
|--------------------|--------------|----|----------------------------------------------|
| bk_biz_id          | int          | 是  | 业务 ID                                        |
| export_format      | string       | 是  | 数据导出格式，目前仅支持 `pprof`                         |
| app_name           | string       | 否  | 应用名称，当 `global_query` 为 `false` 时必填          |
| service_name       | string       | 否  | 服务名称，当 `global_query` 为 `false` 时必填          |
| global_query       | bool         | 否  | 全局查询，默认 `false`。为 `true` 时查询全局上传的 Profile 文件 |
| data_type          | string       | 否  | 采样类型（sample_type），默认值由系统配置决定                 |
| start              | int          | 否  | 开始时间（微秒，Microsecond），与 `start_time` 二选一      |
| start_time         | int          | 否  | 开始时间（秒，Second），与 `start` 二选一                 |
| end                | int          | 否  | 结束时间（微秒，Microsecond），与 `end_time` 二选一        |
| end_time           | int          | 否  | 结束时间（秒，Second），与 `end` 二选一                   |
| profile_id         | string       | 否  | Profile ID，用于导出特定的 Profile 数据                |
| offset             | int          | 否  | 时间偏移量（秒），默认 `0`                              |
| filter_labels      | dict         | 否  | 标签过滤条件，用于精确筛选 Profile 数据                     |
| agg_method         | string       | 否  | 聚合方法，最大长度 64 字符                              |
| is_compared        | bool         | 否  | 是否开启对比模式，默认 `false`                          |
| diff_profile_id    | string       | 否  | 对比的 Profile ID，仅当 `is_compared` 为 `true` 时有效 |
| diff_filter_labels | dict         | 否  | 对比数据的标签过滤条件，仅当 `is_compared` 为 `true` 时有效    |
| diagram_types      | List[string] | 否  | 图表类型列表，默认 `["flamegraph", "table"]`          |
| sort               | string       | 否  | 排序规则，仅对 table 类型有效，默认 `"-total"`             |

#### 时间参数说明

- `start` 和 `start_time` 二选一必填，优先使用 `start`
- `end` 和 `end_time` 二选一必填，优先使用 `end`
- 当传递 `start_time` 或 `end_time` 时，系统会自动转换为微秒级时间戳

### 请求参数示例

```json
{
   "bk_biz_id": 2,
   "app_name": "trpc_test",
   "service_name": "trpc_demo.helloworld",
   "data_type": "cpu/nanoseconds",
   "start": 1769411698000000,
   "end": 1769412598000000,
   "filter_labels": {"app":"trpc_demo"},
   "agg_method": "SUM",
   "export_format": "pprof",
   "diff_filter_labels": {}
}
```

### 响应参数

该接口返回文件流，响应头包含以下信息：

| 响应头                 | 值                          | 描述         |
|---------------------|----------------------------|------------|
| Content-Type        | application/octet-stream   | 二进制流类型     |
| Content-Encoding    | gzip                       | 使用 gzip 压缩 |
| Content-Disposition | attachment; filename="..." | 下载文件名      |

#### 文件命名规则

导出文件名格式：`{app_name}_{data_type}_{timestamp}.{format}`

示例：`my-application_cpu_2026-01-26-15-30-00.pprof`

### 响应示例

```text
HTTP/1.1 200 OK
Content-Type: application/octet-stream
Content-Disposition: attachment; filename="trpc_test-cpu/nanoseconds-2026-01-26-16-19-16.pprof"
Content-Encoding: gzip
```

### 使用说明

1. **全局查询模式**：当 `global_query` 为 `true` 时，将查询全局上传的 Profile 文件，此时无需传递 `app_name` 和 `service_name`。

2. **时间范围处理**：系统会根据 `offset` 参数自动调整查询的时间范围，并根据时间跨度自动选择合适的聚合周期（5 分钟内为秒级，5 分钟以上为分钟级）。

3. **数据聚合**：通过 `agg_method` 可指定聚合方法，系统会根据时间范围自动计算聚合间隔。

4. **文件格式**：导出的文件为 gzip 压缩的 Protocol Buffers 格式，可使用相应的工具进行解析和分析。

5. **空数据处理**：当查询结果为空时，仍会返回一个空的压缩文件。

6. **性能优化**：对于大型应用，系统会自动限制查询的数据量以避免接口超时。

7. **Profile ID 查询**：如果指定了 `profile_id`，将导出特定的 Profile 数据，通常用于导出已上传的 Profile 文件。

### 注意事项

1. 导出大量数据时可能需要较长时间，建议合理设置时间范围
2. 导出的文件需要使用支持 gzip 和 Protocol Buffers 的工具进行解析
3. 确保应用已开启性能分析功能，否则可能无法导出数据
4. 建议在非高峰期进行大量数据导出操作

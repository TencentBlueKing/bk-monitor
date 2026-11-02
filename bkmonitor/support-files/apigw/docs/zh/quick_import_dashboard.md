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
    "dash_name": "host"
}
```

**导入 GPU 性能仪表盘到指定文件夹**：

```json
{
    "bk_biz_id": 2,
    "dash_name": "gpu-performance.json",
    "folder_name": "GPU监控"
}
```

### GPU 性能模板

`dash_name` 为 `gpu-performance` 或 `gpu-performance.json`，导入后的仪表盘标题为「GPU 性能」。

适用于已接入 NVIDIA DCGM 指标的 Kubernetes 集群，使用原始 `DCGM_FI_DEV_*` 和 `DCGM_FI_PROF_*` 指标。目标业务需已采集并入库对应指标；TKE elastic 的 `gpu_*` 和非 Kubernetes 主机的 `nvidia_smi_*` 指标不适用于此模板。

模板包含 3 个分组、22 张图表：

| 分组 | 内容 |
|---|---|
| GPU 基础性能（集群维度） | 物理卡数、各节点物理卡数、整卡 GPU 利用率和低利用率卡 |
| GPU MIG 切片（profiling） | Tensor Core 活跃度、显存带宽活跃度、未挂 Pod 的卡或 MIG 切片的显存占用 |
| GPU 基础性能（Pod 维度） | 整卡数和利用率、显存、温度、编解码器、功耗与能耗、时钟频率、PCIe 重放计数 |

- **数据源**：导入时自动绑定目标业务的「蓝鲸监控 - 指标数据」数据源，不依赖来源业务的数据源 UID。
- **指标前缀**：`MetricPrefix` 默认为空，适用于标准容器采集。通过自定义采集来源上报时，填写对应的 `data_label:`（包含末尾冒号，例如 `example_metrics:`），显式指定指标来源。该前缀同时应用于集群、Pod 枚举和全部图表；裸指标在全业务可查，不保证带集群条件时仍能路由到相同来源。
- **筛选变量**：`Cluster` 单选集群，`Pod` 支持多选；均从对应来源的 `DCGM_FI_DEV_FB_USED` 枚举。Pod 的 All 值为 `.+`，只包含非空 Pod；集群和 MIG 分组不受 Pod 筛选影响。
- **默认时间范围**：最近 6 小时。
- **指标口径**：物理卡数按 `node`、`gpu`、`UUID` 去重。`DCGM_FI_DEV_GPU_UTIL` 展示整卡利用率；MIG 活跃度依赖对应的 profiling 指标，未采集或不支持这些指标时相关图表可能为空。
- **时钟单位**：SM 和显存时钟的原值单位为 MHz，图表使用 MHz 显示口径，例如原值 `1500` 对应 `1500 MHz`（可自动缩放为 `1.5 GHz`）。
- **能耗聚合**：按 `pod_name`、`node`、`gpu`、`UUID` 去除重复采集系列后，再累加同一 Pod 关联的不同物理卡。区间能耗先对各原始计数器计算 `increase`，再去重求和，保留计数器重置处理。例如两张卡在 1 小时内各增加 `3600000000 mJ`，Pod 合计为 `2 kWh`，重复采集副本不再重复累加。
- **能耗归属**：累计值是设备自驱动加载以来的计数，非 Pod 生命周期累计；图表展示 Pod 关联物理卡的能耗，MIG 共享卡不按切片分摊。同一物理卡关联多个 Pod 时，各 Pod 的数值可能重叠，不宜跨 Pod 相加。

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
    "message": "bk_biz_id[2], quick import dashboard[gpu-performance.json] failed",
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
4. **重复导入**：沿用覆写导入模式（`overwrite=true`），同一目标目录内同名仪表盘的用户修改可能被覆盖。需要保留自行修改的版本时，请使用独立目录。
5. **按需导入**：GPU 性能模板通过本接口按需创建，不会自动添加到所有业务。

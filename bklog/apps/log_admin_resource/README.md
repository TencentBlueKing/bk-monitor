# BKLOG Admin Resource

`POST /api/v1/admin/resource/call/` 是提供给受信管理端的统一资源调用入口。调用方通过 `__meta__`
读取 operation 的参数、响应 JSON Schema、示例和 `safety_level`，不能直接拼 BKBase URL 或传入
`bk_username`、`operator`、`bk_tenant_id` 等鉴权身份。

BKLOG 按业务的在线聚类配置解析 BKBase 用户，并从 `Space` 记录严格解析租户；缺少租户映射时返回
独立证据错误，不回退为调用方或默认生产租户。

## 日志聚类只读操作

| Operation | 用途 |
| --- | --- |
| `bklog.index_set.list` | 索引集分页查询，并返回聚类配置摘要和唯一配置跳转 ID |
| `bklog.index_set.detail` | 索引集、索引组成员及其全部聚类配置关系 |
| `bklog.clustering_config.list` | 聚类配置分页查询、Flow/RT 引用和接入存储状态 |
| `bklog.clustering_config.detail` | 按精确 `config_id` 返回所有聚类参数；大段生成 Flow 配置显式加载 |
| `bklog.clustering_config.access_pipeline` | 接入任务历史、选中任务、串行 Pipeline 引擎状态和持久化步骤 |
| `bklog.bkdata.raw.snapshot` | RawData 部署信息和最新原始样本 |
| `bklog.bkdata.clean.snapshot` | 清洗定义和清洗分发任务 |
| `bklog.bkdata.flow.snapshot` | 指定任意 Flow 的详情、最近部署和真实 Graph |
| `bklog.bkdata.result_table.snapshot_batch` | 最多 20 个 RT 的详情和 Tail 采样，外部并发不超过 5 |

配置只读操作的 `safety_level` 为 `read`。可能返回用户日志样本的操作为 `inspect`，并标记
`data_classification=sensitive_logs`。实际调用仍受 Admin Resource APIGW 和应用白名单保护；管理端负责
人员权限、审计和页面展示控制。

## 证据协议

BKBase 子探测统一返回：

```json
{
  "probe_status": "success | failed | skipped",
  "exists": true,
  "empty": false,
  "observed_at": "2026-08-12T10:52:14+08:00",
  "duration_ms": 123.45,
  "data": {},
  "error": null,
  "warnings": []
}
```

- 成功但无采样是 `probe_status=success, exists=true, empty=true`，不得等同于资源不存在。
- 只有明确不存在时 `exists=false`；请求失败或未检查时为 `null`。
- 同一 snapshot 的子探测独立返回，允许部分成功。
- 错误保留上游 code、message 和已透传的 request ID，并归一化认证、权限、超时、不存在、解码、
  非法响应和普通请求失败。
- BKLOG 只返回事实证据，不计算健康度、延迟阈值或“首个故障节点”。

## Tail 样本

- 默认 10 条，调用方最大指定 20 条。
- 每条样本的原始整行放在 `raw.value`；未超限时字段和日志原文不删减、不脱敏。
- 单条内容预算最大 64 KiB。RawData 同时返回解码内容时，两者共享预算；超限通过 `truncated`、
  `original_size_bytes` 和 `returned_size_bytes` 明示。
- RawData 保留 `value` / `base64_data`，并返回 `decode_status`、`content_encoding` 和 `decoded`。
- 时间证据返回所有候选字段、原值、字段路径、解析状态、时间单位和时区假设，并单独给出选中候选。
  选中值取最高优先级时间字段中的最新时间；BKLOG 不在这里计算 freshness 或 delay。
- BKBase 实时计算节点短路时，中间 RT Tail 可能为空；调用方必须结合实际 Flow Graph 和上下游 RT，
  不能把空 Tail 单独判定为节点故障。

## 明确边界

- 接入 Pipeline 当前只有串行执行，不暴露分支、循环和 ACK 语义。
- Flow snapshot 接受显式 `flow_id`，配置详情只发现配置自身保存的 Flow 引用，不扫描孤儿 Flow。
- 配置详情默认返回全部算法、模型、存储、策略和资源参数；大段生成 Flow 定义通过
  `include_flow_configs=true` 显式加载，并与 BKBase 当前 Graph 分开表达。
- 接入任务历史和步骤不混入配置参数；通过 `clustering_config.access_pipeline` 按最新或显式 `task_id`
  单独加载。Pipeline 节点输入、输出和异常数据保留未知字段，超出 256 KiB 时返回截断元数据。
- 不调用会写入 `access_finished` 的接入状态方法，不启动、停止或修改 BKBase 资源。
- 不探测 CollectorHub；不提供未正式上线的 Mini Link 运行态链路。
- 配置详情中的结构化配置会屏蔽凭据键；Tail 日志内容不按关键词屏蔽，以保留排障原文。
- 运行态 Flow 和 Tail 不缓存；每次上游调用超时为 10 秒。

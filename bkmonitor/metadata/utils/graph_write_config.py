"""业务结果表 Graph V4 option 中的 SurrealDB 写入配置及 BKBase 协议映射。"""

from pydantic import BaseModel, ConfigDict, Field


class GraphBatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 批次最大事件数；越大可减少请求次数，但单批内存和处理耗时可能增加。
    max_events: int | None = Field(default=None, strict=True, gt=0, description="单批最大事件数，不是字节数")
    # 批次未满时的最大等待时间，不是 SurrealDB 请求超时。
    timeout_secs: int | None = Field(default=None, strict=True, gt=0, description="不足一批时的等待上限，单位秒")


class GraphRequestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # 单条 Graph Databus 的下游请求并发；不是 Kafka 分区数或 UQ 查询并发。
    concurrency: int | None = Field(default=None, strict=True, gt=0, description="BKBase 下游写请求并发上限")


class GraphSurrealDBWriteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    batch: GraphBatchConfig | None = None
    request: GraphRequestConfig | None = None
    # BKBase 内顶点写入合并窗口；与关系心跳有效期分开控制，单位秒。
    vertex_debounce_secs: int | None = Field(
        default=None,
        alias="vertexDebounceSecs",
        strict=True,
        ge=0,
        description="BKBase 顶点写入合并/节流窗口，单位秒；0 不增加合并等待",
    )
    # fn::upsert_relation 使用的关系有效期和连续段阈值；不是写入合并窗口。
    # 增大后关系失效更晚；本配置不会减少每个不同关系心跳的 UPDATE 次数。
    heartbeat_gap_ms: int | None = Field(
        default=None,
        alias="heartbeatGapMs",
        strict=True,
        gt=0,
        description="SurrealDB 关系心跳有效窗口，单位毫秒；300000 为五分钟",
    )

    def databus_spec(self) -> dict:
        """只返回 Databus 调优字段，保留 BKBase batch 子字段的 snake_case 协议。"""
        spec = self.model_dump(by_alias=True, exclude_none=True, exclude={"heartbeat_gap_ms"})
        return {name: value for name, value in spec.items() if value != {}}

    def binding_spec(self) -> dict:
        """关系函数窗口属于 SurrealDBBinding，不混入 Databus.spec。"""
        if self.heartbeat_gap_ms is None:
            return {}
        return {"heartbeatGapMs": self.heartbeat_gap_ms}

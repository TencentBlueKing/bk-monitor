from prometheus_client import Counter, Histogram

from . import DECLARATIVE_API_REGISTRY

DB_WRITE_TOTAL = Counter(
    name="db_write_total",
    documentation="db 写次数",
    labelnames=("module_name", "model_name"),
    registry=DECLARATIVE_API_REGISTRY,
)

KAFKA_MESSAGES_PRODUCED = Counter(
    name="kafka_messages_produced_total",
    documentation="total number of Kafka messages produced",
    labelnames=("module_name", "topic"),
    registry=DECLARATIVE_API_REGISTRY,
)


KAFKA_MESSAGES_CONSUMED = Counter(
    name="kafka_messages_consumed_total",
    documentation="total number of Kafka messages consumed",
    labelnames=("module_name", "group_id", "topic"),
    registry=DECLARATIVE_API_REGISTRY,
)

CONTROLLER_RECONCILE_COUNT = Counter(
    name="controller_reconcile_total",
    documentation="controller需要协调流程次数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

CONTROLLER_RECONCILE_PREPARE_COUNT = Counter(
    name="controller_reconcile_prepare_total",
    documentation="controller发送后等待协调流程次数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

CONTROLLER_RECONCILE_FINISHED_COUNT = Counter(
    name="controller_reconcile_finished_total",
    documentation="controller完成了协调流程次数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

CONTROLLER_RECONCILE_DURATION = Histogram(
    name="controller_reconcile_duration_seconds",
    documentation="controller协调流程单次耗时",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

DETECTOR_PERCEPTION_COUNT = Counter(
    name="detector_perception_total",
    documentation="DETECTOR感知状态变化计数",
    labelnames=("resource_type",),
    registry=DECLARATIVE_API_REGISTRY,
)

CONTROLLER_PERCEPTION_DURATION = Histogram(
    name="detector_perception_duration_seconds",
    documentation="DETECTOR感知状态变化耗时",
    labelnames=("resource_type",),
    registry=DECLARATIVE_API_REGISTRY,
)

API_SERVER_APPLY_COUNT = Counter(
    name="api_server_apply_total",
    documentation="api server apply触发次数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

API_SERVER_DELETE_COUNT = Counter(
    name="api_server_delete_total",
    documentation="api server delete触发次数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

TASK_ENGINE_SEND_COUNT = Counter(
    name="task_engine_send_total",
    documentation="TaskEngine任务发送数",
    labelnames=("method_name",),
    registry=DECLARATIVE_API_REGISTRY,
)

TASK_ENGINE_EXEC_COUNT = Counter(
    name="task_engine_execute_total",
    documentation="TaskEngine任务执行数",
    labelnames=("method_name",),
    registry=DECLARATIVE_API_REGISTRY,
)

TASK_FAILED_COUNT = Counter(
    name="task_failed_total",
    documentation="采集任务下发失败数",
    labelnames=("resource_type", "operation_type"),
    registry=DECLARATIVE_API_REGISTRY,
)

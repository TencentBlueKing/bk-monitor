"""Doris 分钟区间 SUM 模板。字段取自同一份分组声明，重算覆盖完整分组。"""

from math import lcm

from metadata.service.doris_job_config import quote_identifier


def qualified(ref):
    return ".".join(quote_identifier(ref[key]) for key in ("database", "table"))


def window_date(ms):
    # FE 调度连接的时区可不同于查询连接；按业务日 (UTC+8) 从 epoch 计算。
    return f"TIMESTAMPADD(SECOND, ({ms}) DIV 1000 + 28800, CAST('1970-01-01' AS DATETIME))"


def day_number(ms):
    return f"CAST(DATE_FORMAT({window_date(ms)}, '%Y%m%d') AS INT)"


def render_sum_without(config):
    params = config["params"]
    source, target = config["sources"]["raw"], config["targets"]["aggregate"]
    labels = params["labels"]
    window_ms = int(params["window_minutes"]) * 60000
    lookback_ms = int(params["lookback_minutes"]) * 60000
    projection = []
    for label in labels:
        col = quote_identifier(label)
        value = f"COALESCE({col}, '')"
        if label == "callee_method" and params.get("normalize_callee_method"):
            value = (
                f"CASE WHEN {col} REGEXP '^/idx_schedule/_doc/[^/]+$' THEN '/idx_schedule/_doc/:id' ELSE {value} END"
            )
        projection.append(f"{value} AS {col}")
    group_columns = ", ".join(["window_end", "source_metric", *map(quote_identifier, labels)])
    key_columns = ", ".join(["thedate", "dtEventTimeStamp", "metric_name", *map(quote_identifier, labels)])
    prefix = params["output_prefix"].replace("\\", "\\\\").replace("'", "''")
    columns = ", ".join(["metric_name AS source_metric", *projection, "metric_value"])
    output = ", ".join([f"CONCAT('{prefix}', source_metric)", *map(quote_identifier, labels)])
    sql = f"""INSERT INTO {qualified(target)} ({key_columns}, metric_value, source_sample_count, refreshed_at, dtEventTime)
WITH bounds AS (
    SELECT (UNIX_TIMESTAMP() DIV {window_ms // 1000}) * {window_ms} AS end_ms
), samples AS (
    SELECT ((dtEventTimeStamp - 1) DIV {window_ms} + 1) * {window_ms} AS window_end, {columns}
    FROM {qualified(source)} CROSS JOIN bounds
    WHERE thedate BETWEEN {day_number(f"end_ms - {lookback_ms}")} AND {day_number("end_ms")}
      AND dtEventTimeStamp > end_ms - {lookback_ms} AND dtEventTimeStamp <= end_ms
)
SELECT {day_number("window_end")}, window_end, {output}, SUM(metric_value), COUNT(*), NOW(),
       DATE_FORMAT({window_date("window_end")}, '%Y-%m-%d %H:%i:%s')
FROM samples GROUP BY {group_columns}"""
    return {
        **config,
        "insert_sql": sql,
        "template_inputs": {"sources": config["sources"], "targets": config["targets"], "params": params},
    }


def create_aggregate_table(cursor, table, labels, storage):
    # BKBase 默认的 primary_table 使用 __unique_key__，SQL Job 没有 Databus 代算这个字段。
    # 先建实际分组列组成的主键，再由 Binding 登记已存在的表。
    config = storage.doris_storage_config or {}
    buckets = int(config.get("buckets", 16))
    replicas = config.get("replication_num")
    definitions = ["thedate INT NOT NULL", "dtEventTimeStamp BIGINT NOT NULL", "metric_name VARCHAR(255) NOT NULL"]
    definitions.extend(f"{quote_identifier(col)} VARCHAR(65533) NOT NULL" for col in labels)
    definitions.extend(
        ["metric_value DOUBLE", "source_sample_count BIGINT", "refreshed_at DATETIME", "dtEventTime VARCHAR(32)"]
    )
    keys = ", ".join(map(quote_identifier, ["thedate", "dtEventTimeStamp", "metric_name", *labels]))
    distribution = ", ".join(map(quote_identifier, ["metric_name", *labels]))
    props = {
        "enable_unique_key_merge_on_write": "true",
        "dynamic_partition.enable": "true",
        "dynamic_partition.time_unit": "DAY",
        "dynamic_partition.time_zone": "Asia/Shanghai",
        "dynamic_partition.start": f"-{int(storage.expire_days)}",
        "dynamic_partition.end": "1",
        "dynamic_partition.prefix": "p",
        "dynamic_partition.buckets": buckets,
        "dynamic_partition.create_history_partition": "true",
    }
    if replicas is not None:
        props["replication_num"] = props["dynamic_partition.replication_num"] = int(replicas)
    properties = ", ".join(f'"{k}"="{v}"' for k, v in props.items())
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {quote_identifier(table['database'])}")
    cursor.execute(
        f"CREATE TABLE IF NOT EXISTS {qualified(table)} ({', '.join(definitions)}) ENGINE=OLAP "
        f"UNIQUE KEY ({keys}) PARTITION BY RANGE(thedate) () DISTRIBUTED BY HASH({distribution}) "
        f"BUCKETS {buckets} PROPERTIES ({properties})"
    )


def _completed_windows(cursor, job):
    """成功 INSERT 一定覆盖的窗口结束时间范围 (left, right]。"""
    cursor.execute(
        "SELECT UNIX_TIMESTAMP(StartTime) AS started, UNIX_TIMESTAMP(FinishTime) AS finished "
        'FROM tasks("type"="insert") WHERE JobId=%s AND Status=%s ORDER BY FinishTime DESC LIMIT 1',
        (job.remote_id, "SUCCESS"),
    )
    row = cursor.fetchone()
    if not row or row["started"] is None or row["finished"] is None:
        return None
    params = job.template_inputs["params"]
    window = params["window_minutes"] * 60
    end_min = int(row["started"]) // window * window
    end_max = int(row["finished"]) // window * window
    left = end_max - params["lookback_minutes"] * 60
    return (left, end_min) if left < end_min else None


def successful_cutover(cursor, job, previous_job, prepared_at, *, previous_cursor=None):
    """两侧成功 Task 均已覆盖交接窗口。共同边界 B 的点归旧表，B 之后的点归新表。"""
    current = _completed_windows(cursor, job)
    if current is None or previous_job is None:
        return current[1] if current else None
    previous = _completed_windows(previous_cursor or cursor, previous_job)
    if previous is None:
        return None
    window = job.template_inputs["params"]["window_minutes"] * 60
    common = lcm(previous_job.template_inputs["params"]["window_minutes"] * 60, window)
    boundary = min(previous[1], current[1] - window) // common * common
    if boundary < prepared_at or boundary <= previous[0] or boundary + window <= current[0]:
        return None
    return boundary + 1

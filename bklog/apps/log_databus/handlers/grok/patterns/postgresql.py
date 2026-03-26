"""
PostgreSQL 相关 Grok 模式数据
对应 pygrok patterns/postgresql 文件
"""

PATTERNS = [
    {
        "name": "POSTGRESQL",
        "pattern": r"%{DATESTAMP:timestamp} %{TZ} %{DATA:user_id} %{GREEDYDATA:connection_id} %{POSINT:pid}",
        "sample": "03/15/2024-14:30:59 UTC postgres 10.0.0.1(54321) 12345",
        "description": "匹配 PostgreSQL pg_log 默认日志格式，包含时间戳、时区、用户、连接和进程 ID",
    },
]

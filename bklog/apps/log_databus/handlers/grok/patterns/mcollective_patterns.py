"""
MCollective 编排工具扩展模式数据
对应 pygrok patterns/mcollective-patterns 文件

注意：MCOLLECTIVEAUDIT 在此文件和 mcollective 文件中都有定义，
pygrok 会使用最后加载的版本。这里保留两个文件各自的定义。
"""

PATTERNS = [
    {
        "name": "MCOLLECTIVE",
        "pattern": r"., \[%{TIMESTAMP_ISO8601:timestamp} #%{POSINT:pid}\]%{SPACE}%{LOGLEVEL:event_level}",
        "sample": "I, [2024-03-15T14:30:59.123456 #12345]  INFO",
        "description": "匹配 MCollective 日志行，包含时间戳、进程 ID 和日志级别",
    },
]

"""
Ruby 相关 Grok 模式数据
对应 pygrok patterns/ruby 文件
"""

PATTERNS = [
    {
        "name": "RUBY_LOGLEVEL",
        "pattern": r"(?:DEBUG|FATAL|ERROR|WARN|INFO)",
        "sample": "ERROR",
        "description": "匹配 Ruby 日志级别（DEBUG、FATAL、ERROR、WARN、INFO）",
    },
    {
        "name": "RUBY_LOGGER",
        "pattern": r"[DFEWI], \[%{TIMESTAMP_ISO8601:timestamp} #%{POSINT:pid}\] *%{RUBY_LOGLEVEL:loglevel} -- +%{DATA:progname}: %{GREEDYDATA:message}",
        "sample": "E, [2024-03-15T14:30:59.123456 #12345] ERROR -- myapp: Something went wrong",
        "description": "匹配 Ruby Logger 标准日志格式，包含级别缩写、时间戳、进程 ID、级别、程序名和消息",
    },
]

"""
Redis 相关 Grok 模式数据
对应 pygrok patterns/redis 文件
"""

PATTERNS = [
    {
        "name": "REDISTIMESTAMP",
        "pattern": r"%{MONTHDAY} %{MONTH} %{TIME}",
        "sample": "15 Mar 14:30:59",
        "description": "匹配 Redis 日志时间戳格式（日 月 时:分:秒）",
    },
    {
        "name": "REDISLOG",
        "pattern": r"\[%{POSINT:pid}\] %{REDISTIMESTAMP:timestamp} \* ",
        "sample": "[12345] 15 Mar 14:30:59 * ",
        "description": "匹配 Redis 日志行前缀，包含进程 ID 和时间戳",
    },
]

"""
MCollective 编排工具相关 Grok 模式数据
对应 pygrok patterns/mcollective 文件
"""

PATTERNS = [
    {
        "name": "MCOLLECTIVEAUDIT",
        "pattern": r"%{TIMESTAMP_ISO8601:timestamp}:",
        "sample": "2024-03-15T14:30:59+08:00:",
        "description": "匹配 MCollective 审计日志时间戳",
    },
]

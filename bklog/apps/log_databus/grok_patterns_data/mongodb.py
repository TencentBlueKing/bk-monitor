"""
MongoDB 相关 Grok 模式数据
对应 pygrok patterns/mongodb 文件
"""

PATTERNS = [
    {
        "name": "MONGO_LOG",
        "pattern": r"%{SYSLOGTIMESTAMP:timestamp} \[%{WORD:component}\] %{GREEDYDATA:message}",
        "sample": "Mar 15 14:30:59 [conn12345] end connection 192.168.1.1:54321 (3 connections now open)",
        "description": "匹配 MongoDB 2.x 版本日志格式",
    },
    {
        "name": "MONGO_QUERY",
        "pattern": r"\{ (?<={ ).*(?= } ntoreturn:) \}",
        "sample": '{ find: "users", filter: { name: "admin" } }',
        "description": "匹配 MongoDB 查询语句",
    },
    {
        "name": "MONGO_SLOWQUERY",
        "pattern": r"%{WORD} %{MONGO_WORDDASH:database}\.%{MONGO_WORDDASH:collection} %{WORD}: %{MONGO_QUERY:query} %{WORD}:%{NONNEGINT:ntoreturn} %{WORD}:%{NONNEGINT:ntoskip} %{WORD}:%{NONNEGINT:nscanned}.*nreturned:%{NONNEGINT:nreturned}..+ (?<duration>[0-9]+)ms",
        "sample": 'query mydb.users query: { find: "users", filter: { name: "admin" } } ntoreturn:0 ntoskip:0 nscanned:1000 nreturned:1 reslen:200 500ms',
        "description": "匹配 MongoDB 慢查询日志，包含数据库、集合、查询内容和耗时",
    },
    {
        "name": "MONGO_WORDDASH",
        "pattern": r"\b[\w-]+\b",
        "sample": "my-database",
        "description": "匹配 MongoDB 中包含连字符的标识符（如数据库名、集合名）",
    },
    {
        "name": "MONGO3_SEVERITY",
        "pattern": r"\w",
        "sample": "I",
        "description": "匹配 MongoDB 3.x 日志严重级别（F-致命、E-错误、W-警告、I-信息、D-调试）",
    },
    {
        "name": "MONGO3_COMPONENT",
        "pattern": r"%{WORD}|-",
        "sample": "NETWORK",
        "description": "匹配 MongoDB 3.x 日志组件名称",
    },
    {
        "name": "MONGO3_LOG",
        "pattern": r"%{TIMESTAMP_ISO8601:timestamp} %{MONGO3_SEVERITY:severity} %{MONGO3_COMPONENT:component}%{SPACE}(?:\[%{DATA:context}\])? %{GREEDYDATA:message}",
        "sample": "2024-03-15T14:30:59.123+0800 I NETWORK  [conn12345] end connection 192.168.1.1:54321 (3 connections now open)",
        "description": "匹配 MongoDB 3.x 版本日志格式",
    },
]

"""
Ruby on Rails 应用相关 Grok 模式数据
对应 pygrok patterns/rails 文件
"""

PATTERNS = [
    {
        "name": "RUUID",
        "pattern": r"\h{32}",
        "sample": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
        "description": "匹配 Rails UUID（32 位十六进制字符）",
    },
    {
        "name": "RCONTROLLER",
        "pattern": r"(?<controller>[^#]+)#(?<action>\w+)",
        "sample": "UsersController#show",
        "description": "匹配 Rails 控制器和动作（如 UsersController#show）",
    },
    {
        "name": "RAILS3HEAD",
        "pattern": r'(?m)Started %{WORD:verb} "%{URIPATHPARAM:request}" for %{IPORHOST:clientip} at (?<timestamp>%{YEAR}-%{MONTHNUM}-%{MONTHDAY} %{HOUR}:%{MINUTE}:%{SECOND} %{ISO8601_TIMEZONE})',
        "sample": 'Started GET "/api/v1/users" for 192.168.1.1 at 2024-03-15 14:30:59 +0800',
        "description": "匹配 Rails 3 请求开始日志行",
    },
    {
        "name": "RPROCESSING",
        "pattern": r"\W*Processing by %{RCONTROLLER} as (?<format>\S+)(?:\W*Parameters: {%{DATA:params}}\W*)?",
        "sample": "  Processing by UsersController#show as JSON",
        "description": "匹配 Rails 请求处理日志，包含控制器、动作和格式信息",
    },
    {
        "name": "RAILS3FOOT",
        "pattern": r"Completed %{NUMBER:response}%{DATA} in %{NUMBER:totalms}ms %{RAILS3PROFILE}%{GREEDYDATA}",
        "sample": "Completed 200 OK in 150ms (Views: 50ms | ActiveRecord: 30ms)",
        "description": "匹配 Rails 3 请求完成日志行，包含响应码和耗时",
    },
    {
        "name": "RAILS3PROFILE",
        "pattern": r"(?:\(Views: %{NUMBER:viewms}ms \| ActiveRecord: %{NUMBER:activerecordms}ms|\(ActiveRecord: %{NUMBER:activerecordms}ms)?",
        "sample": "(Views: 50ms | ActiveRecord: 30ms",
        "description": "匹配 Rails 3 性能分析信息（视图渲染时间和 ActiveRecord 查询时间）",
    },
    {
        "name": "RAILS3",
        "pattern": r"%{RAILS3HEAD}(?:%{RPROCESSING})?(?<context>(?:%{DATA}\n)*)(?:%{RAILS3FOOT})?",
        "sample": 'Started GET "/api/v1/users" for 192.168.1.1 at 2024-03-15 14:30:59 +0800\n  Processing by UsersController#show as JSON\nCompleted 200 OK in 150ms (Views: 50ms | ActiveRecord: 30ms)',
        "description": "匹配 Rails 3 完整请求日志（多行），包含请求头、处理信息和完成信息",
    },
]

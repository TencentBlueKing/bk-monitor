"""
AWS 相关 Grok 模式数据
对应 pygrok patterns/aws 文件
"""

PATTERNS = [
    {
        "name": "S3_REQUEST_LINE",
        "pattern": r"(?:%{WORD:verb} %{NOTSPACE:request}(?: HTTP/%{NUMBER:httpversion})?|%{DATA:rawrequest})",
        "sample": "GET /mybucket/mykey HTTP/1.1",
        "description": "匹配 S3 请求行，包含 HTTP 方法、请求路径和协议版本",
    },
    {
        "name": "S3_ACCESS_LOG",
        "pattern": r'%{WORD:owner} %{NOTSPACE:bucket} \[%{HTTPDATE:timestamp}\] %{IP:clientip} %{NOTSPACE:requester} %{NOTSPACE:request_id} %{NOTSPACE:operation} %{NOTSPACE:key} (?:"%{S3_REQUEST_LINE}"|-) (?:%{INT:response:int}|-) (?:-|%{NOTSPACE:error_code}) (?:%{INT:bytes:int}|-) (?:%{INT:object_size:int}|-) (?:%{INT:request_time_ms:int}|-) (?:%{INT:turnaround_time_ms:int}|-) (?:%{QS:referrer}|-) (?:"?%{QS:agent}"?|-) (?:-|%{NOTSPACE:version_id})',
        "sample": 'mybucket-owner mybucket [15/Mar/2024:14:30:59 +0800] 192.168.1.1 arn:aws:iam::123456789:user/testuser ABC123DEF456 REST.GET.OBJECT mykey "GET /mybucket/mykey HTTP/1.1" 200 - 1234 1234 50 40 "https://example.com" "curl/7.68.0" -',
        "description": "匹配 AWS S3 访问日志的完整格式",
    },
    {
        "name": "ELB_URIPATHPARAM",
        "pattern": r"%{URIPATH:path}(?:%{URIPARAM:params})?",
        "sample": "/api/v1/users?page=1&size=10",
        "description": "匹配 ELB 日志中的 URI 路径和参数部分",
    },
    {
        "name": "ELB_URI",
        "pattern": r"%{URIPROTO:proto}://(?:%{USER}(?::[^@]*)?@)?(?:%{URIHOST:urihost})?(?:%{ELB_URIPATHPARAM})?",
        "sample": "https://www.example.com:443/api/v1/users?page=1",
        "description": "匹配 ELB 日志中的完整 URI",
    },
    {
        "name": "ELB_REQUEST_LINE",
        "pattern": r"(?:%{WORD:verb} %{ELB_URI:request}(?: HTTP/%{NUMBER:httpversion})?|%{DATA:rawrequest})",
        "sample": "GET https://www.example.com:443/api/v1/users HTTP/1.1",
        "description": "匹配 ELB 日志中的 HTTP 请求行",
    },
    {
        "name": "ELB_ACCESS_LOG",
        "pattern": r'%{TIMESTAMP_ISO8601:timestamp} %{NOTSPACE:elb} %{IP:clientip}:%{INT:clientport:int} (?:(%{IP:backendip}:?:%{INT:backendport:int})|-) %{NUMBER:request_processing_time:float} %{NUMBER:backend_processing_time:float} %{NUMBER:response_processing_time:float} %{INT:response:int} %{INT:backend_response:int} %{INT:received_bytes:int} %{INT:bytes:int} "%{ELB_REQUEST_LINE}"',
        "sample": '2024-03-15T14:30:59.123456Z my-elb 192.168.1.1:54321 10.0.0.1:80 0.000086 0.001048 0.000057 200 200 0 1234 "GET https://www.example.com:443/api/v1/users HTTP/1.1"',
        "description": "匹配 AWS ELB（弹性负载均衡）访问日志的完整格式",
    },
]

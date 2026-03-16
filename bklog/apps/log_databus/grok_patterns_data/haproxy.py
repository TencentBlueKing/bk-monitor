"""
HAProxy 负载均衡器相关 Grok 模式数据
对应 pygrok patterns/haproxy 文件
"""

PATTERNS = [
    {
        "name": "HAPROXYTIME",
        "pattern": r"(?!<[0-9])%{HOUR:haproxy_hour}:%{MINUTE:haproxy_minute}(?::%{SECOND:haproxy_second})(?![0-9])",
        "sample": "14:30:59",
        "description": "匹配 HAProxy 日志时间格式（时:分:秒）",
    },
    {
        "name": "HAPROXYDATE",
        "pattern": r"%{MONTHDAY:haproxy_monthday}/%{MONTH:haproxy_month}/%{YEAR:haproxy_year}:%{HAPROXYTIME:haproxy_time}.%{INT:haproxy_milliseconds}",
        "sample": "15/Mar/2024:14:30:59.123",
        "description": "匹配 HAProxy 日志日期格式（日/月/年:时:分:秒.毫秒）",
    },
    {
        "name": "HAPROXYCAPTUREDREQUESTHEADERS",
        "pattern": r"%{DATA:captured_request_headers}",
        "sample": "www.example.com|Mozilla/5.0",
        "description": "匹配 HAProxy 捕获的请求头信息",
    },
    {
        "name": "HAPROXYCAPTUREDRESPONSEHEADERS",
        "pattern": r"%{DATA:captured_response_headers}",
        "sample": "text/html|gzip",
        "description": "匹配 HAProxy 捕获的响应头信息",
    },
    {
        "name": "HAPROXYHTTPBASE",
        "pattern": r'%{IP:client_ip}:%{INT:client_port} \[%{HAPROXYDATE:accept_date}\] %{NOTSPACE:frontend_name} %{NOTSPACE:backend_name}/%{NOTSPACE:server_name} %{INT:time_request}/%{INT:time_queue}/%{INT:time_backend_connect}/%{INT:time_backend_response}/%{NOTSPACE:time_duration} %{INT:http_status_code} %{NOTSPACE:bytes_read} %{DATA:captured_request_cookie} %{DATA:captured_response_cookie} %{NOTSPACE:termination_state} %{INT:actconn}/%{INT:feconn}/%{INT:beconn}/%{INT:srvconn}/%{NOTSPACE:retries} %{INT:srv_queue}/%{INT:backend_queue} (\{%{HAPROXYCAPTUREDREQUESTHEADERS}\})?( )?(\{%{HAPROXYCAPTUREDRESPONSEHEADERS}\})?( )?"(<BADREQ>|(%{WORD:http_verb} (%{URIPROTO:http_proto}://)?(?:%{USER:http_user}(?::[^@]*)?@)?(?:%{URIHOST:http_host})?(?:%{URIPATHPARAM:http_request})?( HTTP/%{NUMBER:http_version})?))?"',
        "sample": '192.168.1.1:54321 [15/Mar/2024:14:30:59.123] frontend-http backend-app/server1 10/0/30/100/140 200 1234 - - ---- 100/50/30/20/0 0/0 "GET /api/v1/users HTTP/1.1"',
        "description": "匹配 HAProxy HTTP 日志的基础格式（不含 syslog 头部）",
    },
    {
        "name": "HAPROXYHTTP",
        "pattern": r"(?:%{SYSLOGTIMESTAMP:syslog_timestamp}|%{TIMESTAMP_ISO8601:timestamp8601}) %{IPORHOST:syslog_server} %{SYSLOGPROG}: %{HAPROXYHTTPBASE}",
        "sample": 'Mar 15 14:30:59 lb01 haproxy[12345]: 192.168.1.1:54321 [15/Mar/2024:14:30:59.123] frontend-http backend-app/server1 10/0/30/100/140 200 1234 - - ---- 100/50/30/20/0 0/0 "GET /api/v1/users HTTP/1.1"',
        "description": "匹配 HAProxy HTTP 日志的完整格式（含 syslog 头部）",
    },
    {
        "name": "HAPROXYTCP",
        "pattern": r"(?:%{SYSLOGTIMESTAMP:syslog_timestamp}|%{TIMESTAMP_ISO8601:timestamp8601}) %{IPORHOST:syslog_server} %{SYSLOGPROG}: %{IP:client_ip}:%{INT:client_port} \[%{HAPROXYDATE:accept_date}\] %{NOTSPACE:frontend_name} %{NOTSPACE:backend_name}/%{NOTSPACE:server_name} %{INT:time_queue}/%{INT:time_backend_connect}/%{NOTSPACE:time_duration} %{NOTSPACE:bytes_read} %{NOTSPACE:termination_state} %{INT:actconn}/%{INT:feconn}/%{INT:beconn}/%{INT:srvconn}/%{NOTSPACE:retries} %{INT:srv_queue}/%{INT:backend_queue}",
        "sample": "Mar 15 14:30:59 lb01 haproxy[12345]: 192.168.1.1:54321 [15/Mar/2024:14:30:59.123] frontend-tcp backend-db/db-server1 0/30/60000 1234 -- 100/50/30/20/0 0/0",
        "description": "匹配 HAProxy TCP 日志的完整格式",
    },
]

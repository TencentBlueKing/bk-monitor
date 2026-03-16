"""
Juniper 网络设备相关 Grok 模式数据
对应 pygrok patterns/junos 文件
"""

PATTERNS = [
    {
        "name": "RT_FLOW_EVENT",
        "pattern": r"(RT_FLOW_SESSION_CREATE|RT_FLOW_SESSION_CLOSE|RT_FLOW_SESSION_DENY)",
        "sample": "RT_FLOW_SESSION_CREATE",
        "description": "匹配 Juniper RT_FLOW 事件类型（会话创建、关闭或拒绝）",
    },
    {
        "name": "RT_FLOW1",
        "pattern": r"%{RT_FLOW_EVENT:event}: %{GREEDYDATA:close-reason}: %{IP:src-ip}/%{INT:src-port}->%{IP:dst-ip}/%{INT:dst-port} %{DATA:service} %{IP:nat-src-ip}/%{INT:nat-src-port}->%{IP:nat-dst-ip}/%{INT:nat-dst-port} %{DATA:src-nat-rule-name} %{DATA:dst-nat-rule-name} %{INT:protocol-id} %{DATA:policy-name} %{DATA:from-zone} %{DATA:to-zone} %{INT:session-id} \d+\(%{DATA:sent}\) \d+\(%{DATA:received}\) %{INT:elapsed-time} .*",
        "sample": "RT_FLOW_SESSION_CLOSE: TCP RST: 10.0.0.1/54321->192.168.1.1/80 http 10.0.0.1/54321->192.168.1.1/80 src-nat-rule dst-nat-rule 6 default-policy trust untrust 12345 10(1234) 20(5678) 60 ",
        "description": "匹配 Juniper RT_FLOW 会话关闭日志（含关闭原因、流量统计）",
    },
    {
        "name": "RT_FLOW2",
        "pattern": r"%{RT_FLOW_EVENT:event}: session created %{IP:src-ip}/%{INT:src-port}->%{IP:dst-ip}/%{INT:dst-port} %{DATA:service} %{IP:nat-src-ip}/%{INT:nat-src-port}->%{IP:nat-dst-ip}/%{INT:nat-dst-port} %{DATA:src-nat-rule-name} %{DATA:dst-nat-rule-name} %{INT:protocol-id} %{DATA:policy-name} %{DATA:from-zone} %{DATA:to-zone} %{INT:session-id} .*",
        "sample": "RT_FLOW_SESSION_CREATE: session created 10.0.0.1/54321->192.168.1.1/80 http 10.0.0.1/54321->192.168.1.1/80 src-nat-rule dst-nat-rule 6 default-policy trust untrust 12345 ",
        "description": "匹配 Juniper RT_FLOW 会话创建日志",
    },
    {
        "name": "RT_FLOW3",
        "pattern": r"%{RT_FLOW_EVENT:event}: session denied %{IP:src-ip}/%{INT:src-port}->%{IP:dst-ip}/%{INT:dst-port} %{DATA:service} %{INT:protocol-id}\(\d\) %{DATA:policy-name} %{DATA:from-zone} %{DATA:to-zone} .*",
        "sample": "RT_FLOW_SESSION_DENY: session denied 10.0.0.1/54321->192.168.1.1/80 http 6(0) deny-policy trust untrust ",
        "description": "匹配 Juniper RT_FLOW 会话拒绝日志",
    },
]

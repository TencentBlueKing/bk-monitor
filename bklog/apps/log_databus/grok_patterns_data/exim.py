"""
Exim 邮件传输代理相关 Grok 模式数据
对应 pygrok patterns/exim 文件
"""

PATTERNS = [
    {
        "name": "EXIM_MSGID",
        "pattern": r"[0-9A-Za-z]{6}-[0-9A-Za-z]{6}-[0-9A-Za-z]{2}",
        "sample": "1a2B3c-4d5E6f-Gh",
        "description": "匹配 Exim 邮件消息ID",
    },
    {
        "name": "EXIM_FLAGS",
        "pattern": r"(<=|[-=>*]>|[*]{2}|==)",
        "sample": "<=",
        "description": "匹配 Exim 日志标志（<=接收、=>投递、->路由、*>扩展、**失败、==延迟）",
    },
    {
        "name": "EXIM_DATE",
        "pattern": r"%{YEAR:exim_year}-%{MONTHNUM:exim_month}-%{MONTHDAY:exim_day} %{TIME:exim_time}",
        "sample": "2024-03-15 14:30:59",
        "description": "匹配 Exim 日志日期格式（年-月-日 时:分:秒）",
    },
    {
        "name": "EXIM_PID",
        "pattern": r"\[%{POSINT}\]",
        "sample": "[12345]",
        "description": "匹配 Exim 进程ID",
    },
    {
        "name": "EXIM_QT",
        "pattern": r"((\d+y)?(\d+w)?(\d+d)?(\d+h)?(\d+m)?(\d+s)?)",
        "sample": "1h30m5s",
        "description": "匹配 Exim 队列时间格式（如 1h30m5s）",
    },
    {
        "name": "EXIM_EXCLUDE_TERMS",
        "pattern": r"(Message is frozen|(Start|End) queue run| Warning: | retry time not reached | no (IP address|host name) found for (IP address|host) | unexpected disconnection while reading SMTP command | no immediate delivery: |another process is handling this message)",
        "sample": "Message is frozen",
        "description": "匹配 Exim 排除过滤的特定日志术语",
    },
    {
        "name": "EXIM_REMOTE_HOST",
        "pattern": r"(H=(%{NOTSPACE:remote_hostname} )?(\(%{NOTSPACE:remote_heloname}\) )?\[%{IP:remote_host}\])",
        "sample": "H=mail.example.com (mail.example.com) [192.168.1.1]",
        "description": "匹配 Exim 远程主机信息，包含主机名、HELO 名称和 IP 地址",
    },
    {
        "name": "EXIM_INTERFACE",
        "pattern": r"(I=\[%{IP:exim_interface}\](:%{NUMBER:exim_interface_port}))",
        "sample": "I=[10.0.0.1]:25",
        "description": "匹配 Exim 网络接口信息，包含 IP 和端口",
    },
    {
        "name": "EXIM_PROTOCOL",
        "pattern": r"(P=%{NOTSPACE:protocol})",
        "sample": "P=esmtp",
        "description": "匹配 Exim 使用的协议（如 esmtp、smtp、local）",
    },
    {
        "name": "EXIM_MSG_SIZE",
        "pattern": r"(S=%{NUMBER:exim_msg_size})",
        "sample": "S=1234",
        "description": "匹配 Exim 邮件消息大小（字节）",
    },
    {
        "name": "EXIM_HEADER_ID",
        "pattern": r"(id=%{NOTSPACE:exim_header_id})",
        "sample": "id=abc123@example.com",
        "description": "匹配 Exim 邮件头部消息 ID",
    },
    {
        "name": "EXIM_SUBJECT",
        "pattern": r"(T=%{QS:exim_subject})",
        "sample": 'T="Hello World"',
        "description": "匹配 Exim 邮件主题",
    },
]

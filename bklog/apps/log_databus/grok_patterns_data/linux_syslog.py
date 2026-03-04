"""
Linux Syslog 相关 Grok 模式数据
对应 pygrok patterns/linux-syslog 文件
"""

PATTERNS = [
    {
        "name": "SYSLOG5424PRINTASCII",
        "pattern": r"[!-~]+",
        "sample": "myapp",
        "description": "匹配 RFC5424 中的可打印 ASCII 字符串",
    },
    {
        "name": "SYSLOGBASE2",
        "pattern": r"(?:%{SYSLOGTIMESTAMP:timestamp}|%{TIMESTAMP_ISO8601:timestamp8601}) (?:%{SYSLOGFACILITY} )?%{SYSLOGHOST:logsource}+(?: %{SYSLOGPROG}:|)",
        "sample": "Mar 15 14:30:59 myhost.example.com sshd[12345]:",
        "description": "匹配 Syslog 日志的基础前缀（扩展版，支持 ISO8601 时间戳）",
    },
    {
        "name": "SYSLOGPAMSESSION",
        "pattern": r"%{SYSLOGBASE} (?=%{GREEDYDATA:message})%{WORD:pam_module}\(%{DATA:pam_caller}\): session %{WORD:pam_session_state} for user %{USERNAME:username}(?: by %{GREEDYDATA:pam_by})?",
        "sample": "Mar 15 14:30:59 myhost.example.com sshd[12345]: pam_unix(sshd:session): session opened for user admin by (uid=0)",
        "description": "匹配 PAM 会话相关的 Syslog 日志（登录/注销事件）",
    },
    {
        "name": "CRON_ACTION",
        "pattern": r"[A-Z ]+",
        "sample": "CMD",
        "description": "匹配 Cron 操作类型（如 CMD、RELOAD）",
    },
    {
        "name": "CRONLOG",
        "pattern": r"%{SYSLOGBASE} \(%{USER:user}\) %{CRON_ACTION:action} \(%{DATA:message}\)",
        "sample": "Mar 15 14:30:59 myhost.example.com CRON[12345]: (root) CMD (/usr/bin/cleanup.sh)",
        "description": "匹配 Cron 定时任务的 Syslog 日志",
    },
    {
        "name": "SYSLOGLINE",
        "pattern": r"%{SYSLOGBASE2} %{GREEDYDATA:message}",
        "sample": "Mar 15 14:30:59 myhost.example.com sshd[12345]: Accepted publickey for admin from 192.168.1.1 port 54321 ssh2",
        "description": "匹配完整的 Syslog 日志行",
    },
    {
        "name": "SYSLOG5424PRI",
        "pattern": r"<%{NONNEGINT:syslog5424_pri}>",
        "sample": "<34>",
        "description": "匹配 RFC5424 Syslog 优先级标识",
    },
    {
        "name": "SYSLOG5424SD",
        "pattern": r"\[%{DATA}\]+",
        "sample": '[exampleSDID@32473 iut="3" eventSource="Application"]',
        "description": "匹配 RFC5424 结构化数据部分",
    },
    {
        "name": "SYSLOG5424BASE",
        "pattern": r"%{SYSLOG5424PRI}%{NONNEGINT:syslog5424_ver} +(?:%{TIMESTAMP_ISO8601:syslog5424_ts}|-) +(?:%{HOSTNAME:syslog5424_host}|-) +(-|%{SYSLOG5424PRINTASCII:syslog5424_app}) +(-|%{SYSLOG5424PRINTASCII:syslog5424_proc}) +(-|%{SYSLOG5424PRINTASCII:syslog5424_msgid}) +(?:%{SYSLOG5424SD:syslog5424_sd}|-|)",
        "sample": '<34>1 2024-03-15T14:30:59.123Z myhost.example.com myapp 12345 ID47 [exampleSDID@32473 iut="3"]',
        "description": "匹配 RFC5424 Syslog 日志的基础部分（优先级、版本、时间戳、主机名、应用、进程ID、消息ID、结构化数据）",
    },
    {
        "name": "SYSLOG5424LINE",
        "pattern": r"%{SYSLOG5424BASE} +%{GREEDYDATA:syslog5424_msg}",
        "sample": '<34>1 2024-03-15T14:30:59.123Z myhost.example.com myapp 12345 ID47 [exampleSDID@32473 iut="3"] This is a syslog message',
        "description": "匹配 RFC5424 Syslog 完整日志行",
    },
]

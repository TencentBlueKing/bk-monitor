"""
防火墙相关 Grok 模式数据
对应 pygrok patterns/firewalls 文件
包含 NetScreen、Cisco ASA 和 Shorewall 防火墙日志模式
"""

PATTERNS = [
    # NetScreen 防火墙
    {
        "name": "NETSCREENSESSIONLOG",
        "pattern": r"%{SYSLOGTIMESTAMP:date} %{IPORHOST:device} %{IPORHOST}: NetScreen device_id=%{WORD:device_id}%{DATA}: start_time=%{QUOTEDSTRING:start_time} duration=%{INT:duration} policy_id=%{INT:policy_id} service=%{DATA:service} proto=%{INT:proto} src zone=%{WORD:src_zone} dst zone=%{WORD:dst_zone} action=%{WORD:action} sent=%{INT:sent} rcvd=%{INT:rcvd} src=%{IPORHOST:src_ip} dst=%{IPORHOST:dst_ip} src_port=%{INT:src_port} dst_port=%{INT:dst_port} src-xlated ip=%{IPORHOST:src_xlated_ip} port=%{INT:src_xlated_port} dst-xlated ip=%{IPORHOST:dst_xlated_ip} port=%{INT:dst_xlated_port} session_id=%{INT:session_id} reason=%{GREEDYDATA:reason}",
        "sample": 'Mar 15 14:30:59 10.0.0.1 10.0.0.1: NetScreen device_id=netscreen1 [Root]system-notification-00257(traffic): start_time="2024-03-15 14:30:00" duration=60 policy_id=100 service=http/tcp proto=6 src zone=Trust dst zone=Untrust action=Permit sent=1234 rcvd=5678 src=10.0.0.1 dst=192.168.1.1 src_port=54321 dst_port=80 src-xlated ip=10.0.0.100 port=54321 dst-xlated ip=192.168.1.1 port=80 session_id=12345 reason=Close - TCP FIN',
        "description": "匹配 NetScreen 防火墙会话日志的完整格式",
    },
    # Cisco ASA 通用
    {
        "name": "CISCO_TAGGED_SYSLOG",
        "pattern": r"^<%{POSINT:syslog_pri}>%{CISCOTIMESTAMP:timestamp}( %{SYSLOGHOST:sysloghost})? ?: %%{CISCOTAG:ciscotag}:",
        "sample": "<166>Mar 15 14:30:59 fw01 : %ASA-6-302013:",
        "description": "匹配 Cisco 标记的 Syslog 消息头部",
    },
    {
        "name": "CISCOTIMESTAMP",
        "pattern": r"%{MONTH} +%{MONTHDAY}(?: %{YEAR})? %{TIME}",
        "sample": "Mar 15 2024 14:30:59",
        "description": "匹配 Cisco 设备日志时间戳",
    },
    {
        "name": "CISCOTAG",
        "pattern": r"[A-Z0-9]+-%{INT}-(?:[A-Z0-9_]+)",
        "sample": "ASA-6-302013",
        "description": "匹配 Cisco 日志标签（设备-级别-消息ID）",
    },
    {
        "name": "CISCO_ACTION",
        "pattern": r"Built|Teardown|Deny|Denied|denied|requested|permitted|denied by ACL|discarded|est-allowed|Dropping|created|deleted",
        "sample": "Built",
        "description": "匹配 Cisco ASA 防火墙动作类型",
    },
    {
        "name": "CISCO_REASON",
        "pattern": r"Duplicate TCP SYN|Failed to locate egress interface|Invalid transport field|No matching connection|DNS Response|DNS Query|(?:%{WORD}\s*)*",
        "sample": "Duplicate TCP SYN",
        "description": "匹配 Cisco ASA 防火墙事件原因",
    },
    {
        "name": "CISCO_DIRECTION",
        "pattern": r"Inbound|inbound|Outbound|outbound",
        "sample": "Inbound",
        "description": "匹配 Cisco ASA 流量方向（入站或出站）",
    },
    {
        "name": "CISCO_INTERVAL",
        "pattern": r"first hit|%{INT}-second interval",
        "sample": "300-second interval",
        "description": "匹配 Cisco ASA 日志间隔（首次命中或秒间隔）",
    },
    {
        "name": "CISCO_XLATE_TYPE",
        "pattern": r"static|dynamic",
        "sample": "dynamic",
        "description": "匹配 Cisco ASA 地址转换类型（静态或动态）",
    },
    # Cisco ASA 特定消息
    {
        "name": "CISCOFW104001",
        "pattern": r"\((?:Primary|Secondary)\) Switching to ACTIVE - %{GREEDYDATA:switch_reason}",
        "sample": "(Primary) Switching to ACTIVE - Loss of communication with mate",
        "description": "匹配 Cisco ASA-1-104001：切换到活动状态",
    },
    {
        "name": "CISCOFW104002",
        "pattern": r"\((?:Primary|Secondary)\) Switching to STANDBY - %{GREEDYDATA:switch_reason}",
        "sample": "(Secondary) Switching to STANDBY - Detected Active mate",
        "description": "匹配 Cisco ASA-1-104002：切换到备用状态",
    },
    {
        "name": "CISCOFW104003",
        "pattern": r"\((?:Primary|Secondary)\) Switching to FAILED\.",
        "sample": "(Primary) Switching to FAILED.",
        "description": "匹配 Cisco ASA-1-104003：切换到故障状态",
    },
    {
        "name": "CISCOFW104004",
        "pattern": r"\((?:Primary|Secondary)\) Switching to OK\.",
        "sample": "(Primary) Switching to OK.",
        "description": "匹配 Cisco ASA-1-104004：切换到正常状态",
    },
    {
        "name": "CISCOFW105003",
        "pattern": r"\((?:Primary|Secondary)\) Monitoring on [Ii]nterface %{GREEDYDATA:interface_name} waiting",
        "sample": "(Primary) Monitoring on Interface outside waiting",
        "description": "匹配 Cisco ASA-1-105003：接口监控等待中",
    },
    {
        "name": "CISCOFW105004",
        "pattern": r"\((?:Primary|Secondary)\) Monitoring on [Ii]nterface %{GREEDYDATA:interface_name} normal",
        "sample": "(Primary) Monitoring on Interface outside normal",
        "description": "匹配 Cisco ASA-1-105004：接口监控正常",
    },
    {
        "name": "CISCOFW105005",
        "pattern": r"\((?:Primary|Secondary)\) Lost Failover communications with mate on [Ii]nterface %{GREEDYDATA:interface_name}",
        "sample": "(Primary) Lost Failover communications with mate on Interface outside",
        "description": "匹配 Cisco ASA-1-105005：失去与对端的故障转移通信",
    },
    {
        "name": "CISCOFW105008",
        "pattern": r"\((?:Primary|Secondary)\) Testing [Ii]nterface %{GREEDYDATA:interface_name}",
        "sample": "(Primary) Testing Interface outside",
        "description": "匹配 Cisco ASA-1-105008：正在测试接口",
    },
    {
        "name": "CISCOFW105009",
        "pattern": r"\((?:Primary|Secondary)\) Testing on [Ii]nterface %{GREEDYDATA:interface_name} (?:Passed|Failed)",
        "sample": "(Primary) Testing on Interface outside Passed",
        "description": "匹配 Cisco ASA-1-105009：接口测试通过或失败",
    },
    {
        "name": "CISCOFW106001",
        "pattern": r"%{CISCO_DIRECTION:direction} %{WORD:protocol} connection %{CISCO_ACTION:action} from %{IP:src_ip}/%{INT:src_port} to %{IP:dst_ip}/%{INT:dst_port} flags %{GREEDYDATA:tcp_flags} on interface %{GREEDYDATA:interface}",
        "sample": "Inbound TCP connection Built from 192.168.1.1/54321 to 10.0.0.1/80 flags SYN on interface outside",
        "description": "匹配 Cisco ASA-2-106001：入站/出站连接建立或拒绝",
    },
    {
        "name": "CISCOFW106006_106007_106010",
        "pattern": r"%{CISCO_ACTION:action} %{CISCO_DIRECTION:direction} %{WORD:protocol} (?:from|src) %{IP:src_ip}/%{INT:src_port}(\(%{DATA:src_fwuser}\))? (?:to|dst) %{IP:dst_ip}/%{INT:dst_port}(\(%{DATA:dst_fwuser}\))? (?:on interface %{DATA:interface}|due to %{CISCO_REASON:reason})",
        "sample": "Deny Inbound TCP from 192.168.1.1/54321 to 10.0.0.1/80 on interface outside",
        "description": "匹配 Cisco ASA-2-106006/106007/106010：拒绝入站/出站连接",
    },
    {
        "name": "CISCOFW106014",
        "pattern": r"%{CISCO_ACTION:action} %{CISCO_DIRECTION:direction} %{WORD:protocol} src %{DATA:src_interface}:%{IP:src_ip}(\(%{DATA:src_fwuser}\))? dst %{DATA:dst_interface}:%{IP:dst_ip}(\(%{DATA:dst_fwuser}\))? \(type %{INT:icmp_type}, code %{INT:icmp_code}\)",
        "sample": "Deny Inbound icmp src outside:192.168.1.1 dst inside:10.0.0.1 (type 8, code 0)",
        "description": "匹配 Cisco ASA-3-106014：拒绝 ICMP 数据包",
    },
    {
        "name": "CISCOFW106015",
        "pattern": r"%{CISCO_ACTION:action} %{WORD:protocol} \(%{DATA:policy_id}\) from %{IP:src_ip}/%{INT:src_port} to %{IP:dst_ip}/%{INT:dst_port} flags %{DATA:tcp_flags}  on interface %{GREEDYDATA:interface}",
        "sample": "Deny TCP (acl-outside) from 192.168.1.1/54321 to 10.0.0.1/80 flags SYN  on interface outside",
        "description": "匹配 Cisco ASA-6-106015：拒绝 TCP 连接（带策略ID）",
    },
    {
        "name": "CISCOFW106021",
        "pattern": r"%{CISCO_ACTION:action} %{WORD:protocol} reverse path check from %{IP:src_ip} to %{IP:dst_ip} on interface %{GREEDYDATA:interface}",
        "sample": "Deny TCP reverse path check from 192.168.1.1 to 10.0.0.1 on interface outside",
        "description": "匹配 Cisco ASA-1-106021：反向路径检查拒绝",
    },
    {
        "name": "CISCOFW106023",
        "pattern": r'%{CISCO_ACTION:action}( protocol)? %{WORD:protocol} src %{DATA:src_interface}:%{DATA:src_ip}(/%{INT:src_port})?(\(%{DATA:src_fwuser}\))? dst %{DATA:dst_interface}:%{DATA:dst_ip}(/%{INT:dst_port})?(\(%{DATA:dst_fwuser}\))?( \(type %{INT:icmp_type}, code %{INT:icmp_code}\))? by access-group "?%{DATA:policy_id}"? \[%{DATA:hashcode1}, %{DATA:hashcode2}\]',
        "sample": 'Deny TCP src outside:192.168.1.1/54321 dst inside:10.0.0.1/80 by access-group "acl-outside" [0x12345678, 0x87654321]',
        "description": "匹配 Cisco ASA-4-106023：ACL 拒绝数据包",
    },
    {
        "name": "CISCOFW106100_2_3",
        "pattern": r"access-list %{NOTSPACE:policy_id} %{CISCO_ACTION:action} %{WORD:protocol} for user '%{DATA:src_fwuser}' %{DATA:src_interface}/%{IP:src_ip}\(%{INT:src_port}\) -> %{DATA:dst_interface}/%{IP:dst_ip}\(%{INT:dst_port}\) hit-cnt %{INT:hit_count} %{CISCO_INTERVAL:interval} \[%{DATA:hashcode1}, %{DATA:hashcode2}\]",
        "sample": "access-list acl-outside permitted tcp for user 'admin' outside/192.168.1.1(54321) -> inside/10.0.0.1(80) hit-cnt 1 first hit [0x12345678, 0x87654321]",
        "description": "匹配 Cisco ASA-4-106100/106102/106103：ACL 匹配（带用户信息）",
    },
    {
        "name": "CISCOFW106100",
        "pattern": r"access-list %{NOTSPACE:policy_id} %{CISCO_ACTION:action} %{WORD:protocol} %{DATA:src_interface}/%{IP:src_ip}\(%{INT:src_port}\)(\(%{DATA:src_fwuser}\))? -> %{DATA:dst_interface}/%{IP:dst_ip}\(%{INT:dst_port}\)(\(%{DATA:src_fwuser}\))? hit-cnt %{INT:hit_count} %{CISCO_INTERVAL:interval} \[%{DATA:hashcode1}, %{DATA:hashcode2}\]",
        "sample": "access-list acl-outside permitted tcp outside/192.168.1.1(54321) -> inside/10.0.0.1(80) hit-cnt 5 300-second interval [0x12345678, 0x87654321]",
        "description": "匹配 Cisco ASA-5-106100：ACL 匹配统计",
    },
    {
        "name": "CISCOFW110002",
        "pattern": r"%{CISCO_REASON:reason} for %{WORD:protocol} from %{DATA:src_interface}:%{IP:src_ip}/%{INT:src_port} to %{IP:dst_ip}/%{INT:dst_port}",
        "sample": "Failed to locate egress interface for TCP from outside:192.168.1.1/54321 to 10.0.0.1/80",
        "description": "匹配 Cisco ASA-6-110002：无法定位出口接口",
    },
    {
        "name": "CISCOFW302010",
        "pattern": r"%{INT:connection_count} in use, %{INT:connection_count_max} most used",
        "sample": "1000 in use, 5000 most used",
        "description": "匹配 Cisco ASA-6-302010：连接计数统计",
    },
    {
        "name": "CISCOFW302013_302014_302015_302016",
        "pattern": r"%{CISCO_ACTION:action}(?: %{CISCO_DIRECTION:direction})? %{WORD:protocol} connection %{INT:connection_id} for %{DATA:src_interface}:%{IP:src_ip}/%{INT:src_port}( \(%{IP:src_mapped_ip}/%{INT:src_mapped_port}\))?(\(%{DATA:src_fwuser}\))? to %{DATA:dst_interface}:%{IP:dst_ip}/%{INT:dst_port}( \(%{IP:dst_mapped_ip}/%{INT:dst_mapped_port}\))?(\(%{DATA:dst_fwuser}\))?( duration %{TIME:duration} bytes %{INT:bytes})?(?: %{CISCO_REASON:reason})?( \(%{DATA:user}\))?",
        "sample": "Built Inbound TCP connection 12345 for outside:192.168.1.1/54321 (192.168.1.1/54321) to inside:10.0.0.1/80 (10.0.0.1/80)",
        "description": "匹配 Cisco ASA-6-302013/302014/302015/302016：TCP/UDP 连接建立或拆除",
    },
    {
        "name": "CISCOFW302020_302021",
        "pattern": r"%{CISCO_ACTION:action}(?: %{CISCO_DIRECTION:direction})? %{WORD:protocol} connection for faddr %{IP:dst_ip}/%{INT:icmp_seq_num}(?:\(%{DATA:fwuser}\))? gaddr %{IP:src_xlated_ip}/%{INT:icmp_code_xlated} laddr %{IP:src_ip}/%{INT:icmp_code}( \(%{DATA:user}\))?",
        "sample": "Built Inbound ICMP connection for faddr 192.168.1.1/0 gaddr 10.0.0.1/0 laddr 10.0.0.1/0",
        "description": "匹配 Cisco ASA-6-302020/302021：ICMP 连接建立或拆除",
    },
    {
        "name": "CISCOFW305011",
        "pattern": r"%{CISCO_ACTION:action} %{CISCO_XLATE_TYPE:xlate_type} %{WORD:protocol} translation from %{DATA:src_interface}:%{IP:src_ip}(/%{INT:src_port})?(\(%{DATA:src_fwuser}\))? to %{DATA:src_xlated_interface}:%{IP:src_xlated_ip}/%{DATA:src_xlated_port}",
        "sample": "Built dynamic TCP translation from inside:10.0.0.1/54321 to outside:192.168.1.1/12345",
        "description": "匹配 Cisco ASA-6-305011：地址转换建立",
    },
    {
        "name": "CISCOFW313001_313004_313008",
        "pattern": r"%{CISCO_ACTION:action} %{WORD:protocol} type=%{INT:icmp_type}, code=%{INT:icmp_code} from %{IP:src_ip} on interface %{DATA:interface}( to %{IP:dst_ip})?",
        "sample": "Deny ICMP type=8, code=0 from 192.168.1.1 on interface outside to 10.0.0.1",
        "description": "匹配 Cisco ASA-3-313001/313004/313008：拒绝 ICMP 数据包",
    },
    {
        "name": "CISCOFW313005",
        "pattern": r"%{CISCO_REASON:reason} for %{WORD:protocol} error message: %{WORD:err_protocol} src %{DATA:err_src_interface}:%{IP:err_src_ip}(\(%{DATA:err_src_fwuser}\))? dst %{DATA:err_dst_interface}:%{IP:err_dst_ip}(\(%{DATA:err_dst_fwuser}\))? \(type %{INT:err_icmp_type}, code %{INT:err_icmp_code}\) on %{DATA:interface} interface\.  Original IP payload: %{WORD:protocol} src %{IP:orig_src_ip}/%{INT:orig_src_port}(\(%{DATA:orig_src_fwuser}\))? dst %{IP:orig_dst_ip}/%{INT:orig_dst_port}(\(%{DATA:orig_dst_fwuser}\))?",
        "sample": "No matching connection for ICMP error message: icmp src outside:192.168.1.1 dst inside:10.0.0.1 (type 3, code 3) on outside interface.  Original IP payload: udp src 10.0.0.1/53 dst 192.168.1.1/12345",
        "description": "匹配 Cisco ASA-4-313005：ICMP 错误消息无匹配连接",
    },
    {
        "name": "CISCOFW321001",
        "pattern": r"Resource '%{WORD:resource_name}' limit of %{POSINT:resource_limit} reached for system",
        "sample": "Resource 'Conns' limit of 65535 reached for system",
        "description": "匹配 Cisco ASA-5-321001：资源限制达到上限",
    },
    {
        "name": "CISCOFW402117",
        "pattern": r"%{WORD:protocol}: Received a non-IPSec packet \(protocol= %{WORD:orig_protocol}\) from %{IP:src_ip} to %{IP:dst_ip}",
        "sample": "IPSEC: Received a non-IPSec packet (protocol= UDP) from 192.168.1.1 to 10.0.0.1",
        "description": "匹配 Cisco ASA-4-402117：收到非 IPSec 数据包",
    },
    {
        "name": "CISCOFW402119",
        "pattern": r"%{WORD:protocol}: Received an %{WORD:orig_protocol} packet \(SPI= %{DATA:spi}, sequence number= %{DATA:seq_num}\) from %{IP:src_ip} \(user= %{DATA:user}\) to %{IP:dst_ip} that failed anti-replay checking",
        "sample": "IPSEC: Received an ESP packet (SPI= 0x12345678, sequence number= 100) from 192.168.1.1 (user= vpnuser) to 10.0.0.1 that failed anti-replay checking",
        "description": "匹配 Cisco ASA-4-402119：反重放检查失败",
    },
    {
        "name": "CISCOFW419001",
        "pattern": r"%{CISCO_ACTION:action} %{WORD:protocol} packet from %{DATA:src_interface}:%{IP:src_ip}/%{INT:src_port} to %{DATA:dst_interface}:%{IP:dst_ip}/%{INT:dst_port}, reason: %{GREEDYDATA:reason}",
        "sample": "Dropping TCP packet from outside:192.168.1.1/54321 to inside:10.0.0.1/80, reason: Bad TCP flags",
        "description": "匹配 Cisco ASA-4-419001：丢弃数据包（带原因）",
    },
    {
        "name": "CISCOFW419002",
        "pattern": r"%{CISCO_REASON:reason} from %{DATA:src_interface}:%{IP:src_ip}/%{INT:src_port} to %{DATA:dst_interface}:%{IP:dst_ip}/%{INT:dst_port} with different initial sequence number",
        "sample": "Duplicate TCP SYN from outside:192.168.1.1/54321 to inside:10.0.0.1/80 with different initial sequence number",
        "description": "匹配 Cisco ASA-4-419002：重复的 TCP SYN（初始序列号不同）",
    },
    {
        "name": "CISCOFW500004",
        "pattern": r"%{CISCO_REASON:reason} for protocol=%{WORD:protocol}, from %{IP:src_ip}/%{INT:src_port} to %{IP:dst_ip}/%{INT:dst_port}",
        "sample": "Invalid transport field for protocol=TCP, from 192.168.1.1/54321 to 10.0.0.1/80",
        "description": "匹配 Cisco ASA-4-500004：无效的传输字段",
    },
    {
        "name": "CISCOFW602303_602304",
        "pattern": r"%{WORD:protocol}: An %{CISCO_DIRECTION:direction} %{GREEDYDATA:tunnel_type} SA \(SPI= %{DATA:spi}\) between %{IP:src_ip} and %{IP:dst_ip} \(user= %{DATA:user}\) has been %{CISCO_ACTION:action}",
        "sample": "IPSEC: An Inbound ESP SA (SPI= 0x12345678) between 192.168.1.1 and 10.0.0.1 (user= vpnuser) has been created",
        "description": "匹配 Cisco ASA-6-602303/602304：IPSec SA 创建或删除",
    },
    {
        "name": "CISCOFW710001_710002_710003_710005_710006",
        "pattern": r"%{WORD:protocol} (?:request|access) %{CISCO_ACTION:action} from %{IP:src_ip}/%{INT:src_port} to %{DATA:dst_interface}:%{IP:dst_ip}/%{INT:dst_port}",
        "sample": "TCP access permitted from 192.168.1.1/54321 to outside:10.0.0.1/443",
        "description": "匹配 Cisco ASA-7-710001/710002/710003/710005/710006：管理访问请求",
    },
    {
        "name": "CISCOFW713172",
        "pattern": r"Group = %{GREEDYDATA:group}, IP = %{IP:src_ip}, Automatic NAT Detection Status:\s+Remote end\s*%{DATA:is_remote_natted}\s*behind a NAT device\s+This\s+end\s*%{DATA:is_local_natted}\s*behind a NAT device",
        "sample": "Group = VPN-Group, IP = 192.168.1.1, Automatic NAT Detection Status:\tRemote end is behind a NAT device\tThis end is NOT behind a NAT device",
        "description": "匹配 Cisco ASA-6-713172：NAT 自动检测状态",
    },
    {
        "name": "CISCOFW733100",
        "pattern": r"\[\s*%{DATA:drop_type}\s*\] drop %{DATA:drop_rate_id} exceeded. Current burst rate is %{INT:drop_rate_current_burst} per second, max configured rate is %{INT:drop_rate_max_burst}; Current average rate is %{INT:drop_rate_current_avg} per second, max configured rate is %{INT:drop_rate_max_avg}; Cumulative total count is %{INT:drop_total_count}",
        "sample": "[ Scanning] drop rate-1 exceeded. Current burst rate is 100 per second, max configured rate is 50; Current average rate is 80 per second, max configured rate is 40; Cumulative total count is 10000",
        "description": "匹配 Cisco ASA-4-733100：威胁检测丢包速率超标",
    },
    # Shorewall 防火墙
    {
        "name": "SHOREWALL",
        "pattern": r"(%{SYSLOGTIMESTAMP:timestamp}) (%{WORD:nf_host}) kernel:.*Shorewall:(%{WORD:nf_action1})?:(%{WORD:nf_action2})?.*IN=(%{USERNAME:nf_in_interface})?.*(OUT= *MAC=(%{COMMONMAC:nf_dst_mac}):(%{COMMONMAC:nf_src_mac})?|OUT=%{USERNAME:nf_out_interface}).*SRC=(%{IPV4:nf_src_ip}).*DST=(%{IPV4:nf_dst_ip}).*LEN=(%{WORD:nf_len}).?*TOS=(%{WORD:nf_tos}).?*PREC=(%{WORD:nf_prec}).?*TTL=(%{INT:nf_ttl}).?*ID=(%{INT:nf_id}).?*PROTO=(%{WORD:nf_protocol}).?*SPT=(%{INT:nf_src_port}?.*DPT=%{INT:nf_dst_port}?.*)",
        "sample": "Mar 15 14:30:59 fw01 kernel: Shorewall:REJECT:REJECT:IN=eth0 OUT= MAC=0a:1b:2c:3d:4e:5f:6a:7b:8c:9d:0e:1f SRC=192.168.1.1 DST=10.0.0.1 LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID=12345 PROTO=TCP SPT=54321 DPT=80",
        "description": "匹配 Shorewall 防火墙日志，包含源/目的 IP、MAC、协议和端口信息",
    },
]

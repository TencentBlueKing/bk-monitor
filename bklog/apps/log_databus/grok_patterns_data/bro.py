"""
Bro/Zeek 网络安全监控相关 Grok 模式数据
对应 pygrok patterns/bro 文件
"""

PATTERNS = [
    {
        "name": "BRO_HTTP",
        "pattern": r"%{NUMBER:ts}\t%{NOTSPACE:uid}\t%{IP:orig_h}\t%{INT:orig_p}\t%{IP:resp_h}\t%{INT:resp_p}\t%{INT:trans_depth}\t%{GREEDYDATA:method}\t%{GREEDYDATA:domain}\t%{GREEDYDATA:uri}\t%{GREEDYDATA:referrer}\t%{GREEDYDATA:user_agent}\t%{NUMBER:request_body_len}\t%{NUMBER:response_body_len}\t%{GREEDYDATA:status_code}\t%{GREEDYDATA:status_msg}\t%{GREEDYDATA:info_code}\t%{GREEDYDATA:info_msg}\t%{GREEDYDATA:filename}\t%{GREEDYDATA:bro_tags}\t%{GREEDYDATA:username}\t%{GREEDYDATA:password}\t%{GREEDYDATA:proxied}\t%{GREEDYDATA:orig_fuids}\t%{GREEDYDATA:orig_mime_types}\t%{GREEDYDATA:resp_fuids}\t%{GREEDYDATA:resp_mime_types}",
        "sample": "1331901001.234567\tCHhAvVGS1DHFjwGM9\t10.0.0.1\t54321\t192.168.1.1\t80\t1\tGET\twww.example.com\t/index.html\t-\tMozilla/5.0\t0\t1234\t200\tOK\t-\t-\t-\t-\t-\t-\t-\tFnPEwf3JXFoG5nmwn\ttext/html\tFnPEwf3JXFoG5nmwn\ttext/html",
        "description": "匹配 Bro/Zeek HTTP 日志（http.log），包含完整的 HTTP 请求和响应信息",
    },
    {
        "name": "BRO_DNS",
        "pattern": r"%{NUMBER:ts}\t%{NOTSPACE:uid}\t%{IP:orig_h}\t%{INT:orig_p}\t%{IP:resp_h}\t%{INT:resp_p}\t%{WORD:proto}\t%{INT:trans_id}\t%{GREEDYDATA:query}\t%{GREEDYDATA:qclass}\t%{GREEDYDATA:qclass_name}\t%{GREEDYDATA:qtype}\t%{GREEDYDATA:qtype_name}\t%{GREEDYDATA:rcode}\t%{GREEDYDATA:rcode_name}\t%{GREEDYDATA:AA}\t%{GREEDYDATA:TC}\t%{GREEDYDATA:RD}\t%{GREEDYDATA:RA}\t%{GREEDYDATA:Z}\t%{GREEDYDATA:answers}\t%{GREEDYDATA:TTLs}\t%{GREEDYDATA:rejected}",
        "sample": "1331901001.234567\tCHhAvVGS1DHFjwGM9\t10.0.0.1\t54321\t10.0.0.2\t53\tudp\t12345\twww.example.com\t1\tC_INTERNET\t1\tA\t0\tNOERROR\tT\tF\tT\tT\t0\t192.168.1.1\t3600.0\tF",
        "description": "匹配 Bro/Zeek DNS 日志（dns.log），包含完整的 DNS 查询和响应信息",
    },
    {
        "name": "BRO_CONN",
        "pattern": r"%{NUMBER:ts}\t%{NOTSPACE:uid}\t%{IP:orig_h}\t%{INT:orig_p}\t%{IP:resp_h}\t%{INT:resp_p}\t%{WORD:proto}\t%{GREEDYDATA:service}\t%{NUMBER:duration}\t%{NUMBER:orig_bytes}\t%{NUMBER:resp_bytes}\t%{GREEDYDATA:conn_state}\t%{GREEDYDATA:local_orig}\t%{GREEDYDATA:missed_bytes}\t%{GREEDYDATA:history}\t%{GREEDYDATA:orig_pkts}\t%{GREEDYDATA:orig_ip_bytes}\t%{GREEDYDATA:resp_pkts}\t%{GREEDYDATA:resp_ip_bytes}\t%{GREEDYDATA:tunnel_parents}",
        "sample": "1331901001.234567\tCHhAvVGS1DHFjwGM9\t10.0.0.1\t54321\t192.168.1.1\t80\ttcp\thttp\t1.234567\t500\t1234\tSF\t-\t0\tShADadfF\t5\t600\t4\t1334\t-",
        "description": "匹配 Bro/Zeek 连接日志（conn.log），包含网络连接的详细信息",
    },
    {
        "name": "BRO_FILES",
        "pattern": r"%{NUMBER:ts}\t%{NOTSPACE:fuid}\t%{IP:tx_hosts}\t%{IP:rx_hosts}\t%{NOTSPACE:conn_uids}\t%{GREEDYDATA:source}\t%{GREEDYDATA:depth}\t%{GREEDYDATA:analyzers}\t%{GREEDYDATA:mime_type}\t%{GREEDYDATA:filename}\t%{GREEDYDATA:duration}\t%{GREEDYDATA:local_orig}\t%{GREEDYDATA:is_orig}\t%{GREEDYDATA:seen_bytes}\t%{GREEDYDATA:total_bytes}\t%{GREEDYDATA:missing_bytes}\t%{GREEDYDATA:overflow_bytes}\t%{GREEDYDATA:timedout}\t%{GREEDYDATA:parent_fuid}\t%{GREEDYDATA:md5}\t%{GREEDYDATA:sha1}\t%{GREEDYDATA:sha256}\t%{GREEDYDATA:extracted}",
        "sample": "1331901001.234567\tFnPEwf3JXFoG5nmwn\t192.168.1.1\t10.0.0.1\tCHhAvVGS1DHFjwGM9\tHTTP\t0\tMD5,SHA1\ttext/html\tindex.html\t0.123456\t-\tF\t1234\t1234\t0\t0\tF\t-\td41d8cd98f00b204e9800998ecf8427e\tda39a3ee5e6b4b0d3255bfef95601890afd80709\t-\t-",
        "description": "匹配 Bro/Zeek 文件分析日志（files.log），包含传输文件的元数据信息",
    },
]

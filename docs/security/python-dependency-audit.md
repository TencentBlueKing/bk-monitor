# Python 依赖安全审计（2026-11-15）

审计对象是仓库 `4c6743eb3`（2026-11-13 合入 master 的最新提交）。三套 Python 环境的锁定版本与 2026-11-14 相同。数据源是 OSV.dev 的 PyPI 查询和当天的 `PyPI/all.zip`。严重级别取 GitHub Advisory 已审核等级；没有已审核等级时用 CVSS v3，没有 v3 再用 v4。同一条公告的 PYSEC 记录不抬高已审核等级。GHSA 与 PYSEC 按别名合并，同一 CVE 只计一次。

## 结论

运行时有公告的包版本数量没有变化：监控 37/255、基础库 13/97、日志 12/84。去重后的运行时公告仍是 248 条，其中严重 9、高危 110、中危 92、低危 37。2026-11-14 的分桶是严重 13、高危 126、中危 88、低危 21，合计同样是 248。11 月 14 日之后这些公告的 `published` / `modified` 没有变化，分桶差异来自已审核等级低于配对 CVSS 的 25 条公告。

优先处理这几项：

| 包 | 当前版本 | 所在环境 | 最高等级 | 建议升到 | 项目是否用到 |
| --- | --- | --- | --- | --- | --- |
| Django | 日志 4.2.22，监控 4.2.27，基础库 4.2.29 | 三套都在用 | 日志为严重，其余为高危 | 4.2.30 | Web 框架。日志管理查询对 `filter` 做了字段白名单 |
| djangorestframework | 监控 3.15.1，基础库和日志 3.15.2 | 三套 | 高危 | 3.18.2 | API 使用默认 `JSONParser`。基础库约束 `<3.16.0` 挡着修复版本 |
| certifi | 监控 2025.1.31，基础库 2026.2.25 | 监控、基础库 | 严重 | 2026.10.18 | 无直接 import，requests、Elasticsearch、Kubernetes 客户端的 HTTPS 校验会用到 |
| Pillow | 11.2.1 | 监控、基础库 | 严重 | 13.0.0 | 水印只生成 PNG。基础库约束 `<11.3` 挡着修复版本。日志源码引用了 PIL，requirements 未钉版本 |
| urllib3 | 监控和基础库 1.26.20 | 监控、基础库 | 高危 | 2.8.0 | 有直接 import。日志已钉 2.8.0，OSV 无命中 |
| ujson | 监控 5.7.0，日志 5.9.0 | 监控、日志 | 高危 | 5.12.1 | 监控用它替换 `json.loads` / `json.dumps`；日志导出只调用 `dumps` |
| kafka-python | 监控和基础库 1.4.6，日志 2.0.2 | 三套 | 高危 | 2.3.2 | 元数据和告警链路直接创建 `KafkaConsumer` |
| langchain-core | 0.3.75 | 监控、日志 | 严重 | 0.3.81 | 业务只引用 `BaseCallbackHandler`，仓库里没有 `dumps` / `loads` |
| anyio | 4.9.0 | 监控 | 严重 | 4.14.2 | 无直接 import，由 httpx、MCP、Starlette 带入 |
| cryptography | 监控 44.0.2，基础库 46.0.5 | 监控、基础库 | 高危 | 50.0.0 才能清掉现有高危 | 无直接 import，由 bk-crypto-python-sdk 带入 |
| mistune | 监控 0.8.4，日志 3.0.2 | 监控、日志 | 高危 | 3.3.0 | 日志 `version_log` 用它渲染 Markdown。监控约束 `<3` |
| dnspython | 2.6.1 | 监控 | 高危 | 2.9.2 | 只解析配置项 `TRANSFER_HOST` |
| PyJWT | 监控和基础库 2.15.1 | 监控、基础库 | 无公告 | 保持 | 网关和内核 API 中间件直接 `import jwt`。日志 requirements 未钉版本 |

监控默认组 `aidev` 里另有 5 个未进入主闭包的包：`attrdictionary`、`langchain-experimental`、`py`、`retry`、`stackprinter`。这 5 个都没有 OSV 公告。基础库默认组 `cli` 多 7 个包，其中只有 `pygments` 2.19.2 有 1 条低危。

## 范围

| 环境 | 清单 | 锁定包 | 本次统计的运行时版本 | 有公告的版本 |
| --- | --- | --- | --- | --- |
| 监控 `bkmonitor` | `bkmonitor/uv.lock` | 294 | 255 | 37 |
| 基础库 `bk-monitor-base` | `bk-monitor-base/uv.lock` | 151 | 97 | 13 |
| 日志 `bklog` | `bklog/requirements.txt` | 无 lock | 84 个直接 pin | 12 |

运行时闭包按 Linux、CPython 3.11.3+ 计算，去掉了 Windows 和 `python_full_version <= 3.11.2` 才装的包。监控含主依赖；`pyproject.toml` 的默认组 `aidev` 额外 5 包单独列出。基础库不含 `cli` 和 `dev`。日志只扫直接 pin，传递依赖没有锁文件，没有展开。

另外查了开发依赖：监控 dev/test/stubs 30 个仅开发版本，基础库 dev 44 个，日志 `requirements_dev.txt` 9 个。开发侧去重后有高危 17、中危 27、低危 5，没有严重公告。这些包不进业务镜像。

查询的不重复版本一共 430 个，与 11 月 14 日的查询规模一致。

## 严重公告

| 公告 | 包与版本 | 环境 | 修复版本 | 摘要 |
| --- | --- | --- | --- | --- |
| CVE-2026-63374 | anyio 4.9.0 | 监控 | 4.14.2 | AnyIO: TLSStream IDNA 2003 host name encoding enables potential TLS certificate spoofing |
| GHSA-6q48-6c7w-9gw2 | certifi 2025.1.31 | 监控 | 2026.10.18 | certifi bundles emSign root CAs with compromised intermediate CA keys |
| GHSA-6q48-6c7w-9gw2 | certifi 2026.2.25 | 基础库 | 2026.10.18 | certifi bundles emSign root CAs with compromised intermediate CA keys |
| CVE-2025-64459 | django 4.2.22 | 日志 | 4.2.26 | Django vulnerable to SQL injection via _connector keyword argument in QuerySet and Q objects. |
| CVE-2025-68664 | langchain-core 0.3.75 | 监控、日志 | 0.3.81 | LangChain serialization injection vulnerability enables secret extraction in dumps/loads APIs |
| CVE-2026-112393 | pillow 11.2.1 | 监控、基础库 | 13.0.0 | Pillow: Heap buffer overflow in _tiffWriteProc when saving TIFF to BytesIO |
| CVE-2026-112398 | pillow 11.2.1 | 监控、基础库 | 13.0.0 | Pillow: Heap buffer overflow in FlashPix (FPX) JPEG decoding leads to code execution |
| CVE-2026-112403 | pillow 11.2.1 | 监控、基础库 | 13.0.0 | Pillow: Heap buffer overflow in ImagingJpegDecode |
| CVE-2026-112900 | pillow 11.2.1 | 监控、基础库 | 13.0.0 | Pillow: Argument Injection in Ghostscript call, potentially leading into RCE |
| CVE-2026-96639 | pillow 11.2.1 | 监控、基础库 | 13.0.0 | Pillow multi-frame loaders can reuse stale native image storage after mode transitions |

使用情况：

- **CVE-2025-64459** 只打在日志的 Django 4.2.22 上，监控 4.2.27 和基础库 4.2.29 已经过了修复点 4.2.26。触发条件是把 `_connector` 一类关键字传进 `QuerySet` / `Q`。日志管理查询的 `_normalize_filter` 只接受 `ModelSpec` 字段白名单和一层 lookup，`_connector` 进不了 `filter()`。监控和基础库升到 4.2.30 仍值得做，见下一节的高危。
- **certifi** 两个环境都低于 2026.10.18。公告是根证书包里带有私钥已经泄露的 emSign 中间证书。业务代码不直接 import，但所有走 requests 的 HTTPS 都会用这套 CA。这是当前严重项里最值得先升的传递依赖。
- **Pillow** 五条严重都要到 13.0.0，分别落在 TIFF 写入、FlashPix/JPEG 解码、JPEG 解码、Ghostscript 参数注入和多帧 loader。业务水印在 `bkmonitor/packages/utils/signature.py` 和 `bklog/apps/utils/image.py`，只用 `Image.new`、绘制、旋转、裁剪并保存 PNG。`Image.open` 只出现在 `bkmonitor/scripts/verify_pillow_build.py`。基础库 `pillow<11.3` 让 13.0.0 无法被解析进来。日志代码引用了 PIL，`requirements.txt` 没有钉 Pillow。
- **CVE-2025-68664** 修在 langchain-core 0.3.81，问题在 `dumps` / `loads`。仓库里的 langchain 引用是 `ai_agent/llm/__init__.py` 和 `bklog/ai_agent/llm/__init__.py` 的 `BaseCallbackHandler`，没有序列化 API 的调用。
- **CVE-2026-63374** 是 anyio `TLSStream` 仍按 IDNA 2003 编码主机名，修在 4.14.2。监控没有直接 import anyio，调用链来自 httpx、langfuse、MCP 和 Starlette。

## 业务会走到的高危

- **Django 4.2.30** 是 4.2 系列当前能消掉的修复线。监控 4.2.27 仍包含 PostGIS `RasterField` 的 CVE-2026-1207、`FilteredRelation` 的 CVE-2026-1287、Windows `URLField` 的 CVE-2026-25673，以及 ASGI 的 CVE-2026-33034、CVE-2026-3902。基础库 4.2.29 剩下的高危是后两条 ASGI。仓库没有 `django.contrib.gis`，没有 `FilteredRelation`，也没有 `ASGI_APPLICATION`，进程入口是 gunicorn WSGI。CVE-2026-25673 的正文限定 Windows。日志 4.2.22 另外还带着列别名 SQL 注入等更早的高危，升到 4.2.30 可以一次收掉 4.2 线上的修复。
- **OSV 把若干只写了 5.2/6.0 的公告也标到了 4.2。** CVE-2026-15307（高危，GeoDjango 栅格查找）正文只覆盖 5.2.17 / 6.0.8 之前，范围却写成从 0 修到 5.2.17。CVE-2026-15830、CVE-2026-53877、CVE-2026-53878、CVE-2026-48587、CVE-2026-48588、CVE-2026-6873、CVE-2026-8404 同样只点名 5.2 和 6.0，并写明更早的 4.2 系列未评估。这些条目留在计数里，4.2.30 消不掉它们，因为修复号在 5.2/6.0。
- **DRF 3.15.1 / 3.15.2** 的三条高危都在 3.18.2 修复。CVE-2026-114136 是 `JSONParser` 会按攻击者指定的 codec 解码请求体。接口测试和视图按 DRF 默认方式使用 `JSONParser`。基础库 `djangorestframework<3.16.0` 把 3.18.2 挡在外面，监控和日志要跟着一起改。
- **urllib3 1.26.20** 的高危包括解压链、流式解压、重定向和代理 TLS，修复分散在 2.6.0 到 2.8.0。监控代码在 Kubernetes 和 ES 工具里直接 import。日志的 pin 已经是 2.8.0，本次查询没有命中。
- **ujson** 监控 5.7.0 经 `bkmonitor/patches/json.py` 接管无额外参数的 `load` / `loads` / `dump` / `dumps`。解析超大整数的高危因此会落在监控自己的 JSON 入口上。日志 5.9.0 的业务调用是导出时的 `ujson.dumps`。两条解析高危修在 5.12.0，`dump` 写失败泄漏修在 5.12.1。
- **kafka-python** 1.4.6 和 2.0.2 都有未校验帧长度和 SCRAM 迭代次数导致的拒绝服务，修在 2.3.2。监控、基础库和日志都直接创建消费者或管理客户端，连的是平台 Kafka。
- **dnspython 2.6.1** 的高危在解析 DNS 报文时的 CPU 和内存消耗，修到 2.9.2。唯一调用是 `resolve_domain(settings.TRANSFER_HOST)`，域名来自环境变量，默认 `transfer.bkmonitorv3.service.consul`。
- **mistune** 监控被 `django-versionlog` 锁在 0.8.4，且 `pyproject.toml` 写了 `mistune<3`。日志运行时是 3.0.2，`bklog/version_log/utils.py` 用 `mistune.create_markdown` 渲染版本文本。高危主要是恶意 Markdown 的解析耗时和 Include 路径，修在 3.3.0。日志的 `requirements_dev.txt` 另钉了 `mistune==0.8.4`，开发环境和运行时叠装时会把 3.0.2 盖掉。
- **cryptography** 监控 44.0.2 比基础库 46.0.5 多一条高危 CVE-2026-26007，46.0.5 可以去掉它。两边共有的高危要到 48.0.1（轮子里的 OpenSSL）、49.0.0 和 50.0.0。基础库上的 CVE-2026-39892 已审核等级是中危，46.0.7 只能去掉这一条，去不掉高危。业务没有直接 import。
- **Mako 1.3.10** 是监控的模板后端，`TemplateLookup` 有路径穿越，1.3.12 修完。**MCP SDK 1.12.4** 被 `kernel_api` 引用，HTTP/WebSocket 传输相关的高危修到 1.28.1。**pyasn1** 监控 0.6.1、基础库 0.6.2 由 rsa 带入，解码拒绝服务修到 0.6.5。**oauthlib** 由 requests-oauthlib 带入，高危修复在 4.0.0 及以后。**aiohttp 3.11.18** 和 **Starlette 0.47.3** 随 langchain、MCP 进入监控，业务没有直接 import。

idna 3.10（监控）和 3.11（基础库）是中危，requests 用它编码主机名，业务没有直接 import。

## 运行时有公告的包

同一包在不同环境版本不同时各占一行。「消除该等级」取这一等级里、与当前版本同一条发布线的最高修复号。Django 4.2.27 / 4.2.29 因此写成 4.2.30；OSV 另把 CVE-2026-15307 的修复号标成 5.2.17，正文只覆盖 5.2 和 6.0。`bklog/ai_agent` 是指向仓库根目录 `ai_agent` 的符号链接，import 扫描不跟随链接，表里 langchain-core 和 langchain-openai 的引用按源码手工核对。

| 包 | 版本 | 环境 | 最高等级 | 严重 | 高危 | 中危 | 低危 | 消除该等级 | 项目是否使用 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| anyio | 4.9.0 | 监控 | 严重 | 1 | 0 | 1 | 0 | 4.14.2 | 传递：httpx、langfuse、mcp、openai |
| certifi | 2025.1.31 | 监控 | 严重 | 1 | 0 | 0 | 0 | 2026.10.18 | 传递：elasticsearch、elasticsearch-curator、elasticsearch7、httpcore |
| certifi | 2026.2.25 | 基础库 | 严重 | 1 | 0 | 0 | 0 | 2026.10.18 | 传递：elasticsearch、elasticsearch-curator、elasticsearch7、kubernetes |
| django | 4.2.22 | 日志 | 严重 | 1 | 9 | 7 | 11 | 4.2.26 | 直接引用：监控、日志、基础库 |
| langchain-core | 0.3.75 | 监控、日志 | 严重 | 1 | 3 | 1 | 1 | 0.3.81 | 直接引用：ai_agent，只引用 BaseCallbackHandler |
| pillow | 11.2.1 | 监控、基础库 | 严重 | 5 | 37 | 18 | 0 | 13.0.0 | 直接引用：监控、日志 |
| aiohttp | 3.11.18 | 监控 | 高危 | 0 | 5 | 20 | 16 | 3.14.4 | 传递：langchain-community |
| cryptography | 44.0.2 | 监控 | 高危 | 0 | 4 | 1 | 1 | 50.0.0 | 传递：bk-crypto-python-sdk、blue-krill、blueapps |
| cryptography | 46.0.5 | 基础库 | 高危 | 0 | 3 | 2 | 1 | 50.0.0 | 传递：bk-crypto-python-sdk、blue-krill、google-auth |
| django | 4.2.27 | 监控 | 高危 | 0 | 6 | 5 | 10 | 4.2.30 | 直接引用：监控、日志、基础库 |
| django | 4.2.29 | 基础库 | 高危 | 0 | 3 | 4 | 6 | 4.2.30 | 直接引用：监控、日志、基础库 |
| djangorestframework | 3.15.1 | 监控 | 高危 | 0 | 3 | 2 | 1 | 3.18.2 | 直接引用：监控、日志、基础库 |
| djangorestframework | 3.15.2 | 基础库、日志 | 高危 | 0 | 3 | 2 | 0 | 3.18.2 | 直接引用：监控、日志、基础库 |
| dnspython | 2.6.1 | 监控 | 高危 | 0 | 2 | 0 | 0 | 2.9.2 | 直接引用：监控 |
| kafka-python | 1.4.6 | 监控、基础库 | 高危 | 0 | 2 | 0 | 0 | 2.3.2 | 直接引用：监控、日志、基础库 |
| kafka-python | 2.0.2 | 日志 | 高危 | 0 | 2 | 0 | 0 | 2.3.2 | 直接引用：监控、日志、基础库 |
| langchain | 0.3.27 | 监控、日志 | 高危 | 0 | 1 | 1 | 0 | 0.3.30 | 直接引用：监控 |
| langsmith | 0.3.45 | 监控 | 高危 | 0 | 2 | 1 | 0 | 0.8.18 | 传递：langchain、langchain-community、langchain-core |
| mako | 1.3.10 | 监控 | 高危 | 0 | 2 | 1 | 0 | 1.3.12 | 直接引用：监控 |
| mcp | 1.12.4 | 监控 | 高危 | 0 | 3 | 4 | 0 | 1.28.1 | 直接引用：监控 |
| mistune | 0.8.4 | 监控 | 高危 | 0 | 5 | 11 | 0 | 3.3.0 | 直接引用：日志 |
| mistune | 3.0.2 | 日志 | 高危 | 0 | 6 | 11 | 0 | 3.3.0 | 直接引用：日志 |
| msgpack | 1.1.0 | 监控 | 高危 | 0 | 2 | 0 | 0 | 1.2.3 | 传递：influxdb |
| msgpack | 1.1.2 | 基础库 | 高危 | 0 | 2 | 0 | 0 | 1.2.3 | 传递：influxdb |
| oauthlib | 3.2.2 | 监控 | 高危 | 0 | 1 | 2 | 0 | 4.0.0 | 传递：requests-oauthlib |
| oauthlib | 3.3.1 | 基础库 | 高危 | 0 | 2 | 2 | 0 | 4.0.1 | 传递：requests-oauthlib |
| opentelemetry-instrumentation | 0.30b1 | 监控 | 高危 | 0 | 1 | 0 | 0 | 0.41b0 | 传递：opentelemetry-instrumentation-celery、opentelemetry-instrumentation-dbapi、opentelemetry-instrumentation-django、opentelemetry-instrumentation-elasticsearch |
| orjson | 3.10.18 | 监控 | 高危 | 0 | 1 | 0 | 0 | 3.11.5 | 传递：langsmith |
| protobuf | 3.19.5 | 监控 | 高危 | 0 | 2 | 0 | 0 | 5.29.6 | 传递：googleapis-common-protos、opentelemetry-proto |
| protobuf | 3.20.3 | 日志 | 高危 | 0 | 2 | 0 | 0 | 5.29.6 | 传递：运行时闭包 |
| pyasn1 | 0.6.1 | 监控 | 高危 | 0 | 9 | 0 | 0 | 0.6.5 | 传递：pyasn1-modules、rsa |
| pyasn1 | 0.6.2 | 基础库 | 高危 | 0 | 8 | 0 | 0 | 0.6.5 | 传递：pyasn1-modules、rsa |
| python-multipart | 0.0.20 | 监控 | 高危 | 0 | 3 | 1 | 3 | 0.0.30 | 传递：mcp |
| starlette | 0.47.3 | 监控 | 高危 | 0 | 3 | 2 | 1 | 1.3.1 | 传递：mcp |
| ujson | 5.7.0 | 监控 | 高危 | 0 | 3 | 1 | 0 | 5.12.1 | 直接引用：监控、日志 |
| ujson | 5.9.0 | 日志 | 高危 | 0 | 3 | 1 | 0 | 5.12.1 | 直接引用：监控、日志 |
| urllib3 | 1.26.20 | 监控、基础库 | 高危 | 0 | 6 | 1 | 0 | 2.8.0 | 直接引用：监控、日志、基础库 |
| h2 | 4.2.0 | 监控 | 中危 | 0 | 0 | 2 | 0 | 4.4.1 | 传递：grpclib |
| hpack | 4.1.0 | 监控 | 中危 | 0 | 0 | 1 | 0 | 4.2.0 | 传递：h2 |
| idna | 3.10 | 监控 | 中危 | 0 | 0 | 1 | 0 | 3.15 | 传递：anyio、httpx、langfuse、requests |
| idna | 3.11 | 基础库 | 中危 | 0 | 0 | 1 | 0 | 3.15 | 传递：requests |
| langchain-text-splitters | 0.3.11 | 监控 | 中危 | 0 | 0 | 1 | 0 | 1.1.2 | 传递：langchain |
| markdown | 3.3 | 日志 | 中危 | 0 | 0 | 1 | 0 | 3.8.1 | 直接引用：日志 |
| marshmallow | 3.26.1 | 监控 | 中危 | 0 | 0 | 1 | 0 | 3.26.2 | 传递：dataclasses-json、environs |
| opentelemetry-api | 1.11.1 | 监控 | 中危 | 0 | 0 | 2 | 0 | 1.45.2 | 直接引用：监控、日志 |
| opentelemetry-api | 1.24.0 | 日志 | 中危 | 0 | 0 | 2 | 0 | 1.45.2 | 直接引用：监控、日志 |
| python-dotenv | 0.21.1 | 监控 | 中危 | 0 | 0 | 1 | 0 | 1.2.2 | 直接引用：监控 |
| requests | 2.32.5 | 监控、基础库、日志 | 中危 | 0 | 0 | 1 | 0 | 2.33.0 | 直接引用：监控、日志、基础库 |
| setuptools | 79.0.1 | 监控 | 中危 | 0 | 0 | 1 | 1 | 83.0.0 | 传递：apigw-manager、kubernetes、opentelemetry-api、opentelemetry-instrumentation |
| setuptools | 80.9.0 | 日志 | 中危 | 0 | 0 | 1 | 1 | 83.0.0 | 传递：运行时闭包 |
| setuptools | 82.0.1 | 基础库 | 中危 | 0 | 0 | 1 | 1 | 83.0.0 | 传递：kubernetes |
| werkzeug | 3.1.3 | 监控 | 中危 | 0 | 0 | 4 | 0 | 3.1.9 | 传递：aidev-agent、blueapps |
| langchain-openai | 0.3.22 | 监控 | 低危 | 0 | 0 | 0 | 1 | 1.1.14 | 直接引用：ai_agent 的 ChatOpenAI |
| pygments | 2.19.1 | 监控 | 低危 | 0 | 0 | 0 | 1 | 2.20.0 | 传递：ipython、ipython-pygments-lexers |

## 开发依赖

`bklog/requirements_dev.txt` 的 `virtualenv==15.2` 有 10 条高危，其中 CVE-2024-53899 的已审核等级是高危，修复版本 20.26.6。监控开发闭包里的 virtualenv 是 20.30.0，基础库开发闭包是 21.2.0，高危要到 21.14.9 一带才收齐。基础库开发依赖 `filelock` 3.25.1 有 1 条高危，修复版本 4.2.1。这些包只在开发和测试环境出现。

## 挡住修复版本的约束

| 位置 | 约束 | 后果 |
| --- | --- | --- |
| `bk-monitor-base/pyproject.toml` | `pillow<11.3` | 严重修复在 13.0.0，当前锁在 11.2.1 |
| `bk-monitor-base/pyproject.toml` | `djangorestframework<3.16.0` | JSONParser 高危修在 3.18.2 |
| `bkmonitor/pyproject.toml` | `mistune<3` | 注释写明 version-log 需要 3 以下，高危修在 3.3.0 |
| `bk-monitor-base/pyproject.toml` | `django<5` | 4.2.30 仍在约束内 |
| `bklog/requirements_dev.txt` | `mistune==0.8.4` | 与运行时 `mistune==3.0.2` 冲突，开发安装会降级 |
| `bklog/requirements.txt` | 无 lock，且未钉 Pillow、PyJWT | 源码已经 `import PIL` 和 `import jwt`，版本由安装时的解析结果决定 |

本次只记录版本和调用位置，没有修改依赖，也没有做漏洞利用验证。

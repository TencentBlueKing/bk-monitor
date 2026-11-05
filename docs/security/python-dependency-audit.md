# Python 依赖安全审计

扫描日期：2026-10-31。数据来源：OSV.dev 对 PyPI 精确版本的查询；GHSA 与 PYSEC 按 CVE 别名合并。严重程度取 CVSS v3 基础分（≥9.0 严重，≥7.0 高，≥4.0 中，>0 低）与 GHSA 定性等级中的较高者。没有 v3 分数时保留 GHSA 定性，CVSS 列记为 —。源码引用来自对 `.py` 的静态 import，并跟随 `bklog/ai_agent`、`bklog/iam_engine`、`bkmonitor/iam_engine` 这三处符号链接。

## 结论

三套 Python 环境共 **439** 个不重复的包版本（bkmonitor 锁文件 292、bk-monitor-base 锁文件 153、bklog 直接依赖 92）。其中 **67** 个版本命中已知漏洞，展开到各子项目后是 **75** 行。合并后的有等级公告 **301** 条：严重 15、高 148、中 112、低 26。

运行时会安装的受影响记录有 68 行（含 bkmonitor 默认依赖组 `aidev` 和 bk-monitor-base 默认组 `cli`）。其中业务代码直接 import 的 29 行，只在测试代码出现的 2 行，其余 37 行是传递依赖、业务源码没有直接 import。

相对 2026-10-29：两份 `uv.lock` 没有变化。有等级公告从 296 条变为 301 条，增加的 5 条都是高危，严重、中、低的条数不变。受影响版本仍是 67 个，展开后仍是 75 行。对得上的变化是：

- **bklog 直接依赖有三处调整，都没有 OSV 公告。** `bk-crypto-python-sdk` 从 2.0.0 改为 4.1.1（extra `gm`），并新增 `bk-kms-sdk==1.0.0`、`pycryptodome==3.23.0`。业务代码已经在用：`bklog/config/default.py` 与 `bklog/config/kms.py` import `bkcrypto`，`bklog/config/kms.py` 调用 `bk_kms.decrypt`，`bklog/apps/utils/aes.py` 与 `base_crypt.py` import `Crypto`。`pycryptodome` 3.23.0 本来就在另外两份锁文件里。不重复版本从 438 变为 439，是去掉只出现在旧 bklog 清单里的 2.0.0，加上 4.1.1 和 `bk-kms-sdk` 1.0.0。
- **pyasn1 新增 4 条高危**，公布日都是 2026-10-30，CVSS 都是 7.5，内容都是解码时的二次复杂度拒绝服务。bkmonitor 的 0.6.1 高危从 5 条变为 9 条，bk-monitor-base 的 0.6.2 从 4 条变为 8 条。一次清掉已知问题的版本从 0.6.4 改为 **0.6.5**。两处都是传递依赖，源码没有 `import pyasn1`。它随 `google-auth`、`rsa` 进入锁文件；bkmonitor 直接声明了 `google-auth`，两处又都因为直接依赖 `kubernetes` 带上 `google-auth`。
- **oauthlib 新增 CVE-2026-118669**（2026-10-30）。这条只有 CVSS v4 向量，没有 v3 分数，GHSA 定性为高。令牌授予在认证过另一个客户端之后，可以使用攻击者提供的 `client_id`。修复版本仍是 **4.0.0**。bk-monitor-base 3.3.1 的高危从 1 条变为 2 条。bkmonitor 3.2.2 原来最高是中危，现在变成高危。源码没有 `import oauthlib`。锁文件里的路径是 `kubernetes` → `requests-oauthlib` → `oauthlib`，业务代码直接使用 kubernetes 客户端（例如 `bkmonitor/metadata/models/bcs/cluster.py`、`bk-monitor-base/src/bk_monitor_base/metadata/utils/bcs.py`、`bklog/apps/utils/bcs.py`）。bklog 钉了 `kubernetes==18.20.0`，但没有钉 oauthlib 和 pyasn1，这两个版本不在这次查询里。

| 包 | 版本 | 编号 | CVSS | 修复版本 | 摘要 |
| --- | --- | --- | --- | --- | --- |
| `pyasn1` | bkmonitor 0.6.1、base 0.6.2 | CVE-2026-119194 | 7.5 | 0.6.5 | 无 schema 的 BER/CER/DER 容器解码出现二次 CPU 消耗 |
| `pyasn1` | 同上 | CVE-2026-119195 | 7.5 | 0.6.5 | 构造字符串与不定长 ANY 解码的二次时间拒绝服务 |
| `pyasn1` | 同上 | CVE-2026-119196 | 7.5 | 0.6.5 | 构造 BIT STRING 解码的二次 CPU 消耗 |
| `pyasn1` | 同上 | CVE-2026-119197 | 7.5 | 0.6.5 | 二进制 REAL 解码的二次复杂度拒绝服务 |
| `oauthlib` | bkmonitor 3.2.2、base 3.3.1 | CVE-2026-118669 | — | 4.0.0 | 令牌授予可在认证其他客户端后使用攻击者提供的 `client_id` |

优先处理仍被业务代码直接调用、且修复版本明确的几项，和 10-29 相同：

1. **Django 升到 4.2.30。** bklog 仍是 4.2.22，bkmonitor 是 4.2.27，bk-monitor-base 是 4.2.29。三处业务代码都在用 Django。4.2.30 可以清掉 4.2 线上目前已有修复的严重项 CVE-2026-4277（CVSS 9.8，GenericInlineModelAdmin 权限问题）以及这条线上的 SQL 注入和拒绝服务。仓库里没有 `django.contrib.gis`。只在 5.2.17 修复的 GeoDjango 公告 CVE-2026-15307（CVSS 8.8）当前看不到直接调用点，4.2 线建议停在 4.2.30。
2. **PyJWT 升到 2.15.0。** bkmonitor 锁的是 2.10.1，`kernel_api/middlewares/authentication.py` 会 `jwt.decode`。bk-monitor-base 是传递依赖 2.11.0，本目录源码没有直接 import。bklog 的 `apps/middleware/apigw.py` 捕获 `jwt.PyJWTError`，但 `requirements.txt` 没有钉 PyJWT，版本不在这次直接依赖查询里。严重项 CVE-2026-102268 在 2.14.0 修复，高危 CVE-2026-102275 要到 2.15.0。CVE-2025-45768 被上游标为有争议，没有修复版本。
3. **djangorestframework 升到 3.18.2。** 三处都直接使用。bkmonitor 3.15.1，另外两处 3.15.2。只升到 3.15.2 清不掉 2026-10 公布的三条高危。bk-monitor-base 的约束是 `djangorestframework<3.16.0`，挡住了 3.18.2。
4. **Pillow 升到 13.0.0。** bkmonitor 与 bk-monitor-base 都锁在 11.2.1，共 5 条严重、38 条高危。bkmonitor 在 `packages/utils/signature.py` 用 `Image.new` / `ImageDraw` / `ImageFont.truetype` 画水印，不解码用户上传的图片，解码类公告的直接触发面比通用图片服务小。bklog 的 `apps/utils/image.py` 同样画水印，但 requirements 没有钉 Pillow。bk-monitor-base 约束 `pillow<11.3`，挡住 13.0.0。
5. **certifi 升到 2026.10.18 或更新。** bkmonitor 是 2025.1.31，bk-monitor-base 是 2026.2.25。业务代码没有直接 import，它随 requests 做 TLS 校验。GHSA-6q48-6c7w-9gw2：捆绑的 emSign 根证书对应的中间 CA 密钥已失陷。
6. **urllib3 升到 2.8.0。** 三处都在 1.26.19 或 1.26.20。bkmonitor 与 base 的 `metadata` ES 工具直接用了 `urllib3.util.retry.Retry`。bklog 只有 `apps/utils/tests.py` 这个 TestCase 辅助模块 import 了 urllib3，生产代码没有直接引用，但 requests 仍会加载它。OSV 给出的修复都从 2.6.0 起，1.26 没有后续修复版本。
7. **kafka-python 升到 2.3.2。** bkmonitor 与 base 是 1.4.6，bklog 是 2.0.2，三处都直接 `import kafka`。对应 CVE-2026-10142、CVE-2026-10143。从 1.4 到 2.3 需要看 API 兼容。

## 扫描范围

| 子项目 | 清单 | 版本数 | 是否包含传递依赖 |
| --- | --- | ---: | --- |
| bkmonitor | `bkmonitor/uv.lock` | 292 | 是。锁文件中的全部第三方包，含运行时、默认组 `aidev`、开发测试组 |
| bk-monitor-base | `bk-monitor-base/uv.lock` | 153 | 是。锁文件中的全部第三方包，含运行时、默认组 `cli`、开发测试组 |
| bklog | `bklog/requirements.txt`、`requirements_dev.txt` | 92 | 否。没有锁文件。同名包以运行时钉版为准，dev 文件只补运行时没有的名字 |

本地路径包 `bkmonitor`、`bk-monitor-base` 不查 PyPI。`bklog/requirements_env.txt` 只有注释。`requirements_dev.txt` 另钉了 `mistune==0.8.4`，与运行时的 `mistune==3.0.2` 冲突；主索引按运行时版本计，这条降级写在约束一节。

静态扫描文件数：bkmonitor 4824、bk-monitor-base 669、bklog 1547（含符号链接指向的 `ai_agent`）。语法解析失败 0。文件数比 10-29 略多，是因为 master 在两次扫描之间有提交。除 bklog 上述三处钉版外，依赖锁没有变。

「业务代码引用」表示非测试路径里出现了该包的 import。「仅测试代码引用」表示只在 `tests/`、`test_*.py`、`conftest.py` 或名为 `tests.py` 的 TestCase 模块里出现。「源码未见引用」表示上述扫描没看到 import；运行时传递依赖仍会装进环境。这次没有跟踪每个漏洞函数是否被调用到。

## 业务代码直接使用的严重与高危

| 包 | 子项目、版本与公告数（严重/高/中/低） | 建议版本 | 使用情况 |
| --- | --- | --- | --- |
| `django` | bk-monitor-base 4.2.29（运行时直接，业务代码引用，1/3/4/5）<br>bklog 4.2.22（运行时直接，业务代码引用，3/11/7/7）<br>bkmonitor 4.2.27（运行时直接，业务代码引用，1/8/6/6） | **4.2.30** | 三处业务代码都使用 Django。4.2.30 覆盖 4.2 线上已修复的严重和高危。CVE-2026-15307 的修复版本是 5.2.17，仓库内未发现 GeoDjango 引用。 |
| `pyjwt` | bk-monitor-base 2.11.0（传递，源码未见引用，1/6/9/1）<br>bkmonitor 2.10.1（传递，业务代码引用，1/7/8/1） | **2.15.0** | bkmonitor 在认证中间件调用 `jwt.decode`。base 为传递依赖，目录内无直接 import。bklog 中间件引用了 `jwt.PyJWTError`，但没有钉版本。CVE-2025-45768 无修复版本。 |
| `djangorestframework` | bk-monitor-base 3.15.2（运行时直接，业务代码引用，0/3/2/0）<br>bklog 3.15.2（运行时直接，业务代码引用，0/3/2/0）<br>bkmonitor 3.15.1（运行时直接，业务代码引用，0/3/3/0） | **3.18.2** | 三处都 import `rest_framework`。base 约束 `<3.16.0` 与建议版本冲突。 |
| `pillow` | bk-monitor-base 11.2.1（运行时直接，源码未见引用，5/38/15/0）<br>bkmonitor 11.2.1（运行时直接，业务代码引用，5/38/15/0） | **13.0.0** | bkmonitor 用水印绘制调用 PIL。base 同版本但本目录无 import，约束 `pillow<11.3`。bklog 有水印代码但未钉版本。 |
| `urllib3` | bk-monitor-base 1.26.20（传递，业务代码引用，0/6/1/0）<br>bklog 1.26.19（运行时直接，仅测试代码引用，0/6/1/0）<br>bkmonitor 1.26.20（传递，业务代码引用，0/6/1/0） | **2.8.0** | bkmonitor 与 base 使用 `urllib3.util.retry.Retry`。bklog 的直接 import 在 TestCase 辅助模块，生产路径没有。1.26 线没有修复版本。 |
| `kafka-python` | bk-monitor-base 1.4.6（运行时直接，业务代码引用，0/2/0/0）<br>bklog 2.0.2（运行时直接，业务代码引用，0/2/0/0）<br>bkmonitor 1.4.6（运行时直接，业务代码引用，0/2/0/0） | **2.3.2** | 三处都 import `kafka`。1.4.6 与 2.0.2 都受 CVE-2026-10142 / CVE-2026-10143 影响。 |
| `langchain-core` | bklog 0.3.75（运行时直接，业务代码引用，1/3/1/1）<br>bkmonitor 0.3.75（默认组直接，源码未见引用，1/3/1/1） | **0.3.85** | bklog `ai_agent/llm/__init__.py` import `langchain_core`。0.3.85 可清掉严重的序列化注入 CVE-2025-68664。路径穿越 CVE-2026-34070 的修复在 1.2.22。bkmonitor 同版本在默认组 `aidev`，业务代码 import 的是 `langchain`，不是 `langchain_core`。`aidev-agent` 也会把它拉进运行时闭包。 |
| `ujson` | bklog 5.9.0（运行时直接，业务代码引用，0/3/1/0）<br>bkmonitor 5.7.0（运行时直接，业务代码引用，0/3/1/0） | **5.13.0** | bkmonitor `patches/json.py` 与 bklog 导出任务直接 import。 |
| `mistune` | bklog 3.0.2（运行时直接，业务代码引用，0/6/11/0）<br>bkmonitor 0.8.4（运行时直接，源码未见引用，0/5/11/0） | **3.3.0** | bklog `version_log/utils.py` 使用 3.0.2。bkmonitor 声明 `mistune<3`（version-log 需要），锁文件里是 0.8.4，业务代码未见 import。bklog 的 dev 文件另钉 0.8.4，一起安装时会盖掉 3.0.2。 |
| `sqlparse` | bk-monitor-base 0.5.5（传递，源码未见引用，0/3/2/0）<br>bkmonitor 0.5.3（运行时直接，业务代码引用，0/3/3/0） | **0.6.0** | bkmonitor 直接 import。升到 0.5.4 不够，高危修复在 0.6.0。base 是传递依赖 0.5.5，目录内未见 import。 |
| `mako` | bkmonitor 1.3.10（传递，业务代码引用，0/2/1/0） | **1.3.12** | bkmonitor 模板后端 import `mako`。清掉当前高危可以到 1.3.12；一次清掉全部公告需要 1.4.2。 |
| `dnspython` | bkmonitor 2.6.1（运行时直接，业务代码引用，0/1/0/0） | **2.9.0** | bkmonitor `dns_resolve.py` import `dns.resolver`。 |
| `markdown` | bklog 3.3（运行时直接，业务代码引用，0/1/0/0） | **3.8.1** | bklog 常量模块 import `markdown`。CVE-2025-69534。 |
| `langchain` | bklog 0.3.27（运行时直接，源码未见引用，0/1/1/0）<br>bkmonitor 0.3.27（默认组直接，业务代码引用，0/1/1/0） | **0.3.30** | bkmonitor 诊断 agent import `langchain.agents`，属于默认组 `aidev`。0.3.30 覆盖高危；另有公告要到 1.3.9。bklog 声明了同版本，源码未见 `langchain` import（用的是 langchain-core）。 |
| `opentelemetry-instrumentation` | bkmonitor 0.30b1（传递，业务代码引用，0/1/0/0） | **0.41b0** | bkmonitor `bkmonitor/trace/` 直接 import `opentelemetry.instrumentation`。当前 0.30b1 仍命中 CVE-2023-43810。 |

`mcp` 1.12.4 仍是 bkmonitor 的传递依赖，4 条高危，建议 1.30.0。按 import 根核对，仓库里没有 `import mcp` / `from mcp`。它仍会随默认组里的 MCP 适配器装进环境，运行 aidev 时可能加载。

## 会装进运行环境、业务代码没有直接 import 的严重项

这些包在锁文件的运行时闭包里。没有直接 import 不代表进程不会加载它们。

| 包 | 版本 | 所在环境 | 建议 | 说明 |
| --- | --- | --- | --- | --- |
| certifi | 2025.1.31 / 2026.2.25 | bkmonitor / bk-monitor-base | ≥ 2026.10.18 | 根证书包。GHSA-6q48-6c7w-9gw2，严重。随 requests 使用。 |
| cryptography | 46.0.5 | bk-monitor-base 传递依赖 | 先到 46.0.7，清全部高危需 50.0.0 | 严重项 CVE-2026-39892 在 46.0.7 修复。CVE-2026-69248 为中危，修复在 49.0.0。本目录源码未见 import。 |
| cryptography | 44.0.2 | bkmonitor 传递依赖 | 50.0.0 可清当前高危 | 严重项 CVE-2026-39892 未命中这个版本。仅测试代码 import。CVE-2026-69248 在这个版本上没有等级，修复版本仍是 49.0.0。 |
| pillow | 11.2.1 | bk-monitor-base 直接依赖 | 13.0.0 | 与 bkmonitor 同一版本和同一批公告。base 源码未见 PIL import，约束 `pillow<11.3`。 |
| pyjwt | 2.11.0 | bk-monitor-base 传递依赖 | 2.15.0 | 与 bkmonitor 同一批 JWT 公告。目录内未见 `import jwt`。 |
| aiohttp | 3.11.18 | bkmonitor 传递依赖 | 3.14.4 | 严重项 CVE-2026-34520（响应头注入）。源码未见 `import aiohttp`。 |
| anyio | 4.9.0 | bkmonitor 传递依赖 | 4.14.2 | CVE-2026-63374，TLS 主机名 IDNA 编码可能导致证书欺骗。源码未见直接 import。 |
| langchain-core | 0.3.75 | bkmonitor 默认组 aidev | 0.3.85（1.2 线为 1.2.22） | 业务代码 import 的是 langchain，不是 langchain_core。默认 `uv sync` 会装上 aidev。 |

同一档里还有高危传递依赖：msgpack（bkmonitor 1.1.0、base 1.1.2，建议 1.2.3）、pyasn1（bkmonitor 0.6.1、base 0.6.2，建议 0.6.5）、oauthlib（bkmonitor 3.2.2、base 3.3.1，建议 4.0.0）、protobuf（bkmonitor 3.19.5、bklog 3.20.3，业务代码未见 `google.protobuf`，OpenTelemetry 会用到；全部公告到 5.29.6）、python-multipart 0.0.20（建议 0.0.31）、starlette 0.47.3（建议 1.3.1）、langsmith 0.3.45（建议 0.8.18）、orjson 3.10.18（建议 3.11.6）、mcp 1.12.4（建议 1.30.0，源码未见 PyPI 包的 import）。pyasn1 与 oauthlib 这次新增的公告见结论。protobuf、starlette、python-multipart 的修复都跨主版本或跨较大次版本，升级前要看调用方兼容性。

## 只在开发或测试依赖里的问题

| 包 | 版本 | 环境 | 最高等级 | 说明 |
| --- | --- | --- | --- | --- |
| virtualenv | 15.2 | bklog `requirements_dev.txt` | 严重 | 20 条公告，一次清掉要到 21.14.9。不进入生产镜像的话风险限于开发机和 CI。 |
| virtualenv | 20.30.0 / 21.2.0 | bkmonitor / bk-monitor-base 开发组 | 高 | 建议 21.14.9。bkmonitor 的 20.30.0 在同一主版本上还有 20.36.1，但高危修复已经在 21.x。 |
| filelock | 3.18.0 / 3.25.1 | 随开发依赖进入锁文件 | 中 / 高 | 3.18.0 命中 CVE-2026-112909、CVE-2026-112910，覆盖版本 4.2.1。3.25.1 还有高危 CVE-2026-112940，同样要到 4.2.1。两处都只出现在开发测试依赖里。 |
| pytest | 7.0.1 / 8.3.4 | base / bkmonitor 测试组 | 中 | 建议 9.0.3。只在测试代码里 import。 |

## 三套环境版本不一致

同一包在不同子项目里版本不同，修复时需要一起看。

| 包 | bkmonitor | bk-monitor-base | bklog | 覆盖已知公告的版本 |
| --- | --- | --- | --- | --- |
| `django` | 4.2.27（严重） | 4.2.29（严重） | 4.2.22（严重） | 4.2.30；GeoDjango 的 CVE-2026-15307 为 5.2.17 |
| `pyjwt` | 2.10.1（严重） | 2.11.0（严重） | 未钉版本，中间件有引用 | 2.15.0 |
| `djangorestframework` | 3.15.1（高） | 3.15.2（高） | 3.15.2（高） | 3.18.2 |
| `pillow` | 11.2.1（严重） | 11.2.1（严重） | 未钉版本，水印代码有引用 | 13.0.0 |
| `urllib3` | 1.26.20（高） | 1.26.20（高） | 1.26.19（高） | 2.8.0 |
| `certifi` | 2025.1.31（严重） | 2026.2.25（严重） | — | 2026.10.18 |
| `kafka-python` | 1.4.6（高） | 1.4.6（高） | 2.0.2（高） | 2.3.2 |
| `cryptography` | 44.0.2（高） | 46.0.5（严重） | — | 50.0.0 |
| `ujson` | 5.7.0（高） | — | 5.9.0（高） | 5.13.0 |
| `mistune` | 0.8.4（高） | — | 3.0.2（高） | 3.3.0 |
| `sqlparse` | 0.5.3（高） | 0.5.5（高） | — | 0.6.0 |
| `protobuf` | 3.19.5（高） | — | 3.20.3（高） | 5.29.6 |
| `langchain` | 0.3.27（高） | — | 0.3.27（高） | 0.3.30 覆盖高危；全部公告到 1.3.9 |
| `langchain-core` | 0.3.75（严重） | — | 0.3.75（严重） | 0.3.85 覆盖严重项；CVE-2026-34070 为 1.2.22 |
| `requests` | 2.32.5（中） | 2.32.5（中） | 2.32.5（中） | 2.33.0 |
| `setuptools` | 79.0.1（中） | 82.0.1（中） | 80.9.0（中） | 84.1.0 |
| `idna` | 3.10（中） | 3.11（中） | — | 3.15 |
| `opentelemetry-api` | 1.11.1（中） | — | 1.24.0（中） | 1.45.1 |
| `orjson` | 3.10.18（高） | — | — | 3.11.6 |
| `filelock` | 3.18.0（中，仅开发） | 3.25.1（高，仅开发） | — | 4.2.1 |
| `pyasn1` | 0.6.1（高） | 0.6.2（高） | 未钉版本 | 0.6.5 |
| `oauthlib` | 3.2.2（高） | 3.3.1（高） | 未钉版本 | 4.0.0 |

Django 这一行的升级目标是 4.2.30。4.2 是当前发布线，4.2.30 能清掉这条线上已经有修复的严重和高危。protobuf 的 5.29.6、cryptography 的 50.0.0 是一次清掉该版本上全部已知公告的上界，最小安全升级可能更低，升级前要看调用方。

## 声明约束和修复版本冲突

| 位置 | 当前约束 | 冲突 |
| --- | --- | --- |
| `bk-monitor-base/pyproject.toml` | `pillow<11.3` | 严重公告的修复版本是 13.0.0 |
| `bkmonitor/pyproject.toml` | `pillow==11.2.1` | 同上 |
| `bkmonitor/pyproject.toml` | `mistune<3` | bkmonitor 锁的是 0.8.4。3.3.0 才能清掉 bklog 正在使用的 3.0.2 上的高危。version-log 注释写明需要 3 以下 |
| `bklog/requirements_dev.txt` | `mistune==0.8.4` | 与运行时 `mistune==3.0.2` 冲突。一起安装时会降到同样有高危的 0.8.4 |
| `bk-monitor-base/pyproject.toml` | `djangorestframework<3.16.0` | 高危修复在 3.18.2 |
| `bkmonitor/pyproject.toml` | `django==4.2.27` | 4.2 线建议 4.2.30 |
| `bklog/requirements.txt` | `Django==4.2.22` | 同上，并且比另外两处少了 4.2.24 到 4.2.29 之间的修复 |
| `bklog/requirements.txt` | 未钉 Pillow、PyJWT、oauthlib、pyasn1 | 水印和网关中间件已经引用 Pillow、PyJWT。kubernetes 客户端会带上 oauthlib，版本随传递依赖浮动，这次没有可查询的精确版本 |

## 受影响版本索引

每一行是一个子项目里的一个版本。公告列顺序为严重/高/中/低。「覆盖版本」是这些公告各自修复版本里的最高者，用来一次清掉本行列出的已知问题；它不一定是该发布线上的最小升级。

| 子项目 | 包 | 版本 | 依赖角色 | 源码 | 最高 | 公告 | 覆盖版本 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bk-monitor-base | `certifi` | 2026.2.25 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/0/0/0 | 2026.10.18 |
| bk-monitor-base | `cryptography` | 46.0.5 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/3/2/0 | 50.0.0 |
| bk-monitor-base | `django` | 4.2.29 | 运行时 / 运行时直接 | 业务代码引用 | 严重 | 1/3/4/5 | 5.2.17 |
| bk-monitor-base | `pillow` | 11.2.1 | 运行时 / 运行时直接 | 源码未见引用 | 严重 | 5/38/15/0 | 13.0.0 |
| bk-monitor-base | `pyjwt` | 2.11.0 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/6/9/1 | 2.15.0 |
| bklog | `django` | 4.2.22 | 运行时 / 运行时直接 | 业务代码引用 | 严重 | 3/11/7/7 | 5.2.17 |
| bklog | `langchain-core` | 0.3.75 | 运行时 / 运行时直接 | 业务代码引用 | 严重 | 1/3/1/1 | 1.2.22 |
| bklog | `virtualenv` | 15.2 | 开发测试 / 开发测试直接 | 源码未见引用 | 严重 | 1/9/7/3 | 21.14.9 |
| bkmonitor | `aiohttp` | 3.11.18 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/18/16/6 | 3.14.4 |
| bkmonitor | `anyio` | 4.9.0 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/0/1/0 | 4.14.2 |
| bkmonitor | `certifi` | 2025.1.31 | 运行时 / 传递 | 源码未见引用 | 严重 | 1/0/0/0 | 2026.10.18 |
| bkmonitor | `django` | 4.2.27 | 运行时 / 运行时直接 | 业务代码引用 | 严重 | 1/8/6/6 | 5.2.17 |
| bkmonitor | `langchain-core` | 0.3.75 | 运行时 / 默认组直接 | 源码未见引用 | 严重 | 1/3/1/1 | 1.2.22 |
| bkmonitor | `pillow` | 11.2.1 | 运行时 / 运行时直接 | 业务代码引用 | 严重 | 5/38/15/0 | 13.0.0 |
| bkmonitor | `pyjwt` | 2.10.1 | 运行时 / 传递 | 业务代码引用 | 严重 | 1/7/8/1 | 2.15.0 |
| bk-monitor-base | `djangorestframework` | 3.15.2 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/2/0 | 3.18.2 |
| bk-monitor-base | `filelock` | 3.25.1 | 开发测试 / 传递 | 源码未见引用 | 高 | 0/1/6/2 | 4.2.1 |
| bk-monitor-base | `kafka-python` | 1.4.6 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/2/0/0 | 2.3.2 |
| bk-monitor-base | `msgpack` | 1.1.2 | 运行时 / 传递 | 源码未见引用 | 高 | 0/2/0/0 | 1.2.3 |
| bk-monitor-base | `oauthlib` | 3.3.1 | 运行时 / 传递 | 源码未见引用 | 高 | 0/2/2/0 | 4.0.0 |
| bk-monitor-base | `pyasn1` | 0.6.2 | 运行时 / 传递 | 源码未见引用 | 高 | 0/8/0/0 | 0.6.5 |
| bk-monitor-base | `sqlparse` | 0.5.5 | 运行时 / 传递 | 源码未见引用 | 高 | 0/3/2/0 | 0.6.0 |
| bk-monitor-base | `urllib3` | 1.26.20 | 运行时 / 传递 | 业务代码引用 | 高 | 0/6/1/0 | 2.8.0 |
| bk-monitor-base | `virtualenv` | 21.2.0 | 开发测试 / 传递 | 源码未见引用 | 高 | 0/10/6/3 | 21.14.9 |
| bklog | `djangorestframework` | 3.15.2 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/2/0 | 3.18.2 |
| bklog | `kafka-python` | 2.0.2 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/2/0/0 | 2.3.2 |
| bklog | `langchain` | 0.3.27 | 运行时 / 运行时直接 | 源码未见引用 | 高 | 0/1/1/0 | 1.3.9 |
| bklog | `markdown` | 3.3 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/1/0/0 | 3.8.1 |
| bklog | `mistune` | 3.0.2 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/6/11/0 | 3.3.0 |
| bklog | `protobuf` | 3.20.3 | 运行时 / 运行时直接 | 源码未见引用 | 高 | 0/2/0/0 | 5.29.6 |
| bklog | `ujson` | 5.9.0 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/1/0 | 5.13.0 |
| bklog | `urllib3` | 1.26.19 | 运行时 / 运行时直接 | 仅测试代码引用 | 高 | 0/6/1/0 | 2.8.0 |
| bkmonitor | `cryptography` | 44.0.2 | 运行时 / 传递 | 仅测试代码引用 | 高 | 0/4/1/0 | 50.0.0 |
| bkmonitor | `djangorestframework` | 3.15.1 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/3/0 | 3.18.2 |
| bkmonitor | `dnspython` | 2.6.1 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/1/0/0 | 2.9.0 |
| bkmonitor | `kafka-python` | 1.4.6 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/2/0/0 | 2.3.2 |
| bkmonitor | `langchain` | 0.3.27 | 运行时 / 默认组直接 | 业务代码引用 | 高 | 0/1/1/0 | 1.3.9 |
| bkmonitor | `langsmith` | 0.3.45 | 运行时 / 传递 | 源码未见引用 | 高 | 0/2/1/0 | 0.8.18 |
| bkmonitor | `mako` | 1.3.10 | 运行时 / 传递 | 业务代码引用 | 高 | 0/2/1/0 | 1.4.2 |
| bkmonitor | `mcp` | 1.12.4 | 运行时 / 传递 | 源码未见引用 | 高 | 0/4/3/0 | 1.30.0 |
| bkmonitor | `mistune` | 0.8.4 | 运行时 / 运行时直接 | 源码未见引用 | 高 | 0/5/11/0 | 3.3.0 |
| bkmonitor | `msgpack` | 1.1.0 | 运行时 / 传递 | 源码未见引用 | 高 | 0/2/0/0 | 1.2.3 |
| bkmonitor | `oauthlib` | 3.2.2 | 运行时 / 传递 | 源码未见引用 | 高 | 0/1/2/0 | 4.0.0 |
| bkmonitor | `opentelemetry-instrumentation` | 0.30b1 | 运行时 / 传递 | 业务代码引用 | 高 | 0/1/0/0 | 0.41b0 |
| bkmonitor | `orjson` | 3.10.18 | 运行时 / 传递 | 源码未见引用 | 高 | 0/1/0/0 | 3.11.6 |
| bkmonitor | `protobuf` | 3.19.5 | 运行时 / 运行时直接 | 源码未见引用 | 高 | 0/2/0/0 | 5.29.6 |
| bkmonitor | `pyasn1` | 0.6.1 | 运行时 / 传递 | 源码未见引用 | 高 | 0/9/0/0 | 0.6.5 |
| bkmonitor | `python-multipart` | 0.0.20 | 运行时 / 传递 | 源码未见引用 | 高 | 0/3/1/3 | 0.0.31 |
| bkmonitor | `sqlparse` | 0.5.3 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/3/0 | 0.6.0 |
| bkmonitor | `starlette` | 0.47.3 | 运行时 / 传递 | 源码未见引用 | 高 | 0/3/3/0 | 1.3.1 |
| bkmonitor | `ujson` | 5.7.0 | 运行时 / 运行时直接 | 业务代码引用 | 高 | 0/3/1/0 | 5.13.0 |
| bkmonitor | `urllib3` | 1.26.20 | 运行时 / 传递 | 业务代码引用 | 高 | 0/6/1/0 | 2.8.0 |
| bkmonitor | `virtualenv` | 20.30.0 | 开发测试 / 传递 | 源码未见引用 | 高 | 0/10/7/3 | 21.14.9 |
| bk-monitor-base | `idna` | 3.11 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/0 | 3.15 |
| bk-monitor-base | `pytest` | 7.0.1 | 开发测试 / 开发测试直接 | 仅测试代码引用 | 中 | 0/0/1/0 | 9.0.3 |
| bk-monitor-base | `requests` | 2.32.5 | 运行时 / 传递 | 业务代码引用 | 中 | 0/0/1/0 | 2.33.0 |
| bk-monitor-base | `setuptools` | 82.0.1 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/1 | 84.1.0 |
| bklog | `opentelemetry-api` | 1.24.0 | 运行时 / 运行时直接 | 业务代码引用 | 中 | 0/0/1/0 | 1.45.1 |
| bklog | `requests` | 2.32.5 | 运行时 / 运行时直接 | 业务代码引用 | 中 | 0/0/1/0 | 2.33.0 |
| bklog | `setuptools` | 80.9.0 | 运行时 / 运行时直接 | 源码未见引用 | 中 | 0/0/1/1 | 84.1.0 |
| bkmonitor | `filelock` | 3.18.0 | 开发测试 / 传递 | 源码未见引用 | 中 | 0/0/4/0 | 4.2.1 |
| bkmonitor | `h2` | 4.2.0 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/2/0 | 4.4.1 |
| bkmonitor | `hpack` | 4.1.0 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/0 | 4.2.0 |
| bkmonitor | `idna` | 3.10 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/0 | 3.15 |
| bkmonitor | `langchain-text-splitters` | 0.3.11 | 运行时 / 默认组直接 | 源码未见引用 | 中 | 0/0/1/0 | 1.1.2 |
| bkmonitor | `marshmallow` | 3.26.1 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/0 | 3.26.2 |
| bkmonitor | `opentelemetry-api` | 1.11.1 | 运行时 / 运行时直接 | 业务代码引用 | 中 | 0/0/1/0 | 1.45.1 |
| bkmonitor | `pytest` | 8.3.4 | 开发测试 / 开发测试直接 | 仅测试代码引用 | 中 | 0/0/1/0 | 9.0.3 |
| bkmonitor | `python-dotenv` | 0.21.1 | 运行时 / 运行时直接 | 业务代码引用 | 中 | 0/0/1/0 | 1.2.2 |
| bkmonitor | `requests` | 2.32.5 | 运行时 / 传递 | 业务代码引用 | 中 | 0/0/1/0 | 2.33.0 |
| bkmonitor | `setuptools` | 79.0.1 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/1/1 | 84.1.0 |
| bkmonitor | `werkzeug` | 3.1.3 | 运行时 / 传递 | 源码未见引用 | 中 | 0/0/4/0 | 3.1.9 |
| bk-monitor-base | `pygments` | 2.19.2 | 默认组 / 传递 | 源码未见引用 | 低 | 0/0/0/1 | 2.20.0 |
| bkmonitor | `langchain-openai` | 0.3.22 | 运行时 / 默认组直接 | 源码未见引用 | 低 | 0/0/0/1 | 1.1.14 |
| bkmonitor | `pygments` | 2.19.1 | 运行时 / 传递 | 源码未见引用 | 低 | 0/0/0/1 | 2.20.0 |

## 业务直接调用时，严重与高危公告

只列出最高等级达到严重、且业务代码有 import 的包，表内收到严重和高危。中低危见上一节索引。这六处的公告编号和 2026-10-29 相同。

### bklog `django==4.2.22`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.8 | CVE-2025-59681 | 4.2.25 | 2025-10-01 | Django vulnerable to SQL injection in column aliases |
| 严重 | 9.8 | CVE-2026-4277 | 4.2.30 | 2026-04-07 | Django vulnerable to privilege abuse in GenericInlineModelAdmin |
| 严重 | 9.1 | CVE-2025-64459 | 4.2.26 | 2025-11-05 | Django vulnerable to SQL injection via _connector keyword argument in QuerySet and Q objects. |
| 高 | 8.8 | CVE-2026-15307 | 5.2.17 | 2026-08-04 | Django GeoDjango spatial lookups allow file writes and outbound requests through GDAL raster parsing |
| 高 | 8.1 | CVE-2025-57833 | 4.2.24 | 2025-09-03 | Django is subject to SQL injection through its column aliases |
| 高 | 7.5 | CVE-2025-14550 | 4.2.28 | 2026-02-03 | Django has Inefficient Algorithmic Complexity |
| 高 | 7.5 | CVE-2025-64458 | 4.2.26 | 2025-11-05 | Django has a denial-of-service vulnerability in HttpResponseRedirect and HttpResponsePermanentRedirect on Windows |
| 高 | 7.5 | CVE-2025-64460 | 4.2.27 | 2025-12-02 | Django is vulnerable to DoS via XML serializer text extraction |
| 高 | 7.5 | CVE-2026-1285 | 4.2.28 | 2026-02-03 | Django has Inefficient Algorithmic Complexity |
| 高 | 7.5 | CVE-2026-25673 | 4.2.29 | 2026-03-03 | Django vulnerable to Uncontrolled Resource Consumption |
| 高 | 7.5 | CVE-2026-33034 | 4.2.30 | 2026-04-07 | Django: SGI requests with a missing or understated `Content-Length` header could bypass the `DATA_UPLOAD_MAX_MEMORY_SIZE` limit |
| 高 | 7.5 | CVE-2026-3902 | 4.2.30 | 2026-04-07 | Django vulnerable to ASGI header spoofing via underscore/hyphen conflation |
| 高 | 5.4 | CVE-2026-1207 | 4.2.28 | 2026-02-03 | Django has an SQL Injection issue |
| 高 | 5.4 | CVE-2026-1287 | 4.2.28 | 2026-02-03 | Django has an SQL Injection issue |

### bkmonitor `django==4.2.27`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.8 | CVE-2026-4277 | 4.2.30 | 2026-04-07 | Django vulnerable to privilege abuse in GenericInlineModelAdmin |
| 高 | 8.8 | CVE-2026-15307 | 5.2.17 | 2026-08-04 | Django GeoDjango spatial lookups allow file writes and outbound requests through GDAL raster parsing |
| 高 | 7.5 | CVE-2025-14550 | 4.2.28 | 2026-02-03 | Django has Inefficient Algorithmic Complexity |
| 高 | 7.5 | CVE-2026-1285 | 4.2.28 | 2026-02-03 | Django has Inefficient Algorithmic Complexity |
| 高 | 7.5 | CVE-2026-25673 | 4.2.29 | 2026-03-03 | Django vulnerable to Uncontrolled Resource Consumption |
| 高 | 7.5 | CVE-2026-33034 | 4.2.30 | 2026-04-07 | Django: SGI requests with a missing or understated `Content-Length` header could bypass the `DATA_UPLOAD_MAX_MEMORY_SIZE` limit |
| 高 | 7.5 | CVE-2026-3902 | 4.2.30 | 2026-04-07 | Django vulnerable to ASGI header spoofing via underscore/hyphen conflation |
| 高 | 5.4 | CVE-2026-1207 | 4.2.28 | 2026-02-03 | Django has an SQL Injection issue |
| 高 | 5.4 | CVE-2026-1287 | 4.2.28 | 2026-02-03 | Django has an SQL Injection issue |

### bk-monitor-base `django==4.2.29`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.8 | CVE-2026-4277 | 4.2.30 | 2026-04-07 | Django vulnerable to privilege abuse in GenericInlineModelAdmin |
| 高 | 8.8 | CVE-2026-15307 | 5.2.17 | 2026-08-04 | Django GeoDjango spatial lookups allow file writes and outbound requests through GDAL raster parsing |
| 高 | 7.5 | CVE-2026-33034 | 4.2.30 | 2026-04-07 | Django: SGI requests with a missing or understated `Content-Length` header could bypass the `DATA_UPLOAD_MAX_MEMORY_SIZE` limit |
| 高 | 7.5 | CVE-2026-3902 | 4.2.30 | 2026-04-07 | Django vulnerable to ASGI header spoofing via underscore/hyphen conflation |

### bkmonitor `pyjwt==2.10.1`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.1 | CVE-2026-102268 | 2.14.0 | 2026-09-29 | PyJWT: Asymmetric-PEM detection bypass: whitespace/line-ending-mutated public keys skip the HS/asymmetric confusion guard |
| 高 | 8.2 | CVE-2026-102275 | 2.15.0 | 2026-09-28 | PyJWT accepts inconsistent OKP x/d JWKs, causing public/private key identity confusion |
| 高 | 7.5 | CVE-2026-32597 | 2.12.0 | 2026-03-13 | PyJWT accepts unknown `crit` header extensions |
| 高 | 7.4 | CVE-2026-102267 | 2.14.0 | 2026-09-29 | PyJWT: PyJWKClient follows redirects when fetching JWKS |
| 高 | 7.4 | CVE-2026-102271 | 2.14.0 | 2026-09-29 | PyJWT: Public keys in DER form are accepted as HMAC secrets, bypassing the CVE-2022-29217 guard |
| 高 | 7.4 | CVE-2026-48526 | 2.13.0 | 2026-05-28 | PyJWT: Public-key JWK accepted as HMAC secret enables forged HS256 tokens when mixed families are allowed |
| 高 | 7.4 | GHSA-pxh4-856f-4h89 | 2.14.0 | 2026-10-22 | PyJWT: HS256/384/512 verify accepts empty HMAC key via oct JWK (PyJWK/PyJWKClient) enabling token forgery |
| 高 | 7.0 | CVE-2025-45768 | — | 2025-07-31 | pyjwt v2.10.1 was discovered to contain weak encryption. NOTE: this is disputed by the Supplier because the key length is chosen by the application that uses the library (admitt... |

### bkmonitor `pillow==11.2.1`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.8 | CVE-2026-112398 | 13.0.0 | 2026-10-19 | Pillow: Heap buffer overflow in FlashPix (FPX) JPEG decoding leads to code execution |
| 严重 | 9.8 | CVE-2026-112403 | 13.0.0 | 2026-10-19 | Pillow: Heap buffer overflow in ImagingJpegDecode |
| 严重 | 9.8 | CVE-2026-96639 | 13.0.0 | 2026-10-21 | Pillow multi-frame loaders can reuse stale native image storage after mode transitions |
| 严重 | — | CVE-2026-112393 | 13.0.0 | 2026-10-21 | Pillow: Heap buffer overflow in _tiffWriteProc when saving TIFF to BytesIO |
| 严重 | — | CVE-2026-112900 | 13.0.0 | 2026-10-21 | Pillow: Argument Injection in Ghostscript call, potentially leading into RCE |
| 高 | 8.2 | CVE-2026-112394 | 13.0.0 | 2026-10-19 | Pillow: P;2L and P;4L decoders may read 1 to 3 bytes past the passed buffer size |
| 高 | 8.2 | CVE-2026-59197 | 12.3.0 | 2026-07-14 | Pillow: Heap out-of-bounds write in `ImageFilter.RankFilter` via integer overflow in `ImagingExpand` |
| 高 | 8.1 | CVE-2026-96644 | 13.0.0 | 2026-10-21 | Pillow: Heap over-read in WMF/EMF rendering via 16-bit dimension truncation (Windows builds) |
| 高 | 8.1 | GHSA-78g4-xqwv-q3g8 | 13.0.0 | 2026-10-22 | Pillow: Bundled libopenjp2 2.5.4 in all wheels since 11.1.0 carries OSV-2025-219 heap-buffer-overflow write reachable from Image.open().load() |
| 高 | 7.8 | CVE-2026-42311 | 12.2.0 | 2026-05-04 | Pillow has an OOB Write with Invalid PSD Tile Extents (Integer Overflow) |
| 高 | 7.5 | CVE-2026-112392 | 13.0.0 | 2026-10-19 | Pillow: NULL dereference in ImagingExpand via rank filters on zero-size images |
| 高 | 7.5 | CVE-2026-112397 | 13.0.0 | 2026-10-19 | Pillow: Out-of-bounds access in _imagingmorph on a zero-width image |
| 高 | 7.5 | CVE-2026-112402 | 13.0.0 | 2026-10-19 | Pillow: Double free in ImagingScaleAffine on calloc failure via Image.transform |
| 高 | 7.5 | CVE-2026-112901 | 13.0.0 | 2026-10-19 | Pillow: ReDoS in XbmImagePlugin: 512-byte file stalls Image.open() for minutes |
| 高 | 7.5 | CVE-2026-25990 | 12.1.1 | 2026-02-11 | Pillow affected by out-of-bounds write when loading PSD images |
| 高 | 7.5 | CVE-2026-40192 | 12.2.0 | 2026-04-13 | FITS GZIP decompression bomb in Pillow |
| 高 | 7.5 | CVE-2026-54059 | 12.3.0 | 2026-07-06 | Pillow `PcfFontFile._load_bitmaps()`: `Image.frombytes()` called without `_decompression_bomb_check()` — bomb protection bypass via PCF font loading |
| 高 | 7.5 | CVE-2026-54060 | 12.3.0 | 2026-07-06 | Pillow: `FontFile.compile()`: `Image.new()` called without `_decompression_bomb_check()` |
| 高 | 7.5 | CVE-2026-55379 | 12.3.0 | 2026-07-06 | Pillow `BdfFontFile`: `Image.new()` called without `_decompression_bomb_check()` — bomb protection bypass via font loading |
| 高 | 7.5 | CVE-2026-55380 | 12.3.0 | 2026-07-06 | Pillow `GdImageFile._open()`: image dimensions accepted without `_decompression_bomb_check()` |
| 高 | 7.5 | CVE-2026-59199 | 12.3.0 | 2026-07-14 | Pillow: Heap out-of-bounds write `Image.paste()` / `Image.crop()` via signed coordinate overflow |
| 高 | 7.5 | CVE-2026-59200 | 12.3.0 | 2026-07-20 | Pillow: Decompression Bomb DoS via PdfParser.PdfStream.decode() |
| 高 | 7.5 | CVE-2026-59205 | 12.3.0 | 2026-07-14 | Pillow: Controlled heap out-of-bounds write in Pillow `ImageCmsTransform.apply()` via output mode mismatch |
| 高 | 7.1 | CVE-2025-48379 | 11.3.0 | 2025-07-01 | Pillow vulnerability can cause write buffer overflow on BCn encoding |
| 高 | 7.1 | CVE-2026-112896 | 13.0.0 | 2026-10-19 | Pillow: TIFF encoder ColorMap plane-size mismatch causes a heap out-of-bounds read |
| 高 | 6.5 | CVE-2026-96637 | 13.0.0 | 2026-10-21 | Pillow: Decompression bomb check bypass in SpiderImagePlugin.seek() leads to unbounded allocation DoS |
| 高 | 6.5 | CVE-2026-96642 | 13.0.0 | 2026-10-21 | Pillow: TarIO negative size field causes infinite CPU-spin loop |
| 高 | 6.5 | CVE-2026-96643 | 13.0.0 | 2026-10-21 | Pillow: PNG eXIf chunk makes EXIF parsing run in quadratic time |
| 高 | — | CVE-2026-112390 | 13.0.0 | 2026-10-21 | Pillow: Infinite loop in MIC n_frames when the embedded TIFF |
| 高 | — | CVE-2026-112399 | 13.0.0 | 2026-10-21 | Pillow: APNG background disposal allocates full canvas before decompression bomb check |
| 高 | — | CVE-2026-112400 | 13.0.0 | 2026-10-20 | Pillow: GIF seek keeps rejected size after DecompressionBombError, allowing DoS |
| 高 | — | CVE-2026-112404 | 13.0.0 | 2026-10-20 | Pillow: OOB read in TiffDecode.c tile and RGBA paths leaks heap memory into pixels |
| 高 | — | CVE-2026-112406 | 13.0.0 | 2026-10-21 | Pillow: Infinite loop in PdfParser.rewrite_pages on page tree Parent cycle |
| 高 | — | CVE-2026-112892 | 13.0.0 | 2026-10-21 | Pillow: MSP RLE decoder expands a tiny file into unbounded memory |
| 高 | — | CVE-2026-112893 | 13.0.0 | 2026-10-21 | Pillow: Invalid free in FreeType glyph rendering when a stroker is active |
| 高 | — | CVE-2026-112894 | 13.0.0 | 2026-10-21 | Pillow: Quadratic-time DoS in PDF save_all (PdfParser.next_object_id) |
| 高 | — | CVE-2026-112895 | 13.0.0 | 2026-10-20 | Pillow: Unbounded recursion parsing a PDF page tree or trailer chain (incomplete fix for CVE-2026-42310) |
| 高 | — | CVE-2026-112897 | 13.0.0 | 2026-10-20 | Pillow: TiffDecode returns uninitialized memory as pixels for short JPEG strips |
| 高 | — | CVE-2026-112902 | 13.0.0 | 2026-10-21 | Pillow: Memory disclosure and segfault in libtiff encoder via crafted TIFF tags |
| 高 | — | CVE-2026-54058 | 12.3.0 | 2026-07-20 | Pillow: Out-of-bounds read via attacker-controlled row stride on Pillow's mmap path (McIdas AREA files) |
| 高 | — | CVE-2026-59204 | 12.3.0 | 2026-07-20 | Pillow JPEG2000 tiled decode retains a growing scratch buffer and can be used for denial of service |
| 高 | — | CVE-2026-96640 | 13.0.0 | 2026-10-22 | Pillow PDF append accepts malformed shared page-tree DAG causing resource exhaustion |
| 高 | — | CVE-2026-96778 | 13.0.0 | 2026-10-22 | Pillow: Heap buffer overflow writing JPEG comment after ICC profile fills buffer |

### bklog `langchain-core==0.3.75`

| 等级 | CVSS | 编号 | 修复版本 | 公布 | 摘要 |
| --- | ---: | --- | --- | --- | --- |
| 严重 | 9.3 | CVE-2025-68664 | 0.3.81 | 2025-12-23 | LangChain serialization injection vulnerability enables secret extraction in dumps/loads APIs |
| 高 | 8.2 | CVE-2026-44843 | 0.3.85 | 2026-05-08 | LangChain vulnerable to unsafe deserialization of attacker-controlled objects through overly broad `load()` allowlists |
| 高 | 7.5 | CVE-2026-34070 | 1.2.22 | 2026-03-27 | LangChain Core has Path Traversal vulnerabilites in legacy `load_prompt` functions |
| 高 | — | CVE-2025-65106 | 0.3.80 | 2025-11-20 | LangChain Vulnerable to Template Injection via Attribute Access in Prompt Templates |


## 局限

- bklog 没有锁文件。`requirements.txt` 里没有写的传递依赖（例如水印用到的 Pillow、网关中间件用到的 PyJWT，以及 kubernetes 带上的 oauthlib、pyasn1）没有版本，也没有查 OSV。
- 静态 import 看不到动态导入、入口点和只写在 Django `INSTALLED_APPS` 字符串里的应用。传递依赖标成「源码未见引用」时，仍可能在运行时被加载。
- 命中公告只说明当前版本落在受影响范围内，没有确认漏洞函数一定被调用，也没有做利用验证。
- OSV 的 `querybatch` 只返回编号，严重程度和修复版本来自随后拉取的公告全文。CVSS 只解析了 v3 向量；没有 v3 时使用 GHSA 的定性等级。只有 CVSS v4 的记录不会折算成分数。CVE-2026-118669 属于这种情况。
- 与 2026-10-29 相比，两份锁文件和优先升级项没有变化。bklog 把 `bk-crypto-python-sdk` 升到 4.1.1，并钉上 `bk-kms-sdk` 1.0.0 与 `pycryptodome` 3.23.0，这三项没有已知公告。公告侧的增量是 pyasn1 的 4 条高危，以及 oauthlib 的 CVE-2026-118669；后者把 bkmonitor 3.2.2 的最高等级从中危抬到高危。

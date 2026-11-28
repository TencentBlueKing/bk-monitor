# Python 依赖安全审计报告

- 扫描日期：2026-10-27
- 漏洞数据：OSV.dev 上的 PyPI 公告（GitHub Advisory Database 的 GHSA，以及 PyPA Advisory Database 的 PYSEC）
- 匹配方式：按锁定或声明的精确版本查询。同一 CVE 的 GHSA 与 PYSEC 已合并
- 严重级别：优先采用 GitHub Advisory 的定性等级；没有定性等级时，用 CVSS v3 基础分换算（≥9.0 严重，≥7.0 高，≥4.0 中，>0 低）
- 使用情况：在各组件源码中检索生产代码的 `import` / `from`。已排除虚拟环境、迁移、静态资源和测试文件（含 `tests.py`、`conftest.py`）

本报告只判断依赖版本是否落在已公开公告的影响范围内，以及仓库源码是否直接引用对应模块。它不证明某条公告在部署环境里一定可被触发。

## 结论

三个组件合计查询了 **439** 个不重复的「包名 + 版本」。其中 **66** 个版本落在已知公告内，对应 **42** 个包、**285** 条按包去重的公告。同一公告出现在多个组件时分开计数，展开后为 **533** 条记录。

按包去重后的严重级别：

| 级别 | 公告数 |
| --- | ---: |
| 严重 | 14 |
| 高 | 137 |
| 中 | 107 |
| 低 | 27 |

42 个受影响包里，**16** 个能在生产代码中找到直接引用，**1** 个只出现在测试代码，**25** 个没有直接 import。没有直接 import 不表示运行时不会加载：`requests` 会带上 `urllib3`、`certifi`、`idna`，PyJWT 和 `blue-krill` 在部分算法下会加载 `cryptography`。

建议先处理下面这些组合：版本受影响，并且生产路径会加载该库。

1. **Django**：三个组件都在 4.2 线，且业务代码大量引用。`bklog` 停在 4.2.22，仍包含已在 4.2.25 / 4.2.26 修复的 SQL 注入公告。三个组件都低于 4.2.30。4.2 线上的统一目标是 **4.2.30**。
2. **PyJWT**：`bkmonitor` 鉴权中间件直接调用 `jwt.decode`。当前 2.10.1 / 2.11.0，建议升到 **2.15.0**。
3. **djangorestframework**：三个组件都在用。`bkmonitor` 的 3.15.1 还包含 3.15.2 已修复的 XSS。高危公告的修复版本是 **3.18.2**。`bk-monitor-base` 目前约束 `<3.16.0`，升级前要先放宽约束。
4. **kafka-python**：告警与元数据链路直接创建 Consumer / AdminClient。1.4.6 与 2.0.2 的两条拒绝服务公告都在 **2.3.2** 修复。
5. **urllib3 1.26**：1.26 线没有后续安全版本，已知修复都在 2.6.0 至 **2.8.0**。`requests` 与 Elasticsearch 工具代码会用到它。升级到 2.x 前要确认 elasticsearch 5/6/7 客户端的兼容性。
6. **certifi**：没有业务代码直接 import，但 `requests` 默认使用它的 CA 包。2025.1.31 与 2026.2.25 都受 GHSA-6q48-6c7w-9gw2 影响（内置 emSign 根证书的中间 CA 密钥问题），修复版本为 **2026.10.18**。
7. **Pillow 11.2.1**：公告数量最多（严重 5、高 36、中 17），清除全部公告需要 **13.0.0**。当前生产代码只在内存里绘制文字水印并输出 PNG，不解码外部 TIFF、JPEG、PDF、PSD。解码类缺陷默认走不到这条路径，库本身仍随进程加载。
8. **sqlparse、ujson、mistune、mako、markdown、OpenTelemetry instrumentation**：生产代码有直接引用，修复版本见下文。

仅开发环境安装的 `virtualenv`、`filelock`、`pytest` 不进入线上进程，优先级低于运行时依赖。`bklog/requirements_dev.txt` 仍固定 `virtualenv==15.2`，这条线上有严重公告。

## 扫描范围

| 组件 | 清单 | 解析方式 | 包数量 | 构成 |
| --- | --- | --- | --- | --- |
| bkmonitor | `bkmonitor/uv.lock` | uv 锁定，含传递依赖 | 293 | 直接运行时 91，传递运行时 165，直接开发 20，传递开发 15，本地包 1（`bk-monitor-base`）。`tomli` 未归入上述闭包 |
| bk-monitor-base | `bk-monitor-base/uv.lock` | uv 锁定，含传递依赖 | 153 | 直接运行时 39，传递运行时 62，直接开发 16，传递开发 36 |
| bklog | `bklog/requirements.txt`、`requirements_dev.txt` | 只扫描声明的直接版本 | 91 | 直接运行时 82，直接开发 9 |

`bklog` 没有锁文件，本次看不到它的传递依赖。`aiohttp`、`cryptography`、`pyjwt`、`certifi` 等如果被 `blueapps` 或其他直接依赖拉入，不会出现在 `bklog` 的结果里。

Python 版本：`bkmonitor` 与 `bk-monitor-base` 锁定为 3.11。

## 优先处理

### Django

| 组件 | 版本 | 角色 | 生产代码引用 | 公告（严重/高/中/低） | 4.2 线上可清除的版本 |
| --- | --- | --- | --- | ---: | --- |
| bklog | 4.2.22 | 直接运行时 | 462 个文件 | 3 / 11 / 7 / 7 | 4.2.30 |
| bkmonitor | 4.2.27 | 直接运行时 | 1302 个文件 | 1 / 8 / 6 / 6 | 4.2.30 |
| bk-monitor-base | 4.2.29 | 直接运行时 | 179 个文件 | 1 / 3 / 4 / 5 | 4.2.30 |

三个组件共同仍受影响的严重公告是 CVE-2026-4277（`GenericInlineModelAdmin` 权限问题，CVSS 9.8，4.2.30 修复）。仓库中没有检索到 `GenericInlineModelAdmin`。

只有 `bklog` 4.2.22 还落在另外两条严重公告里：

- CVE-2025-59681：列别名 SQL 注入，4.2.25 修复
- CVE-2025-64459：`QuerySet` / `Q` 的 `_connector` SQL 注入，4.2.26 修复

`bkmonitor` 4.2.27 与 `bk-monitor-base` 4.2.29 已经高于这两个修复版本。

4.2.30 同时覆盖当前 4.2 线上仍开放的高危项，包括 ASGI 头混淆（CVE-2026-3902）和 `Content-Length` 与 `DATA_UPLOAD_MAX_MEMORY_SIZE`（CVE-2026-33034）。CVE-2026-15307（GeoDjango 栅格解析）没有 4.2 修复版本，修复从 5.2.17 / 6.0.8 开始。仓库中没有 `django.contrib.gis` 引用。

### PyJWT

| 组件 | 版本 | 角色 | 使用情况 |
| --- | --- | --- | --- |
| bkmonitor | 2.10.1 | 传递运行时（`blue-krill` 等） | `bkmonitor/kernel_api/middlewares/authentication.py` 调用 `jwt.decode` |
| bk-monitor-base | 2.11.0 | 传递运行时 | 该组件源码未直接 import |

严重公告 CVE-2026-102268（非对称 PEM 检测可被空白字符绕过，CVSS 9.1）在 2.14.0 修复。把仍开放的高危项一并清掉需要 **2.15.0**（含 CVE-2026-102275）。CVE-2025-45768 被维护者标记为有争议，且没有修复版本，本次不把它当作升级目标。

`bklog` 的直接依赖里没有 PyJWT，传递依赖未扫描。

### djangorestframework

| 组件 | 版本 | 生产代码引用 | 说明 |
| --- | --- | ---: | --- |
| bkmonitor | 3.15.1 | 303 个文件 | 额外受 CVE-2024-21520（XSS）影响，3.15.2 已修复 |
| bk-monitor-base | 3.15.2 | 17 个文件 | 约束为 `<3.16.0` |
| bklog | 3.15.2 | 119 个文件 | 与 base 相同，不再受上述 XSS 影响 |

三个版本共同的高危项在 **3.18.2** 修复，包括 Accept 协商的 CPU 消耗（CVE-2026-114138）、JSON 解析器使用请求指定的 codec（CVE-2026-114136），以及 `TokenProxy.delete()` 未真正吊销（CVE-2026-114137）。

### kafka-python

生产代码约 22 个文件直接 import `kafka`，覆盖元数据、告警接入和日志采集。两个组件的版本都受 CVE-2026-10142（协议帧长度未校验）和 CVE-2026-10143（SCRAM 迭代次数未设上限）影响，修复版本都是 **2.3.2**。

| 组件 | 版本 |
| --- | --- |
| bkmonitor | 1.4.6 |
| bk-monitor-base | 1.4.6 |
| bklog | 2.0.2 |

从 1.4 升到 2.3 是主版本变化，需要单独做消费者兼容验证。

### urllib3 与 certifi

| 包 | bkmonitor | bk-monitor-base | bklog | 建议 |
| --- | --- | --- | --- | --- |
| urllib3 | 1.26.20，传递；`es_tools.py` 使用 `urllib3.util.retry.Retry` | 1.26.20，传递；同样引用 Retry | 1.26.19，直接声明；仅测试辅助模块直接 import | 2.8.0。1.26 没有更高安全版本 |
| certifi | 2025.1.31，传递 | 2026.2.25，传递 | 未出现在直接依赖中 | ≥ 2026.10.18 |

urllib3 的高危项集中在流式解压和重定向（CVE-2025-66418、CVE-2025-66471、CVE-2026-21441、CVE-2026-44431、CVE-2026-97687、CVE-2026-97689）。`requests` 在三个组件的生产代码里都有引用，因此这两项传递依赖会进入线上 HTTP 调用。

### Pillow

`bkmonitor` 与 `bk-monitor-base` 都直接依赖 **11.2.1**。去重后 58 条公告：严重 5、高 36、中 17。11.x 没有能一次清掉这些公告的版本，目标是 **13.0.0**。严重项包括：

- CVE-2026-96639：多帧加载复用失效的原生图像缓冲
- CVE-2026-112393：TIFF 写入堆溢出
- CVE-2026-112398：FlashPix JPEG 解码堆溢出
- CVE-2026-112403：JPEG 解码堆溢出
- CVE-2026-112900：调用 Ghostscript 时的参数注入

生产引用只有水印绘制：

- `bkmonitor/packages/utils/signature.py`
- `bklog/apps/utils/image.py`（`bklog` 的 requirements 没有声明 pillow，这次无法核对它实际安装的版本）

这两处使用 `Image.new`、`ImageDraw`、`ImageFont.truetype`、旋转、裁剪、粘贴和 PNG 保存，不打开外部图片文件。多数严重公告位于外部图像解码。当前水印路径默认不经过这些入口。

### 其他已在生产代码中引用的高危包

| 包 | 当前版本 | 引用 | 建议版本 | 说明 |
| --- | --- | --- | --- | --- |
| sqlparse | bkmonitor 0.5.3（直接）；base 0.5.5（传递） | 3 个文件，含 `query_api/sql_parse` | 0.6.0 | 高危项是解析阶段的 ReDoS / CPU 消耗。0.5.4 不能清掉这些高危项 |
| ujson | bkmonitor 5.7.0（直接，源码未直接 import）；bklog 5.9.0（直接） | bklog 5 个文件 | ≥ 5.12.1 | 大整数解析内存泄漏、`indent` 溢出、`dump` 写失败泄漏 |
| mistune | bkmonitor 0.8.4（直接，源码未直接 import）；bklog 运行时 3.0.2，开发依赖另固定 0.8.4 | `bklog/version_log/utils.py` | 3.3.0 | `bkmonitor/pyproject.toml` 为 version-log 把 mistune 限制在 `<3`。升到 3.3.0 前要确认 version-log 是否仍要求 2.x |
| mako | bkmonitor 1.3.10（传递） | Django 模板后端 `packages/monitor_web/core/template/backends/mako.py` | 1.3.12 | `TemplateLookup` 路径穿越。反斜杠相关的一条主要影响 Windows |
| markdown | bklog 3.3 | `apps/log_databus/constants.py` | 3.8.1 | CVE-2025-69534，未捕获异常 |
| opentelemetry-instrumentation | bkmonitor 0.30b1（传递） | 6 个文件，跟踪埋点入口 | ≥ 0.41b0 | CVE-2023-43810，指标基数不受限导致的拒绝服务。bklog 直接依赖的 instrumentation 为 0.45b0，高于该修复版本 |
| langchain | bkmonitor 传递、bklog 直接，均为 0.3.27 | `bkmonitor/metadata/agents/diagnostic/metadata_diagnostic_agent.py` 引用 `langchain.agents` | 0.3.30 | 可清掉 0.3 线上的高危项。bklog 源码未直接 import langchain |

`langchain-core` 0.3.75 在 bkmonitor（传递）和 bklog（直接）中都存在，源码没有直接 import `langchain_core`。严重公告 CVE-2025-68664（序列化注入，CVSS 9.3）在 0.3.81 修复；把 0.3 线上其余高危项清掉的版本是 **0.3.85**。CVE-2026-34070（旧 `load_prompt` 路径穿越）只在 1.2.22 修复，仓库中未检索到 `load_prompt`。

### 生产代码未直接引用、但仍在运行时闭包里的高危或严重包

这些包会装进运行环境。是否执行到有缺陷的函数，取决于上层库怎么调用它们。

| 包 | 版本 | 所在组件 | 建议 | 备注 |
| --- | --- | --- | --- | --- |
| cryptography | 44.0.2 | bkmonitor，传递 | 50.0.0 可清掉已给出修复版本的高危项；46.0.5 可先消化子群验证缺失（CVE-2026-26007） | 另有一条 PYSEC 没有可用严重级别 |
| cryptography | 46.0.5 | bk-monitor-base，传递 | 同版本线先到 46.0.7（CVE-2026-39892，CVSS 9.8，非连续 buffer 溢出）；其余高危项需 48.0.1 至 50.0.0 | 源码未直接 import |
| certifi | 见上 | 两个锁文件 | ≥ 2026.10.18 | `requests` 默认 CA 包 |
| anyio | 4.9.0 | bkmonitor，传递 | 4.14.2 | CVE-2026-63374，`TLSStream` 的 IDNA 2003 主机名编码。未发现直接引用 |
| aiohttp | 3.11.18 | bkmonitor，传递 | 3.14.4 | 17 条高危，集中在解析器、压缩和连接复用。随 langchain / HTTP 栈进入环境 |
| protobuf | 3.19.5 / 3.20.3 | bkmonitor、bklog，均为直接依赖 | 5.29.6 可同时覆盖两条高危拒绝服务 | 源码未直接 import `google.protobuf`。与当前 OpenTelemetry 0.30 / 1.11 的兼容性需要单独验证 |
| pyasn1 | 0.6.1 / 0.6.2 | 两个锁文件，传递 | 0.6.4 | 解码拒绝服务 |
| python-multipart | 0.0.20 | bkmonitor，传递 | 0.0.31 | 随 Starlette / MCP 进入环境 |
| starlette | 0.47.3 | bkmonitor，传递 | 1.3.1 | 高危项含 Range 头合并和 `request.form()` 限制被忽略 |
| mcp | 1.12.4 | bkmonitor，传递 | ≥ 1.28.1 | HTTP 会话未校验主体、DNS rebinding、WebSocket 的 Host/Origin |
| msgpack | 1.1.0 / 1.1.2 | 两个锁文件，传递 | 1.2.1 | `Unpacker` 出错后复用导致越界读 |
| orjson | 3.10.18 | bkmonitor，传递 | ≥ 3.11.5 | 深层 JSON 递归未限制 |
| langsmith | 0.3.45 | bkmonitor，传递 | 0.8.18 可覆盖两条高危项中较晚的修复 | 随 langchain 进入环境 |

## 中危与低危

生产代码有引用、最高为中危的包：

| 包 | 版本 | 引用 | 公告 | 修复版本 |
| --- | --- | --- | --- | --- |
| requests | 三个组件均为 2.32.5 | 73 个生产文件 | CVE-2026-25645，`extract_zipped_paths()` 临时文件复用 | 2.33.0 |
| opentelemetry-api | bkmonitor 1.11.1；bklog 1.24.0 | 68 个生产文件 | CVE-2026-114603，`tracestate` 解析无上限 | 1.45.1 |
| python-dotenv | bkmonitor 0.21.1 | `bkmonitor/manage.py` | CVE-2026-28684，`set_key` 跟随符号链接 | 1.2.2 |

其余最高为中危或低危、且源码未直接引用的运行时包：`h2` 4.2.0、`hpack` 4.1.0、`idna` 3.10 / 3.11、`langchain-text-splitters` 0.3.11、`marshmallow` 3.26.1、`oauthlib` 3.2.2 / 3.3.1、`setuptools` 79.0.1 / 80.9.0 / 82.0.1、`werkzeug` 3.1.3、`langchain-openai` 0.3.22、`pygments` 2.19.1。`idna` 会被 `requests` 间接使用。`werkzeug` 由 `aidev-agent` 拉入，主站 Django 不依赖它。

## 仅开发或测试依赖

这些包不应当进入线上镜像。若镜像构建时安装了 dev 组，风险会变高。

| 包 | 版本 | 组件 | 最高级别 | 说明 |
| --- | --- | --- | --- | --- |
| virtualenv | 15.2 | bklog，直接开发 | 严重 | `requirements_dev.txt` 中的旧版本。激活脚本相关公告的修复集中在 21.14.x |
| virtualenv | 20.30.0 / 21.2.0 | bkmonitor / base，传递开发 | 高 | 同上，目标 21.14.9 可覆盖已列出的高危修复版本 |
| filelock | 3.25.1 | base，传递开发 | 高 | CVE-2026-112940，建议 4.2.1。bkmonitor 的 3.18.0 为中危 |
| pytest | 8.3.4 / 7.0.1 | bkmonitor / base，直接开发 | 中 | 只被测试代码引用。修复版本 9.0.3 |
| pygments | 2.19.2 | base，传递开发 | 低 | bkmonitor 的 2.19.1 在运行时闭包中，同样是低危 |
| mistune | 0.8.4 | bklog，直接开发 | 高 | 运行时 requirements 已是 3.0.2。开发文件里的 0.8.4 与运行时不是同一个安装集合，但版本过旧 |

## 组件之间的版本差

同一包在三个组件里的版本并不一致，安全修复不能只改一处。

| 包 | bkmonitor | bk-monitor-base | bklog |
| --- | --- | --- | --- |
| Django | 4.2.27 | 4.2.29 | 4.2.22 |
| djangorestframework | 3.15.1 | 3.15.2 | 3.15.2 |
| kafka-python | 1.4.6 | 1.4.6 | 2.0.2 |
| urllib3 | 1.26.20 | 1.26.20 | 1.26.19 |
| protobuf | 3.19.5 | 未单独作为 base 直接漏洞版本出现 | 3.20.3 |
| PyJWT | 2.10.1 | 2.11.0 | 直接依赖中未声明 |
| cryptography | 44.0.2 | 46.0.5 | 传递依赖未扫描 |
| certifi | 2025.1.31 | 2026.2.25 | 直接依赖中未声明 |
| OpenTelemetry API | 1.11.1 | 未在本次命中列表 | 1.24.0 |
| ujson | 5.7.0 | 未在本次命中列表 | 5.9.0 |
| mistune | 0.8.4 | 未在本次命中列表 | 运行时 3.0.2 |

## 方法与局限

- 版本来自 `bkmonitor/uv.lock`、`bk-monitor-base/uv.lock` 和 `bklog` 的 requirements。没有重新解析 PyPI，也没有把公告里的修复版本安装下来做回归。
- `bklog` 只覆盖直接声明的版本。它的传递依赖不在本报告的命中集合里。
- 「项目是否使用」指源码里的静态 import。动态导入、Django `INSTALLED_APPS` 字符串和仅由依赖库内部 import 的情况，会表现为「未发现直接引用」。
- 公告描述的是特定函数、解析器或文件格式。安装了受影响版本，只说明进程里有这段代码，不说明当前请求一定会走到它。
- OSV 的版本区间偶发过宽。本次抽查 Pillow 与 Django 的严重公告时，影响范围与 `affected` 区间一致，因此保留这些记录。
- CVE-2025-45768（PyJWT）维持「有争议」状态，不纳入建议升级的理由。
- 数据截止扫描当日的 OSV 快照。之后新公开的公告不会自动进入本文。

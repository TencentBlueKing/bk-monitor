# Python 依赖安全扫描报告

- 扫描日期：2026-11-16
- 代码版本：`4c6743eb3`
- 漏洞数据： [OSV](https://osv.dev) 的 PyPI 生态记录，严重程度采用 GitHub Advisory Database 已审定的定性等级
- 结论范围：依赖是否被锁定或钉死、公告等级、生产环境会不会装上、业务代码有没有直接引用

本报告只记录公开公告的编号、影响面和修复版本，不包含利用步骤。

## 扫描范围

仓库里有三套 Python 依赖，生产安装方式不同。

| 组件 | 清单 | 生产环境如何安装 | 本次纳入生产闭包 |
| --- | --- | --- | --- |
| 监控 `bkmonitor` | `bkmonitor/uv.lock`（294 个锁定包） | 镜像执行 `uv sync --locked --no-dev`。`dev` / `test` / `stubs` 不安装；`aidev` 写在 `default-groups` 里，会装进镜像 | 259 个 |
| 基础库 `bk-monitor-base` | `bk-monitor-base/uv.lock`（151 个锁定包） | 作为监控的路径依赖时只带运行时依赖。单独锁定的版本和监控镜像不完全相同 | 96 个运行时包 |
| 日志 `bklog` | `bklog/requirements.txt`（84 个 `==` 钉死的直接依赖） | 镜像安装该文件，不安装 `requirements_dev.txt` | 84 个直接依赖 |

监控镜像以 `bkmonitor/uv.lock` 为准。基础库锁文件里的 Django、cryptography、certifi 版本更高，不能当成监控镜像已经升到这些版本。

日志没有锁文件，传递依赖没有钉死，本次只覆盖 `requirements.txt` 里写明版本的直接依赖。

去重后向 OSV 查询了 **434** 个发行版。41 个发行版至少有一条未撤回公告。同一 CVE 的 GHSA 与 PYSEC 已合并，严重程度以 GHSA 的定性等级为准，不用另一条记录的 CVSS 分数把等级抬高。合并后共 **413** 条「包 + 锁定版本 + 公告」。其中严重 10 条（9 个公告，certifi 同一公告出现在两个锁定版本上）、高 180、中 151、低 68、无定性等级 4。

使用情况按下面三类判断：

- **直接引用**：非测试代码里出现 `import` / `from`，包括函数内部导入。
- **间接使用**：生产闭包会安装，业务代码没有直接导入，但请求、加密、证书校验或消息客户端会加载它。
- **未进生产**：只出现在开发、测试或 `requirements_dev.txt`。

解释环境按监控镜像的运行时估算：CPython 3.11、Linux x86_64。只在 Windows 上生效的依赖标记已排除。

## 优先处理

下面按「生产会装上，并且项目确实会走到」排序，不是只按 CVSS。

### 1. 日志平台 Django 4.2.22：严重，框架本身在用

`bklog/requirements.txt` 将 Django 钉在 **4.2.22**。日志业务代码直接使用 Django。

[GHSA-frmv-pr5f-9mcr](https://github.com/advisories/GHSA-frmv-pr5f-9mcr)（CVE-2025-64459）为严重。公告说明 `QuerySet` 与 `Q` 对象的 `_connector` 参数存在 SQL 注入，4.2 分支的修复版本是 **4.2.26**。因此 4.2.22 仍受影响。同一锁定版本上还有 9 条高、7 条中、11 条低。

监控镜像是 Django **4.2.27**，基础库单独锁定是 **4.2.29**，这两条线不再落在上述 SQL 注入的修复点之前，但各自仍有高危公告：

| 组件 | 锁定版本 | 直接引用 | 高 / 中 / 低 | 公告中的 4.2 修复版本 |
| --- | --- | --- | --- | --- |
| 日志 | 4.2.22 | 是 | 严重 1，高 9，中 7，低 11 | 4.2.26 起，后续公告更高 |
| 监控镜像 | 4.2.27 | 是 | 高 6，中 5，低 10 | 代表项修复到 4.2.29 |
| 基础库锁文件 | 4.2.29 | 是 | 高 3，中 4，低 6 | 代表项修复到 4.2.30 |

监控 4.2.27 的代表高危是 [GHSA-8p8v-wh79-9r56](https://github.com/advisories/GHSA-8p8v-wh79-9r56)（不受控的资源消耗）。基础库 4.2.29 的代表高危是 [GHSA-933h-hp56-hf7m](https://github.com/advisories/GHSA-933h-hp56-hf7m)（SGI 请求在 `Content-Length` 缺失或偏小时可能绕过上传体积限制）。三条线若继续留在 4.2，需要至少评估到 **4.2.30**，升完后再对目标版本复扫。

### 2. certifi：严重，HTTPS 校验会用到

业务代码没有 `import certifi`，但 Elasticsearch、Kubernetes 客户端、requests 和 httpx 都依赖它做证书校验。

[GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2) 为严重：打包进去的 emSign 根证书对应的中间证书密钥已不可信。修复版本 **2026.10.18**。

| 组件 | 锁定版本 | 是否低于修复版本 |
| --- | --- | --- |
| 监控镜像 | 2025.1.31 | 是 |
| 基础库锁文件 | 2026.2.25 | 是 |

监控镜像用的是更旧的 2025.1.31。

### 3. Pillow 11.2.1：严重，已安装并被水印功能导入

监控和基础库都把 Pillow 钉在 **11.2.1**，并作为直接依赖。该版本有 **5 条严重、37 条高、18 条中**。严重项的修复版本都是 **13.0.0**。

严重公告：

| 公告 | 影响（公告摘要） |
| --- | --- |
| [GHSA-5x8w-8jj5-q52h](https://github.com/advisories/GHSA-5x8w-8jj5-q52h) | FlashPix JPEG 解码堆缓冲区溢出，可导致代码执行 |
| [GHSA-8g5g-8vmr-9782](https://github.com/advisories/GHSA-8g5g-8vmr-9782) | JPEG 解码堆缓冲区溢出 |
| [GHSA-332p-7hrc-92wf](https://github.com/advisories/GHSA-332p-7hrc-92wf) | 把 TIFF 保存到 `BytesIO` 时的堆缓冲区溢出 |
| [GHSA-v9pv-5gc8-w2m6](https://github.com/advisories/GHSA-v9pv-5gc8-w2m6) | 多帧加载器在模式切换后复用已失效的原生图像内存 |
| [GHSA-w889-685w-c8fh](https://github.com/advisories/GHSA-w889-685w-c8fh) | 调用 Ghostscript 时的参数注入 |

项目里的直接引用是本地绘制水印，不是打开外部图片：

- `bkmonitor/packages/utils/signature.py` 使用 `Image.new`、`ImageDraw`、`ImageFont`
- `bklog/apps/utils/image.py` 同样绘制水印。日志的 `requirements.txt` **没有声明** Pillow，但代码导入了 `PIL`
- 仓库里唯一的 `Image.open` 在 `bkmonitor/scripts/verify_pillow_build.py`，用于镜像构建校验

因此，解码类严重缺陷在当前业务调用点上没有直接入口；字体渲染和图像保存仍走这套已安装的库。基础库声明了 Pillow，非测试代码里没有直接导入。

### 4. LangChain 0.3.75：严重，随监控默认组装进镜像

`langchain-core==0.3.75` 同时出现在监控默认组 `aidev` 和日志的直接依赖里。

[GHSA-c67j-w6g6-q2cm](https://github.com/advisories/GHSA-c67j-w6g6-q2cm)（CVE-2025-68664）为严重：序列化接口在 `dumps` / `loads` 路径上可被用于提取密钥。0.3 分支的修复版本是 **0.3.81**。该锁定版本另有 3 条高、1 条中、1 条低。

监控业务代码在 `bkmonitor/metadata/agents/diagnostic/metadata_diagnostic_agent.py` 直接导入 `langchain.agents.Tool`。没有发现对 `langchain_core` 的直接导入，它由 langchain 系列包拉入。日志声明了 `langchain==0.3.27` 和 `langchain-core==0.3.75`，日志业务代码里没有发现对应导入。

`langchain==0.3.27` 另有高危 [GHSA-3644-q5cj-c5c7](https://github.com/advisories/GHSA-3644-q5cj-c5c7)：公开 prompt 拉取会反序列化不受信任的清单。公告给出的 0.3 修复版本是 **0.3.30**。

### 5. 监控镜像上的 urllib3 仍停在 1.26.20

日志已经把 urllib3 钉在 **2.8.0**，这次查询没有命中公告。监控和基础库锁定的是 **1.26.20**，有 6 条高、1 条中。

业务代码直接使用它，例如 `bkmonitor/metadata/utils/es_tools.py` 和 `bkmonitor/kernel_api/rpc/functions/admin/kubernetes_pods.py`。Elasticsearch 5/6/7 客户端、requests、Kubernetes 客户端和 botocore 也会加载它。

代表高危：

- [GHSA-2xpw-w6gg-jr37](https://github.com/advisories/GHSA-2xpw-w6gg-jr37)：流式接口对高度压缩数据的处理不当，修复版本 2.6.0
- [GHSA-38jv-5279-wg99](https://github.com/advisories/GHSA-38jv-5279-wg99)：跟随重定向时解压炸弹防护可被绕过，修复版本 2.6.3

1.26 系列落后于这些修复点。旧的 Elasticsearch 客户端仍在依赖树上，升级前需要确认它们能否接受 urllib3 2.6 以上。

## 其余高危：生产已安装

下表每个包只列代表公告。数量是该锁定版本上等级为「高」的公告条数。

| 组件 | 包 | 锁定版本 | 角色 | 直接引用 | 高 | 修复版本 | 代表公告 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 监控 | aiohttp | 3.11.18 | 传递（langchain-community） | 否 | 5 | 3.14.4 | [GHSA-2g87-pp6c-29x5](https://github.com/advisories/GHSA-2g87-pp6c-29x5) 不受限的内存或 CPU 消耗。另有 20 条中、16 条低 |
| 监控 / 基础库 | cryptography | 44.0.2 / 46.0.5 | 传递（bk-crypto-python-sdk、blue-krill、blueapps） | 否 | 4 / 3 | 48.0.1 | [GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf) 轮子内带的 OpenSSL 有已知问题。加密能力通过 bk-crypto SDK 使用 |
| 监控 / 基础库 | pyasn1 | 0.6.1 / 0.6.2 | 传递（rsa、pyasn1-modules） | 否 | 9 / 8 | 0.6.5 | [GHSA-2qm8-x737-gmw5](https://github.com/advisories/GHSA-2qm8-x737-gmw5) BER 解码存在二次方 CPU 消耗 |
| 监控、日志、基础库 | djangorestframework | 3.15.1 / 3.15.2 | 直接依赖 | 是 | 3 | 3.18.2 | [GHSA-33wh-fxxf-88vv](https://github.com/advisories/GHSA-33wh-fxxf-88vv) `Accept` 协商可造成明显 CPU 消耗。3.15 到 3.18 跨度较大 |
| 监控 / 日志 | ujson | 5.7.0 / 5.9.0 | 直接依赖 | 是 | 3 | 5.12.1 | [GHSA-c38f-wx89-p2xg](https://github.com/advisories/GHSA-c38f-wx89-p2xg) 写出失败时泄漏内存。监控在 `bkmonitor/patches/json.py` 用它替换 Django 的 json 实现；日志多个查询与导出路径直接导入 |
| 监控 / 日志 | mistune | 0.8.4 / 3.0.2 | 直接依赖 | 监控否，日志是 | 5 / 6 | 3.3.0 | [GHSA-4j32-57v6-6g45](https://github.com/advisories/GHSA-4j32-57v6-6g45) Markdown 解析存在二次方时间复杂度。日志 `bklog/version_log/utils.py` 直接渲染版本说明；监控侧由 django-versionlog 引入，业务代码未直接导入 |
| 监控、日志、基础库 | kafka-python | 1.4.6 / 2.0.2 | 直接依赖 | 是 | 2 | 2.3.2 | [GHSA-2jcm-hq8r-84wx](https://github.com/advisories/GHSA-2jcm-hq8r-84wx) SCRAM 迭代次数未限制，可导致拒绝服务。监控与基础库为 1.4.6，日志为 2.0.2，三条线都低于 2.3.2。监控在 metadata 的数据源与存储代码中直接导入 |
| 监控 | dnspython | 2.6.1 | 直接依赖 | 是 | 2 | 2.9.0 | [GHSA-45c3-73f7-pv4m](https://github.com/advisories/GHSA-45c3-73f7-pv4m) 域名解析可造成过高 CPU。引用点包括 `bkmonitor/bkmonitor/utils/dns_resolve.py` |
| 监控 | mako | 1.3.10 | 传递（blueapps） | 是 | 2 | 1.3.12 | [GHSA-2h4p-vjrc-8xpq](https://github.com/advisories/GHSA-2h4p-vjrc-8xpq) `TemplateLookup` 的路径处理问题。监控模板后端 `packages/monitor_web/core/template/backends/mako.py` 直接使用。该代表项描述的是 Windows 反斜杠路径，Linux 镜像上的可达性更低 |
| 监控 / 基础库 | msgpack | 1.1.0 / 1.1.2 | 传递（influxdb） | 否 | 2 | 1.2.1 | [GHSA-6v7p-g79w-8964](https://github.com/advisories/GHSA-6v7p-g79w-8964) 捕获错误后重复使用 `Unpacker` 时越界读取 |
| 监控 / 基础库 | oauthlib | 3.2.2 / 3.3.1 | 传递（requests-oauthlib） | 否 | 1 / 2 | 4.0.0 / 4.0.1 | [GHSA-3jp2-3mrg-2vxc](https://github.com/advisories/GHSA-3jp2-3mrg-2vxc) 设备流程中，知道合法 client ID 即可能取回 Bearer token |
| 日志 / 监控 | protobuf | 3.20.3 / 3.19.5 | 直接依赖 | 否 | 2 | 5.29.6 或 6.33.5 | [GHSA-7gcm-g887-7qv7](https://github.com/advisories/GHSA-7gcm-g887-7qv7) JSON 递归深度限制可被绕过。OpenTelemetry 与监控声明把 protobuf 留在 3.x，修复版本跨越大版本 |
| 监控 | mcp | 1.12.4 | 传递（langchain-mcp-adapters） | 否 | 3 | 1.23.0 起 | [GHSA-9h52-p55h-vw2f](https://github.com/advisories/GHSA-9h52-p55h-vw2f) 默认未启用 DNS rebinding 防护 |
| 监控 | python-multipart | 0.0.20 | 传递（mcp） | 否 | 3 | 0.0.30 | [GHSA-5rvq-cxj2-64vf](https://github.com/advisories/GHSA-5rvq-cxj2-64vf) 查询串解析存在二次方 CPU 消耗。另有一条高危涉及非默认配置下的任意文件写入 |
| 监控 | starlette | 0.47.3 | 传递（mcp） | 否 | 3 | 0.49.1 | [GHSA-7f5h-v6xp-fcq8](https://github.com/advisories/GHSA-7f5h-v6xp-fcq8) `FileResponse` 合并 Range 头时的二次方拒绝服务 |
| 监控 | langsmith | 0.3.45 | 传递（langchain 系列） | 否 | 2 | 0.8.0 | [GHSA-f4xh-w4cj-qxq8](https://github.com/advisories/GHSA-f4xh-w4cj-qxq8) `TracingMiddleware` 可读取服务端文件 |
| 监控 | anyio | 4.9.0 | 传递（httpx、mcp、starlette 等） | 否 | 严重 1 | 4.14.2 | [GHSA-82r6-8w77-94w6](https://github.com/advisories/GHSA-82r6-8w77-94w6) `TLSStream` 仍按 IDNA 2003 编码主机名，存在证书欺骗可能 |
| 监控 | opentelemetry-instrumentation | 0.30b1 | 传递 | 是（opentelemetry 命名空间） | 1 | 0.41b0 | [GHSA-5rv5-6h4r-h22v](https://github.com/advisories/GHSA-5rv5-6h4r-h22v) 指标基数不受限制，可导致拒绝服务。监控多处直接使用 OpenTelemetry API |
| 监控 | orjson | 3.10.18 | 传递（langsmith） | 否 | 1 | 3.11.6 | [GHSA-hx9q-6w63-j58v](https://github.com/advisories/GHSA-hx9q-6w63-j58v) 深层嵌套 JSON 没有递归上限 |

`mcp`、`python-multipart`、`starlette`、`langsmith`、`orjson` 都挂在监控默认组 `aidev` 带入的链路上。不用这组 AI 能力时，它们仍然会按当前 Dockerfile 装进监控镜像。

## 中危与低危

这些包的最高等级是中或低，且会进生产安装集。

| 包 | 锁定版本 | 直接引用 | 说明 |
| --- | --- | --- | --- |
| requests | 2.32.5（三个组件一致） | 是 | [CVE-2026-25645](https://osv.dev/vulnerability/CVE-2026-25645)，修复版本 2.33.0。`extract_zipped_paths()` 使用可预测的临时文件名 |
| opentelemetry-api | 监控 1.11.1，日志 1.24.0 | 是 | 修复版本 1.45.1，tracestate 解析不受限 |
| python-dotenv | 监控 0.21.1 | 是 | 修复版本 1.2.2。`set_key` 在跨设备回退时可能跟随符号链接并覆盖文件 |
| markdown | 日志 3.3 | 是 | 修复版本 3.8.1，未捕获异常。日志数据总线常量模块直接导入 |
| langchain-text-splitters | 监控 0.3.11 | 否 | 修复版本 1.1.2，从 URL 拉 HTML 时的重定向绕过。属 aidev 直接依赖 |
| marshmallow | 监控 3.26.1 | 否 | 修复版本 3.26.2，`Schema.load(many=...)` 拒绝服务。由 environs / dataclasses-json 引入 |
| idna | 监控 3.10，基础库 3.11 | 否 | 修复版本 3.15。requests、httpx、yarl 会用到 |
| h2 / hpack | 监控 4.2.0 / 4.1.0 | 否 | 修复版本 4.4.1 / 4.2.0。由 grpclib 引入，重复 Host 头与超长整数解码 |
| setuptools | 监控 79.0.1，日志 80.9.0，基础库 82.0.1 | 否 | 代表修复版本 83.0.0。代表公告描述的是 macOS 上 sdist 清单绕过，Linux 镜像收益有限 |
| werkzeug | 监控 3.1.3 | 否 | 由 aidev-agent、blueapps 引入。代表项是 Windows 设备名路径，Linux 镜像收益有限 |
| pygments | 监控 2.19.1 | 否 | 低。正则表达式拒绝服务，修复版本 2.20.0 |
| langchain-openai | 监控 0.3.22 | 否 | 低。图片 token 计数的 SSRF 防护可被绕过，修复版本 1.1.14 |

## 未进入生产镜像

这些高危包在锁定结果里，但当前生产安装命令不会装它们。

| 包 | 版本 | 位置 | 说明 |
| --- | --- | --- | --- |
| virtualenv | 15.2 | 日志 `requirements_dev.txt` 直接依赖 | 10 条高。激活脚本会执行路径中的命令，修复版本远高于 15.2（20.26.6 之后仍有新的高危，开发锁里的 20.30.0 / 21.2.0 仍低于 21.7.13） |
| virtualenv | 20.30.0 / 21.2.0 | 监控与基础库的开发依赖传递 | 各 10 条高，修复版本 21.7.13。只影响本机或 CI 创建虚拟环境，不进业务镜像 |
| filelock | 基础库 3.25.1 | 基础库开发依赖传递 | 1 条高，修复版本 4.2.1。监控开发锁里的 3.18.0 最高为中 |
| pytest | 基础库 7.0.1，监控 8.3.4 | 直接开发依赖 | 中，测试工具 |

## 抽查后未命中公告的包

同一次查询中，下面这些常用直接依赖没有未撤回的 OSV 记录：

- Jinja2 **3.1.6**（监控与日志）
- PyYAML **6.0.1**（监控）与 **6.0.2**（日志）
- Gunicorn **23.0.0**
- 日志侧 urllib3 **2.8.0**

没有记录只说明扫描当日的公开库没有匹配项，不表示这些包没有其他风险。

## 建议的处理顺序

1. 把日志 Django 从 4.2.22 升到不低于 4.2.30，并复扫。这是当前唯一落在严重 SQL 注入修复点之前的业务框架版本。
2. 把监控镜像的 certifi 升到不低于 2026.10.18。基础库锁文件里的 2026.2.25 也低于该版本。
3. 评估 Pillow 11.2.1 升到 13.0.0。水印路径本身不解码外部图片，但生产镜像装的是带多条严重内存缺陷的版本，日志代码还在导入一个未声明的 `PIL`。
4. 若继续把 `aidev` 装进监控镜像，将 `langchain-core` 升到不低于 0.3.81，`langchain` 升到不低于 0.3.30，并连带看 langsmith、mcp、starlette、python-multipart。
5. 把监控与基础库的 urllib3 从 1.26.20 推向 2.6.3 以上，先确认 Elasticsearch 5/6 客户端是否还能工作。日志已经在 2.8.0。
6. 将 ujson 升到不低于 5.12.1。监控用它替换了 Django 的 json 实现。
7. djangorestframework、kafka-python、dnspython、mistune、cryptography、protobuf 的修复版本跨度较大，适合单独排期，不要和上面几项捆成一次大升级。

## 局限

- 日志的传递依赖没有锁文件，不在本次版本范围内。
- 导入扫描覆盖不到完全动态的导入；字符串形式的 Django 应用路径可能漏记。已经核对过的直接引用在上文点了文件。
- 公告描述的是上游缺陷，不代表每条都能在当前部署里被触发。Windows 或 macOS 专用项已在正文标明。
- 严重程度来自 2026-11-16 的 GitHub 审定等级。之后撤回、拆分或补充修复版本时，应以复扫结果为准。

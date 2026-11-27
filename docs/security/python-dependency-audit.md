# Python 依赖安全扫描报告

- 扫描日期：2026-11-27
- 代码版本：`a7394b1e4c`
- 漏洞数据：[OSV](https://osv.dev) 的 PyPI 记录。同一 CVE 的 GHSA 与 PYSEC 已合并。严重程度采用 GitHub Advisory 已审定的定性等级；没有已审定等级时，依次使用 CVSS v3、v4
- 结论范围：锁定或钉死的版本、公告等级、生产环境会不会装上、业务代码有没有直接引用

本报告只记录公开公告的编号、影响面和修复版本，不包含利用步骤。

## 扫描范围

仓库里有三套 Python 依赖，生产安装方式不同。

| 组件 | 清单 | 生产环境如何安装 | 本次纳入生产闭包 |
| --- | --- | --- | --- |
| 监控 `bkmonitor` | `bkmonitor/uv.lock`（解析出 298 条记录，含虚拟项目和路径包 `bk-monitor-base`） | 镜像 `bkmonitor/Dockerfile` 执行 `uv sync --locked --no-install-project --no-dev`。`--no-dev` 只排除名为 `dev` 的组；`test` / `stubs` 不在默认组里。`aidev` 写在 `default-groups` 里，会装进镜像 | 262 个 |
| 基础库 `bk-monitor-base` | `bk-monitor-base/uv.lock`（151 个可安装包，另有 1 条本项目记录） | 作为监控的路径依赖时只带运行时依赖。单独锁定的版本和监控镜像不完全相同 | 97 个运行时包 |
| 日志 `bklog` | `bklog/requirements.txt`（84 个 `==` 钉死的直接依赖） | 安装该文件，不安装 `requirements_dev.txt` | 84 个直接依赖 |

监控镜像以 `bkmonitor/uv.lock` 为准。基础库锁文件里的 Django、cryptography、certifi 版本更高，不能当成监控镜像已经升到这些版本。

日志没有锁文件，传递依赖没有钉死，本次只覆盖 `requirements.txt` 里写明版本的直接依赖。`requirements_dev.txt` 里的 9 个钉死版本只计入开发依赖。

按 Linux x86_64、CPython 3.11.3 解释依赖标记后，去重向 OSV 查询了 **431** 个版本字符串。版本字符串和发行版数量相同。只在 Windows 上安装，或只在 3.11.2 及更早解释器上安装的条件依赖没有计入。本地路径包 `bk-monitor-base` 也没有拿去查询。62 个发行版至少有一条未撤回公告，369 个版本字符串没有匹配记录。查询没有失败。

`bkmonitor/support-files/bkai/package/skills/bk-monitor-data-fetcher/requirements.txt` 只给 `requests` 和 `PyYAML` 写了范围，没有钉版本，也不在上面三个生产安装命令里，本次没有单独查询。

生产闭包（监控镜像、基础库运行时、日志直接依赖）里有 **54** 个受影响发行版，其中 6 个的最高等级是严重。只出现在开发或测试依赖里的受影响发行版有 8 个。

同一 CVE 只计一次时，生产闭包上的公告是 **256** 条：严重 9、高 119、中 91、低 37。命中的包版本数量是监控 36/262、基础库 13/97、日志 12/84。

使用情况按下面三类判断：

- **直接引用**：非测试代码里出现 `import` / `from`，包括函数内部导入。`bklog/ai_agent` 是指向仓库根 `ai_agent` 的符号链接，按同一份代码计。
- **间接使用**：生产闭包会安装，业务代码没有直接导入，但请求、加密、证书校验、Markdown 渲染或消息客户端会加载它。
- **未进生产**：只出现在开发、测试或 `requirements_dev.txt`。

## 与上次扫描的差异

上次扫描是 2026-11-26，代码 `4d87976fa8`。本次代码是 `a7394b1e4c`。监控镜像仍执行 `uv sync --locked --no-install-project --no-dev`，`aidev` 仍写在 `default-groups` 里，会装进镜像。构建时仍设置 `TIKTOKEN_CACHE_DIR`，并预置 `cl100k_base` 和 `o200k_base`。

依赖清单只新增了监控的直接依赖 `promql-parser==0.12.0`：

- `bkmonitor/pyproject.toml` 和 `bkmonitor/uv.lock` 增加了 **promql-parser 0.12.0**。锁里它没有传递依赖，没有带入其他锁定版本。
- `bk-monitor-base/uv.lock`、`bklog/requirements.txt` 和 `bklog/requirements_dev.txt` 没有变化。blueapps 仍是 **4.16rc9**，没有未撤回的 OSV 记录。

promql-parser **0.12.0** 没有未撤回的 OSV 记录。业务代码在 `bkmonitor/packages/fta_web/alert/promql.py` 直接 `import promql_parser`，用它解析告警策略里的 PromQL，判断维度过滤能否前推。解析失败时保留原来的查询行为。

因此监控生产闭包从 261 变成 **262**，全部组从 291 变成 **292**。版本字符串从 430 变成 **431**。有公告的发行版仍是 62 个；没有公告的版本字符串是 369 个，多出来的是 promql-parser 这一条干净记录。

OSV 按同一规则重新查询了这 431 个版本字符串（Linux x86_64、CPython 3.11.3）。原始编号仍是 514 个。版本查询没有带回的 GHSA 别名仍是这 3 个：GHSA-6269-cqxg-mhhv、GHSA-ccfx-mfmx-2fx9、GHSA-4f8h-vr72-p32c。查询没有失败。

按已审核 GHSA 合并之后，生产受影响发行版仍是 **54** 个，其中 6 个的最高等级是严重。包命中是监控 36/262、基础库 13/97、日志 12/84。只出现在开发或测试依赖里的受影响发行版仍是 8 个。去重后的运行时公告仍是 **256** 条：严重 9、高 119、中 91、低 37。

2026-11-25 01:08 UTC 之后，没有新发布、也没有被修改、并且命中当前生产版本的公告。aiohttp **3.11.18** 上那四条高危的修改时间仍是 2026-11-24 10:10–10:11 UTC，等级仍是高，修复版本仍是 **3.14.4**。这一版仍是 13 条高、21 条中、16 条低。业务代码没有 `import aiohttp`，也没有用它启动 HTTP 服务。

`4d87976fa8` 之后，Python 依赖版本只增加了 promql-parser。`bkmonitor/settings.py` 仍通过 `monkey.patch_all` 把 `json` 换成 `patches/json.py`。水印、`dns_resolve.py`、`ai_agent/llm`、诊断代理读取本地 markdown、日志 `model_query._normalize_filter` 和监控 `bkm_cli/db.py` 的字段白名单都还在。非测试代码里没有 `OAuthClientProvider`、`django.contrib.gis`、`get_asgi_application`，也没有直接导入 `aiohttp`、`mcp` 或 `starlette`。`bklog/ai_agent` 仍是指向仓库根 `ai_agent` 的符号链接。没有搜到业务代码直接调用 LangChain 的 `dumps` / `loads`。监控锁的 tiktoken 仍是 **0.9.0**，日志钉的仍是 **0.11.0**，这两个版本没有未撤回公告。

范围规则和上次相同。mistune 的 CVE-2026-44898 / CVE-2026-44899 只覆盖 3.2.0。cryptography 的 CVE-2026-69248 从 45.0.0 起，只算基础库 46.0.5。virtualenv 的 CVE-2026-113713 只覆盖 21.14.8 和 21.14.9，15.2、20.30.0、21.2.0 不计入。15.2 和 20.30.0 仍有中危 CVE-2026-22702，修复版本 20.36.1。

下面各节的版本、公告和修复点与 2026-11-26 的报告相同。新增的 promql-parser 0.12.0 没有公告。

## 优先处理

下面按「生产会装上，并且项目确实会走到」排序。

### 1. Django：日志仍有严重 SQL 注入，监控 4.2.27 仍低于后续 SQL 注入修复点

三条线都直接使用 Django。日志钉在 **4.2.22**，监控镜像是 **4.2.27**，基础库单独锁定是 **4.2.29**。这三处版本和上次相同。

[GHSA-frmv-pr5f-9mcr](https://github.com/advisories/GHSA-frmv-pr5f-9mcr)（CVE-2025-64459）为严重。公告说明 `QuerySet` 与 `Q` 对象的 `_connector` 参数存在 SQL 注入，4.2 分支的修复版本是 **4.2.26**。因此只有日志的 4.2.22 仍落在这个修复点之前。日志这一版另有 9 条高、7 条中、11 条低。

监控 4.2.27 已经越过 4.2.26，但仍有两条高危 SQL 注入，修复版本都是 **4.2.28**：

- [GHSA-mwm9-4648-f68q](https://github.com/advisories/GHSA-mwm9-4648-f68q)（CVE-2026-1207）
- [GHSA-gvg8-93h5-g6qq](https://github.com/advisories/GHSA-gvg8-93h5-g6qq)（CVE-2026-1287）

| 组件 | 锁定版本 | 直接引用 | 严重 / 高 / 中 / 低 | 4.2 线上仍未盖住的代表修复点 |
| --- | --- | --- | --- | --- |
| 日志 | 4.2.22 | 是 | 1 / 9 / 7 / 11 | 4.2.26 起，后续公告更高 |
| 监控镜像 | 4.2.27 | 是 | 0 / 6 / 5 / 10 | 4.2.28 的 SQL 注入，以及 4.2.29、4.2.30 |
| 基础库锁文件 | 4.2.29 | 是 | 0 / 3 / 4 / 6 | 4.2.30 |

三条线共有的、OSV 没有给出 4.2 修复版本的高危是 [GHSA-wvqv-fj8w-qmhm](https://github.com/advisories/GHSA-wvqv-fj8w-qmhm)（CVE-2026-15307）。公告范围写成从旧版本修到 **5.2.17**，以及 6.0 线上的 **6.0.8**，描述的是 GeoDjango 空间查询。当前非测试代码里没有 `django.contrib.gis`。升到 4.2.30 不能从 OSV 记录里消掉这一条。

另外两条要到 **4.2.30** 才从 4.2 线上消失：

- [GHSA-933h-hp56-hf7m](https://github.com/advisories/GHSA-933h-hp56-hf7m)：SGI 请求在 `Content-Length` 缺失或偏小时可能绕过上传体积限制。监控由 Gunicorn 以 WSGI 方式提供服务，这条比下面的 ASGI 公告更接近现有部署。
- [GHSA-mvfq-ggxm-9mc5](https://github.com/advisories/GHSA-mvfq-ggxm-9mc5)：ASGI 请求头里下划线与连字符的混淆。仓库里没有 `get_asgi_application`。

日志 `bklog/apps/log_admin_resource/handlers/model_query.py` 的 `_normalize_filter` 对字段和 lookup 做了白名单，并拒绝跨关系过滤。监控 `kernel_api/rpc/functions/bkm_cli/db.py` 同样先按模型白名单整理 filter，再交给 `QuerySet.filter`。这两处只约束各自的只读查询，不能代替升级 Django。

### 2. certifi：严重，HTTPS 校验会用到

业务代码没有 `import certifi`。Elasticsearch、Kubernetes 客户端、requests 和 httpx 用它做证书校验。

[GHSA-6q48-6c7w-9gw2](https://github.com/advisories/GHSA-6q48-6c7w-9gw2) 为严重：打包进去的 emSign 根证书对应的中间证书密钥已不可信。修复版本 **2026.10.18**。

| 组件 | 锁定版本 | 是否低于修复版本 |
| --- | --- | --- |
| 监控镜像 | 2025.1.31 | 是 |
| 基础库锁文件 | 2026.2.25 | 是 |

监控镜像用的是更旧的 2025.1.31。日志的 `requirements.txt` 没有钉 certifi。

### 3. Pillow 11.2.1：严重，已安装，水印功能会调用

监控和基础库都把 Pillow 钉在 **11.2.1**。该版本有 **5 条严重、37 条高、18 条中**。严重项的修复版本都是 **13.0.0**。基础库声明了 `pillow<11.3`，这个上限挡着 13.0.0。

严重公告：

| 公告 | 影响（公告摘要） |
| --- | --- |
| [GHSA-5x8w-8jj5-q52h](https://github.com/advisories/GHSA-5x8w-8jj5-q52h) | FlashPix JPEG 解码堆缓冲区溢出 |
| [GHSA-8g5g-8vmr-9782](https://github.com/advisories/GHSA-8g5g-8vmr-9782) | JPEG 解码堆缓冲区溢出 |
| [GHSA-332p-7hrc-92wf](https://github.com/advisories/GHSA-332p-7hrc-92wf) | 把 TIFF 保存到 `BytesIO` 时的堆缓冲区溢出 |
| [GHSA-v9pv-5gc8-w2m6](https://github.com/advisories/GHSA-v9pv-5gc8-w2m6) | 多帧加载器在模式切换后复用已失效的原生图像内存 |
| [GHSA-w889-685w-c8fh](https://github.com/advisories/GHSA-w889-685w-c8fh) | 调用 Ghostscript 时的参数注入 |

直接引用是本地绘制水印，输出 PNG，不是打开外部图片：

- `bkmonitor/packages/utils/signature.py` 使用 `Image.new`、`ImageDraw`、`ImageFont`，再 `save(..., "PNG")`
- `bklog/apps/utils/image.py` 同样绘制水印。日志的 `requirements.txt` **没有声明** Pillow，但代码导入了 `PIL`
- 仓库里唯一的 `Image.open` 在 `bkmonitor/scripts/verify_pillow_build.py`，用于镜像构建校验

解码类缺陷在当前业务调用点上没有直接入口。字体渲染、旋转、粘贴和 PNG 保存仍走这套已安装的库。

### 4. LangChain：监控镜像上的严重项已经离开 0.3.86，日志仍停在 0.3.75

`langchain-core` 在两条线上版本已经分开。

| 组件 | 锁定版本 | 严重 / 高 / 中 / 低 | 说明 |
| --- | --- | --- | --- |
| 监控镜像 | **0.3.86** | 0 / 1 / 0 / 1 | 0.3 线上的严重项和反序列化高危已经越过 |
| 日志 | **0.3.75** | 1 / 3 / 1 / 1 | 仍低于 0.3.81 |

日志上的严重项是 [GHSA-c67j-w6g6-q2cm](https://github.com/advisories/GHSA-c67j-w6g6-q2cm)（CVE-2025-68664）：序列化接口在 `dumps` / `loads` 路径上可被用于提取密钥。0.3 分支的修复版本是 **0.3.81**。同一旧版本上还有：

| 公告 | 等级 | 0.3 修复版本 | 说明 |
| --- | --- | --- | --- |
| [GHSA-6qv9-48xg-fc7f](https://github.com/advisories/GHSA-6qv9-48xg-fc7f) | 高 | 0.3.80 | 提示词模板的属性访问 |
| [GHSA-pjwx-r37v-7724](https://github.com/advisories/GHSA-pjwx-r37v-7724) | 高 | 0.3.85 | `load()` 允许名单过宽时的反序列化 |
| [GHSA-qh6h-p6c9-ff54](https://github.com/advisories/GHSA-qh6h-p6c9-ff54) | 高 | 无，公告只写到 1.2.22 | 旧的 `load_prompt` 路径处理 |

监控 0.3.86 只剩最后这一条高危和一条低危。`load_prompt` 在 0.3 上没有修复版本。若日志继续留在 0.3，至少要评估到 **0.3.85** 才能盖住严重项和反序列化高危。

直接引用：

- `ai_agent/llm/__init__.py` 导入 `langchain_core.callbacks.BaseCallbackHandler` 和 `langchain_openai.ChatOpenAI`。日志通过符号链接使用同一份代码，并且在 `requirements.txt` 里钉了 `langchain-core==0.3.75`
- `bkmonitor/metadata/agents/diagnostic/metadata_diagnostic_agent.py` 导入 `langchain.agents.Tool`。同文件的 `_load_prompt` 读取本地 markdown，不是 LangChain 的 `load_prompt`

没有搜到业务代码直接调用 LangChain 的 `dumps` / `loads`。监控镜像已经装上 0.3.86；日志安装的仍是 0.3.75。

`langchain==0.3.27` 在监控和日志上都有高危 [GHSA-3644-q5cj-c5c7](https://github.com/advisories/GHSA-3644-q5cj-c5c7)：公开 prompt 拉取会反序列化不受信任的清单。0.3 修复版本是 **0.3.30**。同一条公告在 langsmith 0.3.45 上的修复点是 0.8.0。langsmith 上文件读取那条高危 [GHSA-f4xh-w4cj-qxq8](https://github.com/advisories/GHSA-f4xh-w4cj-qxq8) 的修复点是 **0.8.18**。

同一条 `aidev` 链还带入 `aiohttp==3.11.18`。它现在有 **13 条高、21 条中、16 条低**。13 条高危的修复版本是 **3.14.4**。其中四条的 OSV 记录在 2026-11-24 被修改过，等级和修复版本没有变，见上面的差异说明。业务代码没有 `import aiohttp`，也没有用它启动 HTTP 服务。

### 5. 监控镜像上的 urllib3 仍停在 1.26.20

日志已经把 urllib3 钉在 **2.8.0**，这次查询没有命中公告。监控和基础库锁定的是 **1.26.20**，有 6 条高、1 条中。盖住这 6 条高危的版本是 **2.8.0**。其中两条修复点高于 2.6.3：

- [GHSA-8988-9cw3-xx77](https://github.com/advisories/GHSA-8988-9cw3-xx77)：HTTPS 代理的 TLS 配置可能被忽略或覆盖，修复版本 2.8.0
- [GHSA-vxq7-64xx-v4gw](https://github.com/advisories/GHSA-vxq7-64xx-v4gw)：`stream()` / `read_chunked()` 会把没有上限的 chunk-size 行放进内存，修复版本 2.8.0

另外两条仍可作为代表：

- [GHSA-2xpw-w6gg-jr37](https://github.com/advisories/GHSA-2xpw-w6gg-jr37)：流式接口对高度压缩数据的处理不当，修复版本 2.6.0
- [GHSA-38jv-5279-wg99](https://github.com/advisories/GHSA-38jv-5279-wg99)：跟随重定向时解压保护可被绕过，修复版本 2.6.3

业务代码直接使用它，例如 `bkmonitor/metadata/utils/es_tools.py` 和基础库同名文件里的 `Retry`，以及 `bkmonitor/kernel_api/rpc/functions/admin/kubernetes_pods.py` 的 `Timeout`。Elasticsearch 5/6/7 客户端、requests、Kubernetes 客户端也会加载它。

1.26 系列落后于这些修复点。升到 2.6.3 或 2.7.0 仍会留下上面两条 2.8.0 的高危。旧的 Elasticsearch 客户端仍在依赖树上，升级前需要确认它们能否接受 urllib3 2.8。

### 6. ujson：监控用它替换了标准库 json

监控 **5.7.0**、日志 **5.9.0**，都有 3 条高、1 条中。3 条高危的修复版本是 **5.12.1**。中危 [GHSA-3j69-69wj-xqx2](https://github.com/advisories/GHSA-3j69-69wj-xqx2) 要到 **5.13.0**，描述的是 `dumps` 会接受残缺的 UTF-8 并静默改写。

[GHSA-c38f-wx89-p2xg](https://github.com/advisories/GHSA-c38f-wx89-p2xg) 是写出失败时的内存泄漏。监控在 `settings.py` 里通过 `monkey.patch_all` 把 `json` 换成 `patches/json.py`，其中 `load` / `dump` / `loads` / `dumps` 会调用 ujson。日志多个查询与导出路径直接 `import ujson`。

### 7. mistune：日志会调用 3.x 解析器，高危覆盖点是 3.3.4

日志钉 **3.0.2**（8 条高、9 条中），监控锁 **0.8.4**（7 条高、9 条中）。能盖住当前高危的版本是 **3.3.4**。中危比上次少 2 条，是因为 CVE-2026-44898 和 CVE-2026-44899 的已审核范围只有 3.2.0。监控 `mistune<3`，这个上限挡着 3.3.4。版本和上次相同，两条 2026-11-19 的高危仍在范围内：

- [GHSA-ww7q-mxrj-5ffg](https://github.com/advisories/GHSA-ww7q-mxrj-5ffg)：内联图片解析的二次方 CPU 消耗
- [GHSA-phmp-hrw4-r36r](https://github.com/advisories/GHSA-phmp-hrw4-r36r)：空标签链接的括号扫描

OSV 的影响范围写成 `< 3.3.4`，所以 0.8.4 和 3.0.2 都被标成受影响。公告正文描述的是 3.x 解析器。日志 `bklog/version_log/utils.py` 用 `mistune.create_markdown` 解析部署目录里的版本说明 markdown，和这条描述一致；输入来自仓库自带的 md 文件，不是请求体。监控业务代码没有 `import mistune`，但 `bkmonitor/urls.py` 挂了 `version_log`，而 `django-versionlog` 依赖 `mistune<3`。

此前已有的高危 [GHSA-4j32-57v6-6g45](https://github.com/advisories/GHSA-4j32-57v6-6g45) 在 3.3.0 修复，升到 3.3.4 可以一并盖住。

## 其余高危：生产已安装

下表每个包只列代表公告。数量是该锁定版本上等级为「高」的公告条数。「修复版本」取能盖住这些高危的版本；个别包的中危或低危还要更高，已在说明里标出。

| 组件 | 包 | 锁定版本 | 角色 | 直接引用 | 高 | 修复版本 | 代表公告 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 监控 / 基础库 | cryptography | 44.0.2 / 46.0.5 | 传递（bk-crypto-python-sdk、blue-krill、blueapps） | 业务代码否，测试有 | 4 / 3 | 48.0.1 起，部分要到 50.0.0 | [GHSA-537c-gmf6-5ccf](https://github.com/advisories/GHSA-537c-gmf6-5ccf) 轮子内带的 OpenSSL 有已知问题。加密能力通过 bk-crypto SDK 使用。基础库 46.0.5 另有两条中危：[GHSA-m2h6-j472-rp4c](https://github.com/advisories/GHSA-m2h6-j472-rp4c) 修复 49.0.0，[GHSA-p423-j2cm-9vmq](https://github.com/advisories/GHSA-p423-j2cm-9vmq) 修复 46.0.7。已审核 GHSA 的引入版本是 45.0.0，监控 44.0.2 不在这个范围内。同 CVE 的 PYSEC 把范围写成从 0 起 |
| 监控 / 基础库 | pyasn1 | 0.6.1 / 0.6.2 | 传递（rsa、pyasn1-modules） | 否 | 9 / 8 | 0.6.5 | [GHSA-2qm8-x737-gmw5](https://github.com/advisories/GHSA-2qm8-x737-gmw5) BER 解码存在二次方 CPU 消耗 |
| 监控、日志、基础库 | djangorestframework | 3.15.1 / 3.15.2 | 直接依赖 | 是 | 3 | 3.18.2 | [GHSA-33wh-fxxf-88vv](https://github.com/advisories/GHSA-33wh-fxxf-88vv) `Accept` 协商可造成明显 CPU 消耗。基础库 `djangorestframework<3.16.0` 挡着 3.18.2 |
| 监控、日志、基础库 | kafka-python | 1.4.6 / 2.0.2 | 直接依赖 | 是 | 2 | 2.3.2 | [GHSA-2jcm-hq8r-84wx](https://github.com/advisories/GHSA-2jcm-hq8r-84wx) SCRAM 迭代次数未限制。监控 metadata 的数据源与存储代码直接导入 |
| 监控 | dnspython | 2.6.1 | 直接依赖 | 是 | 2 | 2.9.2 | [GHSA-45c3-73f7-pv4m](https://github.com/advisories/GHSA-45c3-73f7-pv4m) 域名解析可造成过高 CPU，这条在 2.9.0 修复。另一条高危 [GHSA-vvf4-9x63-8xvv](https://github.com/advisories/GHSA-vvf4-9x63-8xvv) 要到 2.9.2。调用点是 `bkmonitor/bkmonitor/utils/dns_resolve.py`，目前只被 `transfer_story.py` 用来解析 `settings.TRANSFER_HOST` |
| 监控 | mako | 1.3.10 | 传递（blueapps） | 是 | 2 | 1.3.12（另有中危到 1.4.2） | [GHSA-2h4p-vjrc-8xpq](https://github.com/advisories/GHSA-2h4p-vjrc-8xpq) `TemplateLookup` 的路径处理。监控模板后端 `packages/monitor_web/core/template/backends/mako.py` 直接使用。高危和那条中危描述的都是 Windows 路径 |
| 监控 / 基础库 | msgpack | 1.1.0 / 1.1.2 | 传递（influxdb） | 否 | 2 | 1.2.3 | [GHSA-6v7p-g79w-8964](https://github.com/advisories/GHSA-6v7p-g79w-8964) 捕获错误后重复使用 `Unpacker` 时越界读取，这条在 1.2.1 修复。另一条高危要到 1.2.3 |
| 监控 / 基础库 | oauthlib | 3.2.2 / 3.3.1 | 传递（requests-oauthlib） | 否 | 1 / 2 | 4.0.0 / 4.0.1 | [GHSA-3jp2-3mrg-2vxc](https://github.com/advisories/GHSA-3jp2-3mrg-2vxc) 只影响 3.3.0 及以上：设备流程中，知道合法 client ID 即可能取回 Bearer token。监控 3.2.2 的那条高危修复点是 4.0.0 |
| 日志 / 监控 | protobuf | 3.20.3 / 3.19.5 | 直接依赖 | 否 | 2 | 5.29.6 | [GHSA-7gcm-g887-7qv7](https://github.com/advisories/GHSA-7gcm-g887-7qv7) JSON 递归深度限制可被绕过。另一条高危在 4.25.8 已修复，5.29.6 可以同时盖住。OpenTelemetry 把 protobuf 留在 3.x |
| 监控 | mcp | 1.27.1 | `aidev` 直接钉死，也由 langchain-mcp-adapters 带入 | 否 | 4 | 1.30.0 | [GHSA-qx49-fqc8-xw99](https://github.com/advisories/GHSA-qx49-fqc8-xw99) OAuth 客户端可能把凭据交给 MCP 服务端指定的授权服务器。仓库里没有 `OAuthClientProvider`。另外两条高危要到 1.27.2，WebSocket Host/Origin 那条要到 1.28.1。四条中危的修复点也是 1.30.0 |
| 监控 | python-multipart | 0.0.20 | 传递（mcp） | 否 | 3 | 0.0.30（另有低危到 0.0.31） | [GHSA-5rvq-cxj2-64vf](https://github.com/advisories/GHSA-5rvq-cxj2-64vf) 查询串解析存在二次方 CPU 消耗 |
| 监控 | starlette | 0.50.0 | `aidev` 直接钉死，也由 mcp 带入 | 否 | 2 | 1.3.1 | [GHSA-82w8-qh3p-5jfq](https://github.com/advisories/GHSA-82w8-qh3p-5jfq) `request.form()` 对 `application/x-www-form-urlencoded` 的体积限制可能不生效。另一条高危修复点是 1.1.0，描述的是 Windows 上的 UNC 路径 |
| 监控 | langsmith | 0.3.45 | 传递（langchain 系列） | 否 | 2 | 0.8.18 | [GHSA-f4xh-w4cj-qxq8](https://github.com/advisories/GHSA-f4xh-w4cj-qxq8) `TracingMiddleware` 可读取服务端文件 |
| 监控 | anyio | 4.9.0 | 传递（httpx、mcp、starlette） | 否 | 严重 1 | 4.14.2 | [GHSA-82r6-8w77-94w6](https://github.com/advisories/GHSA-82r6-8w77-94w6) `TLSStream` 仍按 IDNA 2003 编码主机名 |
| 监控 | orjson | 3.10.18 | 传递（langsmith） | 否 | 1 | 3.11.6 | [GHSA-hx9q-6w63-j58v](https://github.com/advisories/GHSA-hx9q-6w63-j58v) 深层嵌套 JSON 没有递归上限。已审定的 GHSA 写明 3.11.6；同 CVE 的 PYSEC 写成 3.11.5，这里取 GHSA |
| 监控 | langchain-core | 0.3.86 | `aidev` 直接依赖 | 是 | 1 | 1.2.22 | [GHSA-qh6h-p6c9-ff54](https://github.com/advisories/GHSA-qh6h-p6c9-ff54) 旧的 `load_prompt` 路径。0.3 线上没有修复版本 |

`mcp`、`python-multipart`、`starlette`、`langsmith`、`orjson`、`aiohttp` 都挂在监控默认组 `aidev` 带入的链路上。不用这组 AI 能力时，它们仍然会按当前 Dockerfile 装进监控镜像。

## 中危与低危

这些包的最高等级是中或低，且会进生产安装集。

| 包 | 锁定版本 | 直接引用 | 说明 |
| --- | --- | --- | --- |
| requests | 2.32.5（三个组件一致） | 是 | [CVE-2026-25645](https://osv.dev/vulnerability/CVE-2026-25645)，修复版本 2.33.0。`extract_zipped_paths()` 使用可预测的临时文件名 |
| opentelemetry-api | 监控 1.25.0，日志 1.24.0 | 是 | 修复版本 1.45.2。1.45.1 只盖住 tracestate；traceparent 解析那条中危要到 1.45.2。监控已从 1.11.1 升到 1.25.0，这两条仍在 |
| python-dotenv | 监控 0.21.1 | 是 | 修复版本 1.2.2。`set_key` 在跨设备回退时可能跟随符号链接。监控 `manage.py` 直接导入。基础库锁的是 1.2.2，这条中危不再命中基础库 |
| markdown | 日志 3.3 | 是 | 修复版本 3.8.1，未捕获异常。日志数据总线常量模块直接导入 |
| langchain-text-splitters | 监控 0.3.11 | 否 | 修复版本 1.1.2，从 URL 拉 HTML 时的重定向。属 aidev 直接依赖 |
| marshmallow | 监控 3.26.1 | 否 | 修复版本 3.26.2，`Schema.load(many=...)` 的拒绝服务。由 environs / dataclasses-json 引入 |
| idna | 监控 3.10，基础库 3.11 | 否 | 修复版本 3.15。requests、httpx、yarl 会用到 |
| h2 / hpack | 监控 4.2.0 / 4.1.0 | 否 | 修复版本 4.4.1 / 4.2.0。由 grpclib 引入。4.3.0 只盖住其中一条中危 |
| setuptools | 监控 79.0.1，日志 80.9.0，基础库 82.0.1 | 否 | 代表修复版本 83.0.0，描述的是 sdist 清单绕过，运行中的服务收益有限。另有一条低危要到 84.1.0，描述的是 Windows 路径 |
| werkzeug | 监控 3.1.3 | 否 | 由 aidev-agent、blueapps 引入。代表项是 Windows 设备名路径，当前公告要到 3.1.9 |
| pygments | 监控 2.19.1 | 否 | 低。正则表达式拒绝服务，修复版本 2.20.0 |
| langchain-openai | 监控 0.3.35 | 是（`ai_agent`） | 低。图片 token 计数的 SSRF 防护可被绕过，修复版本 1.1.14 |

## 未进入生产镜像

这些高危包在锁定结果里，但当前生产安装命令不会装它们。

| 包 | 版本 | 位置 | 说明 |
| --- | --- | --- | --- |
| virtualenv | 15.2 | 日志 `requirements_dev.txt` | 10 条高。盖住这 10 条的版本是 21.14.9。另有中危 [GHSA-597g-3phw-6986](https://github.com/advisories/GHSA-597g-3phw-6986)（CVE-2026-22702），修复版本 20.36.1 |
| virtualenv | 20.30.0 / 21.2.0 | 监控与基础库的开发依赖传递 | 各 10 条高，同样要到 21.14.9。20.30.0 另有中危 CVE-2026-22702，修复版本 20.36.1。CVE-2026-113713 的已审核范围只有 21.14.8 和 21.14.9，这三个版本都不计入。只影响本机或 CI 创建虚拟环境 |
| filelock | 基础库 3.25.1 | 基础库开发依赖传递 | 1 条高，修复版本 4.2.1。监控开发锁里的 3.18.0 最高为中，但其中部分中危的修复点也是 4.2.1 |
| pytest | 基础库 7.0.1，监控 8.3.4 | 直接开发依赖 | 中，修复版本 9.0.3 |

## 抽查后未命中公告的包

同一次查询中，下面这些直接依赖没有未撤回的 OSV 记录：

- Jinja2 **3.1.6**
- PyYAML **6.0.1**（监控、基础库）与 **6.0.2**（日志）
- Gunicorn **23.0.0**
- Redis **4.6.0**、Celery **5.4.0**、Elasticsearch **7.17.12**
- PyJWT **2.15.1**、sqlparse **0.6.1**
- 日志侧 urllib3 **2.8.0**
- 监控镜像里的 openai **2.38.0**、uuid-utils **0.19.0**、tiktoken **0.9.0**、promql-parser **0.12.0**
- 日志钉死的 tiktoken **0.11.0**

没有记录只说明扫描当日的公开库没有匹配项，不表示这些包没有其他风险。

## 建议的处理顺序

1. 把日志 Django 从 4.2.22 升到不低于 4.2.30，并复扫。这是当前唯一落在严重 SQL 注入修复点之前的业务框架版本。
2. 把监控镜像的 Django 从 4.2.27 升到不低于 4.2.30。4.2.27 仍低于 CVE-2026-1207 和 CVE-2026-1287 的 4.2.28。基础库锁文件里的 4.2.29 也低于 4.2.30。GeoDjango 那条在 OSV 里没有 4.2 修复版本，当前代码未使用 GeoDjango。
3. 把监控镜像的 certifi 升到不低于 2026.10.18。基础库锁文件里的 2026.2.25 也低于该版本。
4. 评估 Pillow 11.2.1 升到 13.0.0，并放宽基础库的 `pillow<11.3`。水印路径本身不解码外部图片，但生产镜像装的是带多条严重内存缺陷的版本，日志代码还在导入一个未声明的 `PIL`。
5. 把日志的 `langchain-core` 升到不低于 0.3.85，`langchain` 升到不低于 0.3.30。监控镜像的 langchain-core 已是 0.3.86，严重项和 0.3 线上的反序列化高危已经离开；`load_prompt` 高危在 0.3 上没有修复版本。若继续把 `aidev` 装进监控镜像，将 `aiohttp` 升到不低于 3.14.4，`langsmith` 升到不低于 0.8.18，`starlette` 升到不低于 1.3.1，`mcp` 升到不低于 1.30.0，并连带看 python-multipart。mcp 1.27.1 仍低于 1.27.2。
6. 把监控与基础库的 urllib3 从 1.26.20 升到不低于 2.8.0，先确认 Elasticsearch 5/6 客户端是否还能工作。日志已经在 2.8.0，且这次没有公告。
7. 将 ujson 升到不低于 5.12.1 以盖住高危；中危要到 5.13.0。监控启动时用它替换了 `json` 的读写函数。
8. 日志的 mistune 可升到不低于 3.3.4。监控的 `mistune<3` 会挡住这个版本，需要和 `django-versionlog` 一起看。当前日志只解析部署目录里的版本说明。
9. djangorestframework、kafka-python、dnspython（2.9.2）、msgpack（1.2.3）、cryptography、protobuf 的修复版本跨度较大，适合单独排期。基础库的 `djangorestframework<3.16.0` 会挡住对应修复版本。

## 局限

- 日志的传递依赖没有锁文件，不在本次版本范围内。日志代码导入了 `PIL`，但 requirements 没有钉 Pillow。
- `bkmonitor/support-files/bkai/package/skills/bk-monitor-data-fetcher/requirements.txt` 只写了 `requests` 和 `PyYAML` 的范围，没有钉版本，不在这次精确版本查询里。其中脚本直接导入 requests。同目录下的 `mcp` 是这个脚本的别名，不是 PyPI 上的 `mcp` 包。
- OSV 对 mistune 两条高危的范围是 `< 3.3.4`。公告正文讲的是 3.x 解析器，0.8.4 是否包含同一段实现，范围本身没有分开写。
- mistune 的 CVE-2026-44898、CVE-2026-44899：已审核 GHSA 只覆盖 3.2.0，修复 3.2.1。PYSEC 从 0 起，因此查询会命中 0.8.4 和 3.0.2。按已审核 GHSA 的范围，这两个锁定版本不计入这两条中危。
- cryptography 的 CVE-2026-69248：已审核 GHSA 从 45.0.0 修到 49.0.0，基础库 46.0.5 命中，等级为中。同 CVE 的 PYSEC 把引入版本写成 0，因此查询也会命中监控 44.0.2。按已审核 GHSA 的范围，监控 44.0.2 不计入这条。基础库 46.0.5 另有中危 CVE-2026-39892，修复版本 46.0.7。
- virtualenv 的 CVE-2026-113713：已审核 GHSA 只覆盖 21.14.8 和 21.14.9，修复 21.14.10。PYSEC 从 20.0.6 起，因此查询会命中 20.30.0 和 21.2.0。按已审核 GHSA 的范围，当前三个锁定版本都不计入。15.2 和 20.30.0 另有中危 CVE-2026-22702，修复版本 20.36.1。
- 导入扫描覆盖不到完全动态的导入。已经核对过的直接引用在上文点了文件。

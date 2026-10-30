# BKLog KMS 启动凭据

KMS 是显式开启的启动配置来源。业务进程在内存解密一次，不连接远程 KMS，不写回环境变量或配置文件。进程重启前沿用启动时的快照。

## 接入接口

- `ENABLE_KMS=true`
- `KMS_ENVELOPE_FILE=/etc/bk-kms/envelope`
- `KMS_PRIVATE_KEY_FILE=/etc/bk-kms/private-key`
- `BKPAAS_APP_ID`（或原 `APP_ID`）保留为预期应用标识，必须和信封中的 `app_code` 一致。

两个文件均为官方 SDK 接收的 Base64 字符串。不要预先 Base64 解码。信封和私钥必须配套，JSON 使用最终确认的七组结构：

```json
{
  "bkapp_id_secret": {"default": {"app_code": "bk_log_search", "app_secret": "..."}},
  "mysql": {"default": {"username": "...", "password": "..."}},
  "rabbitmq": {"default": {"username": "...", "password": "..."}},
  "redis": {"default": {"password": "..."}},
  "bkrepo": {"default": {"username": "...", "password": "..."}},
  "bcs": {"default": {"token": "..."}},
  "encryption": {"bk_crypto_key": ""}
}
```

所有字段必须存在且为字符串；APP 身份、MySQL/RabbitMQ 用户名、BCS token 不允许为空。密码字段可以显式为空（例如无鉴权 Redis）；启用 BKRepo 时它的用户名和密码必须非空。`bk_crypto_key` 可以为空，继续使用 SaaS 内原有的 `SECRET_KEY` 回退。没有 Sentinel 密码字段。

缺文件、错误私钥、错误 JSON、缺字段、应用标识不匹配、不可用业务加密 key/算法均阻止启动。错误信息仅包含字段名和失败阶段。KMS 模式禁止同时注入原来的业务明文凭据环境变量，以及 CELERY_BROKER_URL / CELERY_BROKER_READ_URL / CELERY_BROKER_WRITE_URL；非敏感地址、端口、数据库名、vhost 等沿用现有配置。

身份经 `config.get_env_or_raise()` 提供给 Blueapps，Redis 默认缓存派生前注入密码；prod/stag/dev 的环境及本地配置加载后统一应用最终凭据。RabbitMQ 用户名、密码及框架生成的 vhost 进行 URL 转义。Grafana 仍使用独立原生 Secret 提供管理身份及数据库凭据，未放入应用信封。

## 版本与兼容

- KMS 使用 `bk-kms-sdk==1.0.0`，需要 Python >=3.11,<3.15；加密库固定 `bk-crypto-python-sdk[gm]==4.1.1`。
- 当前基线已有 `bamboo-pipeline==4.0.0` 要求 Python 3.11。非 K8s 回归在同一受支持版本下执行；关闭 KMS 的运行路径不导入 SDK，也不读取信封文件。Python 3.10 完整依赖解析因原有 pipeline 约束失败，不能声称该版本已通过兼容验证。
- 取钥 hook 只保留原始密钥优先级；通过 SDK 的 SYMMETRIC_CIPHER_CLASSES 标准扩展点，在 cipher 构造时保留 2.x 的“编码后按字节截断”规则。此时每个别名的 key_size、encoding 已合并，保留 mode/padding/前缀。不得重写历史密文或重新生成业务 key。
- `BaseCrypt` 仍直接依赖 `SECRET_KEY`；配置独立 `bk_crypto_key` 不代表可以安全轮转 APP Secret。切换 KMS 时录入原值。
- `Crypto.*` 仍由显式 `pycryptodome` 依赖提供。

## 本地验证

在两个隔离解释器中分别安装旧 SDK 2.0.0 与当前 requirements，然后执行：

```sh
BKLOG_CRYPTO2_PYTHON=/path/to/crypto2/bin/python python -m pytest bklog/tests/kms -q
```

测试使用随机生成的本地 RSA 密钥、合成凭据和临时 SQLite，不读取环境业务秘密。覆盖真实 CBC/CTR 信封、字段/故障校验、全部业务入口的最终 settings、Redis 单机/Sentinel、非 K8s 与 KMS 关闭路径，以及旧→新→旧 ORM 密文互读。

Helm Chart 单独运行 `bk-log-search/ci/test_kms_render.py`，覆盖业务进程和 Job、辅助容器、ESO/TLS/SA、Grafana、渲染中明文排除及关闭兼容。

本地 settings/ORM/渲染验证不替代镜像运行与环境联调。ESO 实际鉴权、首次安装/升级、滚动重启、外部中间件连通及业务验收需在环境联调阶段验证。

2026-10-30 复查修复：Redis LOCATION 的 URL 认证段及 password 查询参数会被清理，最终由 OPTIONS.PASSWORD 提供密码；地址、ACL 用户名、DB、TLS 参数保留。Chart 环境变量只展开一次，校验后输出同一结果。回归加入真实 Celery 连接、Redis 连接池和 default/archive 双别名 ORM 互读。

2026-10-30 剩余入口修复：最终配置同时处理 BROKER_URL、BROKER_READ_URL、BROKER_WRITE_URL 及 CELERY_ 别名，保留各自地址、端口、vhost、query 和 list/tuple/分号故障转移结构；未配置的读写地址保持原回退，隐式主机默认行为保留。Redis CONNECTION_POOL_KWARGS 中已有的 password 同步取 KMS（空密码按库的 None 无鉴权语义），其他连接池参数及 Sentinel 认证不变。

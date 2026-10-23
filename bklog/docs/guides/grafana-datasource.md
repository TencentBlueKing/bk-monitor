# 日志平台 Grafana 数据源接入指南

本文说明如何在自建 Grafana 中安装日志平台数据源插件，并查询日志数据。

接入方式与监控平台的 Grafana 数据源一致：插件通过监控平台的日志查询代理访问日志数据，日志平台侧无需额外配置。

## 前置条件

- Grafana 版本 >= 7.5
- 能访问监控平台地址
- 具备监控平台的 Grafana Editor 或「业务规则管理」权限，用于获取 Token

## 1. 安装插件

将 `bk_log_datasource.zip` 解压到 Grafana 的插件目录：

```bash
unzip bk_log_datasource.zip -d /var/lib/grafana/plugins/

# 确认插件目录直接包含 plugin.json
ls /var/lib/grafana/plugins/bk_log_datasource/plugin.json
```

## 2. 放行未签名插件

编辑 Grafana 的 `grafana.ini`：

```ini
[plugins]
allow_loading_unsigned_plugins = bk_log_datasource
```

如果已配置其他插件，用英文逗号追加，不要在逗号后加空格。

## 3. 重启 Grafana

```bash
systemctl restart grafana-server
```

重启后可在「管理 → 插件」中看到 `BlueKing Log TimeSeries`。

## 4. 添加数据源

进入「管理 → 数据源 → 添加数据源」，搜索 `BlueKing Log TimeSeries`，按下表填写：

| 字段 | 值 |
| --- | --- |
| Base Url | `https://<监控平台域名>/rest/v2/grafana/bk_log_search/` |
| 蓝鲸监控 | 打开 |
| Allowed cookies | 留空；需要多租户隔离时按需配置 |
| 业务ID | 需要查询的业务 ID |
| Token | 见下一步 |

注意：

- Base Url 必须包含 `bk_log_search/`，且保留末尾斜杠，否则请求会 404
- 「蓝鲸监控」开关必须打开。关闭后插件会走浏览器直连，自建 Grafana 没有监控登录态，查询会失败

## 5. 获取 Token

在已登录监控平台的浏览器中访问：

```
https://<监控平台域名>/rest/v2/commons/token_manager/get_api_token/?bk_biz_id=<业务ID>&type=grafana
```

返回结果中的 `data` 字段即 Token，填入数据源配置后保存。

Token 为业务级凭证，只能查询其绑定业务的数据。

## 6. 验证

保存后点击 Save & Test：

- 提示 404 属于已知现象：插件的测试请求指向 Base Url 根路径，监控侧没有该路由，不影响查询
- 提示 401/403 时，检查 Token 是否有效，以及业务 ID 是否与获取 Token 时的 `bk_biz_id` 一致

实际查询验证：新建 Explore，选择该数据源，指标下拉应能加载业务下的索引集列表；切换到日志查询可查看日志明细。

## 常见问题

**查询返回 `namespace biz#x is not allowed in [biz#y]`**

Token 绑定的业务与请求的业务不一致。检查数据源的「业务ID」是否与获取 Token 时的 `bk_biz_id` 相同。

**指标或日志为空**

确认业务下已有索引集，且当前账号在监控平台有该业务的查看权限。

**插件加载失败**

检查 `allow_loading_unsigned_plugins` 是否包含 `bk_log_datasource`，以及插件目录下是否直接存在 `plugin.json`（不要多套一层目录）。

**Token 失效**

重新访问第 5 步的地址获取 Token，覆盖数据源中的 Token 后保存。

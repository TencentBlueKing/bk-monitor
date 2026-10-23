# Grafana 添加日志数据源

1. 将数据源插件包解压到 Grafana 的 plugins 目录中

2. 在 grafana.ini 中放行未签名插件

```ini
[plugins]
allow_loading_unsigned_plugins = bk_log_datasource
```

3. 重启 Grafana

4. Base Url 配置示例：`https://<监控平台域名>/rest/v2/grafana/bk_log_search/`（不同环境仅需更改域名）

5. 配置数据源需要填写业务 ID，并打开「蓝鲸监控」开关

6. Token 通过以下 URL 获取：

```
https://<监控平台域名>/rest/v2/commons/token_manager/get_api_token/?bk_biz_id=${你的业务ID}&type=grafana
```

7. 可以配置 Allowed cookies，配置后会提取对应的 cookies 加入过滤条件

> 注：Save & Test 提示 404 属于已知现象，插件的测试请求指向 Base Url 根路径，不影响查询

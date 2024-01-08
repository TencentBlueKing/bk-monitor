# 企业版移动端配置

## Nginx代理配置
企业版蓝鲸往往部署在内网环境，如果需要对外暴露移动端的访问地址，则需要使用nginx等服务进行服务代理。
在此情况下，对外提供服务的域名与访问路径，可能和内网的配置完全不同。
监控的移动端服务路径为`/weixin/`子目录，静态文件为`/static/weixin/`。出于安全考虑，!!#ff0000 强烈建议!!只暴露这两个路径到外网，减小可能的风险。
在多层代理的情况，域名和访问路径都会丢失，而监控的服务需要得到实际的外网域名与外网访问地址，因此需要传递额外的请求头，将相关信息传递下去。

举个例子:
移动端服务的内网地址是 `http://internal.com/o/bk_monitorv3/weixin/`，但是用户希望的外网访问地址应该是`http://external.com/xxxxx/bkmonitor/`

此时，需要在nginx的代理配置中，增加以下请求头。
```
proxy_set_header X-Forwarded-WeiXin-Host "external.com";
proxy_set_header X-Original-URI "/xxxxx/bkmonitor/";
```

## 环境变量
```
# 启用移动端服务
BKAPP_USE_WEIXIN="1"
# 使用企业微信鉴权
BKAPP_IS_QY_WEIXIN="1"

# 移动端外网访问地址，需要与nginx的实际配置对应
BKAPP_WEIXIN_SITE_URL="/xxxxx/bkmonitor/"
# 移动端静态资源外网访问地址，需要与nginx的实际配置对应
BKAPP_WEIXIN_STATIC_URL="/xxxxx/bkmonitor/static/"
# 移动端外网域名schema http/https，如果内外网一致可以不配置
BKAPP_WEIXIN_APP_EXTERNAL_SCHEME="https"
# 移动端外网访问域名
BKAPP_WEIXIN_APP_EXTERNAL_HOST="external.com"

# 微信 appid / 企业微信 corp id
BKAPP_WEIXIN_APP_ID="app1"
# 微信/企业微信 secret
BKAPP_WEIXIN_APP_SECRET="xxxxxxxxxxxxxxxx"
# 企业微信 agent id
BKAPP_WEIXIN_AGENT_ID=""

# 私有化版本企业微信配置
# 私有化版本企业微信oauth地址，对应SaaS版的 https://open.weixin.qq.com
BKAPP_WEIXIN_QY_OPEN_DOMAIN=""
# 私有化企业微信API地址，对应SaaS版的 https://qyapi.weixin.qq.com
BKAPP_WEIXIN_QY_API_DOMAIN=""
```

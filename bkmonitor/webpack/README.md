#### 监控前端构建使用说明

###### 安装和更新前端依赖（`nodejs`最小依赖版本为`V14.18.0`）

```bash
cd webpack
npm i -g pnpm
pnpm i
```

如果您尚未安装过 `nodejs` [详细安装参见](https://nodejs.org/zh-cn/download/)

###### 本地开发模式

- 本地启动

  ```bash
  # 监控平台本地开发模式
  npm run dev
  # 移动端本地开发模式
  npm run mobile:dev
  # 故障自愈本地开发模式
  npm run fta:dev
  ```

- 前端环境变量配置

  1. 新建文件 `local.settings.js`

  2. 配置自定义内容 参考如下 [更多配置参见](https://webpack.docschina.org/configuration/dev-server/)

     ```js
    const context = ['/apm', '/rest', '/fta', '/api', '/weixin', '/version_log', '/calendars'];
    const changeOrigin = true;
    const secure = false;

    const devProxyUrl = 'http://hostname.com'
    const loginHost = `${devProxyUrl}/login`
    const host = 'appdev.hostname.com'
    const proxy = {
      context,
      changeOrigin,
      secure,
      target: devProxyUrl,
      headers: {
        host: devProxyUrl.replace(/https?:\/\//i, ''),
        referer: devProxyUrl,
        // 'X-CSRFToken': '',
        // Cookie: ``
      }
    }

    module.exports = {
      devProxyUrl,
      loginHost,
      host,
      proxy
    };

     ```

###### 生产构建

- 构建 pc 端和移动端

  ```bash
  npm run build
  ```

- 仅构建 pc 端

  ```bash
  npm run pc:build
  ```

- 仅构建移动端

  ```bash
  npm run mobile:build
  ```
- 仅构建故障自愈

  ```bash
  npm run fta:build
  ```

###### 其他命令

- 本地一键构建用于上云环境

  ```bash
  npm run prod
  ```

- 移动构建产品到 `static/`目录下

  ```bash
  npm run replace
  ```

- 分析构建产物组成

  ```bash
  # pc端生产环境构建产物分析
  npm run analyze
  # 移动端生产环境构建产物分析
  npm run analyze:mobile
  ```

###### 前端构建工具 `@blueking/bkmonitor-cli`

```bash
cd webpack
git submodule update packages/cli
```

#### help

- 前端构建最小依赖 node 版本 V14.18.1 更推荐使用 V16.13.0以上版本node 性能更好
- 编译过程中出现任何问题请联系 admin

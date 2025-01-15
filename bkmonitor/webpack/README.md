### 蓝鲸监控平台前端开发指引

#### 安装依赖

- [pnpm](https://pnpm.io/installation) 用于前端依赖管理

- [nvm](https://github.com/nvm-sh/nvm?tab=readme-ov-file#installing-and-updating) 用于nodejs 版本管理 `nodejs`版本要求在 `20`版本以上

#### 开发使用

- 安装依赖

  ```bas
  nvm use
  pnpm i // 或者使用 make deps
  ```

- 开发本地配置

  - 在前端根目录下创建文件 `local.settings.js` 并复制和按需配置 `webpack server` 配置

  - ```javascript
    const context = ['/apm', '/rest', '/fta', '/api', '/weixin', '/version_log', '/calendars', '/alert', '/query-api'];
    const changeOrigin = true;
    const secure = false;
    const devProxyUrl = 'http://xxx.com'; // 代理的后台api目标环境地址

    const host = `appdev.${devProxyUrl.match(/\.([^.]+)\.com\/?/)[1]}.com`; // 本地hosts配置的同级域名
    const proxy = {
      context,
      changeOrigin,
      secure,
      target: devProxyUrl,
      headers: {
        host: devProxyUrl.replace(/https?:\/\//i, ''),
        referer: devProxyUrl,
        'X-CSRFToken': '', // 监控平台api所需的 X-CSRFToken
        Cookie: ``, // 监控平台api所需的 cookie
      },
    };
    const defaultBizId = proxy.headers.Cookie.match(/bk_biz_id=([^;]+);?/)[1]; // 默认空间业务id
    module.exports = {
      devProxyUrl,
      host,
      proxy,
      defaultBizId,
    };
    ```

  - 执行命令 `pnpm dev` 或者 `make pc:dev`

  - 监控平台前端采用的是微前端架构，启动或开发其他微应用的指令可参考 `package.json` 中`scripts`项的配置 或者查看 `Makefile`文件（推荐）

  - 其他 `make --`指令如下

    ```javascript
    Usage:
      make <target>

    Dependencies
      deps             Install frontend dependencies.

    Development
      dev-pc           Start development server for Monitor.
      dev-apm          Start development server for Monitor APM.
      dev-fta          Start development server for Monitor FTA.
      dev-vue3         Start development server for Monitor Vue3 APP.
      dev-mobile       Start development server for Monitor Mobile APP.
      dev-external     Start development server for Monitor External APP.

    Build
      build            Build all applications in parallel.
      prod             Build for production, then clean and move files to ../static/.
      build-s          Build all applications in serial.
      build-pc         Build Monitor.
      build-apm        Build Monitor APM.
      build-fta        Build Monitor FTA.
      build-vue3       Build Monitor Vue3 APP.
      build-mobile     Build Monitor Mobile APP.
      build-external   Build Monitor External APP.

    Linter
      check-pc         Biome check monitor-pc code.
      eslint-pc        Eslint check monitor-pc code.

    Visualization
      vis-pc           Visualize Monitor.
      vis-apm          Visualize Monitor APM.
      vis-fta          Visualize Monitor FTA.
      vis-vue3         Visualize Monitor Vue3 APP.
      vis-mobile       Visualize Monitor Mobile APP.
      vis-external     Visualize Monitor External APP.

    Docker
      docker-build     Build Docker image and extract frontend.tar.gz.

    Utilities
      clean            Clean old static files.
      move             Move new build files to static directory.
      reflesh-git-hooks  Reflesh git hooks.

    Help
      help             Display this help.
    ```

#### 构建监控

- 并行构建

  ```bash
  pnpm run build // 或者 make build
  ```

- 串行构建

  ```bas
  make build-s // 或者 使用 npx run-s [...targes]
  ```

- Paas平台构建

  ```bash
  make prod // 或者 pnpm run prod
  ```

- Docker 构建

  ```bash
  make docker-build // 或者 ./docker_build.sh
  ```

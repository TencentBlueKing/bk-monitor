import logWebManifest from '@blueking/log-web';

/**
 * 构建完整的资源 URL
 * @param relativePath 相对路径
 * @param isDev 是否为开发环境, process.env.NODE_ENV === 'development'
 * @returns 完整的资源 URL
 */
export const getResourceUrl = (relativePath: string) => {
  // 获取 BK_STATIC_URL，例如: "/static/dist"
  const bkStaticUrl = (window as any).BK_STATIC_URL || '/static/dist';

  // 生产环境：根据 BK_STATIC_URL 构建完整路径（V1版本兼容包）
  // 例如: BK_STATIC_URL = "/static/dist" -> "/static/dist/log-web1-dll/js/main.xxx.js"
  return `${bkStaticUrl}/log-web1-dll/${relativePath}`;
};

/**
 * 检查资源是否存在
 * @param url 资源 URL
 * @param timeout 超时时间（毫秒），默认 5000ms
 * @returns Promise<boolean> 资源是否存在
 */
export const checkResourceExists = async (url: string, timeout = 5000): Promise<boolean> => {
  return new Promise((resolve) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => {
      controller.abort();
      resolve(false);
    }, timeout);

    fetch(url, {
      method: 'HEAD',
      signal: controller.signal,
      cache: 'no-cache',
    })
      .then((response) => {
        clearTimeout(timeoutId);
        resolve(response.ok);
      })
      .catch(() => {
        clearTimeout(timeoutId);
        resolve(false);
      });
  });
};

/**
 * 验证资源清单和资源文件
 * @returns Promise<{ valid: boolean; error?: string }> 验证结果
 */
export const validateResources = async (): Promise<{ valid: boolean; error?: string }> => {
  try {
    const manifest = logWebManifest;
    if (!manifest || !manifest.entryJs || !manifest.entryCss) {
      return { valid: false, error: '资源清单不完整' };
    }

    const jsUrl = getResourceUrl(manifest.entryJs);
    const cssUrl = getResourceUrl(manifest.entryCss);

    // 并行检查 JS 和 CSS 资源
    const [jsExists, cssExists] = await Promise.all([checkResourceExists(jsUrl), checkResourceExists(cssUrl)]);

    if (!jsExists && !cssExists) {
      return {
        valid: false,
        error: `资源文件不存在，请检查构建配置。JS: ${manifest.entryJs}, CSS: ${manifest.entryCss}`,
      };
    }
    if (!jsExists) {
      return {
        valid: false,
        error: `JS 资源文件不存在: ${manifest.entryJs}，请检查构建配置`,
      };
    }
    if (!cssExists) {
      return {
        valid: false,
        error: `CSS 资源文件不存在: ${manifest.entryCss}，请检查构建配置`,
      };
    }

    return { valid: true };
  } catch (err: any) {
    return { valid: false, error: err.message || '资源验证失败' };
  }
};

// 获取主站点中的环境变量
export const getEnvVariables = (isDev: boolean) => {
  const envVars = [
    'SITE_URL',
    'AJAX_URL_PREFIX',
    'BK_STATIC_URL',
    'LOGIN_SERVICE_URL',
    'MONITOR_URL',
    'BKDATA_URL',
    'COLLECTOR_GUIDE_URL',
    'FEATURE_TOGGLE',
    'FEATURE_TOGGLE_WHITE_LIST',
    'SPACE_UID_WHITE_LIST',
    'FIELD_ANALYSIS_CONFIG',
    'REAL_TIME_LOG_MAX_LENGTH',
    'REAL_TIME_LOG_SHIFT_LENGTH',
    'RUN_VER',
    'TITLE_MENU',
    'MENU_LOGO_URL',
    'APP_CODE',
    'BK_DOC_URL',
    'BK_FAQ_URL',
    'BK_DOC_QUERY_URL',
    'BK_HOT_WARM_CONFIG_URL',
    'BIZ_ACCESS_URL',
    'DEMO_BIZ_ID',
    'ES_STORAGE_CAPACITY',
    'TAM_AEGIS_KEY',
    'BK_LOGIN_URL',
    'BK_DOC_DATA_URL',
    'BK_PLAT_HOST',
    'BK_ARCHIVE_DOC_URL',
    'BK_ETL_DOC_URL',
    'BK_ASSESSMEN_HOST_COUNT',
    'ENABLE_CHECK_COLLECTOR',
    'IS_EXTERNAL',
    'BCS_WEB_CONSOLE_DOMAIN',
    'VERSION',
    'BK_SHARED_RES_URL',
  ];

  // 辅助函数：将相对地址转换为完整地址
  const ensureAbsoluteUrl = (url: string): string => {
    if (!url || typeof url !== 'string') {
      return url;
    }

    // 如果已经是完整地址（以 http://、https:// 或 // 开头），直接返回
    if (/^(https?:)?\/\//.test(url)) {
      return url;
    }

    // 如果是相对地址，基于当前页面的 origin 构建完整地址
    try {
      // 确保 url 以 / 开头
      const normalizedUrl = url.startsWith('/') ? url : `/${url}`;
      // 使用当前页面的 origin 构建完整 URL
      const fullUrl = new URL(normalizedUrl, window.location.origin);
      return fullUrl.href;
    } catch (e) {
      console.warn('Failed to convert relative URL to absolute URL:', url, e);
      // 如果转换失败，返回原始值
      return url;
    }
  };

  let envScript = envVars
    .map((varName) => {
      let value = (window as any)[varName];
      if (value === undefined || value === null) {
        return '';
      }

      // 特殊处理 AJAX_URL_PREFIX：如果是相对地址，转换为完整地址
      if (varName === 'AJAX_URL_PREFIX' && typeof value === 'string') {
        value = ensureAbsoluteUrl(value);
      }

      // 处理不同类型的值
      if (typeof value === 'string') {
        return `window.${varName} = ${JSON.stringify(value)};`;
      }
      if (typeof value === 'number' || typeof value === 'boolean') {
        return `window.${varName} = ${value};`;
      }
      if (typeof value === 'object') {
        return `window.${varName} = ${JSON.stringify(value)};`;
      }
      return '';
    })
    .filter(Boolean)
    .join('\n    ');

  // 设置 webpack public path
  const publicPath = isDev ? '/log-web1-dll/' : `${(window as any).BK_STATIC_URL}/log-web1-dll/`;
  envScript += `window.__WEBPACK_PUBLIC_PATH__ = '${publicPath}';`;

  return envScript;
};

// 解析 hash 中的查询参数
const parseHashQuery = (hash: string) => {
  const query: Record<string, string> = {};
  if (!hash) {
    return query;
  }

  const hashParts = hash.split('?');
  if (hashParts.length > 1) {
    const queryString = hashParts[1];
    const params = new URLSearchParams(queryString);
    for (const [key, value] of params) {
      query[key] = value;
    }
  }
  return query;
};

// 获取当前页面的路由信息（父级 window）
const getRouteInfo = () => {
  const location = window.location;
  const hash = location.hash || '';
  const hashPath = hash.startsWith('#') ? hash.substring(1) : hash;

  return {
    href: location.href,
    hash,
    hashPath,
    search: location.search || '',
    query: parseHashQuery(hash),
    origin: location.origin,
    pathname: location.pathname,
  };
};

// 生成 iframe 的 srcdoc 内容
export const generateIframeSrcdoc = (isDev: boolean) => {
  const manifest = logWebManifest;
  if (!manifest || !manifest.entryJs || !manifest.entryCss) {
    throw new Error('资源清单不完整');
  }

  // 获取资源路径
  const jsUrl = getResourceUrl(manifest.entryJs);
  const cssUrl = getResourceUrl(manifest.entryCss);

  // 获取环境变量脚本
  const envScript = getEnvVariables(isDev);

  // 获取当前路由信息
  const routeInfo = getRouteInfo();
  const initialHash = routeInfo.hashPath || '/';
  const initialQuery = routeInfo.query;

  // 获取基础 URL 信息
  const basePath = routeInfo.pathname.substring(0, routeInfo.pathname.lastIndexOf('/') + 1);
  const baseHref = routeInfo.origin + basePath;

  // 生成 srcdoc HTML 内容
  return `
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>日志检索</title>
  <base href="${baseHref}">
  <style>
    * {
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }
    body {
      width: 100%;
      height: 100%;
      overflow: hidden;
    }
    #app {
      width: 100%;
      height: 100%;
    }
    .loading-container {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 100%;
      height: 100%;
      font-size: 14px;
      color: #63656e;
    }
  </style>
  <link rel="stylesheet" href="${cssUrl}">
</head>
<body>
  <div id="app">
    <div class="loading-container">加载中...</div>
  </div>
  <script>
    // === Location 代理：直接使用父级的 location ===
    // iframe 中的 location 直接代理父级的 location，保证 URL 一致
    // iframe 只作为容器隔离运行环境（Vue2 和 Vue3）

    let isLocationProxySetup = false;

    const setupLocationProxy = () => {
      if (isLocationProxySetup) return;

      try {
        const descriptor = Object.getOwnPropertyDescriptor(window, 'location');
        if (descriptor && !descriptor.configurable) {
          isLocationProxySetup = true;
          return;
        }
      } catch (e) {
        // 继续执行
      }

      // 保存原始 location
      window._originalLocation = window.location;

      // 创建 location 代理对象，直接使用父级的 location
      const parentLocation = window.parent.location;
      
      // 辅助函数：确保返回有效的 URL
      const ensureValidUrl = (url, fallback = 'http://localhost/') => {
        try {
          new URL(url);
          return url;
        } catch (e) {
          console.warn('Invalid URL detected, using fallback:', url, e);
          return fallback;
        }
      };
      
      // 辅助函数：确保返回有效的 origin（直接从 href 构建，最可靠）
      const ensureValidOrigin = (fallback = 'http://localhost') => {
        try {
          const href = parentLocation.href;
          const url = new URL(href);
          return url.origin;
        } catch (e) {
          console.warn('Failed to build origin from href, using fallback:', e);
          return fallback;
        }
      };
      
      const locationProxy = {
        // 直接返回父级 location 的属性，但确保是有效的 URL
        get href() {
          try {
            const href = parentLocation.href;
            return ensureValidUrl(href);
          } catch (e) {
            console.warn('Failed to get parent location.href:', e);
            return 'http://localhost/';
          }
        },
        get origin() {
          // 直接从 href 构建 origin，确保始终有效
          return ensureValidOrigin();
        },
        get protocol() {
          try {
            return parentLocation.protocol || 'http:';
          } catch (e) {
            return 'http:';
          }
        },
        get host() {
          try {
            return parentLocation.host || 'localhost';
          } catch (e) {
            return 'localhost';
          }
        },
        get hostname() {
          try {
            return parentLocation.hostname || 'localhost';
          } catch (e) {
            return 'localhost';
          }
        },
        get port() {
          try {
            return parentLocation.port || '';
          } catch (e) {
            return '';
          }
        },
        get pathname() {
          try {
            return parentLocation.pathname || '/';
          } catch (e) {
            return '/';
          }
        },
        get search() {
          try {
            return parentLocation.search || '';
          } catch (e) {
            return '';
          }
        },
        get hash() {
          try {
            return parentLocation.hash || '';
          } catch (e) {
            return '';
          }
        },

        reload: function() {
          // 在 iframe 中，阻止实际刷新页面
          console.warn('location.reload() called in iframe, ignoring to prevent infinite refresh');
          if (window.vueRouter) {
            window.vueRouter.replace(window.vueRouter.currentRoute.fullPath);
          }
        },

        toString: function() {
          return parentLocation.href;
        }
      };

      // 重写 window.location
      try {
        Object.defineProperty(window, 'location', {
          get: () => locationProxy,
          configurable: true
        });
      } catch (e) {
        console.warn('Failed to define location property:', e);
        isLocationProxySetup = true;
        return;
      }

      // 设置初始路由数据供 Vue Router 使用
      window.INITIAL_ROUTE_DATA = {
        hash: '${initialHash}',
        fullPath: '${initialHash}',
        query: ${JSON.stringify(initialQuery)},
        params: {}
      };

      console.log('Location proxy initialized, using parent location:', parentLocation.href);
      isLocationProxySetup = true;
    };

    // 更新路由数据（当父级 hash 变化时调用）
    let lastUpdateHash = null;
    let updateTimer = null;
    
    window.updateHashRoute = (newHashData) => {
      // 防抖：避免频繁更新导致循环刷新
      if (updateTimer) {
        clearTimeout(updateTimer);
      }
      
      updateTimer = setTimeout(() => {
        const targetHash = newHashData.hash || newHashData.path || '';
        // 如果 hash 没有变化，直接返回
        if (lastUpdateHash === targetHash) {
          return;
        }
        lastUpdateHash = targetHash;
        
        // 由于 location 直接代理父级，这里只需要更新 Vue Router
        if (window.vueRouter) {
          const targetPath = newHashData.path || newHashData.hash;
          const targetQuery = newHashData.query || {};
          const currentRoute = window.vueRouter.currentRoute;

          // 只有当路由真正变化时才更新，避免循环刷新
          if (currentRoute.path !== targetPath || JSON.stringify(currentRoute.query) !== JSON.stringify(targetQuery)) {
            // 先更新 Vue Router
            window.vueRouter.replace({
              path: targetPath,
              query: targetQuery
            });
            // 不触发 hashchange 事件，因为 location 已经代理父级，Vue Router 会通过 location.hash 获取到正确的值
          }
        } else {
          // 如果 VueRouter 还没有加载，等待它加载完成后再更新
          // 不触发 hashchange 事件，避免循环刷新
          console.log('VueRouter not loaded yet, will update after initialization');
        }
      }, 50);
    };

    // 在 DOM 加载前设置 location 代理
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', setupLocationProxy, { once: true });
    } else {
      setupLocationProxy();
    }
  </script>

  <script>
    // 预加载环境变量：从主站点注入到 iframe
    (function() {
      ${envScript}
    })();

    // 预加载函数：等待资源加载完成
    function preloadResources() {
      return new Promise((resolve, reject) => {
        // 检查 CSS 是否已加载
        const checkCSS = () => {
          const link = document.querySelector('link[href*="${manifest.entryCss}"]');
          if (link) {
            link.onload = () => resolve();
            link.onerror = () => reject(new Error('CSS 加载失败'));
          } else {
            resolve();
          }
        };

        // 动态加载 JS
        const script = document.createElement('script');
        script.src = "${jsUrl}";
        script.onload = () => {
          checkCSS();
          setTimeout(() => resolve(), 100);
        };
        script.onerror = () => reject(new Error('JS 加载失败'));
        document.head.appendChild(script);
      });
    }

    // 挂载逻辑：等待 Vue2 应用初始化
    function mountApp() {
      // Vue2 应用应该会自动挂载到 #app
      if (window.Vue2App && typeof window.Vue2App.mount === 'function') {
        window.Vue2App.mount('#app');
      }

      // 通知父窗口加载完成
      if (window.parent) {
        window.parent.postMessage({
          type: 'vue2-app-loaded',
          source: 'vue2-container'
        }, '*');
      }
    }

    // 执行预加载和挂载
    preloadResources()
      .then(() => {
        mountApp();
      })
      .catch((err) => {
        console.error('加载失败:', err);
        const app = document.getElementById('app');
        if (app) {
          app.innerHTML = '<div class="loading-container">加载失败: ' + err.message + '</div>';
        }
        // 通知父窗口加载失败
        if (window.parent) {
          window.parent.postMessage({
            type: 'vue2-app-error',
            source: 'vue2-container',
            error: err.message
          }, '*');
        }
      });
  </script>
</body>
</html>`;
};

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

(async () => {
  const send = type => parent.postMessage({ source: 'bklog-legacy-v1', version: 1, type }, location.origin);
  const fail = error => { document.getElementById('app').textContent = `封版检索加载失败：${error.message}`; };
  try {
    const root = new URL('./', location.href);
    const [manifestResponse, envResponse] = await Promise.all([
      fetch(new URL('sealed-manifest.json', root)),
      fetch('/api/v1/meta/index_html_environment/', { credentials: 'include' }),
    ]);
    if (envResponse.status === 401) { send('auth-required'); throw new Error('登录已过期'); }
    if (!manifestResponse.ok || !envResponse.ok) throw new Error('无法读取封版资源或运行配置');
    const manifest = await manifestResponse.json();
    const envBody = await envResponse.json();
    if (envBody.result === false) throw new Error(envBody.message || '运行配置读取失败');
    const env = envBody.data || {};
    for (const key of ['SITE_URL', 'AJAX_URL_PREFIX', 'LOGIN_SERVICE_URL', 'MONITOR_URL', 'BKDATA_URL', 'COLLECTOR_GUIDE_URL', 'FEATURE_TOGGLE', 'FEATURE_TOGGLE_WHITE_LIST', 'FEATURE_TOGGLE_BLACK_LIST', 'SPACE_UID_WHITE_LIST', 'FIELD_ANALYSIS_CONFIG', 'REAL_TIME_LOG_MAX_LENGTH', 'REAL_TIME_LOG_SHIFT_LENGTH', 'RUN_VER', 'TITLE_MENU', 'MENU_LOGO_URL', 'APP_CODE', 'BK_DOC_URL', 'BK_FAQ_URL', 'BK_DOC_QUERY_URL', 'IS_EXTERNAL', 'BK_LOGIN_URL', 'VERSION', 'BK_SHARED_RES_URL', 'BK_USER_URL', 'BK_IAM_URL']) {
      if (!(key in env)) continue;
      let value = env[key];
      if (typeof value === 'string' && /^(?:FEATURE_TOGGLE|SPACE_UID|FIELD_ANALYSIS)/.test(key)) {
        try { value = JSON.parse(value); } catch { throw new Error(`运行配置 ${key} 格式错误`); }
      }
      window[key] = value;
    }
    window.AJAX_URL_PREFIX ||= '/api/v1';
    window.__WEBPACK_PUBLIC_PATH__ = new URL('assets/', root).href;
    const hash = location.hash.slice(1) || '/retrieve';
    window.INITIAL_ROUTE_DATA = { hash, fullPath: hash, query: Object.fromEntries(new URLSearchParams(hash.split('?')[1] || '')), params: {} };
    const entryUrl = entry => {
      const url = new URL(entry, window.__WEBPACK_PUBLIC_PATH__);
      if (!url.href.startsWith(window.__WEBPACK_PUBLIC_PATH__)) throw new Error('无效封版资源路径');
      return url.href;
    };
    const css = document.createElement('link'); css.rel = 'stylesheet'; css.href = entryUrl(manifest.entry.entryCss);
    document.head.appendChild(css);
    const script = document.createElement('script'); script.src = entryUrl(manifest.entry.entryJs);
    script.onerror = () => fail(new Error('脚本加载失败'));
    script.onload = () => {
      if (window.Vue2App?.mount) window.Vue2App.mount('#app');
      let attempts = 0;
      const mounted = setInterval(() => {
        if (window.mainComponent?.$el?.nodeType === 1) { clearInterval(mounted); send('ready'); }
        else if (++attempts > 200) { clearInterval(mounted); fail(new Error('应用初始化超时')); }
      }, 100);
      addEventListener('pagehide', () => clearInterval(mounted), { once: true });
    };
    document.head.appendChild(script);
    addEventListener('message', event => {
      if (event.origin !== location.origin || event.source !== parent) return;
      const data = event.data;
      if (data?.source !== 'bklog-legacy-v1' || data.version !== 1 || data.type !== 'navigate') return;
      if (typeof data.path === 'string' && /^\/retrieve(?:\/[^/?#]+)?(?:\?|$)/.test(data.path)) location.hash = data.path;
    });
  } catch (error) { fail(error); }
})();

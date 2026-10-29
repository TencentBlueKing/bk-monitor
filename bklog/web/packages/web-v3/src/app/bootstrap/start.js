import { ServicesInstance } from '@/platform/services';
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

import './public-path';
import '../../platform/compat/tdesign/legacy-control-styles';
import { initOpenTelemetry } from '../../platform/observability/open-telemetry';

import { createApp, h } from 'vue';
import { configureApp } from './configure-app';

import i18n from '@/platform/i18n/i18n';
import { debounce } from 'lodash-es';

import http from '../../platform/http/index';
import App from '../shell/app.tsx';
import { bus } from '../../shared/lib/bus';
import '../../shared/lib/preload-import.ts';

import '../../shared/directives/index';
import preload, { getAllSpaceList, getExternalMenuListBySpace, requestUserGuideData } from './preload';
import getRouter from '../router/index';
import store from '../state/index';
import { performanceMonitorService } from '../../platform/persistence/index';

import 'vue-virtual-scroller/dist/vue-virtual-scroller.css';
import '../../shared/styles/theme/theme-dark.scss';
import '../../shared/styles/theme/theme-light.scss';
import '../../shared/assets/static/font-face/index.css';
import '../../shared/assets/static/style.css';
import '@blueking/bk-user-selector/vue2/vue2.css';
import { BK_LOG_STORAGE } from '../state/store.type.ts';
import { urlArgs } from '../state/default-values.ts';
import { DEFAULT_MENU_LISTS } from '../state/menu-config.ts';
import '../../platform/compat/tdesign/runtime-contract';
import '../../shared/styles/theme/tdesign-bklog.scss';


const isHeadlessRoute = () =>
  new URLSearchParams(window.location.hash.split('?')[1] || window.location.search).get('hl') === '1';

const createBootstrapMenuList = () => {
  const normalizeMenu = menu => ({
    feature: 'on',
    ...menu,
    children: Array.isArray(menu.children) ? menu.children.map(normalizeMenu) : menu.children,
  });

  return DEFAULT_MENU_LISTS.map(normalizeMenu);
};

const fadeOutBootstrapLoading = () => {
  const loading = document.querySelector('.bklog-bootstrap-loading');
  const appRoot = document.getElementById('app');

  if (appRoot) {
    appRoot.classList.add('bklog-bootstrap-app-enter');
  }

  if (!loading) {
    return;
  }

  window.setTimeout(() => {
    loading.classList.add('is-leaving');
  }, 60);

  window.setTimeout(() => {
    loading.parentNode?.removeChild(loading);
  }, 520);
};

// import { localSettings } from './local.po';

const setRouterErrorHandle = router => {
  router.onError(err => {
    const pattern = /Loading (CSS chunk|chunk) (\d)+ failed/g;
    const isChunkLoadFailed = err.message.match(pattern);
    const targetPath = router.history?.pending?.fullPath;
    if (isChunkLoadFailed) {
      router.replace(targetPath);
    }
  });
};

window.bus = bus;

let rumInstance;

/** Publish the mounted Vue3 proxy, preserving the V2 mainComponent contract. */
export const mountApplication = (app, target) => {
  const instance = app.mount(target);
  window.mainComponent = instance;
  return instance;
};

const mountedVueInstance = () => {
  // Object.assign(window, localSettings);
  window.mainComponent = {
    $t(key, params) {
      return i18n.t(key, params);
    },
  };

  preload({ http, store, isHeadless: isHeadlessRoute() }).then(([spaceRequest]) => {
    rumInstance?.setUser({ id: store.state.userMeta?.username });

    const { space, spaceUid, bkBizId } = spaceRequest.value ?? {};
    store.commit('updateState', { spaceResolveFailed: !space });

    let externalMenu = [];
    if (window.IS_EXTERNAL && space) {
      externalMenu = getExternalMenuListBySpace(space) ?? [];
      store.commit('updateState', {
        externalMenu,
        externalPermissions: space.external_permission ?? [],
      });
    }

    const router = getRouter(spaceUid, bkBizId, externalMenu);
    setRouterErrorHandle(router);
    performanceMonitorService.init(router);

    if (!store.state.topMenu?.length) {
      store.commit('updateState', { topMenu: createBootstrapMenuList() });
    }

    const patchLogCollectionMenu = (menuList = []) => {
      menuList
        .find(item => item.id === 'manage')
        ?.children?.forEach(group => {
          group?.children?.forEach(nav => {
            if (nav.id === 'log-collection') {
              Object.assign(nav, {
                children: [
                  {
                    id: 'collection-item',
                    name: i18n.t('采集项'),
                    project_manage: nav.project_manage,
                  },
                  {
                    id: 'log-index-set',
                    name: i18n.t('索引集'),
                    project_manage: nav.project_manage,
                  },
                ],
              });
            }
          });
        });
    };

    const refreshMenuList = () => {
      store
        .dispatch('requestMenuList', spaceUid)
        .then((menuList = []) => {
          patchLogCollectionMenu(menuList);
          store.commit('updateState', { topMenu: structuredClone(menuList) });
        })
        .catch(e => {
          console.error('获取菜单列表失败', e);
        })
        .finally(() => {});
    };

    if (window.requestIdleCallback) {
      window.requestIdleCallback(refreshMenuList, { timeout: 1500 });
    } else {
      window.setTimeout(refreshMenuList, 300);
    }

    (() => {
      const app = createApp({
        components: {
          App,
        },
        created() {
          if (!space) {
            // 等待首个路由解析完成（含根路径重定向），首页直接渲染未授权态并保留 URL。
            this.$router.isReady().then(() => {
              if (['retrieve', 'share'].includes(this.$route.name)) {
                return;
              }
              this.$router.push({
                path: '/un-authorized',
                query: {
                  ...this.$route.query,
                  type: 'space',
                  spaceUid: spaceUid ?? store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
                  bkBizId: bkBizId ?? store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
                  indexId: this.$route.params.indexId ?? this.$route.query.indexId ?? urlArgs.index_id,
                  from: urlArgs.from,
                },
              });
            });
            return;
          }

          // if (
          //   ['/retrieve', '/'].includes(this.$route.path)
          //   && (this.$route.query.spaceUid !== spaceUid || this.$route.query.bizId !== bkBizId)
          // ) {
          //   this.$router.push({
          //     name: 'retrieve',
          //     params: {
          //       indexId: urlArgs.index_id,
          //     },
          //     query: {
          //       ...(this.$route.query ?? {}),
          //       spaceUid: spaceUid ?? store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID],
          //       bizId: bkBizId ?? store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
          //       start_time: urlArgs.start_time ?? this.$store.state.indexItem.start_time,
          //       end_time: urlArgs.end_time ?? this.$store.state.indexItem.end_time,
          //       timezone: urlArgs.timezone ?? this.$store.state.indexItem.time_zone,
          //       format: urlArgs.format ?? this.$store.state.indexItem.format,
          //       interval: urlArgs.interval ?? this.$store.state.indexItem.interval,
          //       search_mode: urlArgs.search_mode ?? this.$store.state.indexItem.search_mode,
          //       from: urlArgs.from,
          //     },
          //   });
          // }
        },
        mounted() {
          fadeOutBootstrapLoading();
          // 对于手动输入URL，直接刷新页面重置所有参数和状态
          window.addEventListener('hashchange', this.reset);
          if (!isHeadlessRoute()) {
            getAllSpaceList(http, store);
            const requestUserGuide = () => {
              requestUserGuideData({ http, store }).catch(e => {
                console.error('获取用户引导数据失败', e);
              });
            };
            if (window.requestIdleCallback) {
              window.requestIdleCallback(requestUserGuide, { timeout: 2500 });
            } else {
              window.setTimeout(requestUserGuide, 1200);
            }
          }
        },
        beforeUnmount() {
          window.removeEventListener('hashchange', this.reset);
        },
        methods: {
          reset() {
            window.location.reload();
          },
        },
        render() {
          return h(App);
        },
      });
      configureApp(app);
      app.use(store);
      app.use(i18n);
      app.use(router);
      return mountApplication(app, '#app');
    })();
  });
};

if (process.env.NODE_ENV === 'development') {
  ServicesInstance.meta.getEnvConstant().then(res => {
    const { data } = res;
    Object.keys(data).forEach(key => {
      window[key] = data[key];
    });
    window.FEATURE_TOGGLE = JSON.parse(data.FEATURE_TOGGLE);
    window.FEATURE_TOGGLE_WHITE_LIST = JSON.parse(data.FEATURE_TOGGLE_WHITE_LIST);
    window.FEATURE_TOGGLE_BLACK_LIST = JSON.parse(data.FEATURE_TOGGLE_BLACK_LIST);
    window.SPACE_UID_WHITE_LIST = JSON.parse(data.SPACE_UID_WHITE_LIST);
    window.FIELD_ANALYSIS_CONFIG = JSON.parse(data.FIELD_ANALYSIS_CONFIG);
    rumInstance = initOpenTelemetry();
    mountedVueInstance();
  });
} else {
  rumInstance = initOpenTelemetry();
  mountedVueInstance();
}

const BaseResizeObserver = window.ResizeObserver;
window.ResizeObserver = class ResizeObserver extends BaseResizeObserver {
  constructor(callback) {
    callback = debounce(callback);
    super(callback);
  }
};

window.$t = function (key, params) {
  return i18n.t(key, params);
};

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

import Vue from 'vue';

import LogButton from '@/components/log-button';
import i18n from '@/language/i18n';
import docsLinkMixin from '@/mixins/docs-link-mixin';

import { debounce } from 'lodash';

import App from './App';
import http from './api';
import { bus } from './common/bus';
import { renderHeader } from './common/util';
import './directives/index';
import JsonFormatWrapper from './global/json-format-wrapper.vue';
import methods from './plugins/methods';
import getRouter from './router';
import store from './store';
import preload from './preload';

import './static/style.css';
import './static/font-face/index.css';
import './scss/theme/theme-dark.scss';
import './scss/theme/theme-light.scss';
import { BK_LOG_STORAGE } from './store/store.type';

Vue.prototype.$renderHeader = renderHeader;

const setRouterErrorHandle = router => {
  router.onError(err => {
    const pattern = /Loading (CSS chunk|chunk) (\d)+ failed/g;
    const isChunkLoadFailed = err.message.match(pattern);
    const targetPath = router.history.pending.fullPath;
    if (isChunkLoadFailed) {
      router.replace(targetPath);
    }
  });
};

Vue.component('JsonFormatWrapper', JsonFormatWrapper);
Vue.component('LogButton', LogButton);
Vue.mixin(docsLinkMixin);
Vue.use(methods);

const mountedVueInstance = () => {
  window.mainComponent = {
    $t: function (key, params) {
      return i18n.t(key, params);
    },
  };
  preload({ http, store, isExternal: window.IS_EXTERNAL }).then(() => {
    const spaceUid = store.state.storage[BK_LOG_STORAGE.BK_SPACE_UID];
    const bkBizId = store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID];

    store.commit('requestMenuList', spaceUid);
    const router = getRouter(spaceUid, bkBizId);
    setRouterErrorHandle(router);

    window.mainComponent = new Vue({
      el: '#app',
      router,
      store,
      i18n,
      components: {
        App,
      },
      template: '<App/>',
    });
  });
};
window.bus = bus;

if (process.env.NODE_ENV === 'development') {
  http.request('meta/getEnvConstant').then(res => {
    const { data } = res;
    Object.keys(data).forEach(key => {
      window[key] = data[key];
    });
    window.FEATURE_TOGGLE = JSON.parse(data.FEATURE_TOGGLE);
    window.FEATURE_TOGGLE_WHITE_LIST = JSON.parse(data.FEATURE_TOGGLE_WHITE_LIST);
    window.SPACE_UID_WHITE_LIST = JSON.parse(data.SPACE_UID_WHITE_LIST);
    window.FIELD_ANALYSIS_CONFIG = JSON.parse(data.FIELD_ANALYSIS_CONFIG);
    mountedVueInstance();
    Vue.config.devtools = true;
  });
} else {
  mountedVueInstance();
  Vue.config.devtools = true;
}

const _ResizeObserver = window.ResizeObserver;
window.ResizeObserver = class ResizeObserver extends _ResizeObserver {
  constructor(callback) {
    callback = debounce(callback);
    super(callback);
  }
};

window.$t = function (key, params) {
  return i18n.t(key, params);
};

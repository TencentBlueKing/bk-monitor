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

import './public-path.ts';
import 'monitor-common/polyfill';

import i18n from './i18n/i18n';
import Vue from 'vue';

import 'monitor-ui/directive/index';

import Api from 'monitor-api/api';
import { setVue, type VueInstance } from 'monitor-api/utils/index';
import { immediateRegister } from 'monitor-common/service-worker/service-worker';
import { getUrlParam, mergeSpaceList, setGlobalBizId } from 'monitor-common/utils';
import { assignWindowField } from 'monitor-common/utils/assign-window';

import App from './pages/app';
import router from './router/router';
import Authority from './store/modules/authority';
import store from './store/store';
import 'monitor-pc/common/global-login';
import 'monitor-pc/common/import-magicbox-ui';

import './static/scss/global.scss';
import 'monitor-pc/static/css/reset.scss';
import 'monitor-static/icons/monitor-icons.css';
// import 'monitor-pc/tailwind.css';
Vue.config.devtools = process.env.NODE_ENV === 'development';
window.source_app = 'fta';
const spaceUid = getUrlParam('space_uid');
const bizId = getUrlParam('bizId')?.replace(/\//gim, '');
setVue(Vue as VueInstance);
if (process.env.NODE_ENV === 'development') {
  window.site_url = '/';
}
if (window.__BK_WEWEB_APP_KEY__) {
  store.commit('app/SET_APP_STATE', {
    userName: window.user_name,
    bizId: window.cc_biz_id,
    bizList: window.space_list,
    csrfCookieName: window.csrf_cookie_name || '',
    siteUrl: window.site_url,
    bkUrl: window.bk_url,
  });

  new Vue({
    el: '#app',
    router,
    store,
    i18n,
    render: h => h(App),
  });
  Vue.prototype.$bus = new Vue();
  Vue.prototype.$api = Api;
  Vue.prototype.$authorityStore = Authority;
} else {
  Api.model
    .enhancedContext({
      space_uid: spaceUid || undefined,
      bk_biz_id: !spaceUid ? +bizId || process.env.defaultBizId : undefined,
      context_type: 'basic',
    })
    .then(data => {
      assignWindowField(data);
      mergeSpaceList(window.space_list);
      window.username = window.uin;
      window.user_name = window.uin;
      window.cc_biz_id = +window.bk_biz_id;
      window.bk_log_search_url = data.BKLOGSEARCH_HOST;
      const bizId = setGlobalBizId();
      if (bizId === false) return;
      store.commit('app/SET_APP_STATE', {
        userName: window.user_name,
        bizId: window.cc_biz_id,
        bizList: window.space_list,
        csrfCookieName: window.csrf_cookie_name || '',
        siteUrl: window.site_url,
        bkUrl: window.bk_url,
      });

      new Vue({
        el: '#app',
        router,
        store,
        i18n,
        render: h => h(App),
      });
      Vue.prototype.$bus = new Vue();
      Vue.prototype.$api = Api;
      Vue.prototype.$authorityStore = Authority;
      Api.model
        .enhancedContext({
          space_uid: spaceUid || undefined,
          bk_biz_id: bizId,
          context_type: 'extra',
        })
        .then(data => {
          assignWindowField(data);
        });
    })
    .catch(e => console.error(e))
    .finally(() => {
      immediateRegister();
    });
}

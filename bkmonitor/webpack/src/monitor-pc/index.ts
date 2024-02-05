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
/* eslint-disable max-len */
/* eslint-disable no-param-reassign */

// eslint-disable-next-line simple-import-sort/imports
import './public-path';
import '../monitor-common/polyfill';
import Vue from 'vue';
import i18n from './i18n/i18n';

import './common/import-magicbox-ui';
import '../monitor-ui/directive/index';
import './common/global';
import '../monitor-static/svg-icons';

import Api from '../monitor-api/api';
import Axios from '../monitor-api/axios/axios';
import { setVue } from '../monitor-api/utils/index';
import * as serviceWorker from '../monitor-common/service-worker/service-wroker';
import { getUrlParam, mergeSpaceList, setGlobalBizId } from '../monitor-common/utils';

import App from './pages/app';
import router from './router/router';
import Authority from './store/modules/authority';
import store from './store/store';
import '../monitor-static/icons/monitor-icons.css';
import './static/css/reset.scss';
import './static/css/global.scss';
// todo: 子应用externals
// import './common/externals';
// app 标识
window.source_app = 'monitor';
// 全局图表数量变量
window.slimit = 500;
setVue(Vue);
const hasRouteHash = getUrlParam('routeHash');
const spaceUid = getUrlParam('space_uid');
const bizId = getUrlParam('bizId')?.replace(/\//gim, '');
if (process.env.NODE_ENV === 'development') {
  window.site_url = '/';
}
// 通知人可无权限进入事件详情
if (hasRouteHash) {
  const isSpecEvent = hasRouteHash.indexOf('event-center') > -1;
  let url = `${location.origin}${location.pathname}?bizId=${bizId}${isSpecEvent ? '&specEvent=1' : ''}${
    hasRouteHash.match(/^#/) ? hasRouteHash : `#/${hasRouteHash}`
  }`;
  /* 如果包含批量操作则需要将batchAction带过去 */
  const hasBatchAction = getUrlParam('batchAction');
  if (!!hasBatchAction) {
    url = `${url}&batchAction=${hasBatchAction}`;
  }
  location.href = url;
} else {
  const pathname = `${window.location.pathname}`;
  if (process.env.APP !== 'external' && !window.__POWERED_BY_BK_WEWEB__ && pathname !== window.site_url) {
    location.pathname = window.site_url || '/';
  } else {
    Api.model
      .enhancedContext({
        space_uid: spaceUid || undefined,
        bk_biz_id: !spaceUid ? +bizId || process.env.defaultBizId : undefined,
        context_type: 'basic'
      })
      .then(data => {
        Object.keys(data).forEach(key => {
          window[key.toLocaleLowerCase()] = data[key];
        });
        mergeSpaceList(window.space_list);
        window.user_name = window.uin;
        window.username = window.uin;
        window.user_name = window.uin;
        window.cc_biz_id = +window.bk_biz_id;
        window.bk_log_search_url = data.BKLOGSEARCH_HOST;
        const bizId = setGlobalBizId();
        if (bizId === false) return;
        store.commit('app/SET_APP_STATE', {
          userName: window.user_name,
          isSuperUser: window.is_superuser,
          bizId: window.cc_biz_id,
          bizList: window.space_list,
          csrfCookieName: window.csrf_cookie_name || [],
          siteUrl: window.site_url,
          maxAvailableDurationLimit: window.max_available_duration_limit,
          cmdbUrl: window.bk_cc_url,
          bkLogSearchUrl: window.bk_log_search_url,
          bkUrl: window.bk_url,
          bkNodemanHost: window.bk_nodeman_host,
          enable_cmdb_level: !!window.enable_cmdb_level,
          bkPaasHost: window.bk_paas_host,
          jobUrl: window.bk_job_url
        });
        // eslint-disable-next-line no-new
        new Vue({
          el: '#app',
          router,
          store,
          i18n,
          render: h => h(App)
        });
        Vue.prototype.$bus = new Vue();
        Vue.prototype.$platform = window.platform;
        Vue.prototype.$api = Api;
        Vue.prototype.$http = Axios;
        Vue.prototype.$ELEMENT = { size: '', zIndex: 3000 };
        Vue.prototype.$authorityStore = Authority;
        Api.model
          .enhancedContext({
            space_uid: spaceUid || undefined,
            bk_biz_id: bizId,
            context_type: 'extra'
          })
          .then(data => {
            Object.keys(data).forEach(key => {
              window[key.toLocaleLowerCase()] = data[key];
            });
            store.commit('app/SET_APP_STATE', {
              collectingConfigFileMaxSize: data.COLLECTING_CONFIG_FILE_MAXSIZE
            });
          });
      })
      .catch(e => console.error(e))
      .finally(() => {
        serviceWorker.immediateRegister();
      });
  }
}

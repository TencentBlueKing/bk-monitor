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
/* eslint-disable no-new */
/* eslint-disable new-cap */
// eslint-disable-next-line simple-import-sort/imports
import './public-path.ts';
import Vue from 'vue';
import i18n from './i18n/i18n';

import { setVue } from '../monitor-api/utils/index';
import * as serviceWorker from 'monitor-common/service-worker/service-wroker';
import { getUrlParam } from 'monitor-common/utils/utils';

import App from './pages/app.vue';
import router from './router/router';
import store from './store/store';

import 'monitor-static/icons/monitor-icons.css';
import 'vant/lib/icon/local.css';
import './static/scss/global.scss';
import 'vant/lib/index.css';
// eslint-disable-next-line import/newline-after-import
import Notify from 'vant/lib/notify';
interface IMessageParam {
  message: string;
  theme: 'primary' | 'success' | 'danger' | 'warning' | 'error';
}
Vue.config.devtools = process.env.NODE_ENV === 'development';
const bizId = getUrlParam('bizId')?.replace(/\//gim, '');
const enableConsole = getUrlParam('console');
window.cc_biz_id = bizId;
if (process.env.NODE_ENV !== 'production') {
  window.site_url = '/weixin/';
}
enableConsole &&
  import('vconsole').then(module => {
    new module.default();
  });
Vue.prototype.$bkMessage = (params: IMessageParam) => {
  Notify({
    type: params.theme === 'error' ? 'danger' : params.theme,
    message: params.message
  });
};
setVue(Vue);
window.i18n = i18n;
store.commit('app/SET_APP_DATA', {
  bizId,
  collectId: getUrlParam('collectId')
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
process.env.NODE_ENV === 'production' ? serviceWorker.register() : serviceWorker.unregister();

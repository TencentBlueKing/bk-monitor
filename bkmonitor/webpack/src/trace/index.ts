/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
// eslint-disable-next-line simple-import-sort/imports
import './public-path';
import '../monitor-common/polyfill';
import i18n from './i18n/i18n';

import { createApp } from 'vue';
import { Message } from 'bkui-vue';

import Api from '../monitor-api/api';
import { getContext } from '../monitor-api/modules/commons';
import { setVue } from '../monitor-api/utils/index';
import * as serviceWorker from '../monitor-common/service-worker/service-wroker';
import { getUrlParam, setGlobalBizId } from '../monitor-common/utils';

import directives from './directive/index';
import App from './pages/app';
import router from './router/router';
import { useAuthorityStore } from './store/modules/authority';
import store from './store/store';

import '../monitor-static/icons/monitor-icons.css';
import './static/scss/global.scss';

if (process.env.NODE_ENV === 'development') {
  window.site_url = '/';
  const spaceUid = getUrlParam('space_uid');
  const bizId = getUrlParam('bizId')?.replace(/\//gim, '');
  getContext({
    space_uid: spaceUid || undefined,
    bk_biz_id: !spaceUid ? bizId || process.env.defaultBizId : undefined
  }).then(data => {
    Object.keys(data).forEach(key => {
      (window as any)[key.toLocaleLowerCase()] = data[key];
    });
    window.username = window.uin;
    window.bk_log_search_url = window.bklogsearch_host;
    setGlobalBizId();
    const app = createApp(App);
    setVue(app);
    app.use(store).use(router).use(i18n).use(directives).mount('#app');
    serviceWorker.unregister();
    app.config.globalProperties = {
      $api: Api,
      $Message: Message,
      $authorityStore: useAuthorityStore()
    };
  });
} else {
  setGlobalBizId();
  const app = createApp(App);
  setVue(app);
  app.use(store).use(router).use(i18n).use(directives).mount('#app');
  serviceWorker.register();
  app.config.globalProperties = {
    $api: Api,
    $Message: Message,
    $authorityStore: useAuthorityStore()
  };
}

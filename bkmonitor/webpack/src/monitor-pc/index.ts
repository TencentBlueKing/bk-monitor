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
import 'monitor-common/polyfill';

import i18n from './i18n/i18n';
import Vue from 'vue';

import './common/import-magicbox-ui';
import 'monitor-static/svg-icons';
import 'monitor-ui/directive/index';

import Aegis from 'aegis-web-sdk';
import Api from 'monitor-api/api';
import Axios from 'monitor-api/axios/axios';
import { setVue } from 'monitor-api/utils/index';
import { immediateRegister } from 'monitor-common/service-worker/service-wroker';
import { getUrlParam, mergeSpaceList, setGlobalBizId } from 'monitor-common/utils';
import { asignWindowField } from 'monitor-common/utils/asign-window';

import './common/global-login';
import App from './pages/app';
import router from './router/router';
import Authority from './store/modules/authority';
import store from './store/store';

import './static/css/global.scss';
import './static/css/reset.scss';
import 'monitor-static/icons/monitor-icons.css';
// import './tailwind.css';
// todo: 子应用externals
// import './common/externals';
// app 标识
window.source_app = 'monitor';
// 全局图表数量变量
window.slimit = 500;
window.AJAX_URL_PREFIX = '/apm_log_forward/bklog/api/v1';
Vue.config.ignoredElements = ['custom-incident-detail'];
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
  if (hasBatchAction) {
    url = `${url}&batchAction=${hasBatchAction}`;
  }
  location.href = url;
} else {
  const pathname = `${window.location.pathname}`;
  if (process.env.APP !== 'external' && !window.__POWERED_BY_BK_WEWEB__ && pathname !== window.site_url) {
    location.pathname = window.site_url || '/';
  } else {
    const appLoadingNode: HTMLDivElement = document.body.querySelector('#__app_loading__');
    Api.model
      .enhancedContext({
        space_uid: spaceUid || undefined,
        bk_biz_id: !spaceUid ? +bizId || process.env.defaultBizId : undefined,
        context_type: 'basic',
      })
      .then(data => {
        appLoadingNode && (appLoadingNode.style.display = 'none');
        asignWindowField(data);
        mergeSpaceList(window.space_list);
        window.user_name = window.uin;
        window.username = window.uin;
        window.user_name = window.uin;
        window.cc_biz_id = +window.bk_biz_id;
        window.bk_log_search_url = data.BKLOGSEARCH_HOST;
        const bizId = setGlobalBizId();
        if (bizId === false) return;
        // document.title = window.page_title;
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
          bkNodeManHost: window.bk_nodeman_host,
          enable_cmdb_level: !!window.enable_cmdb_level,
          bkPaasHost: window.bk_paas_host,
          jobUrl: window.bk_job_url,
          k8sV2EnableList: (!data.K8S_V2_BIZ_LIST?.length ? [] : data.K8S_V2_BIZ_LIST).slice(),
          defaultBizId: window.default_biz_id || '',
          customMetricV2EnableList: (!data.ENABLE_CUSTOM_TS_V2_BIZ_LIST?.length
            ? []
            : data.ENABLE_CUSTOM_TS_V2_BIZ_LIST
          ).slice(),
        });
        window.mainComponent = new Vue({
          el: '#app',
          router,
          store,
          i18n,
          render: h => h(App),
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
            context_type: 'extra',
          })
          .then(data => {
            asignWindowField(data);
            store.commit('app/SET_APP_STATE', {
              collectingConfigFileMaxSize: data.COLLECTING_CONFIG_FILE_MAXSIZE,
            });
          });
      })
      .catch(e => console.error(e))
      .finally(() => {
        immediateRegister();
        appLoadingNode?.remove();
        console.info(window.rum_access_url);
        window.aegisInstance = new Aegis({
          id: 'bk_monitor_test', // 项目上报id
          uin: window.user_name || window.username, // 用户唯一标识（可选）
          reportApiSpeed: true, // 接口测速
          reportAssetSpeed: true, // 静态资源测速
          pagePerformance: true, // 是否开启页面测速
          hostUrl: window.rum_access_url.replace(/\/logs$/, ''), // 上报域名，
          webVitals: true, // 是否开启 web vitals 测速
          onError: true, // 当前实例是否需要进行错误监听，获取错误日志
          aid: true, // 当前实例是否生成aid,
          random: 1, // 0~1 抽样率
          spa: true, // 当前页面是否是单页应用？true的话将会监听hashchange及history api，在页面跳转时进行pv上报,
          pageUrl: location.href, // 修改上报数据中页面地址，开发者可以主动对数据进行聚合和降低维度
          reportImmediately: true, // 采集完数据后是否立即上报，默认为 true，如果设置为 false，则只采集数据，不触发数据上报，需要业务主动调用 aegis.ready() 方法才能触发上报，该参数一般用于业务有异步上报诉求的场景（例如预加载）。当 Aegis 初始化的时候，无法获取到正确的 uin，但是开发者希望上报 pv 的时候都带上 uin 数据，也可以用此参数控制获取 uin 后再执行 ready 方法，可以配合 setConfig 去设置 uin
          delay: 1000, // 上报节流时间，在该时间段内的上报将会合并到一个上报请求中
          repeat: 5, // 重复上报次数，对于同一个错误或者同一个接口测速超过多少次不上报。如果传入 repeat 参数为 0，则不限制。
          api: {
            apiDetail: true,
          },
        });
        Vue.config.errorHandler = (err, vm, info) => {
          window.aegisInstance.error(`Error: ${err.toString()}\nStack: ${err.stack}\nInfo: ${info}`);
        };
      });
  }
}

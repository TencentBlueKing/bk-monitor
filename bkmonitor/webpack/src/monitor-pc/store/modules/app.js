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
import Vue from 'vue';
import { docCookies, LANGUAGE_COOKIE_KEY, LOCAL_BIZ_STORE_KEY } from 'monitor-common/utils';

export const SET_TITLE = 'SET_TITLE';
export const SET_BACK = 'SET_BACK';
export const SET_BIZ_ID = 'SET_BIZ_ID';
export const SET_HANDLE_BACK = 'SET_HANDLE_BACK';
export const SET_APP_STATE = 'SET_APP_STATE';
export const SET_NAV_ID = 'SET_NAV_ID';
export const SET_NAV_TITLE = 'SET_NAV_TITLE';
export const SET_MAIN_LOADING = 'SET_MAIN_LOADING';
export const SET_MESSAGE_QUEUE = 'SET_MESSAGE_QUEUE';
export const SET_LOGIN_URL = 'SET_LOGIN_URL';
export const SET_FULL_SCREEN = 'SET_FULL_SCREEN';
// 路由切换时需获取权限中心权限 这里有一段loading
export const SET_ROUTE_CHANGE_LOADNG = 'SET_ROUTE_CHANGE_LOADNG';
// 路由面包屑数据
export const SET_NAV_ROUTE_LIST = 'SET_NAV_ROUTE_LIST';
// 设置 biz bg color
export const SET_BIZ_BGCOLOR = 'SET_BIZ_BGCOLOR';
// 切换业务id全局标识
export const SET_BIZ_CHANGE_PEDDING = 'SET_BIZ_CHANGE_PEDDING';

const state = {
  title: '',
  csrfCookieName: window.csrf_cookie_name || 'enterprise_monitor_csrftoken',
  needBack: false,
  bizId: '',
  spaceUid: '',
  bizList: [],
  userName: '',
  isSuperUser: false,
  navId: '',
  navTitle: '',
  mcMainLoading: false, // 框架内容loading
  maxAvailableDurationLimit: 3000, // 拨测超时设置最大值
  cmdbUrl: '',
  bkLogSearchUrl: '', // 日志检索url
  bkUrl: '',
  bkNodemanHost: '', // 节点管理域名
  loginUrl: '', // 登录Url
  navToggle: localStorage.getItem('navigationToogle') === 'true',
  collectingConfigFileMaxSize: null, // 插件参数文件大小限制单位M
  enable_cmdb_level: false, // 是否启用功能视图勾选Topo节点的功能开关
  siteUrl: '',
  bkPaasHost: '',
  jobUrl: '', // JOB地址
  routeChangeLoading: false, // JOB地址
  isFullScreen: false, //
  bkBcsUrl: '', // bcs地址
  bizBgColor: '', // 业务颜色
  navRouteList: [], // 路由面包屑数据,
  lang: docCookies.getItem(LANGUAGE_COOKIE_KEY) || 'zh-cn',
  bizIdChangePedding: '', // 业务id是否切换
  extraDocLinkMap: {}
};

const mutations = {
  [SET_TITLE](state, title) {
    state.title = title;
  },
  [SET_FULL_SCREEN](state, isFullScreen) {
    state.isFullScreen = isFullScreen;
  },
  [SET_BACK](state, back) {
    state.needBack = back;
  },
  [SET_BIZ_ID](state, id) {
    state.bizId = id;
  },
  [SET_APP_STATE](state, data) {
    Object.keys(data).forEach(key => {
      if (key === 'bizList') {
        state[key] = data[key].map(item => {
          const pinyinStr = Vue.prototype.$bkToPinyin(item.space_name, true, ',') || '';
          const pyText = pinyinStr.replace(/,/g, '');
          const pyfText = pinyinStr
            .split(',')
            .map(str => str.charAt(0))
            .join('');
          return {
            ...item,
            py_text: pyText,
            pyf_text: pyfText
          };
        });
        return;
      }
      state[key] = data[key];
    });
    // state.userName = data.userName;
    // state.bizId = data.bizId;
    // state.isSuperUser = data.isSuperUser;
    // // eslint-disable-next-line max-len
    // state.bizList = data.bizList.map(item => ({ ...item, py_text: Vue.prototype.$bkToPinyin(item.space_name, true) }));
    // state.siteUrl = data.siteUrl;
    // state.bkPaasHost = data.bkPaasHost;
    // state.maxAvailableDurationLimit = data.maxAvailableDurationLimit;
    // state.cmdbUrl = data.cmdbUrl;
    // state.bkLogSearchUrl = data.bkLogSearchUrl;
    // state.bkUrl = data.bkUrl;
    // state.bkNodemanHost = data.bkNodemanHost;
    // state.collectingConfigFileMaxSize = data.collectingConfigFileMaxSize;
    // state.enable_cmdb_level = data.enable_cmdb_level;
    // state.jobUrl = data.jobUrl;
    // state.bkBcsUrl = data.bkBcsUrl;
  },
  [SET_NAV_ID](state, id) {
    state.navId = id;
  },
  [SET_NAV_TITLE](state, title) {
    state.navTitle = title;
  },
  [SET_MAIN_LOADING](state, loading) {
    state.mcMainLoading = loading;
  },
  [SET_LOGIN_URL](state, url) {
    state.loginUrl = url;
  },
  [SET_ROUTE_CHANGE_LOADNG](state, val) {
    state.routeChangeLoading = val;
  },
  [SET_NAV_ROUTE_LIST](state, list) {
    state.navRouteList = list;
  },
  [SET_BIZ_BGCOLOR](state, val) {
    state.bizBgColor = val;
  },
  [SET_BIZ_CHANGE_PEDDING](state, val) {
    state.bizIdChangePedding = val;
  },
  setNavToggle(state, status) {
    state.navToggle = status;
  },
  /** 切换业务id逻辑 */
  handleChangeBizId(state, { bizId, ctx }) {
    window.cc_biz_id = +bizId;
    window.bk_biz_id = +bizId;
    window.space_uid = state.bizList?.find(item => +item.id === +bizId)?.space_uid;
    const isDemo = state.bizList?.find(item => +item.id === +bizId)?.is_demo;
    !isDemo && localStorage.setItem(LOCAL_BIZ_STORE_KEY, `${bizId}`);
    this.commit('app/SET_BIZ_ID', +bizId);
    const { navId } = ctx.$route.meta;
    const handleReload = () => {
      const { needClearQuery } = ctx.$route.meta;
      // 清空query查询条件
      if (needClearQuery) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${ctx.$route.path}`;
      } else {
        location.search = `?bizId=${window.cc_biz_id}`;
      }
    };
    // 所有页面的子路由在切换业务的时候都统一返回到父级页面
    if (navId !== ctx.$route.name) {
      const parentRoute = ctx.$router.options.routes.find(item => item.name === navId);
      if (parentRoute) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${parentRoute.path}`;
      } else {
        handleReload();
      }
    } else {
      handleReload();
    }
  },
  /**
   * @description: 更新文档链接
   * @param {Object} data
   */
  updateExtraDocLinkMap(state, data) {
    state.extraDocLinkMap = data;
  }
};

export default {
  namespaced: true,
  state,
  mutations
};

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
const getters = {
  bizId: state => state.app.bizId,
  bizName: state => state.app.bizList.find(item => +item.bk_biz_id === (+state.app.bizId || +window.bk_biz_id))?.name,
  bizList: state => state.app.bizList.slice(),
  spaceUid: state => state.app.bizList.find(item => +item.bk_biz_id === +state.app.bizId)?.space_uid,
  title: state => state.app.title,
  needBack: state => state.app.needBack,
  csrfCookieName: state => state.app.csrfCookieName,
  userName: state => state.app.userName,
  isSuperUser: state => state.app.isSuperUser,
  siteUrl: state => state.app.siteUrl,
  bkPaasHost: state => state.app.bkPaasHost,
  navId: state => state.app.navId,
  navTitle: state => state.app.navTitle,
  mcMainLoading: state => state.app.mcMainLoading,
  maxAvailableDurationLimit: state => state.app.maxAvailableDurationLimit,
  cmdbUrl: state => state.app.cmdbUrl,
  bkLogSearchUrl: state => state.app.bkLogSearchUrl,
  bkUrl: state => state.app.bkUrl,
  bkNodeManHost: state => state.app.bkNodeManHost,
  loginUrl: state => state.app.loginUrl,
  navToggle: state => state.app.navToggle,
  collectingConfigFileMaxSize: state => state.app.collectingConfigFileMaxSize,
  enable_cmdb_level: state => state.app.enable_cmdb_level,
  jobUrl: state => state.app.jobUrl,
  isFullScreen: state => state.app.isFullScreen,
  // 路由切换时需获取权限中心权限 这里有一段loading
  routeChangeLoading: state => state.app.routeChangeLoading,
  /** 是否存在demo业务 */
  hasDemoBizId: state => !!state.app.bizList.find(item => item.is_demo),
  /** BCS 地址 */
  bkBcsUrl: state => state.app.bkBcsUrl,
  navRouteList: state => state.app.navRouteList,
  // biz bg color
  bizBgColor: state => state.app.bizBgColor,
  lang: state => state.app.lang,
  bizIdChangePending: state => state.app.bizIdChangePending,
  spaceUidMap: state => state.app.spaceUidMap,
  bizIdMap: state => state.app.bizIdMap,
  paddingRoute: state => state.app.paddingRoute,
  k8sV2EnableList: state => state.app.k8sV2EnableList,
  isEnableK8sV2: state => state.app.k8sV2EnableList.some(id => (id === 0 ? true : +id === +state.app.bizId)),
  defaultBizId: state => state.app.defaultBizId,
  defaultBizIdApiId: state => state.app.defaultBizIdApiId,
};

export default getters;

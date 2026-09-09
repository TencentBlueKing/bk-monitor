/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import {
  IndexFieldInfo,
  IndexItem,
  IndexSetQueryResult,
  getStorageOptions,
  indexSetClusteringData,
  urlArgs,
} from './default-values.ts';
import { BK_LOG_STORAGE } from './store.type.ts';

const stateTpl = {
  userMeta: {
    chname: '',
    language: '',
    operator: '',
    time_zone: '',
    username: '',
  }, // /meta/mine
  /** 跨租户访问失败时后端 3641001 下发的当前/目标租户 */
  tenantMismatch: null,
  pageLoading: true,
  authDialogData: null,
  // 是否将unix时间戳格式化
  isFormatDate: true,
  // 当前运行环境
  runVersion: '',
  // 系统当前登录用户
  user: {},
  // 是否作为iframe被嵌套
  iframeQuery: {},
  // 当前项目及Id
  space: {},
  spaceUid: urlArgs.spaceUid ?? '',
  indexId: urlArgs.index_id ?? '',
  indexItem: { ...IndexItem },
  /** 联合查询ID列表 */
  unionIndexList: [...(urlArgs.unionList || [])],
  /** 联合查询元素列表 */
  unionIndexItemList: [],

  // 收藏列表
  favoriteList: [],

  /** 索引集对应的字段列表信息 */
  // @ts-ignore
  indexFieldInfo: { ...structuredClone(IndexFieldInfo) },
  indexSetQueryResult: { ...IndexSetQueryResult },
  indexSetFieldConfig: { clustering_config: { ...indexSetClusteringData } },
  indexSetFieldConfigList: {
    is_loading: false,
    data: [],
  },
  indexSetOperatorConfig: {
    /** 当前日志来源是否展示  用于字段更新后还保持显示状态 */
    isShowSourceField: false,
  },
  // 业务Id
  bkBizId: urlArgs.bizId ?? '',
  // 默认业务ID
  defaultBizId: '',

  // 我的项目列表
  mySpaceList: [],
  spaceListLoaded: false,
  currentMenu: {},
  topMenu: [],
  menuList: [],
  visibleFields: [],
  // 数据接入权限
  menuProject: [],
  // 全局配置
  globalsData: {},
  activeTopMenu: {},
  activeManageNav: {},
  activeManageSubNav: {},
  showFieldsConfigPopoverNum: 0,
  showRouterLeaveTip: false,
  // 新人指引
  userGuideData: {},
  curCustomReport: null,
  // demo 业务链接
  demoUid: '',
  spaceBgColor: '', // 空间颜色
  isEnLanguage: false,
  chartSizeNum: 0, // 自定义上报详情拖拽后 表格chart需要自适应新宽度
  isExternal: false, // 外部版
  /** 是否展示全局脱敏弹窗 */
  isShowGlobalDialog: false,
  /** 当前全局设置弹窗的活跃id */
  globalActiveLabel: 'masking-setting', // masking-setting
  /** 全局设置列表 */
  globalSettingList: [],
  /** 日志灰度 */
  maskingToggle: {
    toggleString: 'off',
    toggleList: [],
  },
  /** 外部版路由菜单 */
  externalMenu: [],
  /** 外部版当前空间的原始授权项（ExternalPermissionActionEnum），用于菜单以外的功能级显隐 */
  externalPermissions: [],
  isAppFirstLoad: true,
  /** 是否清空了显示字段，展示全量字段 */
  isNotVisibleFieldsShow: false,
  showAlert: false, // 是否展示跑马灯
  storeIsShowClusterStep: false,
  retrieveDropdownDataVersion: 0,
  fieldAggsItemsVersion: 0,
  operatorDictionaryVersion: 0,
  fieldMetaVersion: 0,
  fieldWidthVersion: 0,
  notTextTypeFields: [],
  isSetDefaultTableColumn: false,
  tookTime: 0,
  searchTotal: 0,
  clearSearchValueNum: 0,
  // 存放接口报错信息的对象
  apiErrorInfo: {},
  clusterParams: null,
  storage: {
    ...getStorageOptions({
      [BK_LOG_STORAGE.BK_BIZ_ID]: urlArgs.bizId,
      [BK_LOG_STORAGE.BK_SPACE_UID]: urlArgs.spaceUid,
    }),
  },
  features: {
    isAiAssistantActive: false,
  },
  localSort: false,
  dateTimeSort: false,
  dateTimeSortList: [],
  spaceUidMap: new Map(),
  bizIdMap: new Map(),
  aiMode: {
    active: false,
    filterList: [],
  },
};

export const createStoreState = () => structuredClone(stateTpl);
export default stateTpl;

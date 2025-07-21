/* eslint-disable @typescript-eslint/no-misused-promises */
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

import { axiosInstance } from '@/api';
import http from '@/api';
import {
  unifyObjectStyle,
  getOperatorKey,
  readBlobRespToJson,
  parseBigNumberList,
  setDefaultTableWidth,
  formatDate,
} from '@/common/util';
import { handleTransformToTimestamp } from '@/components/time-range/utils';
import { builtInInitHiddenList } from '@/const/index.js';
import DOMPurify from 'dompurify';
/**
 * @file main store
 * @author  <>
 */
import Vue, { set } from 'vue';
import Vuex from 'vuex';

import { deepClone } from '../components/monitor-echarts/utils';
import { menuArr } from '../components/nav/complete-menu';

import collect from './collect';
import { ConditionOperator } from './condition-operator';
import {
  IndexSetQueryResult,
  IndexFieldInfo,
  IndexItem,
  indexSetClusteringData,
  getDefaultRetrieveParams,
  getStorageOptions,
  BkLogGlobalStorageKey,
  URL_ARGS,
} from './default-values.ts';
import globals from './globals';
import {
  isAiAssistantActive,
  getCommonFilterAdditionWithValues,
} from './helper';
import RequestPool from './request-pool';
import retrieve from './retrieve';
import { BK_LOG_STORAGE, SEARCH_MODE_DIC } from './store.type.ts';
Vue.use(Vuex);

export const SET_APP_STATE = 'SET_APP_STATE';

const stateTpl = {
  activeManageNav: {},
  activeManageSubNav: {},
  activeTopMenu: {},
  // 存放接口报错信息的对象
  apiErrorInfo: {},
  // 是否作为iframe被嵌套
  asIframe: false,
  authDialogData: null,
  bizIdMap: new Map(),
  // 业务Id
  bkBizId: URL_ARGS.bizId ?? '',
  chartSizeNum: 0, // 自定义上报详情拖拽后 表格chart需要自适应新宽度
  clearSearchValueNum: 0,
  clusterParams: null,
  // -- id, id对应数据
  collectDetail: [0, {}],
  curCustomReport: null,
  currentMenu: {},
  currentMenuItem: {},

  // 默认业务ID
  defaultBizId: '',

  /** 索引集对应的字段列表信息 */
  // demo 业务链接
  demoUid: '',
  errorPage: ['notTraceIndex'],
  /** 外部版路由菜单 */
  externalMenu: [],
  // 收藏列表
  favoriteList: [],
  features: {
    isAiAssistantActive: false,
  },
  /** 当前全局设置弹窗的活跃id */
  globalActiveLabel: 'masking-setting', // masking-setting
  /** 全局设置列表 */
  globalSettingList: [],
  // 全局配置
  globalsData: {},

  iframeQuery: {},
  // @ts-ignore
  indexFieldInfo: { ...IndexFieldInfo },
  indexId: URL_ARGS.index_id ?? '',
  indexItem: { ...IndexItem },
  indexSetFieldConfig: { clustering_config: { ...indexSetClusteringData } },
  indexSetFieldConfigList: {
    data: [],
    is_loading: false,
  },
  indexSetOperatorConfig: {
    /** 当前日志来源是否展示  用于字段更新后还保持显示状态 */
    isShowSourceField: false,
  },
  indexSetQueryResult: { ...IndexSetQueryResult },
  isAppFirstLoad: true,
  isEnLanguage: false,
  isExternal: false, // 外部版
  // 是否将unix时间戳格式化
  isFormatDate: true,
  /** 是否清空了显示字段，展示全量字段 */
  isNotVisibleFieldsShow: false,
  isSetDefaultTableColumn: false,
  /** 是否展示全局脱敏弹窗 */
  isShowGlobalDialog: false,
  localSort: false,
  /** 日志灰度 */
  maskingToggle: {
    toggleList: [],
    toggleString: 'off',
  },
  menuList: [],
  // 数据接入权限
  menuProject: [],
  // 我的项目列表
  mySpaceList: [],
  notTextTypeFields: [],
  operatorDictionary: {},
  pageLoading: true,
  retrieveDropdownData: {},
  // 当前运行环境
  runVersion: '',
  searchTotal: 0,
  showAlert: false, // 是否展示跑马灯
  showFieldsConfigPopoverNum: 0,
  showRouterLeaveTip: false,
  // 当前项目及Id
  space: {},
  spaceBgColor: '', // 空间颜色
  spaceUid: URL_ARGS.spaceUid ?? '',
  spaceUidMap: new Map(),
  storage: {
    ...getStorageOptions({
      [BK_LOG_STORAGE.BK_BIZ_ID]: URL_ARGS.bizId,
      [BK_LOG_STORAGE.BK_SPACE_UID]: URL_ARGS.spaceUid,
    }),
  },
  storeIsShowClusterStep: false,
  tookTime: 0,
  topMenu: [],
  traceIndexId: '',
  /** 联合查询元素列表 */
  unionIndexItemList: [],
  /** 联合查询ID列表 */
  unionIndexList: [...(URL_ARGS.unionList ?? [])] ?? [],
  // 系统当前登录用户
  user: {},
  // 新人指引
  userGuideData: {},
  userMeta: {}, // /meta/mine
  visibleFields: [],
};

const store = new Vuex.Store({
  actions: {
    changeShowUnionSource({ commit, state }) {
      commit('updateIndexSetOperatorConfig', {
        isShowSourceField: !state.indexSetOperatorConfig.isShowSourceField,
      });
    },

    // 判断有无权限
    checkAllowed(context, paramData) {
      return new Promise(async (resolve, reject) => {
        try {
          const checkRes = await http.request('auth/checkAllowed', {
            data: paramData,
          });
          for (const item of checkRes.data) {
            if (item.is_allowed === false) {
              // 无权限
              resolve({
                isAllowed: false,
              });
              return;
            }
          }
          // 有权限
          resolve({
            isAllowed: true,
          });
        } catch (err) {
          // 请求出错
          reject(err);
        }
      });
    },
    // 判断有无权限，无权限获取相关信息
    checkAndGetData(context, paramData) {
      return new Promise(async (resolve, reject) => {
        try {
          const checkRes = await http.request('auth/checkAllowed', {
            data: paramData,
          });
          for (const item of checkRes.data) {
            if (item.is_allowed === false) {
              // 无权限
              const applyDataRes = await http.request('auth/getApplyData', {
                data: paramData,
              });
              resolve({
                data: applyDataRes.data,
                isAllowed: false,
              });
              return;
            }
          }
          // 有权限
          resolve({
            isAllowed: true,
          });
        } catch (err) {
          // 请求出错
          reject(err);
        }
      });
    },
    clearApiError({ commit }, apiName) {
      commit('CLEAR_API_ERROR', apiName);
    },
    // 已知无权限，需要获取信息
    getApplyData(context, paramData) {
      return http.request('auth/getApplyData', {
        data: paramData,
      });
    },
    // -- 代码调整
    getCollectDetail({ commit, state }, data) {
      // 判断是否有该id的缓存数据
      if (state.collectDetail[0] !== data.collector_config_id) {
        commit('updateCollectDetail', [data.collector_config_id, data || {}]);
        return data;
      }
    },
    getGlobalsData({ commit }) {
      return http.request('collect/globals', { query: {} }).then((response) => {
        const globalsData = response.data || {};
        commit('updateGlobalsData', globalsData);
        return globalsData;
      });
    },
    /**
     * 获取菜单列表
     *
     * @param {Function} commit store commit mutation handler
     * @param {Object} state store state
     * @param {Function} dispatch store dispatch action handler
     * @param {Object} params 请求参数
     * @param {Object} config 请求的配置
     *
     * @return {Promise} promise 对象
     */
    getMenuList({}, spaceUid) {
      return http.request('meta/menu', {
        query: {
          space_uid: spaceUid,
        },
      });
    },

    handleTrendDataZoom({ commit, getters }, payload) {
      const { end_time, format, start_time } = payload;
      const formatStr = getters.retrieveParams.format;

      const [startTimeStamp, endTimeStamp] = format
        ? handleTransformToTimestamp([start_time, end_time], formatStr)
        : [start_time, end_time];

      commit('updateIndexItem', {
        datePickerValue: [start_time, end_time],
        end_time: endTimeStamp,
        start_time: startTimeStamp,
      });

      return Promise.resolve(true);
    },

    requestFavoriteList({ commit, state }, payload) {
      commit('updateFavoriteList', []);
      return http
        .request('favorite/getFavoriteByGroupList', {
          query: {
            order_type:
              payload?.sort ??
              (localStorage.getItem('favoriteSortType') || 'NAME_ASC'),
            space_uid: payload?.spaceUid ?? state.spaceUid,
          },
        })
        .then((resp) => {
          const results = (resp.data || []).map((item) => {
            item.favorites?.forEach((sub) => {
              sub.full_name = `${item.group_name}/${sub.name}`;
            });
            return item;
          });
          commit('updateFavoriteList', results);
          return resp;
        });
    },
    requestFieldConfigList({ commit, state }, payload) {
      const cancelTokenKey = 'requestFieldConfigCancelToken';
      RequestPool.execCanceToken(cancelTokenKey);
      const requestCancelToken =
        payload.cancelToken ?? RequestPool.getCancelToken(cancelTokenKey);
      commit('updateIndexSetFieldConfigList', {
        data: [],
        is_loading: true,
      });
      return http
        .request(
          'retrieve/getFieldsListConfig',
          {
            data: {
              ...(state.indexItem.isUnionIndex
                ? { index_set_ids: state.unionIndexList }
                : { index_set_id: state.indexId }),
              index_set_type: state.indexItem.isUnionIndex ? 'union' : 'single',
              scope: 'default',
            },
          },
          {
            cancelToken: requestCancelToken,
          }
        )
        .then((resp) => {
          commit('updateIndexSetFieldConfigList', {
            data: resp.data ?? [],
          });

          return resp;
        })
        .finally(() => {
          commit('updateIndexSetFieldConfigList', {
            is_loading: false,
          });
        });
    },

    /** 请求获取用户个人配置信息 */
    requestIndexSetCustomConfigInfo({ commit, state }) {
      // @ts-ignore
      const {
        end_time = '',
        ids = [],
        isUnionIndex,
        start_time = '',
      } = state.indexItem;
      if (!ids.length) {
        return;
      }
      const urlStr = isUnionIndex
        ? 'unionSearch/unionMapping'
        : 'retrieve/getLogTableHead';
      !isUnionIndex && commit('deleteApiError', urlStr);
      const queryData = {
        end_time,
        is_realtime: 'True',
        start_time,
      };
      if (isUnionIndex) {
        Object.assign(queryData, {
          index_set_ids: ids,
        });
      }
      return http
        .request(
          urlStr,
          {
            data: isUnionIndex ? queryData : undefined,
            params: { index_set_id: ids[0] },
            query: !isUnionIndex ? queryData : undefined,
          },
          isUnionIndex ? {} : { catchIsShowMessage: false }
        )
        .then((res) => {
          commit(
            'retrieve/updateCatchFieldCustomConfig',
            res.data.user_custom_config
          ); // 更新用户个人配置
          return res;
        })
        .catch(() => {
          commit('retrieve/updateCatchFieldCustomConfig', {
            ...state.retrieve.catchFieldCustomConfig,
            filterSetting: {},
          });
        })
        .finally();
    },

    /** 请求字段config信息 */
    requestIndexSetFieldInfo({ commit, state }) {
      // @ts-ignore
      const {
        end_time = '',
        ids = [],
        isUnionIndex,
        start_time = '',
      } = state.indexItem;
      commit('resetIndexFieldInfo');
      commit('updataOperatorDictionary', {});
      commit('updateNotTextTypeFields', {});
      commit('updateIndexSetFieldConfig', {});
      commit('updateVisibleFields', []);

      if (!ids.length) {
        return;
      }
      commit('resetIndexFieldInfo', { is_loading: true });
      const urlStr = isUnionIndex
        ? 'unionSearch/unionMapping'
        : 'retrieve/getLogTableHead';
      !isUnionIndex && commit('deleteApiError', urlStr);
      const queryData = {
        end_time,
        is_realtime: 'True',
        start_time,
      };
      if (isUnionIndex) {
        Object.assign(queryData, {
          index_set_ids: ids,
        });
      }

      return http
        .request(
          urlStr,
          {
            data: isUnionIndex ? queryData : undefined,
            params: { index_set_id: ids[0] },
            query: !isUnionIndex ? queryData : undefined,
          },
          isUnionIndex ? {} : { catchIsShowMessage: false }
        )
        .then((res) => {
          commit('updateIndexFieldInfo', res.data ?? {});
          commit('updataOperatorDictionary', res.data ?? {});
          commit('updateNotTextTypeFields', res.data ?? {});
          commit('updateIndexSetFieldConfig', res.data ?? {});
          commit(
            'retrieve/updateFiledSettingConfigID',
            res.data?.config_id ?? -1
          ); // 当前字段配置configID
          commit(
            'retrieve/updateCatchFieldCustomConfig',
            res.data.user_custom_config
          ); // 更新用户个人配置
          commit('resetVisibleFields');
          commit('resetIndexSetOperatorConfig');
          commit('updateIsSetDefaultTableColumn');
          return res;
        })
        .catch((err) => {
          !isUnionIndex &&
            commit('updateApiError', { apiName: urlStr, errorMessage: err });
          commit('updateIndexFieldInfo', { is_loading: false });
        })
        .finally(() => {
          commit('updateIndexFieldInfo', { is_loading: false });
        });
    },

    /**
     * 索引集选择改变事件
     * 更新索引集相关缓存 & 发起当前索引集所需字段信息请求
     * @param {*} param0
     * @param {*} payload
     */
    requestIndexSetItemChanged({ commit, dispatch }, payload) {
      commit('updateIndexItem', payload);
      commit('resetIndexSetQueryResult', { is_loading: true, search_count: 0 });

      if (!payload.isUnionIndex) {
        commit('updateIndexId', payload.ids[0]);
      }

      return dispatch('requestIndexSetFieldInfo');
    },

    /**
     * 执行查询
     *
     * @param {Boolean} payload.isPagination - 是否是分页请求。
     * @param {CancelToken} payload.cancelToken - 用于取消请求的 Axios cancel token。
     * @param {Number} payload.searchCount - 自定义的查询计数器。
     *
     */
    requestIndexSetQuery(
      { commit, dispatch, getters, state },
      payload = {
        cancelToken: null,
        isPagination: false,
        searchCount: undefined,
      }
    ) {
      if (!payload?.isPagination) {
        commit('updateIndexSetQueryResult', {
          list: [],
          origin_log_list: [],
        });
      }

      if (
        (!state.indexItem.isUnionIndex && !state.indexId) ||
        (state.indexItem.isUnionIndex && !state.indexItem.ids.length)
      ) {
        state.searchTotal = 0;
        commit('updateSqlQueryFieldList', []);
        commit('updateIndexSetQueryResult', {
          exception_msg: '',
          is_error: false,
        });
        return; // Promise.reject({ message: `index_set_id is undefined` });
      }
      let begin = state.indexItem.begin;
      const { format, size, ...otherPrams } = getters.retrieveParams;

      // 如果是第一次请求
      // 分页请求后面请求{ start_time, end_time }要保证和初始值一致
      if (!payload?.isPagination) {
        // 每次请求这里需要根据选择日期时间这里计算最新的timestamp
        // 最新的 start_time, end_time 也要记录下来，用于字段统计时，保证请求的参数一致
        const { datePickerValue } = state.indexItem;
        const letterRegex = /[a-zA-Z]/;
        const needTransform = datePickerValue.every((d) => letterRegex.test(d));

        const [start_time, end_time] = needTransform
          ? handleTransformToTimestamp(datePickerValue, format)
          : [state.indexItem.start_time, state.indexItem.end_time];

        if (needTransform) {
          commit('updateIndexItem', { end_time, start_time });
        }
      }

      const searchCount =
        payload.searchCount ?? state.indexSetQueryResult.search_count + 1;
      commit(
        payload.isPagination
          ? 'updateIndexSetQueryResult'
          : 'resetIndexSetQueryResult',
        {
          is_loading: true,
          search_count: searchCount,
        }
      );

      const baseUrl =
        process.env.NODE_ENV === 'development'
          ? 'api/v1'
          : window.AJAX_URL_PREFIX;
      const cancelTokenKey = 'requestIndexSetQueryCancelToken';
      RequestPool.execCanceToken(cancelTokenKey);
      const requestCancelToken =
        payload.cancelToken ?? RequestPool.getCancelToken(cancelTokenKey);

      // 区分联合查询和单选查询
      const searchUrl = !state.indexItem.isUnionIndex
        ? `/search/index_set/${state.indexId}/search/`
        : '/search/index_set/union_search/';

      const { end_time, start_time } = state.indexItem;

      const baseData = {
        bk_biz_id: state.bkBizId,
        size,
        ...otherPrams,
        addition: [
          ...otherPrams.addition,
          ...getCommonFilterAdditionWithValues(state),
        ],
        end_time,
        sort_list: state.localSort
          ? otherPrams.sort_list
          : getters.custom_sort_list,
        start_time,
      };

      // 更新联合查询的begin
      const unionConfigs = state.unionIndexList.map((item) => ({
        begin: payload.isPagination
          ? (state.indexItem.catchUnionBeginList.find(
              (cItem) => String(cItem?.index_set_id) === item
            )?.begin ?? 0)
          : 0,
        index_set_id: item,
      }));

      const queryBegin = payload.isPagination ? (begin += size) : 0;

      const queryData = Object.assign(
        baseData,
        !state.indexItem.isUnionIndex
          ? {
              begin: queryBegin, // 单选检索的begin
            }
          : {
              union_configs: unionConfigs,
            }
      );
      const params = {
        baseURL: baseUrl,
        cancelToken: requestCancelToken,
        data: queryData,
        method: 'post',
        responseType: 'blob',
        url: searchUrl,
        withCredentials: true,
      };
      if (state.isExternal) {
        params.headers = {
          'X-Bk-Space-Uid': state.spaceUid,
        };
      }

      return axiosInstance(params)
        .then((resp) => {
          if (resp.data && !resp.message) {
            return readBlobRespToJson(resp.data).then(
              ({ code, data, message, result }) => {
                const rsolvedData = data;
                if (result) {
                  const indexSetQueryResult = state.indexSetQueryResult;
                  const logList = parseBigNumberList(rsolvedData.list);
                  const originLogList = parseBigNumberList(
                    rsolvedData.origin_log_list
                  );
                  const size = logList.length;

                  rsolvedData.list = payload.isPagination
                    ? indexSetQueryResult.list.concat(logList)
                    : logList;
                  rsolvedData.origin_log_list = payload.isPagination
                    ? indexSetQueryResult.origin_log_list.concat(originLogList)
                    : originLogList;

                  const catchUnionBeginList = parseBigNumberList(
                    rsolvedData?.union_configs || []
                  );
                  state.tookTime = payload.isPagination
                    ? state.tookTime + Number(data?.took || 0)
                    : Number(data?.took || 0);

                  if (!payload?.isPagination) {
                    commit('updateIsSetDefaultTableColumn', { list: logList });
                    dispatch('requestSearchTotal');
                  }
                  // 更新页数
                  commit('updateSqlQueryFieldList', logList);
                  commit('updateIndexItem', {
                    begin: payload.isPagination ? begin : 0,
                    catchUnionBeginList,
                  });
                  commit('updateIndexSetQueryResult', rsolvedData);

                  return {
                    code,
                    data,
                    length: logList.length,
                    message,
                    result,
                    size,
                  };
                }

                commit('updateIndexSetQueryResult', {
                  exception_msg: message,
                  is_error: !result,
                });

                return {
                  code,
                  data,
                  length: 0,
                  message,
                  result,
                  size: 0,
                };
              }
            );
          }

          return { data, message, result: false };
        })
        .catch((e) => {
          state.searchTotal = 0;
          commit('updateSqlQueryFieldList', []);
          if (e.code !== 'ERR_CANCELED') {
            commit('updateIndexSetQueryResult', {
              exception_msg: e?.message ?? e?.toString(),
              is_error: true,
            });
          }
        })
        .finally(() => {
          commit('updateIndexSetQueryResult', { is_loading: false });
        });
    },

    /**
     * 请求提示词列表
     * @param {*} param0
     * @param {*} payload: { force: boolean; fields: []; addition: []; size: number; commit: boolean; cancelToken: boolean }
     * @returns
     */
    requestIndexSetValueList({ commit, state }, payload) {
      const { end_time, start_time } = state.indexItem;
      const lastQueryTimerange = `${start_time}_${end_time}`;

      const cancelTokenKey = 'requestIndexSetValueListCancelToken';
      RequestPool.execCanceToken(cancelTokenKey);
      const requestCancelToken = payload.cancelToken
        ? RequestPool.getCancelToken(cancelTokenKey)
        : null;

      // 本次请求与上次请求时间范围不一致，重置缓存数据
      if (state.indexFieldInfo.last_eggs_request_token !== lastQueryTimerange) {
        set(state.indexFieldInfo, 'aggs_items', {});
      }

      if (!!payload.force) {
        (payload?.fields ?? []).forEach((field) => {
          set(state.indexFieldInfo.aggs_items, field.field_name, []);
        });
      }

      const isDefaultQuery = !(payload?.fields?.length ?? false);
      const filterBuildIn = (field) =>
        isDefaultQuery ? !field.is_built_in : true;

      const filterFn = (field) =>
        !state.indexFieldInfo.aggs_items[field.field_name]?.length &&
        field.es_doc_values &&
        filterBuildIn(field) &&
        ['keyword'].includes(field.field_type) &&
        !/^__dist_/.test(field.field_name);

      const mapFn = (field) => field.field_name;
      const fields = (
        payload?.fields?.length ? payload.fields : state.indexFieldInfo.fields
      )
        .filter(filterFn)
        .map(mapFn);

      if (!fields.length) return Promise.resolve(true);

      const urlStr = state.indexItem.isUnionIndex
        ? 'unionSearch/unionTerms'
        : 'retrieve/getAggsTerms';
      const queryData = {
        addition: payload?.addition ?? [],
        end_time: formatDate(end_time),
        fields,
        keyword: '*',
        size: payload?.size ?? 100,
        start_time: formatDate(start_time),
      };

      if (state.indexItem.isUnionIndex) {
        Object.assign(queryData, {
          index_set_ids: state.unionIndexList,
        });
      }

      const params = {
        index_set_id: state.indexId,
      };

      const body = {
        data: queryData,
        params,
      };

      return http
        .request(urlStr, body, {
          cancelToken: requestCancelToken,
        })
        .then((resp) => {
          if (payload?.commit !== false) {
            commit('updateIndexFieldEggsItems', resp.data.aggs_items ?? {});
          }

          return resp;
        });
    },

    requestMenuList({ commit }, spaceUid) {
      const routeMap = {
        manage_access: 'manage',
        manage_data_link: 'linkConfiguration',
        manage_extract: 'manageExtract',
        manage_index_set: 'indexSet',
        manage_migrate: 'migrate',
        manage_user_group: 'permissionGroup',
        // 后端返回的导航id映射
        search: 'retrieve',
      };

      const replaceMenuId = (list) => {
        list.forEach((item) => {
          if (item.id === 'search') {
            item.id = 'retrieve';
          }
          item.id = item.id.replace(/_/g, '-');
          if (item.children) {
            replaceMenuId(item.children);
          }
        });
        return list;
      };

      const deepUpdateMenu = (oldMenu, resMenu) => {
        // resMenu结果返回的menu子级
        resMenu.name = oldMenu.name;
        resMenu.dropDown = oldMenu.dropDown;
        resMenu.dropDown = oldMenu.dropDown;
        resMenu.level = oldMenu.level;
        resMenu.isDashboard = oldMenu.isDashboard;
        if (resMenu.children) {
          if (oldMenu.children) {
            resMenu.children.forEach((item) => {
              item.id = routeMap[item.id] || item.id;
              const menu = oldMenu.children.find(
                (menuItem) => menuItem.id === item.id
              );
              if (menu) {
                deepUpdateMenu(menu, item);
              }
            });
          }
        } else {
          if (oldMenu.children) {
            resMenu.children = oldMenu.children;
          }
        }
      };

      return http
        .request('meta/menu', {
          query: {
            space_uid: spaceUid,
          },
        })
        .then((res) => {
          const menuList = replaceMenuId(res.data || []);

          menuList.forEach((child) => {
            child.id = routeMap[child.id] || child.id;
            const menu = menuArr.find((menuItem) => menuItem.id === child.id);
            if (menu) {
              deepUpdateMenu(menu, child);
            }
          });
          commit('updateTopMenu', menuList);
          commit('updateMenuProject', res.data || []);

          return menuList;
        });
    },

    requestSearchTotal({ getters, state }) {
      state.searchTotal = 0;
      const start_time = Math.floor(getters.retrieveParams.start_time);
      const end_time = Math.ceil(getters.retrieveParams.end_time);
      http
        .request(
          'retrieve/fieldStatisticsTotal',
          {
            data: {
              ...getters.retrieveParams,
              addition: [
                ...getters.retrieveParams.addition,
                ...getCommonFilterAdditionWithValues(state),
              ],
              bk_biz_id: state.bkBizId,
              end_time,
              index_set_ids: state.indexItem.ids,
              start_time,
            },
          },
          {
            catchIsShowMessage: false,
          }
        )
        .then((res) => {
          const { code, data } = res;
          if (code === 0) state.searchTotal = data.total_count;
        });
    },
    setApiError({ commit }, payload) {
      commit('SET_API_ERROR', payload);
    },
    /**
     * 下钻添加条件到查询搜索
     * @param {*} param0
     * @param {*} payload
     * @returns
     */
    setQueryCondition({ dispatch, state }, payload) {
      const newQueryList = Array.isArray(payload) ? payload : [payload];
      const isLink = newQueryList[0]?.isLink;
      const searchMode =
        SEARCH_MODE_DIC[state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';
      const depth = Number(payload.depth ?? '0');
      const isNestedField = payload?.isNestedField ?? 'false';
      const isNewSearchPage = newQueryList[0].operator === 'new-search-page-is';

      const getTargetField = (field) => {
        return state.visibleFields?.find((item) => item.field_name === field);
      };

      const getFieldType = (field) => {
        return getTargetField(field)?.field_type ?? '';
      };

      const getAdditionMappingOperator = ({ field, operator, value }) => {
        let mappingKey = {
          // is is not 值映射
          is: '=',
          'is not': '!=',
        };

        /** text类型字段类型的下钻映射 */
        const textMappingKey = {
          is: 'contains match phrase',
          'is not': 'not contains match phrase',
        };

        /** keyword 类型字段类型的下钻映射 */
        const keywordMappingKey = {
          is: 'contains',
          'is not': 'not contains',
        };

        const boolMapping = {
          is: `is ${value[0]}`,
          'is not': `is ${/true/i.test(value[0]) ? 'false' : 'true'}`,
        };

        const targetField = getTargetField(field);

        const textType = targetField?.field_type ?? '';
        const isVirtualObjNode = targetField?.is_virtual_obj_node ?? false;

        if (isVirtualObjNode && textType === 'object') {
          mappingKey = textMappingKey;
        }

        if (textType === 'text') {
          mappingKey = textMappingKey;
        }

        if (textType === 'boolean') {
          mappingKey = boolMapping;
          if (value.length) {
            value.splice(0, value.length);
          }
        }

        if ((depth > 1 || isNestedField === 'true') && textType === 'keyword') {
          mappingKey = keywordMappingKey;
        }
        return mappingKey[operator] ?? operator; // is is not 值映射
      };

      const formatJsonString = (formatResult) => {
        if (typeof formatResult === 'string') {
          return DOMPurify.sanitize(formatResult);
        }

        return formatResult;
      };

      const getSqlAdditionMappingOperator = ({ field, operator }) => {
        const textType = getFieldType(field);

        const formatValue = (value) => {
          let formatResult = value;
          if (['text', 'string', 'keyword'].includes(textType)) {
            if (Array.isArray(formatResult)) {
              formatResult = formatResult.map(formatJsonString);
            } else {
              formatResult = formatJsonString(formatResult);
            }
          }

          return formatResult;
        };

        let mappingKey = {
          // is is not 值映射
          is: (val) => `${field}: "${formatValue(val)}"`,
          'is not': (val) => `NOT ${field}: "${formatValue(val)}"`,
        };

        return mappingKey[operator] ?? operator; // is is not 值映射
      };
      /** 判断条件是否已经在检索内 */
      const searchValueIsExist = (newSearchValue, searchMode) => {
        let isExist;
        if (searchMode === 'ui') {
          isExist = state.indexItem.addition.some((addition) => {
            return (
              addition.field === newSearchValue.field &&
              addition.operator === newSearchValue.operator &&
              addition.value.toString() === newSearchValue.value.toString()
            );
          });
        }
        if (searchMode === 'sql') {
          const keyword = state.indexItem.keyword.replace(/^\s*\*\s*$/, '');
          isExist = keyword.indexOf(newSearchValue) !== -1;
        }
        return isExist;
      };
      const filterQueryList = newQueryList
        .map((item) => {
          const isNewSearchPage = item.operator === 'new-search-page-is';
          item.operator = isNewSearchPage ? 'is' : item.operator;
          const { field, operator, value } = item;
          const targetField = getTargetField(field);

          let newSearchValue = null;
          if (searchMode === 'ui') {
            const mapOperator = getAdditionMappingOperator({
              field,
              operator,
              value,
            });
            if (targetField?.is_virtual_obj_node) {
              newSearchValue = Object.assign(
                { field: '*', value },
                { operator: mapOperator }
              );
            } else {
              newSearchValue = Object.assign(
                { field, value },
                { operator: mapOperator }
              );
            }
          }
          if (searchMode === 'sql') {
            if (targetField?.is_virtual_obj_node) {
              newSearchValue = `\"${value[0]}\"`;
            } else {
              newSearchValue = getSqlAdditionMappingOperator({
                field,
                operator,
              })?.(value);
            }
          }
          const isExist = searchValueIsExist(newSearchValue, searchMode);
          return !isExist || isNewSearchPage ? newSearchValue : null;
        })
        .filter(Boolean);

      // list内的所有条件均相同时不进行添加条件处理
      if (!filterQueryList.length)
        return Promise.resolve([filterQueryList, searchMode, isNewSearchPage]);
      if (!isLink) {
        if (searchMode === 'ui') {
          const startIndex = state.indexItem.addition.length;
          state.indexItem.addition.splice(startIndex, 0, ...filterQueryList);
          dispatch('requestIndexSetQuery');
        }

        if (searchMode === 'sql') {
          const keyword = state.indexItem.keyword.replace(/^\s*\*\s*$/, '');
          const keywords = keyword.length > 0 ? [keyword] : [];
          const newSearchKeywords = filterQueryList.filter(
            (item) => keyword.indexOf(item) === -1
          );
          if (newSearchKeywords.length) {
            const lastIndex = newSearchKeywords.length - 1;
            newSearchKeywords[lastIndex] = newSearchKeywords[lastIndex].replace(
              /\s*$/,
              ' '
            );
          }

          if (keywords.length > 0 && !/\s$/.test(keywords[0])) {
            keywords[0] = keywords[0] + ' ';
          }

          const newSearchKeyword = (keywords ?? [])
            .concat(newSearchKeywords)
            .join('AND ');
          state.indexItem.keyword = newSearchKeyword;
          dispatch('requestIndexSetQuery');
        }
      }
      return Promise.resolve([filterQueryList, searchMode, isNewSearchPage]);
    },

    toggleFieldVisible({ commit, state }, { field, visible }) {
      const displayFieldNames = state.visibleFields.map(
        (item) => item.field_name
      );
      if (visible) {
        // 需要显示字段
        displayFieldNames.push(field.field_name);
      } else {
        // 需要隐藏字段
        const index = state.visibleFields.findIndex(
          (item) => field.field_name === item.field_name
        );
        displayFieldNames.splice(index, 1);
      }
      if (!displayFieldNames.length) return; // 可以设置为全部隐藏，但是不请求接口

      http
        .request('retrieve/postFieldsConfig', {
          data: {
            config_id: state.retrieve.filedSettingConfigID,
            display_fields: displayFieldNames,
            index_set_id: state.indexId,
            index_set_ids: state.unionIndexList,
            index_set_type: state.isUnionSearch ? 'union' : 'single',
            sort_list: state.indexFieldInfo.sort_list,
          },
          params: { index_set_id: state.indexId },
        })
        .catch((e) => {
          console.warn(e);
        });
      commit('resetVisibleFields', { displayFieldNames, version: 'v2' });
      commit('updateIsSetDefaultTableColumn', false);
    },
    /**
     * 更新 Vuex 状态中的用户字段配置。
     *
     * @param {Object} userConfig 要更新的用户配置对象。
     * @param {boolean} userConfig.isUpdate 标志是否仅为更新操作。如果为 `true`，表示仅为更新操作，在成功响应后不会提交新的配置到 Vuex。
     * @return {Promise} 一个 Promise，解析为 HTTP 请求的响应。
     */
    userFieldConfigChange({ commit, getters, state }, userConfig) {
      return new Promise(async (resolve, reject) => {
        const indexSetConfig = {
          ...state.retrieve.catchFieldCustomConfig,
          ...userConfig,
        };
        delete indexSetConfig.isUpdate;
        const queryParams = {
          index_set_config: indexSetConfig,
          index_set_id: state.indexId,
          index_set_type: getters.isUnionSearch ? 'union' : 'single',
        };
        if (getters.isUnionSearch) {
          delete queryParams.index_set_id;
          queryParams.index_set_ids = state.unionIndexList;
        }
        try {
          const res = await http.request(
            'retrieve/updateUserFiledTableConfig',
            {
              data: queryParams,
            }
          );
          if (res.code === 0 && !userConfig.isUpdate) {
            const userConfig = res.data.index_set_config;
            commit('retrieve/updateCatchFieldCustomConfig', userConfig);
          }
          resolve(res);
        } catch (err) {
          reject(err);
        }
      });
    },

    /**
     * 获取用户信息
     *
     * @param {Function} commit store commit mutation handler
     * @param {Object} state store state
     * @param {Function} dispatch store dispatch action handler
     * @param {Object} params 请求参数
     * @param {Object} config 请求的配置
     *
     * @return {Promise} promise 对象
     */
    userInfo({ commit }, params, config = {}) {
      return http
        .request('userInfo/getUserInfo', { config, query: params })
        .then((response) => {
          const userData = response.data || {};
          commit('updateUser', userData);
          return userData;
        });
    },
  },
  // 公共 getters
  getters: {
    accessUserManage: (state) =>
      Boolean(
        state.topMenu
          .find((item) => item.id === 'manage')
          ?.children.some(
            (item) =>
              item.id === 'permissionGroup' && item.project_manage === true
          )
      ),
    asIframe: (state) => state.asIframe,
    bkBizId: (state) => state.bkBizId,
    chartSizeNum: (state) => state.chartSizeNum,
    // -- 返回数据
    collectDetail: (state) => state.collectDetail[1],
    custom_sort_list: (state) =>
      state.retrieve.catchFieldCustomConfig.sortList ?? [],
    defaultBizId: (state) => state.defaultBizId,
    demoUid: (state) => state.demoUid,
    getApiError: (state) => (apiName) => {
      return state.apiErrorInfo[apiName];
    },
    globalActiveLabel: (state) => state.globalActiveLabel,
    globalSettingList: (state) => state.globalSettingList,
    globalsData: (state) => state.globalsData,
    iframeQuery: (state) => state.iframeQuery,
    indexId: (state) => state.indexId,
    isAiAssistantActive: (state) => state.features.isAiAssistantActive,
    isEnLanguage: (state) => state.isEnLanguage,
    isLimitExpandView: (state) =>
      state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW],
    isNewRetrieveRoute: () => {
      const v = localStorage.getItem('retrieve_version') ?? 'v2';
      return v === 'v2';
    },
    isNotVisibleFieldsShow: (state) => state.isNotVisibleFieldsShow,
    isShowGlobalDialog: (state) => state.isShowGlobalDialog,
    /** 脱敏灰度判断 */
    isShowMaskingTemplate: (state) =>
      state.maskingToggle.toggleString === 'on' ||
      state.maskingToggle.toggleList.includes(Number(state.bkBizId)),
    /** 是否是联合查询 */
    isUnionSearch: (state) => !!state.indexItem.isUnionIndex,
    maskingToggle: (state) => state.maskingToggle,
    mySpaceList: (state) => state.mySpaceList,
    pageLoading: (state) => state.pageLoading,
    resultTableStaticWidth: (state) => {
      return (
        (state.indexSetOperatorConfig?.bcsWebConsole?.is_active ? 84 : 58) + 50
      );
    },
    // @ts-ignore
    retrieveParams: (state) => {
      const {
        addition,
        begin,
        end_time,
        format,
        host_scopes,
        interval,
        ip_chooser,
        keyword = '*',
        size,
        sort_list,
        start_time,
      } = state.indexItem;

      const search_mode =
        SEARCH_MODE_DIC[state.storage[BK_LOG_STORAGE.SEARCH_TYPE]] ?? 'ui';

      const filterAddition = addition
        .filter((item) => !item.disabled && item.field !== '_ip-select_')
        .map(({ field, operator, showList, value }) => {
          const addition = {
            field,
            operator,
            value,
          };

          if (['is true', 'is false'].includes(addition.operator)) {
            addition.value = [''];
          } else {
            if (showList) {
              addition.value = value.filter((_, index) => !showList[index]);
            }
          }

          return addition;
        });

      // 格式化 addition value
      // 如果字段类型为 text & is_case_sensitive = false 则将 value 转换为小写
      // 操作符为"=~", "&=~", "!=~", "&!=~"  四者之一
      filterAddition.forEach((item) => {
        if (['=~', '&=~', '!=~', '&!=~'].includes(item.operator)) {
          const field = (state.indexFieldInfo?.fields ?? []).find(
            (f) => f.field_name === item.field
          );
          if (
            field?.field_type === 'text' &&
            !(field?.is_case_sensitive ?? true)
          ) {
            item.value = item.value.map((v) => v?.toLowerCase() ?? '');
          }
        }
      });

      const searchParams =
        search_mode === 'sql'
          ? { addition: [], keyword }
          : { addition: filterAddition, keyword: '*' };

      if (searchParams.keyword.replace(/\s*/, '') === '') {
        searchParams.keyword = '*';
      }

      return {
        addition: filterAddition,
        begin,
        bk_biz_id: state.bkBizId,
        end_time,
        format,
        host_scopes,
        interval,
        ip_chooser,
        search_mode,
        size,
        sort_list,
        start_time,
        ...searchParams,
      };
    },
    runVersion: (state) => state.runVersion,
    space: (state) => state.space,
    spaceBgColor: (state) => state.spaceBgColor,
    spaceUid: (state) => state.spaceUid,

    storeIsShowClusterStep: (state) => state.storeIsShowClusterStep,
    traceIndexId: (state) => state.traceIndexId,
    unionIndexItemList: (state) => state.unionIndexItemList,
    /** 联合查询索引集ID数组 */
    unionIndexList: (state) => state.unionIndexList,
    user: (state) => state.user,
    visibleFields: (state) => state.visibleFields,
  },
  // 模块
  modules: {
    collect,
    globals,
    retrieve,
  },
  // 公共 mutations
  mutations: {
    [SET_APP_STATE](state, data) {
      for (const [key, value] of Object.entries(data)) {
        state[key] = value;
      }
    },

    deleteApiError(state, apiName) {
      Vue.delete(state.apiErrorInfo, apiName);
    },

    // 初始化监控默认数据
    initMonitorState(state, payload) {
      Object.assign(state, payload);
    },
    resetIndexFieldInfo(state, payload) {
      const defValue = { ...IndexFieldInfo };
      state.indexFieldInfo = Object.assign(defValue, payload ?? {});
    },
    resetIndexSetOperatorConfig(state) {
      const {
        bcs_web_console: bcsWebConsole,
        bkmonitor,
        context_and_realtime: contextAndRealtime,
      } = state.indexSetFieldConfig;
      // 字段设置的参数传到实时日志和上下文
      let indexSetValue;
      if (!state.indexItem.isUnionIndex) {
        const item = state.indexItem.items[0];
        indexSetValue = {
          scenarioID: item?.scenario_id,
          sortFields: item?.sort_fields ?? [],
          targetFields: item?.target_fields ?? [],
        };
      } else {
        indexSetValue = {};
      }
      store.commit('updateIndexSetOperatorConfig', {
        bcsWebConsole,
        bkmonitor,
        contextAndRealtime,
        indexSetValue,
        toolMessage: {
          contextLog: contextAndRealtime.is_active
            ? window.mainComponent.$t('上下文')
            : contextAndRealtime?.extra?.reason,
          realTimeLog: contextAndRealtime.is_active
            ? window.mainComponent.$t('实时日志')
            : contextAndRealtime?.extra?.reason,
          webConsole: bcsWebConsole.is_active
            ? 'WebConsole'
            : bcsWebConsole?.extra?.reason,
        },
      });
    },
    resetIndexSetQueryResult(state, payload) {
      Object.assign(
        state.indexSetQueryResult,
        IndexSetQueryResult,
        payload ?? {}
      );
    },
    /**
     * 当切换索引集时，重置请求参数默认值
     * @param {*} state
     * @param {*} payload
     */
    resetIndexsetItemParams(state, payload) {
      const defaultValue = {
        ...getDefaultRetrieveParams(),
        isUnionIndex: false,
        selectIsUnionSearch: false,
      };
      ['ids', 'items', 'catchUnionBeginList'].forEach((key) => {
        if (Array.isArray(state.indexItem[key])) {
          state.indexItem[key].splice(
            0,
            state.indexItem[key].length,
            ...(payload?.[key] ?? []).filter(
              (v) => v !== null && v !== undefined
            )
          );
        }
      });

      state.indexItem.isUnionIndex = false;
      state.unionIndexList.splice(0, state.unionIndexList.length);
      state.indexItem.chart_params = deepClone(IndexItem.chart_params);

      if (payload?.addition?.length >= 0) {
        state.indexItem.addition.splice(
          0,
          state.indexItem.addition.length,
          ...payload?.addition.map((item) => {
            const instance = new ConditionOperator(item);
            return { ...item, ...instance.getRequestParam() };
          })
        );
      }

      const copyValue = Object.keys(payload ?? {}).reduce((result, key) => {
        if (
          !['ids', 'items', 'catchUnionBeginList', 'addition'].includes(key)
        ) {
          Object.assign(result, { [key]: payload[key] });
        }

        return result;
      }, {});
      Object.assign(state.indexItem, defaultValue, copyValue);
    },

    resetState(state) {
      Object.assign(state, deepClone(stateTpl));
    },

    /**
     * @desc: 用于更新可见field
     * 根据传入的 `payload` 参数更新当前可见的字段。`payload` 可以是一个字段名称的数组，
     * 或者是包含字段名称数组和版本信息的对象。
     *
     * @param {Array | Object} payload  - 可传入字段名称数组或包含字段数组以及版本信息的对象。
     *   - 当为数组时，表示字段名称列表。
     *   - 当为对象时，应包含以下属性：
     *     - {Array} displayFieldNames - 字段名称数组。
     *     - {string} version - 版本信息，包含 v2时，表示是新版本设计，目前包含了object字段层级展示的添加功能，后续如果需要区别于之前的逻辑处理，可以参照此逻辑处理(暂不生效)
     *
     */
    resetVisibleFields(state, payload) {
      const isVersion2Payload = payload?.version === 'v2';
      const catchDisplayFields =
        store.state.retrieve.catchFieldCustomConfig.displayFields;
      const displayFields = catchDisplayFields.length
        ? catchDisplayFields
        : null;
      // 请求字段时 判断当前索引集是否有更改过字段 若更改过字段则使用session缓存的字段显示
      const filterList =
        (isVersion2Payload
          ? payload.displayFieldNames
          : payload || displayFields) ?? state.indexFieldInfo.display_fields;
      const visibleFields =
        filterList
          .map((displayName) => {
            const field = state.indexFieldInfo.fields.find(
              (field) => field.field_name === displayName
            );
            if (field) return field;
            return {
              description: '',
              es_doc_values: true,
              field_alias: '',
              field_name: displayName,
              field_operator: [],
              field_type: 'object',
              filterVisible: true,
              is_analyzed: true,
              is_built_in: true,
              is_case_sensitive: false,
              is_display: false,
              is_editable: true,
              is_virtual_obj_node: true,
              origin_field: '',
              tag: '',
              tokenize_on_chars: '',
            };
          })
          .filter(Boolean) ?? [];
      store.commit('updateVisibleFields', visibleFields);
      store.commit('updateIsNotVisibleFieldsShow', !visibleFields.length);

      // if (state.indexItem.isUnionIndex) store.dispatch('showShowUnionSource', { keepLastTime: true });
    },

    setDemoUid(state, demoUid) {
      state.demoUid = demoUid;
    },

    /**
     * 设置初始化 loading 是否显示
     */
    setPageLoading(state, loading) {
      state.pageLoading = loading;
    },

    setSpaceBgColor(state, val) {
      state.spaceBgColor = val;
    },

    setUserGuideData(state, userGuideData) {
      state.userGuideData = userGuideData;
    },

    updataOperatorDictionary(state, payload) {
      state.operatorDictionary = {};
      (payload.fields ?? []).forEach((field) => {
        const { field_operator = [] } = field;
        field_operator.forEach((item) => {
          const { operator } = item;
          const key = getOperatorKey(operator);
          Object.assign(state.operatorDictionary, { [key]: item });
        });
      });
    },

    updateActiveManageNav(state, payload) {
      state.activeManageNav = payload;
    },

    updateActiveManageSubNav(state, payload) {
      state.activeManageSubNav = payload;
    },

    updateActiveTopMenu(state, payload) {
      state.activeTopMenu = payload;
    },

    updateAddition(state) {
      state.indexItem.addition.forEach((item) => {
        const instance = new ConditionOperator(item);
        Object.assign(item, instance.getRequestParam());
      });
    },
    updateApiError(state, { apiName, errorMessage }) {
      Vue.set(state.apiErrorInfo, apiName, errorMessage);
    },
    updateAsIframe(state, asIframe) {
      state.asIframe = asIframe;
    },
    updateAuthDialogData(state, payload) {
      state.authDialogData = payload;
    },
    updateChartParams(state, params) {
      Object.keys(params).forEach((key) => {
        if (Array.isArray(state.indexItem.chart_params[key])) {
          state.indexItem.chart_params[key].splice(
            0,
            state.indexItem.chart_params[key].length,
            ...(params[key] ?? [])
          );
        } else {
          set(state.indexItem.chart_params, key, params[key]);
        }
      });
    },
    updateChartSize(state) {
      state.chartSizeNum += 1;
    },
    updateClearSearchValueNum(state, payload) {
      state.clearSearchValueNum = payload;
    },
    updateClusterParams(state, payload) {
      state.clusterParams = payload;
    },
    // -- 代码调整 collectDetail: [id, 数据]
    updateCollectDetail(state, collectDetail) {
      const data = collectDetail[1];
      data.params.paths = data.params.paths.map((item) => ({ value: item }));
      state.collectDetail = data;
    },
    /**
     * 更新当前路由对应导航
     */
    updateCurrentMenu(state, current) {
      Vue.set(state, 'currentMenu', current);
    },
    updateCurrentMenuItem(state, item) {
      Vue.set(state, 'currentMenuItem', item);
    },
    updateExternalMenu(state, val) {
      state.externalMenu = val;
    },
    updateFavoriteList(state, payload) {
      state.favoriteList.length = 0;
      state.favoriteList = [];
      state.favoriteList.push(...(payload ?? []));
    },
    updateGlobalActiveLabel(state, val) {
      state.globalActiveLabel = val;
    },
    updateGlobalSettingList(state, val) {
      state.globalSettingList = val;
    },
    updateGlobalsData(state, globalsData) {
      state.globalsData = globalsData;
      Vue.set(state, 'globalsData', globalsData);
    },
    updateIframeQuery(state, iframeQuery) {
      Object.assign(state.iframeQuery, iframeQuery);
    },
    updateIndexFieldEggsItems(state, payload) {
      const { end_time, start_time } = state.indexItem;
      const lastQueryTimerange = `${start_time}_${end_time}`;
      Object.keys(payload ?? {}).forEach((key) => {
        set(state.indexFieldInfo.aggs_items, key, payload[key]);
      });
      state.indexFieldInfo.last_eggs_request_token = lastQueryTimerange;
    },
    updateIndexFieldInfo(state, payload) {
      const HIDDEN_FIELDS = new Set(builtInInitHiddenList);
      const processedData = payload ? { ...payload } : {};
      if (Array.isArray(processedData.fields)) {
        processedData.fields = [...processedData.fields].sort((a, b) => {
          // dtEventTimeStamp默认在第一个
          if (a.field_name === 'dtEventTimeStamp') {
            return -1;
          }
          if (b.field_name === 'dtEventTimeStamp') {
            return 1;
          }
          const aWeight = HIDDEN_FIELDS.has(a.field_name) ? 1 : 0;
          const bWeight = HIDDEN_FIELDS.has(b.field_name) ? 1 : 0;
          if (aWeight !== bWeight) return aWeight - bWeight;
          if (a.is_built_in !== b.is_built_in) {
            return a.is_built_in ? 1 : -1;
          }
          return 0;
        });
      }
      // Object.assign(state.indexFieldInfo, processedData);
      Object.keys(processedData ?? {}).forEach((key) => {
        set(state.indexFieldInfo, key, processedData[key]);
      });
    },
    updateIndexId(state, indexId) {
      state.indexId = indexId;
    },
    updateIndexItem(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        if (['ids', 'items', 'catchUnionBeginList'].includes(key)) {
          if (
            Array.isArray(state.indexItem[key]) &&
            Array.isArray(payload?.[key] ?? false)
          ) {
            state.indexItem[key].splice(
              0,
              state.indexItem[key].length,
              ...(payload?.[key] ?? []).filter(
                (v) => v !== '' && v !== null && v !== undefined
              )
            );
          } else {
            if (Object.prototype.hasOwnProperty.call(state.indexItem, key)) {
              set(state.indexItem, key, payload[key]);
            }
          }
        } else {
          if (Object.prototype.hasOwnProperty.call(state.indexItem, key)) {
            set(state.indexItem, key, payload[key]);
          }
        }
      });
    },
    updateIndexItemParams(state, payload) {
      if (payload?.addition?.length >= 0) {
        state.indexItem.addition.splice(
          0,
          state.indexItem.addition.length,
          ...payload?.addition.map((item) => {
            const instance = new ConditionOperator(item);
            return { ...item, ...instance.getRequestParam() };
          })
        );
      }

      const copyValue = Object.keys(payload ?? {}).reduce((result, key) => {
        if (!['addition'].includes(key)) {
          Object.assign(result, { [key]: payload[key] });
        }

        return result;
      }, {});

      Object.assign(state.indexItem, copyValue ?? {});
    },
    updateIndexSetCustomConfig(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        set(state.indexFieldInfo.custom_config, key, payload[key]);
      });
    },
    updateIndexSetFieldConfig(state, payload) {
      const defVal = { ...indexSetClusteringData };
      const { config } = payload ?? { config: [] };

      set(state.indexSetFieldConfig, 'clustering_config', defVal);
      (config ?? []).forEach((item) => {
        set(state.indexSetFieldConfig, item.name, item);
      });
    },
    updateIndexSetFieldConfigList() {
      if (payload.is_loading !== undefined) {
        state.indexSetFieldConfigList.is_loading = payload.is_loading;
      }

      if (payload.data) {
        state.indexSetFieldConfigList.data.length = 0;
        state.indexSetFieldConfigList.data.push(...(payload ?? []));
      }
    },
    updateIndexSetOperatorConfig(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        set(state.indexSetOperatorConfig, key, payload[key]);
      });
    },
    updateIndexSetQueryResult(state, payload) {
      Object.keys(payload ?? {}).forEach((key) => {
        if (
          Array.isArray(payload[key]) &&
          Array.isArray(state.indexSetQueryResult[key])
        ) {
          if (Object.isFrozen(state.indexSetQueryResult[key])) {
            state.indexSetQueryResult[key] = undefined;
            set(state.indexSetQueryResult, key, []);
          } else {
            state.indexSetQueryResult[key].length = 0;
            state.indexSetQueryResult[key] = [];
          }

          state.indexSetQueryResult[key].push(
            ...(payload[key] ?? []).filter((v) => v !== null && v !== undefined)
          );
        } else {
          set(state.indexSetQueryResult, key, payload[key]);
        }
      });
    },
    updateIsEnLanguage(state, val) {
      state.isEnLanguage = val;
    },
    updateIsFormatDate(state, payload) {
      state.isFormatDate = payload;
    },
    updateIsNotVisibleFieldsShow(state, val) {
      state.isNotVisibleFieldsShow = val;
    },
    /** 初始化表格宽度 为false的时候会按照初始化的情况来更新宽度 */
    updateIsSetDefaultTableColumn(state, payload) {
      // 如果浏览器记录过当前索引集表格拖动过 则不需要重新计算
      if (!state.isSetDefaultTableColumn) {
        const catchFieldsWidthObj =
          store.state.retrieve.catchFieldCustomConfig.fieldsWidth;
        const staticWidth = state.indexSetOperatorConfig?.bcsWebConsole
          ?.is_active
          ? 104
          : 84;
        setDefaultTableWidth(
          state.visibleFields,
          payload?.list ?? state.indexSetQueryResult.list,
          catchFieldsWidthObj,
          staticWidth + 60
        );
        // request_counter 用于触发查询结果表格的更新
        state.indexFieldInfo.request_counter++;
      }
      if (typeof payload === 'boolean') state.isSetDefaultTableColumn = payload;
    },
    updateIsShowGlobalDialog(state, val) {
      state.isShowGlobalDialog = val;
    },
    updateLocalSort(state, payload) {
      state.localSort = payload;
    },
    updateMaskingToggle(state, val) {
      state.maskingToggle = val;
    },
    updateMenuList(state, menuList) {
      state.menuList.splice(0, state.menuList.length, ...menuList);
    },
    updateMenuProject(state, menuProject) {
      state.menuProject.splice(0, state.menuProject.length, ...menuProject);
    },
    updateMySpaceList(state, spaceList) {
      state.mySpaceList = spaceList.map((item) => {
        const defaultTag = {
          id: item.space_type_id,
          name: item.space_type_name,
          type: item.space_type_id,
        };
        return {
          ...item,
          name: item.space_name.replace(/\[.*?\]/, ''),
          py_text: Vue.prototype.$bkToPinyin(item.space_name, true),
          tags:
            item.space_type_id === 'bkci' && item.space_code
              ? [
                  defaultTag,
                  {
                    id: 'bcs',
                    name: window.mainComponent.$t('容器项目'),
                    type: 'bcs',
                  },
                ]
              : [defaultTag],
        };
      });
    },
    updateNotTextTypeFields(state, payload) {
      state.notTextTypeFields.length = [];
      state.notTextTypeFields = [];

      state.notTextTypeFields.push(
        ...(payload.fields ?? [])
          .filter((field) => field.field_type !== 'text')
          .map((item) => item.field_name)
      );
    },
    updateNoticeAlert(state, val) {
      state.showAlert = val;
    },
    updateRouterLeaveTip(state, isShow) {
      state.showRouterLeaveTip = isShow;
    },

    /**
     * 更新当前运行环境
     * @param {Object} state store state
     * @param {String} runVersion 运行环境
     */
    updateRunVersion(state, runVersion) {
      state.runVersion = runVersion;
    },
    updateShowFieldsConfigPopoverNum(state, showFieldsConfigPopoverNum) {
      state.showFieldsConfigPopoverNum += showFieldsConfigPopoverNum;
    },
    updateSpace(state, spaceUid) {
      state.space =
        state.mySpaceList.find((item) => item.space_uid === spaceUid) || {};
      state.bkBizId = state.space?.bk_biz_id;
      state.spaceUid = state.space?.space_uid;
      state.isSetDefaultTableColumn = false;
      state.features.isAiAssistantActive = isAiAssistantActive([
        state.bkBizId,
        state.spaceUid,
      ]);
    },
    updateSqlQueryFieldList(state, payload) {
      const target = {};
      state.retrieveDropdownData = {};

      const recursiveIncreaseData = (dataItem, prefixFieldKey = '') => {
        dataItem &&
          Object.entries(dataItem).forEach(([field, value]) => {
            if (typeof value === 'object') {
              recursiveIncreaseData(value, `${prefixFieldKey + field}.`);
            } else {
              const fullFieldKey = prefixFieldKey
                ? prefixFieldKey + field
                : field;
              let fieldData = target[fullFieldKey];
              if (fieldData) fieldData.__totalCount += 1;
              if (value || value === 0) {
                if (!fieldData) {
                  Object.assign(target, {
                    [fullFieldKey]: Object.defineProperties(
                      {},
                      {
                        __fieldType: {
                          // 该字段下的值的数据类型，可能是数值、字符串、布尔值
                          value: typeof value,
                        },
                        __totalCount: {
                          // 总记录数量
                          value: 1,
                          writable: true,
                        },
                        __validCount: {
                          // 有效值数量
                          value: 0,
                          writable: true,
                        },
                      }
                    ),
                  });
                  fieldData = target[fullFieldKey];
                }
                fieldData.__validCount += 1;
                fieldData[value] += 1;
                if (
                  state.notTextTypeFields.includes(field) &&
                  !fieldData?.[value]
                ) {
                  // 非 text 类型字段统计可选值，text 则由用户手动输入
                  fieldData[value] = 1;
                }
              }
            }
          });
      };

      // 更新下拉字段可选值信息
      const computeRetrieveDropdownData = (listData) => {
        listData.forEach((dataItem) => {
          recursiveIncreaseData(dataItem);
        });
      };

      computeRetrieveDropdownData(payload ?? []);

      Object.keys(target).forEach((key) => {
        Vue.set(state.retrieveDropdownData, key, target[key]);
      });
    },
    updateStorage(state, payload) {
      Object.keys(payload).forEach((key) => {
        state.storage[key] = payload[key];
      });

      localStorage.setItem(
        BkLogGlobalStorageKey,
        JSON.stringify(state.storage)
      );
    },
    updateStoreIsShowClusterStep(state, val) {
      state.storeIsShowClusterStep = val;
    },
    updateTableLineIsWrap(state, payload) {
      state.storage.tableLineIsWrap = payload;
    },
    updateTopMenu(state, topMenu) {
      state.topMenu.splice(0, state.topMenu.length, ...topMenu);
    },
    updateTraceIndexId(state, indexId) {
      state.traceIndexId = indexId;
    },
    updateUnionIndexItemList(state, unionIndexItemList) {
      state.unionIndexItemList = unionIndexItemList;
    },
    updateUnionIndexList(state, unionIndexList) {
      const updateIndexItem = unionIndexList.updateIndexItem ?? true;
      const list = Array.isArray(unionIndexList)
        ? unionIndexList
        : unionIndexList.list;

      state.unionIndexList.splice(
        0,
        state.unionIndexList.length,
        ...list.filter((v) => v !== null && v !== undefined)
      );

      if (updateIndexItem) {
        state.indexItem.ids.splice(
          0,
          state.indexItem.ids.length,
          ...list.filter((v) => v !== null && v !== undefined)
        );
      }

      const unionIndexItemList = state.retrieve.indexSetList.filter((item) =>
        list.includes(item.index_set_id)
      );
      state.unionIndexItemList.splice(
        0,
        state.unionIndexItemList.length,
        ...unionIndexItemList
      );
    },
    /**
     * 更新当前用户 user
     *
     * @param {Object} state store state
     * @param {Object} user user 对象
     */
    updateUser(state, user) {
      state.user = Object.assign({}, user);
    },
    updateUserMeta(state, payload) {
      state.userMeta = payload;
    },
    updateVisibleFieldMinWidth(state, tableList, fieldList) {
      const staticWidth = state.indexSetOperatorConfig?.bcsWebConsole?.is_active
        ? 84
        : 58 + 50;
      setDefaultTableWidth(
        fieldList ?? state.visibleFields,
        tableList,
        null,
        staticWidth
      );
    },
    updateVisibleFields(state, val) {
      state.visibleFields.splice(0, state.visibleFields.length, ...(val ?? []));
      state.indexFieldInfo.request_counter++;
    },
  },
  // 公共 store
  state: deepClone(stateTpl),
});

/**
 * hack vuex dispatch, add third parameter `config` to the dispatch method
 *
 * 需要对单独的请求做配置的话，无论是 get 还是 post，store.dispatch 都需要三个参数，例如：
 * store.dispatch('example/btn1', {btn: 'btn1'}, {fromCache: true})
 * 其中第二个参数指的是请求本身的参数，第三个参数指的是请求的配置，如果请求本身没有参数，那么
 * 第二个参数也必须占位，store.dispatch('example/btn1', {}, {fromCache: true})
 * 在 store 中需要如下写法：
 * btn1 ({ commit, state, dispatch }, params, config) {
 *     return http.get(`/app/index?invoke=btn1`, params, config)
 * }
 *
 * @param {Object|string} _type vuex type
 * @param {Object} _payload vuex payload
 * @param {Object} config config 参数，主要指 http 的参数，详见 src/api/index initConfig
 *
 * @return {Promise} 执行请求的 promise
 */
store.dispatch = function (_type, _payload, config = {}) {
  const { payload, type } = unifyObjectStyle(_type, _payload);

  const action = { config, payload, type };
  const entry = store._actions[type];
  if (!entry) {
    if (process.env.NODE_ENV !== 'production') {
      console.error(`[vuex] unknown action type: ${type}`);
    }
    return;
  }

  store._actionSubscribers
    .slice()
    .filter((sub) => sub.before)
    .forEach((sub) => sub.before(action, store.state));
  // store._actionSubscribers.forEach(sub => sub(action, store.state));

  return entry.length > 1
    ? Promise.all(entry.map((handler) => handler(payload, config)))
    : entry[0](payload, config);
};

export default store;

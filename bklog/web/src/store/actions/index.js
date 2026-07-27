/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 */
import { requestIndexSetFieldInfoAction, requestIndexSetQueryAction } from './retrieve-search-actions.js';
import {
  checkAllowedAction,
  checkAndGetDataAction,
  getApplyDataAction,
  getGlobalsDataAction,
  getMenuListAction,
  requestFavoriteListAction,
  requestMenuListAction,
  userInfoAction,
} from './app-actions.js';
import {
  handleTrendDataZoomAction,
  requestIndexSetValueListAction,
  requestSearchTotalAction,
  userFieldConfigChangeAction,
} from './retrieve-misc-actions.js';
import { setQueryConditionAction } from './query-condition-actions.js';

const actions = {

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
    userInfo: userInfoAction,

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
    getMenuList: getMenuListAction,
    requestMenuList: requestMenuListAction,
    getGlobalsData: getGlobalsDataAction,
    // 判断有无权限
    checkAllowed: checkAllowedAction,
    // 已知无权限，需要获取信息
    getApplyData: getApplyDataAction,
    // 判断有无权限，无权限获取相关信息
    checkAndGetData: checkAndGetDataAction,

    /** 请求字段config信息 */
    requestIndexSetFieldInfo: requestIndexSetFieldInfoAction,

    /** 执行查询 */
    requestIndexSetQuery: requestIndexSetQueryAction,

    /**
     * 索引集选择改变事件
     * 更新索引集相关缓存 & 发起当前索引集所需字段信息请求
     * @param {*} param0
     * @param {*} payload
     */
    requestIndexSetItemChanged({ commit, dispatch }, payload) {
      commit('updateIndexItem', payload);
      commit('resetIndexSetQueryResult', { search_count: 0, is_loading: true });

      if (!payload.isUnionIndex) {
        commit('updateState', { indexId: payload.ids[0] });
      }

      return dispatch('requestIndexSetFieldInfo');
    },

    /**
     * 请求提示词列表
     * @param {*} param0
     * @param {*} payload: {
     * force: boolean;
     * fields: [];
     * addition: [];
     * size: number;
     * commit: boolean;
     * cancelToken: boolean
     * }
     * @returns
     */
    requestIndexSetValueList: requestIndexSetValueListAction,
    requestFavoriteList: requestFavoriteListAction,
    setQueryCondition: setQueryConditionAction,

    changeShowUnionSource({ commit, state }) {
      commit('updateIndexSetOperatorConfig', {
        isShowSourceField: !state.indexSetOperatorConfig.isShowSourceField,
      });
    },

    requestSearchTotal: requestSearchTotalAction,
    handleTrendDataZoom: handleTrendDataZoomAction,
    /**
     * 更新 Vuex 状态中的用户字段配置。
     *
     * @param {Object} userConfig 要更新的用户配置对象。
     * @param {boolean} userConfig.isUpdate 标志是否仅为更新操作。如果为 `true`，表示仅为更新操作，在成功响应后不会提交新的配置到 Vuex。
     * @return {Promise} 一个 Promise，解析为 HTTP 请求的响应。
     */
    userFieldConfigChange: userFieldConfigChangeAction,
};

export default actions;

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

const getIndexSetList = {
  url: '/search/index_set/',
  method: 'get',
};

const getLogTableHead = {
  url: '/search/index_set/:index_set_id/fields/',
  method: 'get',
};
const getLogTableList = {
  url: '/search/index_set/:index_set_id/search/',
  method: 'post',
};
const getLogChartList = {
  url: '/search/index_set/:index_set_id/aggs/date_histogram/',
  method: 'post',
};

const getFilterBiz = {
  url: '/bizs/',
  method: 'get',
};
// IP快选 选择业务接口调整
const getIpBusinessList = {
  url: '/search/index_set/:index_set_id/bizs/',
  method: 'get',
};
const getIpTree = {
  url: '/bizs/:bk_biz_id/topo/',
  method: 'get',
};
const getOperators = {
  url: '/search/index_set/operators/',
  method: 'get',
};
const getCloudAreaList = {
  url: '/search/index_set/$index_set_id/:tailf/',
  method: 'post',
};

const downloadLog = {
  url: '/search/index_set/:index_set_id/export/',
  method: 'post',
};
const quickDownload = {
  url: '/search/index_set/:index_set_id/quick_export/',
  method: 'post',
};
const unionDownloadLog = {
  url: '/search/index_set/union_search/export/',
  method: 'post',
};
const exportAsync = {
  url: '/search/index_set/:index_set_id/async_export/',
  method: 'post',
};
const unionExportAsync = {
  url: '/search/index_set/union_async_export/',
  method: 'post',
};
const getRealTimeLog = {
  url: '/search/index_set/:index_set_id/tail_f/',
  method: 'post',
};
const getContentLog = {
  url: '/search/index_set/:index_set_id/context/',
  method: 'post',
};
const saveTitleInfo = {
  url: '/search/index_set/:index_set_id/config/',
  method: 'post',
};
const getRetrieveFavorite = {
  url: '/search/favorite/',
  method: 'get',
};
const postRetrieveFavorite = {
  url: '/search/favorite/',
  method: 'post',
};
const deleteRetrieveFavorite = {
  url: '/search/favorite/:id/',
  method: 'delete',
};
const postFieldsConfig = {
  url: '/search/index_set/config/',
  method: 'post',
};
const getWebConsoleUrl = {
  url: '/search/index_set/:index_set_id/bcs_web_console/',
  method: 'get',
};
const getSearchHistory = {
  url: '/search/index_set/:index_set_id/history/',
  method: 'get',
};
const getExportHistoryList = {
  url: '/search/index_set/:index_set_id/export_history/?bk_biz_id=:bk_biz_id&page=:page&pagesize=:pagesize&show_all=:show_all',
  method: 'get',
};
const getFieldsListConfig = {
  url: '/search/index_set/list_config/',
  method: 'post',
};
const createFieldsConfig = {
  url: '/search/index_set/create_config/',
  method: 'post',
};
const updateFieldsConfig = {
  url: '/search/index_set/update_config/',
  method: 'post',
};
const deleteFieldsConfig = {
  url: '/search/index_set/delete_config/',
  method: 'post',
};
const getFieldsConfigByContextLog = {
  url: '/search/index_set/:index_set_id/retrieve_config/?config_id=:config_id',
  method: 'get',
};
const getAggsTerms = {
  url: '/search/index_set/:index_set_id/aggs/terms/',
  method: 'post',
};
/** 获取字段top列表信息 */
const fieldFetchTopList = {
  url: '/field/index_set/fetch_topk_list/',
  method: 'post',
};
/** 获取图表分析信息 */
const fieldStatisticsInfo = {
  url: '/field/index_set/statistics/info/',
  method: 'post',
};
/** 获取趋势图总数的信息 */
const fieldStatisticsTotal = {
  url: '/field/index_set/statistics/total/',
  method: 'post',
};
/** 获取图表分析图表 */
const fieldStatisticsGraph = {
  url: '/field/index_set/statistics/graph/',
  method: 'post',
};
/** 获取字段去重数量 */
const fieldDistinctCount = {
  url: '/field/index_set/fetch_distinct_count_list/',
  method: 'post',
};
/** 聚类告警列表 */
const userGroup = {
  url: '/clustering_monitor/search_user_groups/',
  method: 'post',
};
/** 创建/更新数量突增告警 */
const normalStrategy = {
  url: '/clustering_monitor/:index_set_id/normal_strategy/',
  method: 'post',
};
/** 创建/更新新类告警 */
const newClsStrategy = {
  url: '/clustering_monitor/:index_set_id/new_cls_strategy/',
  method: 'post',
};
/** 获取策略详情 */
const getClusteringInfo = {
  url: '/clustering_monitor/:index_set_id/get_strategy/?strategy_type=:strategy_type',
  method: 'get',
};
/** 删除策略详情 */
const deleteClusteringInfo = {
  url: '/clustering_monitor/:index_set_id/',
  method: 'delete',
};
/** 新建聚类接入*/
const createClusteringConfig = {
  url: '/clustering_config/:index_set_id/access/create/',
  method: 'post',
};
/** 更新聚类接入*/
const updateClusteringConfig = {
  url: '/clustering_config/:index_set_id/access/update/',
  method: 'post',
};
/** 查询聚类接入状态*/
const getClusteringConfigStatus = {
  url: '/clustering_config/:index_set_id/access/status/',
  method: 'get',
};
/** 查询聚类接入状态*/
const updateUserFiledTableConfig = {
  url: '/search/index_set/user_custom_config/',
  method: 'post',
};

/** 输出UI查询转为querystring语法*/
const generateQueryString = {
  url: '/search/index_set/generate_querystring/',
  method: 'post',
};

const setIndexSetCustomConfig = {
  url: '/search/index_set/custom_config/',
  method: 'post',
};
/** 自定义上报地址改成动态展示*/
const getProxyHost = {
  url: '/databus/collectors/proxy_host_info/',
  method: 'get',
};

/**
 * 请求grep结果
 */
const requestGrepResult = {
  url: '/search/index_set/$index_set_id/grep_query/',
  method: 'post',
};

const createOrUpdateToken = {
  url: '/share/create_or_update_token/',
  method: 'post',
};

const getShareParams = {
  url: 'share/get_share_params/',
  method: 'get',
};

/**
 * @api {GET} /index_set/query_by_dataid/?bk_data_id=xxx 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiDescription 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiName query_by_dataid
 * @apiSuccessExample {json} 成功返回:
 */
const getIndexSetDataByDataId = {
  url: '/index_set/query_by_dataid/',
  method: 'get',
};
/**
 * 修改别名
 */
const updateFieldsAlias = {
  url: '/search/index_set/:index_set_id/alias_settings/',
  method: 'post',
};
export {
  getIndexSetList,
  getLogTableHead,
  getLogTableList,
  getLogChartList,
  getFilterBiz,
  getIpTree,
  getOperators,
  getCloudAreaList,
  downloadLog,
  unionDownloadLog,
  exportAsync,
  quickDownload,
  getRealTimeLog,
  getContentLog,
  saveTitleInfo,
  getIpBusinessList,
  getRetrieveFavorite,
  postRetrieveFavorite,
  deleteRetrieveFavorite,
  postFieldsConfig,
  getWebConsoleUrl,
  getSearchHistory,
  getExportHistoryList,
  getFieldsListConfig,
  createFieldsConfig,
  updateFieldsConfig,
  deleteFieldsConfig,
  getFieldsConfigByContextLog,
  getAggsTerms,
  fieldFetchTopList,
  fieldStatisticsInfo,
  fieldStatisticsTotal,
  fieldStatisticsGraph,
  fieldDistinctCount,
  userGroup,
  normalStrategy,
  newClsStrategy,
  getClusteringInfo,
  deleteClusteringInfo,
  createClusteringConfig,
  updateClusteringConfig,
  getClusteringConfigStatus,
  updateUserFiledTableConfig,
  generateQueryString,
  setIndexSetCustomConfig,
  getProxyHost,
  requestGrepResult,
  unionExportAsync,
  createOrUpdateToken,
  getShareParams,
  getIndexSetDataByDataId,
  updateFieldsAlias,
};

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
  method: 'get',
  url: '/search/index_set/',
};

const getLogTableHead = {
  method: 'get',
  url: '/search/index_set/:index_set_id/fields/',
};
const getLogTableList = {
  method: 'post',
  url: '/search/index_set/:index_set_id/search/',
};
const getLogChartList = {
  method: 'post',
  url: '/search/index_set/:index_set_id/aggs/date_histogram/',
};

const getFilterBiz = {
  method: 'get',
  url: '/bizs/',
};
// IP快选 选择业务接口调整
const getIpBusinessList = {
  method: 'get',
  url: '/search/index_set/:index_set_id/bizs/',
};
const getIpTree = {
  method: 'get',
  url: '/bizs/:bk_biz_id/topo/',
};
const getOperators = {
  method: 'get',
  url: '/search/index_set/operators/',
};
const getCloudAreaList = {
  method: 'post',
  url: '/search/index_set/$index_set_id/:tailf/',
};

const downloadLog = {
  method: 'post',
  url: '/search/index_set/:index_set_id/export/',
};
const quickDownload = {
  method: 'post',
  url: '/search/index_set/:index_set_id/quick_export/',
};
const unionDownloadLog = {
  method: 'post',
  url: '/search/index_set/union_search/export/',
};
const exportAsync = {
  method: 'post',
  url: '/search/index_set/:index_set_id/async_export/',
};
const unionExportAsync = {
  method: 'post',
  url: '/search/index_set/union_async_export/',
};
const getRealTimeLog = {
  method: 'post',
  url: '/search/index_set/:index_set_id/tail_f/',
};
const getContentLog = {
  method: 'post',
  url: '/search/index_set/:index_set_id/context/',
};
const saveTitleInfo = {
  method: 'post',
  url: '/search/index_set/:index_set_id/config/',
};
const getRetrieveFavorite = {
  method: 'get',
  url: '/search/favorite/',
};
const postRetrieveFavorite = {
  method: 'post',
  url: '/search/favorite/',
};
const deleteRetrieveFavorite = {
  method: 'delete',
  url: '/search/favorite/:id/',
};
const postFieldsConfig = {
  method: 'post',
  url: '/search/index_set/config/',
};
const getWebConsoleUrl = {
  method: 'get',
  url: '/search/index_set/:index_set_id/bcs_web_console/',
};
const getSearchHistory = {
  method: 'get',
  url: '/search/index_set/:index_set_id/history/',
};
const getExportHistoryList = {
  method: 'get',
  url: '/search/index_set/:index_set_id/export_history/?bk_biz_id=:bk_biz_id&page=:page&pagesize=:pagesize&show_all=:show_all',
};
const getFieldsListConfig = {
  method: 'post',
  url: '/search/index_set/list_config/',
};
const createFieldsConfig = {
  method: 'post',
  url: '/search/index_set/create_config/',
};
const updateFieldsConfig = {
  method: 'post',
  url: '/search/index_set/update_config/',
};
const deleteFieldsConfig = {
  method: 'post',
  url: '/search/index_set/delete_config/',
};
const getFieldsConfigByContextLog = {
  method: 'get',
  url: '/search/index_set/:index_set_id/retrieve_config/?config_id=:config_id',
};
const getAggsTerms = {
  method: 'post',
  url: '/search/index_set/:index_set_id/aggs/terms/',
};
/** 获取字段top列表信息 */
const fieldFetchTopList = {
  method: 'post',
  url: '/field/index_set/fetch_topk_list/',
};
/** 获取图表分析信息 */
const fieldStatisticsInfo = {
  method: 'post',
  url: '/field/index_set/statistics/info/',
};
/** 获取趋势图总数的信息 */
const fieldStatisticsTotal = {
  method: 'post',
  url: '/field/index_set/statistics/total/',
};
/** 获取图表分析图表 */
const fieldStatisticsGraph = {
  method: 'post',
  url: '/field/index_set/statistics/graph/',
};
/** 获取字段去重数量 */
const fieldDistinctCount = {
  method: 'post',
  url: '/field/index_set/fetch_distinct_count_list/',
};
/** 聚类告警列表 */
const userGroup = {
  method: 'post',
  url: '/clustering_monitor/search_user_groups/',
};
/** 创建/更新数量突增告警 */
const normalStrategy = {
  method: 'post',
  url: '/clustering_monitor/:index_set_id/normal_strategy/',
};
/** 创建/更新新类告警 */
const newClsStrategy = {
  method: 'post',
  url: '/clustering_monitor/:index_set_id/new_cls_strategy/',
};
/** 获取策略详情 */
const getClusteringInfo = {
  method: 'get',
  url: '/clustering_monitor/:index_set_id/get_strategy/?strategy_type=:strategy_type',
};
/** 删除策略详情 */
const deleteClusteringInfo = {
  method: 'delete',
  url: '/clustering_monitor/:index_set_id/',
};
/** 新建聚类接入*/
const createClusteringConfig = {
  method: 'post',
  url: '/clustering_config/:index_set_id/access/create/',
};
/** 更新聚类接入*/
const updateClusteringConfig = {
  method: 'post',
  url: '/clustering_config/:index_set_id/access/update/',
};
/** 查询聚类接入状态*/
const getClusteringConfigStatus = {
  method: 'get',
  url: '/clustering_config/:index_set_id/access/status/',
};
/** 查询聚类接入状态*/
const updateUserFiledTableConfig = {
  method: 'post',
  url: '/search/index_set/user_custom_config/',
};

/** 输出UI查询转为querystring语法*/
const generateQueryString = {
  method: 'post',
  url: '/search/index_set/generate_querystring/',
};

const setIndexSetCustomConfig = {
  method: 'post',
  url: '/search/index_set/custom_config/',
};
/** 自定义上报地址改成动态展示*/
const getProxyHost = {
  method: 'get',
  url: '/databus/collectors/proxy_host_info/',
};

/**
 * 请求grep结果
 */
const requestGrepResult = {
  method: 'post',
  url: '/search/index_set/$index_set_id/grep_query/',
};

const createOrUpdateToken = {
  method: 'post',
  url: '/share/create_or_update_token/',
};

const getShareParams = {
  method: 'get',
  url: 'share/get_share_params/',
};

/**
 * @api {GET} /index_set/query_by_dataid/?bk_data_id=xxx 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiDescription 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiName query_by_dataid
 * @apiSuccessExample {json} 成功返回:
 */
const getIndexSetDataByDataId = {
  method: 'get',
  url: '/index_set/query_by_dataid/',
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
};

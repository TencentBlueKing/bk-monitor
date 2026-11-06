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

import { defineEndpoint } from '@/platform/services/runtime/service-client';

export type IndexSetDataList = {
  space_uid: string;
  index_set_id: number;
  index_set_name: string;
  collector_config_id: number | null;
  scenario_id: string;
  storage_cluster_id: number;
  category_id: string;
  created_at: string;
  time_field: string;
  time_field_type: string;
  time_field_unit: string;
  target_fields: any[];
  sort_fields: any[];
  support_doris: boolean;
  doris_table_id: number | null;
  indices: {
    bk_biz_id: number;
    index_set_id: number;
    result_table_id: string;
    result_table_name: string | null;
    time_field: string | null;
  }[];
  scenario_name: string;
  bk_biz_id: number;
  tags: {
    name: string;
    color: string;
    tag_id: number;
  }[];
  is_favorite: boolean;
  no_data_check_time: string;
  collector_scenario_id: number | null;
  permission: {
    search_log_v2: boolean;
  };
}[];
const getIndexSetList = defineEndpoint({
  url: '/search/index_set/',
  method: 'get',
});

const getLogTableHead = defineEndpoint({
  url: '/search/index_set/:index_set_id/fields/',
  method: 'get',
});
export interface LogSearchResult {
  total: number;
  list: {
    __data_label: string;
    __result_table: string;
    _time: string; // 时间戳字符串
    bk_host_id: number;
    cloudId: number;
    dtEventTimeStamp: string; // 时间戳字符串
    gseIndex: number;
    iterationIndex: number;
    log: string;
    path: string;
    serverIp: string;
    time: string; // 时间戳字符串
    __index_set_id__: number;
    index: string;
    __id__: string;
  }[];
  done: boolean;
  trace_id: string;
  result_table_options: {
    [key: string]: {
      search_after: number[];
    };
  };
  aggs: any;
  aggregations: any;
  origin_log_list: {
    __data_label: string;
    __result_table: string;
    _time: string;
    bk_host_id: number;
    cloudId: number;
    dtEventTimeStamp: string;
    gseIndex: number;
    iterationIndex: number;
    log: string;
    path: string;
    serverIp: string;
    time: string;
    __index_set_id__: number;
    index: string;
    __id__: string;
  }[];
  took: number;
  fields: {
    [key: string]: {
      max_length: number;
    };
  };
  raw_took: number;
}

const getLogTableList = defineEndpoint({
  url: '/search/index_set/:index_set_id/search/',
  method: 'post',
});

export interface Histogram {
  aggs: {
    group_by_histogram: {
      buckets: {
        key_as_string: string; // 格式化的时间字符串，如 "2025-08-03 08:00:00"
        key: number; // 时间戳（毫秒）
        doc_count: number; // 文档计数
      }[];
    };
  };
}

const getLogChartList = defineEndpoint({
  url: '/search/index_set/:index_set_id/aggs/date_histogram/',
  method: 'post',
});

const getFilterBiz = defineEndpoint({
  url: '/bizs/',
  method: 'get',
});
// IP快选 选择业务接口调整
const getIpBusinessList = defineEndpoint({
  url: '/search/index_set/:index_set_id/bizs/',
  method: 'get',
});
const getIpTree = defineEndpoint({
  url: '/bizs/:bk_biz_id/topo/',
  method: 'get',
});
const getOperators = defineEndpoint({
  url: '/search/index_set/operators/',
  method: 'get',
});
const getCloudAreaList = defineEndpoint({
  url: '/search/index_set/$index_set_id/:tailf/',
  method: 'post',
});

const downloadLog = defineEndpoint({
  url: '/search/index_set/:index_set_id/export/',
  method: 'post',
});
const quickDownload = defineEndpoint({
  url: '/search/index_set/:index_set_id/quick_export/',
  method: 'post',
});
const unionDownloadLog = defineEndpoint({
  url: '/search/index_set/union_search/export/',
  method: 'post',
});
const exportAsync = defineEndpoint({
  url: '/search/index_set/:index_set_id/async_export/',
  method: 'post',
});
const unionExportAsync = defineEndpoint({
  url: '/search/index_set/union_async_export/',
  method: 'post',
});
const getExportDownloadLink = defineEndpoint({
  url: '/search/export_jobs/:job_id/download_link/',
  method: 'get',
});
const getRealTimeLog = defineEndpoint({
  url: '/search/index_set/:index_set_id/tail_f/',
  method: 'post',
});
const getContentLog = defineEndpoint({
  url: '/search/index_set/:index_set_id/context/',
  method: 'post',
});
const saveTitleInfo = defineEndpoint({
  url: '/search/index_set/:index_set_id/config/',
  method: 'post',
});
const getRetrieveFavorite = defineEndpoint({
  url: '/search/favorite/',
  method: 'get',
});
const postRetrieveFavorite = defineEndpoint({
  url: '/search/favorite/',
  method: 'post',
});
const deleteRetrieveFavorite = defineEndpoint({
  url: '/search/favorite/:id/',
  method: 'delete',
});
const postFieldsConfig = defineEndpoint({
  url: '/search/index_set/config/',
  method: 'post',
});
const getWebConsoleUrl = defineEndpoint({
  url: '/search/index_set/:index_set_id/bcs_web_console/',
  method: 'get',
});
const getSearchHistory = defineEndpoint({
  url: '/search/index_set/:index_set_id/history/',
  method: 'get',
});
const getExportHistoryList = defineEndpoint({
  url: '/search/index_set/:index_set_id/export_history/?bk_biz_id=:bk_biz_id&page=:page&pagesize=:pagesize&show_all=:show_all&start_time=:start_time&end_time=:end_time',
  method: 'get',
});
const getFieldsListConfig = defineEndpoint({
  url: '/search/index_set/list_config/',
  method: 'post',
});
const createFieldsConfig = defineEndpoint({
  url: '/search/index_set/create_config/',
  method: 'post',
});
const updateFieldsConfig = defineEndpoint({
  url: '/search/index_set/update_config/',
  method: 'post',
});
const deleteFieldsConfig = defineEndpoint({
  url: '/search/index_set/delete_config/',
  method: 'post',
});
const getFieldsConfigByContextLog = defineEndpoint({
  url: '/search/index_set/:index_set_id/retrieve_config/?config_id=:config_id',
  method: 'get',
});
const getAggsTerms = defineEndpoint({
  url: '/search/index_set/:index_set_id/aggs/terms/',
  method: 'post',
});
/** 获取字段top列表信息 */
const fieldFetchTopList = defineEndpoint({
  url: '/field/index_set/fetch_topk_list/',
  method: 'post',
});
/** 获取图表分析信息 */
const fieldStatisticsInfo = defineEndpoint({
  url: '/field/index_set/statistics/info/',
  method: 'post',
});
/** 获取趋势图总数的信息 */
const fieldStatisticsTotal = defineEndpoint({
  url: '/field/index_set/statistics/total/',
  method: 'post',
});
/** 获取图表分析图表 */
const fieldStatisticsGraph = defineEndpoint({
  url: '/field/index_set/statistics/graph/',
  method: 'post',
});
/** 获取字段去重数量 */
const fieldDistinctCount = defineEndpoint({
  url: '/field/index_set/fetch_distinct_count_list/',
  method: 'post',
});
export type UserGroupList = {
  id: number;
  name: string;
  bk_biz_id: number;
  need_duty: boolean;
  channels: string[];
  desc: string;
  timezone: string;
  update_user: string;
  update_time: string;
  create_user: string;
  create_time: string;
  duty_rules: any[]; // 无法确定具体结构，使用any[]
  mention_list: {
    id: string;
    type: string;
  }[];
  mention_type: number;
  app: string;
  users: {
    id: string;
    display_name: string;
    type: string;
  }[];
  strategy_count: number;
  rules_count: number;
  delete_allowed: boolean;
  edit_allowed: boolean;
  config_source: string;
}[];

/** 聚类告警列表 */
const userGroup = defineEndpoint({
  url: '/clustering_monitor/search_user_groups/',
  method: 'post',
});
/** 创建/更新数量突增告警 */
const normalStrategy = defineEndpoint({
  url: '/clustering_monitor/:index_set_id/normal_strategy/',
  method: 'post',
});
/** 创建/更新新类告警 */
const newClsStrategy = defineEndpoint({
  url: '/clustering_monitor/:index_set_id/new_cls_strategy/',
  method: 'post',
});
export interface ClusteringInfo {
  strategy_id: number;
  level: number;
  user_groups: number[];
  label_name: string[];
  interval: number;
  threshold: number;
}
/** 获取策略详情 */
const getClusteringInfo = defineEndpoint({
  url: '/clustering_monitor/:index_set_id/get_strategy/?strategy_type=:strategy_type',
  method: 'get',
});
/** 删除策略详情 */
const deleteClusteringInfo = defineEndpoint({
  url: '/clustering_monitor/:index_set_id/',
  method: 'delete',
});
/** 新建聚类接入*/
const createClusteringConfig = defineEndpoint({
  url: '/clustering_config/:index_set_id/access/create/',
  method: 'post',
});
/** 更新聚类接入*/
const updateClusteringConfig = defineEndpoint({
  url: '/clustering_config/:index_set_id/access/update/',
  method: 'post',
});
export interface ClusteringConfigStatus {
  access_finished: boolean;
  flow_create: {
    status: string;
    message: string;
  };
  flow_run: {
    status: string;
    message: string;
  };
  data_check: {
    status: string;
    message: string;
  };
}
/** 查询聚类接入状态*/
const getClusteringConfigStatus = defineEndpoint({
  url: '/clustering_config/:index_set_id/access/status/',
  method: 'get',
});
/** 查询聚类接入状态*/
const updateUserFiledTableConfig = defineEndpoint({
  url: '/search/index_set/user_custom_config/',
  method: 'post',
});

/** 输出UI查询转为querystring语法*/
const generateQueryString = defineEndpoint({
  url: '/search/index_set/generate_querystring/',
  method: 'post',
});

const setIndexSetCustomConfig = defineEndpoint({
  url: '/search/index_set/custom_config/',
  method: 'post',
});
/** 自定义上报地址改成动态展示*/
const getProxyHost = defineEndpoint({
  url: '/databus/collectors/proxy_host_info/',
  method: 'get',
});

/**
 * 请求grep结果
 */
const requestGrepResult = defineEndpoint({
  url: '/search/index_set/$index_set_id/grep_query/',
  method: 'post',
});

const createOrUpdateToken = defineEndpoint({
  url: '/share/create_or_update_token/',
  method: 'post',
});

const getShareParams = defineEndpoint({
  url: 'share/get_share_params/',
  method: 'get',
});

/**
 * 请求grep检索总数
 */
const getGrepResultTotal = defineEndpoint({
  url: '/search/index_set/:index_set_id/grep_query/total/',
  method: 'post',
});

/**
 * @api {GET} /index_set/query_by_dataid/?bk_data_id=xxx 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiDescription 根据 bk_data_id 获取采集项和索引集信息的接口
 * @apiName query_by_dataid
 * @apiSuccessExample {json} 成功返回:
 */
const getIndexSetDataByDataId = defineEndpoint({
  url: '/index_set/query_by_dataid/',
  method: 'get',
});
/**
 * 修改别名
 */
const updateFieldsAlias = defineEndpoint({
  url: '/search/index_set/:index_set_id/alias_settings/',
  method: 'post',
});

/** 获取场景化检索配置列表 */
const getSceneConfigs = defineEndpoint({
  url: '/search/scene/scenes/',
  method: 'get',
});

/** 场景化检索 - 维度值预览 */
const getSceneDimensionValues = defineEndpoint({
  url: '/search/scene/dimension_values/',
  method: 'post',
});

/** 场景化检索 - 字段列表 */
const getSceneFields = defineEndpoint({
  url: '/search/scene/fields/',
  method: 'post',
});

/** 场景化检索 - 趋势图 */
const getSceneDateHistogram = defineEndpoint({
  url: '/search/scene/aggs/date_histogram/',
  method: 'post',
});

/** 场景化检索 - 多字段 terms 聚合（选项卡） */
const getSceneAggsTerms = defineEndpoint({
  url: '/search/scene/aggs/terms/',
  method: 'post',
});

/** 场景化检索 - 字段 TopK 计数 */
const getSceneFieldFetchTopList = defineEndpoint({
  url: '/search/scene/field/fetch_topk_list/',
  method: 'post',
});

/** 场景化检索 - 字段值列表（CSV 下载） */
const getSceneFieldFetchValueList = defineEndpoint({
  url: '/search/scene/field/fetch_value_list/',
  method: 'post',
});

/** 场景化检索 - 字段统计信息 */
const getSceneFieldStatisticsInfo = defineEndpoint({
  url: '/search/scene/field/statistics/info/',
  method: 'post',
});

/** 场景化检索 - 字段统计总条数 */
const getSceneFieldStatisticsTotal = defineEndpoint({
  url: '/search/scene/field/statistics/total/',
  method: 'post',
});

/** 场景化检索 - 字段统计图表 */
const getSceneFieldStatisticsGraph = defineEndpoint({
  url: '/search/scene/field/statistics/graph/',
  method: 'post',
});

/** 场景化检索 - 检索历史 */
const getSceneSearchHistory = defineEndpoint({
  url: '/search/scene/history/',
  method: 'post',
});

/** 场景化检索 - 导出历史 */
const getSceneExportHistory = defineEndpoint({
  url: '/search/scene/export/history/',
  method: 'post',
});

/** 场景化检索 - 取样下载 */
const getSceneExport = defineEndpoint({
  url: '/search/scene/export/sample/',
  method: 'post',
});

/** 场景化检索 - 字段值联想 */
const listSceneFieldCandidates = defineEndpoint({
  url: '/search/scene/list_field_candidates/',
  method: 'post',
});

/** 场景化检索 - 全文下载 */
const getSceneAsyncExport = defineEndpoint({
  url: '/search/scene/export/async/',
  method: 'post',
});

/** 场景化检索 - 快速下载 */
const getSceneQuickExport = defineEndpoint({
  url: '/search/scene/export/quick/',
  method: 'post',
});

/** 场景化检索 - 字段展示配置 读取 */
const getSceneUserCustomConfig = defineEndpoint({
  url: '/search/scene/user_custom_config/',
  method: 'get',
});

/** 场景化检索 - 字段展示配置 保存 */
const sceneFieldsConfig = defineEndpoint({
  url: '/search/scene/user_custom_config/',
  method: 'post',
});

/** 场景化检索 - 字段模板列表 */
const sceneListConfig = defineEndpoint({
  url: '/search/scene/list_config/',
  method: 'post',
});

/** 场景化检索 - 创建字段模板 */
const sceneCreateConfig = defineEndpoint({
  url: '/search/scene/create_config/',
  method: 'post',
});

/** 场景化检索 - 更新字段模板 */
const sceneUpdateConfig = defineEndpoint({
  url: '/search/scene/update_config/',
  method: 'post',
});

/** 场景化检索 - 删除字段模板 */
const sceneDeleteConfig = defineEndpoint({
  url: '/search/scene/delete_config/',
  method: 'post',
});

/** 场景化检索 - 应用字段模板 */
const sceneApplyFieldsConfig = defineEndpoint({
  url: '/search/scene/config/',
  method: 'post',
});

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
  getExportDownloadLink,
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
  getGrepResultTotal,
  getSceneConfigs,
  getSceneDimensionValues,
  getSceneFields,
  getSceneDateHistogram,
  getSceneAggsTerms,
  getSceneFieldFetchTopList,
  getSceneFieldFetchValueList,
  getSceneFieldStatisticsInfo,
  getSceneFieldStatisticsTotal,
  getSceneFieldStatisticsGraph,
  getSceneExport,
  getSceneAsyncExport,
  getSceneQuickExport,
  getSceneSearchHistory,
  getSceneExportHistory,
  getSceneUserCustomConfig,
  sceneFieldsConfig,
  sceneListConfig,
  sceneCreateConfig,
  sceneUpdateConfig,
  sceneDeleteConfig,
  sceneApplyFieldsConfig,
  listSceneFieldCandidates,
};

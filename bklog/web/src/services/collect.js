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

// 获取存储集群
const getStorage = {
  method: 'get',
  url: '/databus/storage/cluster_groups/',
};
// 获取全局配置
const globals = {
  method: 'get',
  url: '/meta/globals/',
};
// 采集项-创建
const addCollection = {
  method: 'post',
  url: '/databus/collectors/',
};
// 采集项-更新
const updateCollection = {
  method: 'put',
  url: '/databus/collectors/:collector_config_id/',
};

// 采集项-更新
const onlyUpdateCollection = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/only_update/',
};

// 索引集信息-快速更新
const fastUpdateCollection = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/fast_update/',
};

// 采集项-只创建配置
const onlyCreateCollection = {
  method: 'post',
  url: '/databus/collectors/only_create/',
};
// 创建采集ITSM单据
const applyItsmTicket = {
  method: 'post',
  url: '/databus/collect_itsm/:collector_config_id/apply_itsm_ticket/',
};
// 查询采集ITSM状态
const queryItsmTicket = {
  method: 'get',
  url: '/databus/collect_itsm/:collector_config_id/',
};

// 字段提取&清洗
const fieldCollection = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/update_or_create_clean_config/',
};
// 字段提取-预览
const getEtlPreview = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/etl_preview/',
};
// 字段提取-时间校验
const getCheckTime = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/etl_time/',
};
// 采集项-详情
const details = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/',
};

// 采集列表-列表
const getCollectList = {
  method: 'get',
  url: '/databus/collectors/',
};
// 采集列表-列表（全量）
const getAllCollectors = {
  method: 'get',
  url: '/databus/collectors/list_collectors/',
};
// 采集插件列表
const getCollectorPlugins = {
  method: 'get',
  url: '/databus/collector_plugins/',
};
// 采集列表-状态
const getCollectStatus = {
  method: 'get',
  // 轮询-批量获取采集项订阅状态
  url: '/databus/collectors/batch_subscription_status/',
};
// 采集列表-启用
const startCollect = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/start/',
};
// 采集列表-停用
const stopCollect = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/stop/',
};
// 采集列表-删除
const deleteCollect = {
  method: 'delete',
  url: '/databus/collectors/:collector_config_id/',
};

// 采集下发-topo树
const getBizTopo = {
  method: 'get',
  url: '/bizs/:bk_biz_id/topo/',
};
// 日志提取无鉴权topo树
const getExtractBizTopo = {
  method: 'get',
  url: '/log_extract/strategies/topo/',
};
// 采集下发-by 静态topo or input
const getHostByIp = {
  method: 'post',
  url: '/bizs/:bk_biz_id/host_instance_by_ip/',
};
// 采集下发-by 动态topo
const getHostByNode = {
  method: 'post',
  url: '/bizs/:bk_biz_id/host_instance_by_node/',
};
// 采集下发-服务模板topo
const getTemplateTopo = {
  method: 'get',
  url: '/bizs/:bk_biz_id/template_topo/',
};
// 采集下发-by 根据服务模板或集群模板获取实例
const getHostByTemplate = {
  method: 'get',
  url: '/bizs/:bk_biz_id/get_nodes_by_template/',
};
// 采集下发-列表&轮询共用同一接口
const getIssuedClusterList = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/task_status/',
};
// 采集下发-重试(批量)
const retry = {
  method: 'post',
  url: '/databus/collectors/:collector_config_id/retry/',
};
// 段日志调试
const regexDebug = {
  method: 'post',
  url: '/databus/collectors/:collector_id/regex_debug/',
};
// 采集下发-任务执行详情(更多)
const executDetails = {
  url: '/databus/collectors/:collector_id/task_detail/',
};
// 获取节点agent数量
const getNodeAgentStatus = {
  method: 'post',
  url: '/bizs/:bk_biz_id/list_agent_status/',
};
// 获取动态分组列表
const getDynamicGroupList = {
  method: 'get',
  url: '/bizs/:bk_biz_id/list_dynamic_group/',
};
// 获取动态分组表格数据
const getDynamicGroup = {
  method: 'post',
  url: '/bizs/:bk_biz_id/get_dynamic_group/',
};
// 获取预检查创建采集项的参数
const getPreCheck = {
  method: 'get',
  url: '/databus/collectors/pre_check/?bk_biz_id=:bk_biz_id&collector_config_name_en=:collector_config_name_en',
};

const createWeWork = {
  method: 'post',
  url: '/esb_api/wework/create_chat/',
};

// 采集项一键检测 - 开启检测
const runCheck = {
  method: 'post',
  url: '/databus/check_collector/run_check_collector/',
};

// 采集项一键检测 - 获取检测信息
const getCheckInfos = {
  method: 'post',
  url: '/databus/check_collector/get_check_collector_infos/',
};

// oplt_log 查看token请求
const reviewToken = {
  method: 'get',
  url: '/databus/collectors/:collector_config_id/report_token/',
};
// 获取日志采集-增加用量数据
const getStorageUsage = {
  method: 'post',
  url: '/index_set/storage_usage/',
};

export {
  getStorage,
  globals,
  addCollection,
  updateCollection,
  onlyUpdateCollection,
  onlyCreateCollection,
  fastUpdateCollection,
  applyItsmTicket,
  queryItsmTicket,
  fieldCollection,
  getEtlPreview,
  getCheckTime,
  details,
  getCollectList,
  getAllCollectors,
  getCollectorPlugins,
  getCollectStatus,
  startCollect,
  stopCollect,
  deleteCollect,
  getExtractBizTopo,
  getBizTopo,
  getHostByIp,
  getNodeAgentStatus,
  getHostByNode,
  getTemplateTopo,
  getHostByTemplate,
  getIssuedClusterList,
  retry,
  regexDebug,
  executDetails,
  getDynamicGroupList,
  getDynamicGroup,
  getPreCheck,
  createWeWork,
  runCheck,
  getCheckInfos,
  reviewToken,
  getStorageUsage,
};

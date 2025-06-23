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
import { request } from '../base';

export const countBaseAlarm = request('GET', 'rest/v1/base_alarm/count/');
export const listBaseAlarm = request('GET', 'rest/v1/base_alarm/');
export const retrieveBaseAlarm = request('GET', 'rest/v1/base_alarm/{pk}/');
export const countSnapshotHostIndex = request('GET', 'rest/v1/snapshot_host_index/count/');
export const listSnapshotHostIndex = request('GET', 'rest/v1/snapshot_host_index/');
export const retrieveSnapshotHostIndex = request('GET', 'rest/v1/snapshot_host_index/{pk}/');
export const countUserConfig = request('GET', 'rest/v1/user_config/count/');
export const createUserConfig = request('POST', 'rest/v1/user_config/');
export const destroyUserConfig = request('DELETE', 'rest/v1/user_config/{pk}/');
export const listUserConfig = request('GET', 'rest/v1/user_config/');
export const partialUpdateUserConfig = request('PATCH', 'rest/v1/user_config/{pk}/');
export const retrieveUserConfig = request('GET', 'rest/v1/user_config/{pk}/');
export const updateUserConfig = request('PUT', 'rest/v1/user_config/{pk}/');
export const countApplicationConfig = request('GET', 'rest/v1/application_config/count/');
export const createApplicationConfig = request('POST', 'rest/v1/application_config/');
export const destroyApplicationConfig = request('DELETE', 'rest/v1/application_config/{pk}/');
export const listApplicationConfig = request('GET', 'rest/v1/application_config/');
export const partialUpdateApplicationConfig = request('PATCH', 'rest/v1/application_config/{pk}/');
export const retrieveApplicationConfig = request('GET', 'rest/v1/application_config/{pk}/');
export const updateApplicationConfig = request('PUT', 'rest/v1/application_config/{pk}/');
export const countGlobalConfig = request('GET', 'rest/v1/global_config/count/');
export const listGlobalConfig = request('GET', 'rest/v1/global_config/');
export const retrieveGlobalConfig = request('GET', 'rest/v1/global_config/{pk}/');
export const listAlarmType = request('GET', 'rest/v1/alarm_type/');
export const countUptimeCheckNode = request('GET', 'rest/v2/uptime_check/uptime_check_node/count/');
export const createUptimeCheckNode = request('POST', 'rest/v2/uptime_check/uptime_check_node/');
export const destroyUptimeCheckNode = request('DELETE', 'rest/v2/uptime_check/uptime_check_node/{pk}/');
export const fixNameConflictUptimeCheckNode = request(
  'GET',
  'rest/v2/uptime_check/uptime_check_node/fix_name_conflict/'
);
export const isExistUptimeCheckNode = request('GET', 'rest/v2/uptime_check/uptime_check_node/is_exist/');
export const listUptimeCheckNode = request('GET', 'rest/v2/uptime_check/uptime_check_node/');
export const partialUpdateUptimeCheckNode = request('PATCH', 'rest/v2/uptime_check/uptime_check_node/{pk}/');
export const retrieveUptimeCheckNode = request('GET', 'rest/v2/uptime_check/uptime_check_node/{pk}/');
export const updateUptimeCheckNode = request('PUT', 'rest/v2/uptime_check/uptime_check_node/{pk}/');
export const changeStatusUptimeCheckTask = request(
  'POST',
  'rest/v2/uptime_check/uptime_check_task/{pk}/change_status/'
);
export const cloneUptimeCheckTask = request('POST', 'rest/v2/uptime_check/uptime_check_task/{pk}/clone/');
export const countUptimeCheckTask = request('GET', 'rest/v2/uptime_check/uptime_check_task/count/');
export const createUptimeCheckTask = request('POST', 'rest/v2/uptime_check/uptime_check_task/');
export const deployUptimeCheckTask = request('POST', 'rest/v2/uptime_check/uptime_check_task/{pk}/deploy/');
export const destroyUptimeCheckTask = request('DELETE', 'rest/v2/uptime_check/uptime_check_task/{pk}/');
export const listUptimeCheckTask = request('GET', 'rest/v2/uptime_check/uptime_check_task/');
export const partialUpdateUptimeCheckTask = request('PATCH', 'rest/v2/uptime_check/uptime_check_task/{pk}/');
export const retrieveUptimeCheckTask = request('GET', 'rest/v2/uptime_check/uptime_check_task/{pk}/');
export const runningStatusUptimeCheckTask = request(
  'GET',
  'rest/v2/uptime_check/uptime_check_task/{pk}/running_status/'
);
export const testUptimeCheckTask = request('POST', 'rest/v2/uptime_check/uptime_check_task/test/');
export const updateUptimeCheckTask = request('PUT', 'rest/v2/uptime_check/uptime_check_task/{pk}/');
export const addTaskUptimeCheckGroup = request('POST', 'rest/v2/uptime_check/uptime_check_group/{pk}/add_task/');
export const createUptimeCheckGroup = request('POST', 'rest/v2/uptime_check/uptime_check_group/');
export const destroyUptimeCheckGroup = request('DELETE', 'rest/v2/uptime_check/uptime_check_group/{pk}/');
export const listUptimeCheckGroup = request('GET', 'rest/v2/uptime_check/uptime_check_group/');
export const partialUpdateUptimeCheckGroup = request('PATCH', 'rest/v2/uptime_check/uptime_check_group/{pk}/');
export const retrieveUptimeCheckGroup = request('GET', 'rest/v2/uptime_check/uptime_check_group/{pk}/');
export const updateUptimeCheckGroup = request('PUT', 'rest/v2/uptime_check/uptime_check_group/{pk}/');
export const checkIdCollectorPlugin = request('GET', 'rest/v2/collector_plugin/check_id/');
export const createCollectorPlugin = request('POST', 'rest/v2/collector_plugin/');
export const deleteCollectorPlugin = request('POST', 'rest/v2/collector_plugin/delete/');
export const destroyCollectorPlugin = request('DELETE', 'rest/v2/collector_plugin/{pk}/');
export const editCollectorPlugin = request('POST', 'rest/v2/collector_plugin/{pk}/edit/');
export const exportPluginCollectorPlugin = request('GET', 'rest/v2/collector_plugin/{pk}/export_plugin/');
export const fetchDebugLogCollectorPlugin = request('GET', 'rest/v2/collector_plugin/{pk}/fetch_debug_log/');
export const importPluginCollectorPlugin = request('POST', 'rest/v2/collector_plugin/import_plugin/');
export const listCollectorPlugin = request('GET', 'rest/v2/collector_plugin/');
export const operatorSystemCollectorPlugin = request('GET', 'rest/v2/collector_plugin/operator_system/');
export const partialUpdateCollectorPlugin = request('PATCH', 'rest/v2/collector_plugin/{pk}/');
export const pluginImportWithoutFrontendCollectorPlugin = request(
  'POST',
  'rest/v2/collector_plugin/plugin_import_without_frontend/'
);
export const releaseCollectorPlugin = request('POST', 'rest/v2/collector_plugin/{pk}/release/');
export const replacePluginCollectorPlugin = request('POST', 'rest/v2/collector_plugin/replace_plugin/');
export const retrieveCollectorPlugin = request('GET', 'rest/v2/collector_plugin/{pk}/');
export const startDebugCollectorPlugin = request('POST', 'rest/v2/collector_plugin/{pk}/start_debug/');
export const stopDebugCollectorPlugin = request('POST', 'rest/v2/collector_plugin/{pk}/stop_debug/');
export const tagOptionsCollectorPlugin = request('GET', 'rest/v2/collector_plugin/tag_options/');
export const updateCollectorPlugin = request('PUT', 'rest/v2/collector_plugin/{pk}/');
export const uploadFileCollectorPlugin = request('POST', 'rest/v2/collector_plugin/upload_file/');
export const batchDeleteIpChooserConfig = request('POST', 'rest/v2/commons/ip_chooser_config/batch_delete/');
export const batchGetIpChooserConfig = request('POST', 'rest/v2/commons/ip_chooser_config/batch_get/');
export const globalConfigIpChooserConfig = request('GET', 'rest/v2/commons/ip_chooser_config/global_config/');
export const updateConfigIpChooserConfig = request('POST', 'rest/v2/commons/ip_chooser_config/update_config/');
export const checkIpChooserHost = request('POST', 'rest/v2/commons/ip_chooser_host/check/');
export const detailsIpChooserHost = request('POST', 'rest/v2/commons/ip_chooser_host/details/');
export const detailsIpChooserServiceInstance = request('POST', 'rest/v2/commons/ip_chooser_service_instance/details/');
export const agentStatisticsIpChooserTemplate = request(
  'POST',
  'rest/v2/commons/ip_chooser_template/agent_statistics/'
);
export const hostsIpChooserTemplate = request('POST', 'rest/v2/commons/ip_chooser_template/hosts/');
export const nodesIpChooserTemplate = request('POST', 'rest/v2/commons/ip_chooser_template/nodes/');
export const serviceInstanceCountIpChooserTemplate = request(
  'POST',
  'rest/v2/commons/ip_chooser_template/service_instance_count/'
);
export const templatesIpChooserTemplate = request('POST', 'rest/v2/commons/ip_chooser_template/templates/');
export const agentStatisticsIpChooserTopo = request('POST', 'rest/v2/commons/ip_chooser_topo/agent_statistics/');
export const queryHostIdInfosIpChooserTopo = request('POST', 'rest/v2/commons/ip_chooser_topo/query_host_id_infos/');
export const queryHostsIpChooserTopo = request('POST', 'rest/v2/commons/ip_chooser_topo/query_hosts/');
export const queryPathIpChooserTopo = request('POST', 'rest/v2/commons/ip_chooser_topo/query_path/');
export const queryServiceInstancesIpChooserTopo = request(
  'POST',
  'rest/v2/commons/ip_chooser_topo/query_service_instances/'
);
export const serviceInstanceCountIpChooserTopo = request(
  'POST',
  'rest/v2/commons/ip_chooser_topo/service_instance_count/'
);
export const treesIpChooserTopo = request('POST', 'rest/v2/commons/ip_chooser_topo/trees/');
export const groupsIpChooserDynamicGroup = request('POST', 'rest/v2/commons/ip_chooser_dynamic_group/groups/');
export const executeIpChooserDynamicGroup = request('POST', 'rest/v2/commons/ip_chooser_dynamic_group/execute/');
export const agentStatisticsIpChooserDynamicGroup = request(
  'POST',
  'rest/v2/commons/ip_chooser_dynamic_group/agent_statistics/'
);
export const enhancedContext = request('GET', 'rest/v2/commons/context/enhanced/');
export const listUsersUser = request('GET', 'rest/v2/commons/user/list_users/');
export const createFavoriteGroup = request('POST', 'rest/v2/favorite_group/');
export const destroyFavoriteGroup = request('DELETE', 'rest/v2/favorite_group/{pk}/');
export const listFavoriteGroup = request('GET', 'rest/v2/favorite_group/');
export const partialUpdateFavoriteGroup = request('PATCH', 'rest/v2/favorite_group/{pk}/');
export const retrieveFavoriteGroup = request('GET', 'rest/v2/favorite_group/{pk}/');
export const updateFavoriteGroup = request('PUT', 'rest/v2/favorite_group/{pk}/');
export const updateGroupOrderFavoriteGroup = request('POST', 'rest/v2/favorite_group/update_group_order/');
export const bulkDeleteFavorite = request('POST', 'rest/v2/favorite/bulk_delete/');
export const bulkUpdateFavorite = request('POST', 'rest/v2/favorite/bulk_update/');
export const createFavorite = request('POST', 'rest/v2/favorite/');
export const destroyFavorite = request('DELETE', 'rest/v2/favorite/{pk}/');
export const listFavorite = request('GET', 'rest/v2/favorite/');
export const listByGroupFavorite = request('GET', 'rest/v2/favorite/list_by_group/');
export const partialUpdateFavorite = request('PATCH', 'rest/v2/favorite/{pk}/');
export const retrieveFavorite = request('GET', 'rest/v2/favorite/{pk}/');
export const shareFavorite = request('POST', 'rest/v2/favorite/share/');
export const updateFavorite = request('PUT', 'rest/v2/favorite/{pk}/');
export const createQueryHistory = request('POST', 'rest/v2/query_history/');
export const destroyQueryHistory = request('DELETE', 'rest/v2/query_history/{pk}/');
export const listQueryHistory = request('GET', 'rest/v2/query_history/');
export const partialUpdateQueryHistory = request('PATCH', 'rest/v2/query_history/{pk}/');
export const retrieveQueryHistory = request('GET', 'rest/v2/query_history/{pk}/');
export const updateQueryHistory = request('PUT', 'rest/v2/query_history/{pk}/');
export const createUserGroup = request('POST', 'rest/v2/user_groups/');
export const destroyUserGroup = request('DELETE', 'rest/v2/user_groups/{pk}/');
export const listUserGroup = request('GET', 'rest/v2/user_groups/');
export const partialUpdateUserGroup = request('PATCH', 'rest/v2/user_groups/{pk}/');
export const retrieveUserGroup = request('GET', 'rest/v2/user_groups/{pk}/');
export const updateUserGroup = request('PUT', 'rest/v2/user_groups/{pk}/');
export const bulkUpdateUserGroup = request('POST', 'rest/v2/user_groups/bulk_update/');
export const createDutyRule = request('POST', 'rest/v2/duty_rules/');
export const destroyDutyRule = request('DELETE', 'rest/v2/duty_rules/{pk}/');
export const listDutyRule = request('GET', 'rest/v2/duty_rules/');
export const partialUpdateDutyRule = request('PATCH', 'rest/v2/duty_rules/{pk}/');
export const retrieveDutyRule = request('GET', 'rest/v2/duty_rules/{pk}/');
export const switchDutyRule = request('POST', 'rest/v2/duty_rules/switch/');
export const updateDutyRule = request('PUT', 'rest/v2/duty_rules/{pk}/');
export const chatChat = request('POST', 'rest/v2/ai_assistant/chat/chat/');
export const chatChatV2 = request('POST', 'rest/v2/ai_assistant/chat/chat_v2/');
export const createActionConfig = request('POST', 'fta/action/config/');
export const destroyActionConfig = request('DELETE', 'fta/action/config/{pk}/');
export const listActionConfig = request('GET', 'fta/action/config/');
export const partialUpdateActionConfig = request('PATCH', 'fta/action/config/{pk}/');
export const retrieveActionConfig = request('GET', 'fta/action/config/{pk}/');
export const updateActionConfig = request('PUT', 'fta/action/config/{pk}/');
export const createActionPluginCurd = request('POST', 'fta/action/plugin_curd/');
export const destroyActionPluginCurd = request('DELETE', 'fta/action/plugin_curd/{pk}/');
export const listActionPluginCurd = request('GET', 'fta/action/plugin_curd/');
export const partialUpdateActionPluginCurd = request('PATCH', 'fta/action/plugin_curd/{pk}/');
export const retrieveActionPluginCurd = request('GET', 'fta/action/plugin_curd/{pk}/');
export const updateActionPluginCurd = request('PUT', 'fta/action/plugin_curd/{pk}/');
export const createSearchFavorite = request('POST', 'fta/alert/search_favorite/');
export const destroySearchFavorite = request('DELETE', 'fta/alert/search_favorite/{pk}/');
export const listSearchFavorite = request('GET', 'fta/alert/search_favorite/');
export const partialUpdateSearchFavorite = request('PATCH', 'fta/alert/search_favorite/{pk}/');
export const retrieveSearchFavorite = request('GET', 'fta/alert/search_favorite/{pk}/');
export const updateSearchFavorite = request('PUT', 'fta/alert/search_favorite/{pk}/');
export const createAssignGroup = request('POST', 'fta/assign/rule_groups/');
export const destroyAssignGroup = request('DELETE', 'fta/assign/rule_groups/{pk}/');
export const listAssignGroup = request('GET', 'fta/assign/rule_groups/');
export const partialUpdateAssignGroup = request('PATCH', 'fta/assign/rule_groups/{pk}/');
export const retrieveAssignGroup = request('GET', 'fta/assign/rule_groups/{pk}/');
export const updateAssignGroup = request('PUT', 'fta/assign/rule_groups/{pk}/');
export const createAssignRule = request('POST', 'fta/assign/rules/');
export const destroyAssignRule = request('DELETE', 'fta/assign/rules/{pk}/');
export const listAssignRule = request('GET', 'fta/assign/rules/');
export const partialUpdateAssignRule = request('PATCH', 'fta/assign/rules/{pk}/');
export const retrieveAssignRule = request('GET', 'fta/assign/rules/{pk}/');
export const updateAssignRule = request('PUT', 'fta/assign/rules/{pk}/');

export default {
  countBaseAlarm,
  listBaseAlarm,
  retrieveBaseAlarm,
  countSnapshotHostIndex,
  listSnapshotHostIndex,
  retrieveSnapshotHostIndex,
  countUserConfig,
  createUserConfig,
  destroyUserConfig,
  listUserConfig,
  partialUpdateUserConfig,
  retrieveUserConfig,
  updateUserConfig,
  countApplicationConfig,
  createApplicationConfig,
  destroyApplicationConfig,
  listApplicationConfig,
  partialUpdateApplicationConfig,
  retrieveApplicationConfig,
  updateApplicationConfig,
  countGlobalConfig,
  listGlobalConfig,
  retrieveGlobalConfig,
  listAlarmType,
  countUptimeCheckNode,
  createUptimeCheckNode,
  destroyUptimeCheckNode,
  fixNameConflictUptimeCheckNode,
  isExistUptimeCheckNode,
  listUptimeCheckNode,
  partialUpdateUptimeCheckNode,
  retrieveUptimeCheckNode,
  updateUptimeCheckNode,
  changeStatusUptimeCheckTask,
  cloneUptimeCheckTask,
  countUptimeCheckTask,
  createUptimeCheckTask,
  deployUptimeCheckTask,
  destroyUptimeCheckTask,
  listUptimeCheckTask,
  partialUpdateUptimeCheckTask,
  retrieveUptimeCheckTask,
  runningStatusUptimeCheckTask,
  testUptimeCheckTask,
  updateUptimeCheckTask,
  addTaskUptimeCheckGroup,
  createUptimeCheckGroup,
  destroyUptimeCheckGroup,
  listUptimeCheckGroup,
  partialUpdateUptimeCheckGroup,
  retrieveUptimeCheckGroup,
  updateUptimeCheckGroup,
  checkIdCollectorPlugin,
  createCollectorPlugin,
  deleteCollectorPlugin,
  destroyCollectorPlugin,
  editCollectorPlugin,
  exportPluginCollectorPlugin,
  fetchDebugLogCollectorPlugin,
  importPluginCollectorPlugin,
  listCollectorPlugin,
  operatorSystemCollectorPlugin,
  partialUpdateCollectorPlugin,
  pluginImportWithoutFrontendCollectorPlugin,
  releaseCollectorPlugin,
  replacePluginCollectorPlugin,
  retrieveCollectorPlugin,
  startDebugCollectorPlugin,
  stopDebugCollectorPlugin,
  tagOptionsCollectorPlugin,
  updateCollectorPlugin,
  uploadFileCollectorPlugin,
  batchDeleteIpChooserConfig,
  batchGetIpChooserConfig,
  globalConfigIpChooserConfig,
  updateConfigIpChooserConfig,
  checkIpChooserHost,
  detailsIpChooserHost,
  detailsIpChooserServiceInstance,
  agentStatisticsIpChooserTemplate,
  hostsIpChooserTemplate,
  nodesIpChooserTemplate,
  serviceInstanceCountIpChooserTemplate,
  templatesIpChooserTemplate,
  agentStatisticsIpChooserTopo,
  queryHostIdInfosIpChooserTopo,
  queryHostsIpChooserTopo,
  queryPathIpChooserTopo,
  queryServiceInstancesIpChooserTopo,
  serviceInstanceCountIpChooserTopo,
  treesIpChooserTopo,
  groupsIpChooserDynamicGroup,
  executeIpChooserDynamicGroup,
  agentStatisticsIpChooserDynamicGroup,
  enhancedContext,
  listUsersUser,
  createFavoriteGroup,
  destroyFavoriteGroup,
  listFavoriteGroup,
  partialUpdateFavoriteGroup,
  retrieveFavoriteGroup,
  updateFavoriteGroup,
  updateGroupOrderFavoriteGroup,
  bulkDeleteFavorite,
  bulkUpdateFavorite,
  createFavorite,
  destroyFavorite,
  listFavorite,
  listByGroupFavorite,
  partialUpdateFavorite,
  retrieveFavorite,
  shareFavorite,
  updateFavorite,
  createQueryHistory,
  destroyQueryHistory,
  listQueryHistory,
  partialUpdateQueryHistory,
  retrieveQueryHistory,
  updateQueryHistory,
  createUserGroup,
  destroyUserGroup,
  listUserGroup,
  partialUpdateUserGroup,
  retrieveUserGroup,
  updateUserGroup,
  bulkUpdateUserGroup,
  createDutyRule,
  destroyDutyRule,
  listDutyRule,
  partialUpdateDutyRule,
  retrieveDutyRule,
  switchDutyRule,
  updateDutyRule,
  chatChat,
  chatChatV2,
  createActionConfig,
  destroyActionConfig,
  listActionConfig,
  partialUpdateActionConfig,
  retrieveActionConfig,
  updateActionConfig,
  createActionPluginCurd,
  destroyActionPluginCurd,
  listActionPluginCurd,
  partialUpdateActionPluginCurd,
  retrieveActionPluginCurd,
  updateActionPluginCurd,
  createSearchFavorite,
  destroySearchFavorite,
  listSearchFavorite,
  partialUpdateSearchFavorite,
  retrieveSearchFavorite,
  updateSearchFavorite,
  createAssignGroup,
  destroyAssignGroup,
  listAssignGroup,
  partialUpdateAssignGroup,
  retrieveAssignGroup,
  updateAssignGroup,
  createAssignRule,
  destroyAssignRule,
  listAssignRule,
  partialUpdateAssignRule,
  retrieveAssignRule,
  updateAssignRule,
};

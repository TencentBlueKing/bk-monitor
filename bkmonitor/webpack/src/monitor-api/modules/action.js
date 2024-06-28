import { request } from '../base';

export const getPlugins = request('GET', 'fta/action/plugins/get_plugins/');
export const getPluginTemplates = request('GET', 'fta/action/plugins/get_plugin_templates/');
export const getTemplateDetail = request('GET', 'fta/action/plugins/get_template_detail/');
export const getDimensions = request('GET', 'fta/action/plugins/get_dimensions/');
export const getConvergeFunction = request('GET', 'fta/action/plugins/get_converge_function/');
export const getVariables = request('GET', 'fta/action/plugins/get_variables/');
export const renderNoticeTemplate = request('POST', 'fta/action/plugins/render_notice_template/');
export const registerBkPlugin = request('GET', 'fta/action/plugins/register_bk_plugin/');
export const batchRegisterBkPlugin = request('GET', 'fta/action/plugins/batch_register_bk_plugin/');
export const getActionParams = request('POST', 'fta/action/instances/get_action_params/');
export const batchCreate = request('POST', 'fta/action/instances/batch_create/');
export const createChatGroup = request('POST', 'fta/action/instances/create_chat_group/');
export const getActionConfigByAlerts = request('POST', 'fta/action/instances/get_action_config_by_alerts/');
export const createDemoAction = request('POST', 'fta/action/instances/create_demo_action/');
export const getDemoActionDetail = request('GET', 'fta/action/instances/get_demo_action_detail/');
export const assignAlert = request('POST', 'fta/action/instances/assign_alert/');

export default {
  getPlugins,
  getPluginTemplates,
  getTemplateDetail,
  getDimensions,
  getConvergeFunction,
  getVariables,
  renderNoticeTemplate,
  registerBkPlugin,
  batchRegisterBkPlugin,
  getActionParams,
  batchCreate,
  createChatGroup,
  getActionConfigByAlerts,
  createDemoAction,
  getDemoActionDetail,
  assignAlert,
};

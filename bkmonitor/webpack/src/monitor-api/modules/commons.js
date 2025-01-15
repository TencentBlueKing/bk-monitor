import { request } from '../base';

export const businessListOption = request('GET', 'rest/v2/commons/business_list_option/');
export const fetchBusinessInfo = request('GET', 'rest/v2/commons/fetch_business_info/');
export const listSpaces = request('GET', 'rest/v2/commons/list_spaces/');
export const listStickySpaces = request('GET', 'rest/v2/commons/space/sticky_list/');
export const stickSpace = request('POST', 'rest/v2/commons/space/stick/');
export const createSpace = request('POST', 'rest/v2/commons/space/new/');
export const listDevopsSpaces = request('GET', 'rest/v2/commons/space/devops_list/');
export const spaceIntroduce = request('GET', 'rest/v2/commons/space_introduce/');
export const listDataPipeline = request('GET', 'rest/v2/commons/list_data_pipeline/');
export const listDataSourceByDataPipeline = request('GET', 'rest/v2/commons/list_data_source_by_data_pipeline/');
export const createDataPipeline = request('POST', 'rest/v2/commons/create_data_pipeline/');
export const updateDataPipeline = request('POST', 'rest/v2/commons/update_data_pipeline/');
export const getClusterInfo = request('GET', 'rest/v2/commons/get_cluster_info/');
export const getEtlConfig = request('GET', 'rest/v2/commons/get_etl_config/');
export const getTransferList = request('GET', 'rest/v2/commons/get_transfer_list/');
export const checkClusterHealth = request('GET', 'rest/v2/commons/check_cluster_health/');
export const listClusters = request('GET', 'rest/v2/commons/list_clusters/');
export const getStorageClusterDetail = request('GET', 'rest/v2/commons/get_storage_cluster_detail/');
export const registerCluster = request('POST', 'rest/v2/commons/register_cluster/');
export const updateRegisteredCluster = request('POST', 'rest/v2/commons/update_registered_cluster/');
export const getDocLink = request('GET', 'rest/v2/commons/get_docs_link/');
export const getLinkMapping = request('GET', 'rest/v2/commons/get_docs_link/mapping/');
export const countryList = request('GET', 'rest/v2/commons/country_list/');
export const ispList = request('GET', 'rest/v2/commons/isp_list/');
export const hostRegionIspInfo = request('GET', 'rest/v2/commons/host_region_isp_info/');
export const ccTopoTree = request('GET', 'rest/v2/commons/cc_topo_tree/');
export const getTopoTree = request('POST', 'rest/v2/commons/get_topo_tree/');
export const getHostInstanceByIp = request('POST', 'rest/v2/commons/get_host_instance_by_ip/');
export const getHostInstanceByNode = request('POST', 'rest/v2/commons/get_host_instance_by_node/');
export const getServiceInstanceByNode = request('POST', 'rest/v2/commons/get_service_instance_by_node/');
export const getServiceCategory = request('POST', 'rest/v2/commons/get_service_category/');
export const hostAgentStatus = request('POST', 'rest/v2/commons/host_agent_status/');
export const getMainlineObjectTopo = request('GET', 'rest/v2/commons/get_mainline_object_topo/');
export const getTemplate = request('POST', 'rest/v2/commons/get_template/');
export const getNodesByTemplate = request('POST', 'rest/v2/commons/get_nodes_by_template/');
export const getBusinessTargetDetail = request('POST', 'rest/v2/commons/get_business_target_detail/');
export const getContext = request('GET', 'rest/v2/commons/get_context/');
export const getLabel = request('GET', 'rest/v2/commons/get_label/');
export const getFooter = request('GET', 'rest/v2/commons/get_footer/');
export const frontendReportEvent = request('POST', 'rest/v2/commons/frontend_report_event/frontend_report_event/');
export const fetchRobotInfo = request('GET', 'rest/v2/commons/fetch_robot_info/');
export const queryAsyncTaskResult = request('GET', 'rest/v2/commons/query_async_task_result/');
export const getApiToken = request('GET', 'rest/v2/commons/token_manager/get_api_token/');
export const getUserDepartments = request('GET', 'rest/v2/commons/user_departments/get_user_departments/');
export const listDepartments = request('GET', 'rest/v2/commons/user_departments/departments_list/');

export default {
  businessListOption,
  fetchBusinessInfo,
  listSpaces,
  listStickySpaces,
  stickSpace,
  createSpace,
  listDevopsSpaces,
  spaceIntroduce,
  listDataPipeline,
  listDataSourceByDataPipeline,
  createDataPipeline,
  updateDataPipeline,
  getClusterInfo,
  getEtlConfig,
  getTransferList,
  checkClusterHealth,
  listClusters,
  getStorageClusterDetail,
  registerCluster,
  updateRegisteredCluster,
  getDocLink,
  getLinkMapping,
  countryList,
  ispList,
  hostRegionIspInfo,
  ccTopoTree,
  getTopoTree,
  getHostInstanceByIp,
  getHostInstanceByNode,
  getServiceInstanceByNode,
  getServiceCategory,
  hostAgentStatus,
  getMainlineObjectTopo,
  getTemplate,
  getNodesByTemplate,
  getBusinessTargetDetail,
  getContext,
  getLabel,
  getFooter,
  frontendReportEvent,
  fetchRobotInfo,
  queryAsyncTaskResult,
  getApiToken,
  getUserDepartments,
  listDepartments,
};

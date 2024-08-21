import { request } from '../base';

export const getScene = request('GET', 'rest/v2/scene_view/get_scene/');
export const getSceneView = request('GET', 'rest/v2/scene_view/get_scene_view/');
export const getSceneViewList = request('GET', 'rest/v2/scene_view/get_scene_view_list/');
export const updateSceneView = request('POST', 'rest/v2/scene_view/update_scene_view/');
export const deleteSceneView = request('POST', 'rest/v2/scene_view/delete_scene_view/');
export const getSceneViewDimensions = request('GET', 'rest/v2/scene_view/get_scene_view_dimensions/');
export const getSceneViewDimensionValue = request('POST', 'rest/v2/scene_view/get_scene_view_dimension_value/');
export const getStrategyAndEventCount = request('POST', 'rest/v2/scene_view/get_strategy_and_event_count/');
export const getHostProcessPortStatus = request('POST', 'rest/v2/scene_view/get_host_process_port_status/');
export const getHostOrTopoNodeDetail = request('POST', 'rest/v2/scene_view/get_host_or_topo_node_detail/');
export const getHostProcessUptime = request('POST', 'rest/v2/scene_view/get_host_process_uptime/');
export const getHostProcessList = request('POST', 'rest/v2/scene_view/get_host_process_list/');
export const getCustomMetricTargetList = request('POST', 'rest/v2/scene_view/get_custom_metric_target_list/');
export const getCustomEventTargetList = request('POST', 'rest/v2/scene_view/get_custom_event_target_list/');
export const getUptimeCheckTaskList = request('POST', 'rest/v2/scene_view/get_uptime_check_task_list/');
export const getUptimeCheckTaskInfo = request('POST', 'rest/v2/scene_view/get_uptime_check_task_info/');
export const getUptimeCheckTaskData = request('POST', 'rest/v2/scene_view/get_uptime_check_task_data/');
export const getUptimeCheckVarList = request('POST', 'rest/v2/scene_view/get_uptime_check_var_list/');
export const getKubernetesClusterList = request('POST', 'rest/v2/scene_view/get_kubernetes_cluster_list/');
export const getKubernetesCluster = request('POST', 'rest/v2/scene_view/get_kubernetes_cluster/');
export const getKubernetesClusterChoices = request('GET', 'rest/v2/scene_view/get_kubernetes_cluster_choices/');
export const getKubernetesUsageRatio = request('POST', 'rest/v2/scene_view/get_kubernetes_usage_ratio/');
export const getKubernetesWorkloadCountByNamespace = request('POST', 'rest/v2/scene_view/get_kubernetes_workload_count_by_namespace/');
export const getKubernetesPod = request('POST', 'rest/v2/scene_view/get_kubernetes_pod/');
export const getKubernetesPodList = request('POST', 'rest/v2/scene_view/get_kubernetes_pod_list/');
export const getKubernetesService = request('POST', 'rest/v2/scene_view/get_kubernetes_service/');
export const getKubernetesServiceList = request('POST', 'rest/v2/scene_view/get_kubernetes_service_list/');
export const getKubernetesContainer = request('POST', 'rest/v2/scene_view/get_kubernetes_container/');
export const getKubernetesContainerList = request('POST', 'rest/v2/scene_view/get_kubernetes_container_list/');
export const getKubernetesWorkload = request('POST', 'rest/v2/scene_view/get_kubernetes_workload/');
export const getKubernetesWorkloadList = request('POST', 'rest/v2/scene_view/get_kubernetes_workload_list/');
export const getKubernetesNode = request('POST', 'rest/v2/scene_view/get_kubernetes_node/');
export const getKubernetesNodeList = request('POST', 'rest/v2/scene_view/get_kubernetes_node_list/');
export const getKubernetesServiceMonitor = request('POST', 'rest/v2/scene_view/get_kubernetes_service_monitor/');
export const getKubernetesServiceMonitorList = request('POST', 'rest/v2/scene_view/get_kubernetes_service_monitor_list/');
export const getKubernetesServiceMonitorEndpoints = request('POST', 'rest/v2/scene_view/get_kubernetes_service_monitor_endpoints/');
export const getKubernetesPodMonitor = request('POST', 'rest/v2/scene_view/get_kubernetes_pod_monitor/');
export const getKubernetesPodMonitorList = request('POST', 'rest/v2/scene_view/get_kubernetes_pod_monitor_list/');
export const getKubernetesPodMonitorEndpoints = request('POST', 'rest/v2/scene_view/get_kubernetes_pod_monitor_endpoints/');
export const getKubernetesEvents = request('POST', 'rest/v2/scene_view/get_kubernetes_events/');
export const getKubernetesWorkloadTypes = request('POST', 'rest/v2/scene_view/get_kubernetes_workload_types/');
export const getKubernetesWorkloadStatusList = request('POST', 'rest/v2/scene_view/get_kubernetes_workload_status_list/');
export const getKubernetesNamespaces = request('POST', 'rest/v2/scene_view/get_kubernetes_namespaces/');
export const getKubernetesObjectCount = request('POST', 'rest/v2/scene_view/get_kubernetes_object_count/');
export const getKubernetesControlPlaneStatus = request('POST', 'rest/v2/scene_view/get_kubernetes_control_plane_status/');
export const getKubernetesWorkloadStatus = request('POST', 'rest/v2/scene_view/get_kubernetes_workload_status/');
export const getHostList = request('POST', 'rest/v2/scene_view/get_host_list/');
export const getHostInfo = request('GET', 'rest/v2/scene_view/get_host_info/');
export const getPluginCollectConfigIdList = request('GET', 'rest/v2/scene_view/get_plugin_collect_config_id_list/');
export const getObservationSceneList = request('GET', 'rest/v2/scene_view/get_observation_scene_list/');
export const getObservationSceneStatusList = request('POST', 'rest/v2/scene_view/get_observation_scene_status_list/');
export const getPluginTargetTopo = request('GET', 'rest/v2/scene_view/get_plugin_target_topo/');
export const getPluginInfoByResultTable = request('GET', 'rest/v2/scene_view/get_plugin_by_result_table/');
export const getKubernetesConsistencyCheck = request('GET', 'rest/v2/scene_view/get_kubernetes_consistency_check/');
export const getKubernetesServiceMonitorPanels = request('GET', 'rest/v2/scene_view/get_kubernetes_service_monitor_panels/');
export const getKubernetesPodMonitorPanels = request('GET', 'rest/v2/scene_view/get_kubernetes_pod_monitor_panels/');
export const getKubernetesNetworkTimeSeries = request('POST', 'rest/v2/scene_view/get_kubernetes_network_time_series/');
export const getKubernetesPreAllocatableUsageRatio = request('POST', 'rest/v2/scene_view/get_kubernetes_pre_allocatable_usage_ratio/');
export const getKubernetesEventCountByType = request('POST', 'rest/v2/scene_view/get_kubernetes_event_count_by_type/');
export const getKubernetesEventCountByEventName = request('POST', 'rest/v2/scene_view/get_kubernetes_event_count_by_event_name/');
export const getKubernetesEventCountByKind = request('POST', 'rest/v2/scene_view/get_kubernetes_event_count_by_kind/');
export const getKubernetesEventTimeSeries = request('POST', 'rest/v2/scene_view/get_kubernetes_event_time_series/');
export const getKubernetesCpuAnalysis = request('GET', 'rest/v2/scene_view/get_kubernetes_cpu_analysis/');
export const getKubernetesMemoryAnalysis = request('GET', 'rest/v2/scene_view/get_kubernetes_memory_analysis/');
export const getKubernetesDiskAnalysis = request('GET', 'rest/v2/scene_view/get_kubernetes_disk_analysis/');
export const getKubernetesOverCommitAnalysis = request('GET', 'rest/v2/scene_view/get_kubernetes_over_commit_analysis/');
export const getKubernetesNodeCpuUsage = request('GET', 'rest/v2/scene_view/get_kubernetes_node_cpu_usage/');
export const getKubernetesNodeMemoryUsage = request('GET', 'rest/v2/scene_view/get_kubernetes_node_memory_usage/');
export const getKubernetesNodeDiskSpaceUsage = request('GET', 'rest/v2/scene_view/get_kubernetes_node_disk_space_usage/');
export const getKubernetesNodeDiskIoUsage = request('GET', 'rest/v2/scene_view/get_kubernetes_node_disk_io_usage/');
export const getIndexSetLogSeries = request('POST', 'rest/v2/scene_view/get_index_set_log_series/');
export const listIndexSetLog = request('POST', 'rest/v2/scene_view/list_index_set_log/');

export default {
  getScene,
  getSceneView,
  getSceneViewList,
  updateSceneView,
  deleteSceneView,
  getSceneViewDimensions,
  getSceneViewDimensionValue,
  getStrategyAndEventCount,
  getHostProcessPortStatus,
  getHostOrTopoNodeDetail,
  getHostProcessUptime,
  getHostProcessList,
  getCustomMetricTargetList,
  getCustomEventTargetList,
  getUptimeCheckTaskList,
  getUptimeCheckTaskInfo,
  getUptimeCheckTaskData,
  getUptimeCheckVarList,
  getKubernetesClusterList,
  getKubernetesCluster,
  getKubernetesClusterChoices,
  getKubernetesUsageRatio,
  getKubernetesWorkloadCountByNamespace,
  getKubernetesPod,
  getKubernetesPodList,
  getKubernetesService,
  getKubernetesServiceList,
  getKubernetesContainer,
  getKubernetesContainerList,
  getKubernetesWorkload,
  getKubernetesWorkloadList,
  getKubernetesNode,
  getKubernetesNodeList,
  getKubernetesServiceMonitor,
  getKubernetesServiceMonitorList,
  getKubernetesServiceMonitorEndpoints,
  getKubernetesPodMonitor,
  getKubernetesPodMonitorList,
  getKubernetesPodMonitorEndpoints,
  getKubernetesEvents,
  getKubernetesWorkloadTypes,
  getKubernetesWorkloadStatusList,
  getKubernetesNamespaces,
  getKubernetesObjectCount,
  getKubernetesControlPlaneStatus,
  getKubernetesWorkloadStatus,
  getHostList,
  getHostInfo,
  getPluginCollectConfigIdList,
  getObservationSceneList,
  getObservationSceneStatusList,
  getPluginTargetTopo,
  getPluginInfoByResultTable,
  getKubernetesConsistencyCheck,
  getKubernetesServiceMonitorPanels,
  getKubernetesPodMonitorPanels,
  getKubernetesNetworkTimeSeries,
  getKubernetesPreAllocatableUsageRatio,
  getKubernetesEventCountByType,
  getKubernetesEventCountByEventName,
  getKubernetesEventCountByKind,
  getKubernetesEventTimeSeries,
  getKubernetesCpuAnalysis,
  getKubernetesMemoryAnalysis,
  getKubernetesDiskAnalysis,
  getKubernetesOverCommitAnalysis,
  getKubernetesNodeCpuUsage,
  getKubernetesNodeMemoryUsage,
  getKubernetesNodeDiskSpaceUsage,
  getKubernetesNodeDiskIoUsage,
  getIndexSetLogSeries,
  listIndexSetLog,
};

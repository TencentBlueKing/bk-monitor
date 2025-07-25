import { request } from '../base';

export const incidentList = request('POST', 'rest/v2/incident/incident_list/');
export const exportIncident = request('POST', 'rest/v2/incident/export_incident/');
export const incidentOverview = request('POST', 'rest/v2/incident/incident_overview/');
export const incidentTopN = request('POST', 'rest/v2/incident/top_n/');
export const incidentValidateQueryString = request('POST', 'rest/v2/incident/validate_query_string/');
export const incidentDetail = request('GET', 'rest/v2/incident/incident_detail/');
export const incidentTopology = request('POST', 'rest/v2/incident/incident_topology/');
export const incidentTopologyMenu = request('GET', 'rest/v2/incident/incident_topology_menu/');
export const incidentTopologyUpstream = request('GET', 'rest/v2/incident/incident_topology_upstream/');
export const incidentTimeLine = request('GET', 'rest/v2/incident/incident_time_line/');
export const incidentAlertAggregate = request('POST', 'rest/v2/incident/incident_alert_aggregate/');
export const incidentHandlers = request('GET', 'rest/v2/incident/incident_handlers/');
export const incidentOperations = request('GET', 'rest/v2/incident/incident_operations/');
export const incidentRecordOperation = request('POST', 'rest/v2/incident/incident_record_operation/');
export const incidentOperationTypes = request('GET', 'rest/v2/incident/incident_operation_types/');
export const editIncident = request('POST', 'rest/v2/incident/edit_incident/');
export const feedbackIncidentRoot = request('POST', 'rest/v2/incident/feedback_incident_root/');
export const incidentAlertList = request('POST', 'rest/v2/incident/incident_alert_list/');
export const incidentAlertView = request('POST', 'rest/v2/incident/incident_alert_view/');
export const alertIncidentDetail = request('GET', 'rest/v2/incident/alert_incident_detail/');
export const incidentResults = request('GET', 'rest/v2/incident/incident_results/');
export const incidentDiagnosis = request('POST', 'rest/v2/incident/incident_diagnosis/');

export default {
  incidentList,
  exportIncident,
  incidentOverview,
  incidentTopN,
  incidentValidateQueryString,
  incidentDetail,
  incidentTopology,
  incidentTopologyMenu,
  incidentTopologyUpstream,
  incidentTimeLine,
  incidentAlertAggregate,
  incidentHandlers,
  incidentOperations,
  incidentRecordOperation,
  incidentOperationTypes,
  editIncident,
  feedbackIncidentRoot,
  incidentAlertList,
  incidentAlertView,
  alertIncidentDetail,
  incidentResults,
  incidentDiagnosis,
};

/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
export const incidentMetricsSearch = request('POST', 'rest/v2/incident_metrics/search/');
export const incidentEventsSearch = request('POST', 'rest/v2/incident_events/search/');
export const incidentEventsDetail = request('POST', 'rest/v2/incident_events/detail/');

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
  incidentMetricsSearch,
  incidentEventsSearch,
  incidentEventsDetail
};

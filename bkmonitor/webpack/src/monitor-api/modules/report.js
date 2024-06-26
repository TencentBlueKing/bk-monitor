import { request } from '../base';

export const reportList = request('GET', 'rest/v2/report/report_list/');
export const statusList = request('GET', 'rest/v2/report/status_list/');
export const graphsListByBiz = request('GET', 'rest/v2/report/graphs_list_by_biz/');
export const getPanelsByDashboard = request('GET', 'rest/v2/report/get_panels_by_dashboard/');
export const reportCreateOrUpdate = request('POST', 'rest/v2/report/report_create_or_update/');
export const reportTest = request('POST', 'rest/v2/report/report_test/');
export const buildInMetric = request('GET', 'rest/v2/report/build_in_metric/');
export const reportContent = request('GET', 'rest/v2/report/report_content/');
export const reportDelete = request('POST', 'rest/v2/report/report_delete/');
export const groupList = request('GET', 'rest/v2/report/group_list/');
export const reportClone = request('GET', 'rest/v2/report/report_clone/');

export default {
  reportList,
  statusList,
  graphsListByBiz,
  getPanelsByDashboard,
  reportCreateOrUpdate,
  reportTest,
  buildInMetric,
  reportContent,
  reportDelete,
  groupList,
  reportClone,
};

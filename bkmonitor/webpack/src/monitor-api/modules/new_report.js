import { request } from '../base';

export const getReportList = request('POST', 'rest/v2/new_report/get_report_list/');
export const getReport = request('GET', 'rest/v2/new_report/get_report/');
export const cloneReport = request('POST', 'rest/v2/new_report/clone_report/');
export const createOrUpdateReport = request('POST', 'rest/v2/new_report/create_or_update_report/');
export const deleteReport = request('POST', 'rest/v2/new_report/delete_report/');
export const sendReport = request('POST', 'rest/v2/new_report/send_report/');
export const cancelOrResubscribeReport = request('POST', 'rest/v2/new_report/cancel_or_resubscribe_report/');
export const getSendRecords = request('GET', 'rest/v2/new_report/get_send_records/');
export const getApplyRecords = request('GET', 'rest/v2/new_report/get_apply_records/');
export const getVariables = request('GET', 'rest/v2/new_report/get_variables/');
export const getExistReports = request('GET', 'rest/v2/new_report/get_exist_reports/');

export default {
  getReportList,
  getReport,
  cloneReport,
  createOrUpdateReport,
  deleteReport,
  sendReport,
  cancelOrResubscribeReport,
  getSendRecords,
  getApplyRecords,
  getVariables,
  getExistReports,
};

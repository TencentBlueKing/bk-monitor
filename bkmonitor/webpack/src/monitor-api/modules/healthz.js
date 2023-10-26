import { request } from '../base';

export const getGlobalStatus = request('GET', 'rest/v1/healthz/');
export const serverGraphPoint = request('GET', 'rest/v1/healthz/graph_point/');
export const serverHostAlarm = request('GET', 'rest/v1/healthz/host_alarm/');
export const jobTestRootApi = request('POST', 'rest/v1/healthz/job_test_root/');
export const jobTestNonRootApi = request('POST', 'rest/v1/healthz/job_test_non_root/');
export const ccTestRootApi = request('POST', 'rest/v1/healthz/cc_test_root/');
export const ccTestNonRootApi = request('POST', 'rest/v1/healthz/cc_test_non_root/');
export const metadataTestRootApi = request('POST', 'rest/v1/healthz/metadata_test_root/');
export const nodemanTestRootApi = request('POST', 'rest/v1/healthz/nodeman_test_root/');
export const bkDataTestRootApi = request('POST', 'rest/v1/healthz/bk_data_test_root/');
export const gseTestRootApi = request('POST', 'rest/v1/healthz/gse_test_root/');
export const getAlarmConfig = request('GET', 'rest/v1/alarm_config/');
export const updateAlarmConfig = request('POST', 'rest/v1/alarm_config/');

export default {
  getGlobalStatus,
  serverGraphPoint,
  serverHostAlarm,
  jobTestRootApi,
  jobTestNonRootApi,
  ccTestRootApi,
  ccTestNonRootApi,
  metadataTestRootApi,
  nodemanTestRootApi,
  bkDataTestRootApi,
  gseTestRootApi,
  getAlarmConfig,
  updateAlarmConfig
};
